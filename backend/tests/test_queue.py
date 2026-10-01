import pytest
from app.models import Campaign, Recipient, SenderAccount, SendJob, SuppressionEntry
from app.services.campaign_service import queue_campaign
from app.services.queue_service import process_next_job

@pytest.mark.asyncio
async def test_queue_and_mock_send(db):
    account = SenderAccount(email="sender@example.com", sender_name="Sender", provider="mock", daily_limit=10, rate_limit_per_minute=10)
    campaign = Campaign(name="Queue Test")
    db.add_all([account, campaign]); db.commit(); db.refresh(account); db.refresh(campaign)
    recipient = Recipient(campaign_id=campaign.id, row_number=2, email="recipient@example.com", subject="Personal subject", message="Individual body", status="READY")
    db.add(recipient); db.commit(); db.refresh(recipient)
    result = queue_campaign(db, campaign, [account.id], test_mode=False, test_addresses=[])
    assert result["queued"] == 1
    assert await process_next_job(db) is True
    db.refresh(recipient)
    job = db.query(SendJob).filter_by(recipient_id=recipient.id).one()
    assert recipient.status == "SENT"
    assert job.status == "SENT"


@pytest.mark.asyncio
async def test_test_mode_does_not_overwrite_lead_address(db):
    account = SenderAccount(email="sender2@example.com", sender_name="Sender", provider="mock", daily_limit=10, rate_limit_per_minute=10)
    campaign = Campaign(name="Test Mode")
    db.add_all([account, campaign]); db.commit(); db.refresh(account); db.refresh(campaign)
    recipient = Recipient(campaign_id=campaign.id, row_number=2, email="lead@example.com", subject="Lead subject", message="Lead body", status="READY")
    db.add(recipient); db.commit(); db.refresh(recipient)
    queue_campaign(db, campaign, [account.id], test_mode=True, test_addresses=["owner@example.com"])
    db.refresh(recipient)
    job = db.query(SendJob).filter_by(recipient_id=recipient.id).one()
    assert recipient.email == "lead@example.com"
    assert job.to_email_override == "owner@example.com"
    assert job.is_test is True
    assert await process_next_job(db) is True
    db.refresh(recipient)
    assert recipient.status == "READY"
    real = queue_campaign(db, campaign, [account.id], test_mode=False, test_addresses=[])
    assert real["queued"] == 1


@pytest.mark.asyncio
async def test_suppression_added_after_queue_blocks_real_send(db):
    account = SenderAccount(email="sender3@example.com", sender_name="Sender", provider="mock", daily_limit=10, rate_limit_per_minute=10)
    campaign = Campaign(name="Suppression race")
    db.add_all([account, campaign]); db.commit(); db.refresh(account); db.refresh(campaign)
    recipient = Recipient(campaign_id=campaign.id, row_number=2, email="lateblock@example.com", subject="Subject", message="Body", status="READY")
    db.add(recipient); db.commit(); db.refresh(recipient)
    queue_campaign(db, campaign, [account.id], test_mode=False, test_addresses=[])
    db.add(SuppressionEntry(email="lateblock@example.com", reason="added after queue")); db.commit()
    assert await process_next_job(db) is True
    db.refresh(recipient)
    job = db.query(SendJob).filter_by(recipient_id=recipient.id, is_test=False).one()
    assert recipient.status == "UNSUBSCRIBED"
    assert job.status == "FAILED"
    assert account.sent_today == 0
