import time
import threading
from backend.database import SessionLocal
from backend.models import SendJob, JobStatus, SenderAccount, Recipient
from backend.providers import MockEmailProvider

class QueueWorker(threading.Thread):
    def __init__(self):
        super().__init__()
        self.daemon = True
        self._stop_event = threading.Event()

    def run(self):
        while not self._stop_event.is_set():
            self.process_queue()
            time.sleep(5)

    def process_queue(self):
        with SessionLocal() as db:
            job = db.query(SendJob).filter(SendJob.status == JobStatus.QUEUED).first()
            if not job: return
            recipient = db.query(Recipient).get(job.recipient_id)
            account = db.query(SenderAccount).get(recipient.sender_account_id)
            if not account or account.sent_today >= account.daily_limit: return
            provider = MockEmailProvider()
            success, error = provider.send(recipient.email, recipient.subject, recipient.message)
            if success:
                job.status = JobStatus.SENT
                recipient.status = JobStatus.SENT
                account.sent_today += 1
            else:
                job.status = JobStatus.FAILED
            db.commit()

    def stop(self):
        self._stop_event.set()
