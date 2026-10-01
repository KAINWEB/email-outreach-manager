from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..config import settings
from ..models import Campaign, Recipient, SenderAccount, SendEvent, SendJob, SuppressionEntry, utcnow
from ..providers.base import TemporaryProviderError, PermanentProviderError
from ..providers.registry import get_provider


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _reset_daily_counter_if_needed(account: SenderAccount) -> None:
    today = date.today().isoformat()
    if account.sent_today_date != today:
        account.sent_today = 0
        account.sent_today_date = today


def _rate_limited(db: Session, account: SenderAccount) -> bool:
    since = utcnow() - timedelta(minutes=1)
    recent = db.scalar(select(func.count()).select_from(SendEvent).where(
        SendEvent.sender_account_id == account.id,
        SendEvent.status.in_(["SENT", "TEST_SENT"]),
        SendEvent.timestamp >= since,
    )) or 0
    return recent >= account.rate_limit_per_minute


def _finish_campaign_if_done(db: Session, campaign_id: int) -> None:
    remaining = db.scalar(select(func.count()).select_from(SendJob).where(
        SendJob.campaign_id == campaign_id,
        SendJob.is_test.is_(False),
        SendJob.status.in_(["QUEUED", "SENDING"]),
    )) or 0
    if remaining == 0:
        campaign = db.get(Campaign, campaign_id)
        if campaign:
            campaign.status = "COMPLETED"
            campaign.completed_at = utcnow()


async def process_next_job(db: Session) -> bool:
    now = utcnow()
    jobs = db.scalars(select(SendJob).where(
        SendJob.status == "QUEUED",
        SendJob.next_attempt_at <= now,
    ).order_by(SendJob.id).limit(25)).all()
    if not jobs:
        return False

    job = None
    account = None
    for candidate in jobs:
        acc = db.get(SenderAccount, candidate.sender_account_id)
        if not acc or not acc.enabled:
            continue
        _reset_daily_counter_if_needed(acc)
        if acc.sent_today >= acc.daily_limit or _rate_limited(db, acc):
            continue
        job, account = candidate, acc
        break
    if job is None or account is None:
        db.commit()
        return False

    recipient = db.get(Recipient, job.recipient_id)
    if not recipient:
        job.status = "FAILED"
        job.last_error = "Recipient missing"
        db.commit()
        return True

    target_email = (job.to_email_override or recipient.email).lower()
    if db.scalar(select(SuppressionEntry).where(SuppressionEntry.email == target_email)):
        job.status = "FAILED"
        job.last_error = "Suppressed before send"
        if not job.is_test:
            recipient.status = "UNSUBSCRIBED"
            _finish_campaign_if_done(db, job.campaign_id)
        db.commit()
        return True

    job.status = "SENDING"
    if not job.is_test:
        recipient.status = "SENDING"
    job.attempts += 1
    db.commit()

    provider = get_provider(account.provider, account)
    try:
        result = await provider.send(
            sender_email=account.email,
            sender_name=account.sender_name,
            to_email=target_email,
            subject=recipient.subject,
            message=recipient.message,
        )
        job.status = "SENT"
        if not job.is_test:
            recipient.status = "SENT"
        account.sent_today += 1
        account.last_error = None
        db.add(SendEvent(
            campaign_id=job.campaign_id,
            recipient_id=recipient.id,
            sender_account_id=account.id,
            job_id=job.id,
            subject=recipient.subject,
            status="TEST_SENT" if job.is_test else "SENT",
            provider_response=(f"TEST MODE to {target_email}; " if job.is_test else "") + result.response,
        ))
    except TemporaryProviderError as exc:
        account.last_error = str(exc)
        if job.attempts >= settings.max_retry_attempts:
            job.status = "FAILED"
            if not job.is_test:
                recipient.status = "FAILED"
            job.last_error = str(exc)
            db.add(SendEvent(campaign_id=job.campaign_id, recipient_id=recipient.id, sender_account_id=account.id, job_id=job.id, subject=recipient.subject, status="FAILED", provider_response=str(exc)))
        else:
            job.status = "QUEUED"
            if not job.is_test:
                recipient.status = "QUEUED"
            job.last_error = str(exc)
            job.next_attempt_at = utcnow() + timedelta(seconds=min(300, 2 ** job.attempts))
    except (PermanentProviderError, ValueError) as exc:
        job.status = "FAILED"
        if not job.is_test:
            recipient.status = "FAILED"
        job.last_error = str(exc)
        account.last_error = str(exc)
        db.add(SendEvent(campaign_id=job.campaign_id, recipient_id=recipient.id, sender_account_id=account.id, job_id=job.id, subject=recipient.subject, status="FAILED", provider_response=str(exc)))
    except Exception as exc:
        # Unknown failures are capped; they are not retried forever.
        job.last_error = str(exc)
        account.last_error = str(exc)
        if job.attempts >= settings.max_retry_attempts:
            job.status = "FAILED"
            if not job.is_test:
                recipient.status = "FAILED"
            db.add(SendEvent(campaign_id=job.campaign_id, recipient_id=recipient.id, sender_account_id=account.id, job_id=job.id, subject=recipient.subject, status="FAILED", provider_response=f"Unexpected: {exc}"))
        else:
            job.status = "QUEUED"
            if not job.is_test:
                recipient.status = "QUEUED"
            job.next_attempt_at = utcnow() + timedelta(seconds=min(300, 2 ** job.attempts))
    if not job.is_test:
        _finish_campaign_if_done(db, job.campaign_id)
    db.commit()
    return True
