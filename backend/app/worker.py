import asyncio
import logging
from .config import settings
from .db import SessionLocal
from .services.queue_service import process_next_job

logger = logging.getLogger(__name__)


async def worker_loop(stop_event: asyncio.Event):
    logger.info("Queue worker started")
    while not stop_event.is_set():
        processed = False
        db = SessionLocal()
        try:
            processed = await process_next_job(db)
        except Exception:
            logger.exception("Worker iteration failed")
            db.rollback()
        finally:
            db.close()
        if not processed:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=settings.worker_poll_seconds)
            except asyncio.TimeoutError:
                pass
    logger.info("Queue worker stopped")
