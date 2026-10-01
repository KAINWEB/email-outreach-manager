from __future__ import annotations
from itertools import cycle
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..models import Campaign, Recipient, SenderAccount, SendJob, SuppressionEntry


def campaign_summary(db: Session, campaign_id: int) -> dict:
    rows = db.execute(
        select(Recipient.status, func.count()).where(Recipient.campaign_id == campaign_id).group_by(Recipient.status)
    ).all()
    by_status = {status: count for status, count in rows}
    duplicates = db.scalar(select(func.count()).select_from(Recipient).where(Recipient.campaign_id == campaign_id, Recipient.is_duplicate.is_(True))) or 0
    total = sum(by_status.values())
    return {
        "recipients": total,
        "ready": by_status.get("READY", 0),
        "errors": by_status.get("SKIPPED", 0),
        "duplicates": duplicates,
        "excluded": by_status.get("UNSUBSCRIBED", 0),
        "by_status": by_status,
    }


def queue_campaign(db: Session, campaign: Campaign, sender_account_ids: list[int], *, test_mode: bool, test_addresses: list[str]) -> dict:
    accounts = db.scalars(select(SenderAccount).where(SenderAccount.id.in_(sender_account_ids), SenderAccount.enabled.is_(True))).all()
    if not accounts:
        raise ValueError("Select at least one enabled sender account")
    recipients = db.scalars(select(Recipient).where(Recipient.campaign_id == campaign.id, Recipient.status == "READY").order_by(Recipient.id)).all()
    if not recipients:
        raise ValueError("No READY recipients")
    test_list = list(dict.fromkeys(x.lower() for x in test_addresses))
    if test_mode:
        if not test_list:
            raise ValueError("Test Mode requires at least one test address")
        recipients = recipients[: max(1, min(len(recipients), len(test_list)))]
    chooser = cycle(accounts)
    created = 0
    suppressed = {x.lower() for x in db.scalars(select(SuppressionEntry.email)).all()}
    for idx, recipient in enumerate(recipients):
        if recipient.email.lower() in suppressed:
            recipient.status = "UNSUBSCRIBED"
            recipient.validation_error = "Address is in suppression list"
            continue
        if db.scalar(select(SendJob).where(SendJob.recipient_id == recipient.id, SendJob.is_test.is_(False))):
            continue
        account = next(chooser)
        target_override = test_list[idx % len(test_list)] if test_mode else None
        if not test_mode:
            recipient.sender_account_id = account.id
            recipient.status = "QUEUED"
        db.add(SendJob(
            campaign_id=campaign.id,
            recipient_id=recipient.id,
            sender_account_id=account.id,
            status="QUEUED",
            to_email_override=target_override,
            is_test=test_mode,
        ))
        created += 1
    if not test_mode:
        campaign.status = "RUNNING"
        from ..models import utcnow
        campaign.started_at = utcnow()
    db.commit()
    return {"queued": created}
