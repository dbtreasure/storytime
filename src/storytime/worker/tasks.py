import time
import logging
from .celery_app import celery_app

@celery_app.task(name="storytime.worker.tasks.generate_tts")
def generate_tts(book_id):
    logging.info(f"[Celery] Dummy generate_tts called for book_id={book_id}")
    time.sleep(5)
    logging.info(f"[Celery] Dummy generate_tts finished for book_id={book_id}")
    return f"Done: {book_id}" 