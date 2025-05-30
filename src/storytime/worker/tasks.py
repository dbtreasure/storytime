import time
import logging
from .celery_app import celery_app
from storytime.services.tts_generator import TTSGenerator
from storytime.infrastructure.spaces import download_file, upload_file
from storytime.database import AsyncSessionLocal, Book as DBBook, BookStatus
import os
import tempfile
import asyncio
from storytime.models import TextSegment, Chapter, SpeakerType
from sqlalchemy.ext.asyncio import AsyncSession
from celery import Task

@celery_app.task(
    name="storytime.worker.tasks.generate_tts",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    retry_backoff=True,
)
def generate_tts(self, book_id):
    logging.info(f"[Celery] generate_tts called for book_id={book_id}")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_generate_tts_async(self, book_id))
    return f"Done: {book_id}"

async def _generate_tts_async(self, book_id):
    async with AsyncSessionLocal() as session:
        book = await session.get(DBBook, book_id)
        try:
            if not book:
                logging.error(f"[Celery] Book not found: {book_id}")
                return
            if not book.text_key:
                logging.error(f"[Celery] No text_key for book_id={book_id}")
                book.error_msg = "No text_key found for this book."
                book.status = BookStatus.FAILED
                await session.commit()
                return
            # Download text from Spaces
            with tempfile.NamedTemporaryFile("w+b", delete=False, suffix=".txt") as tmp:
                tmp_path = tmp.name
            try:
                download_file(book.text_key, tmp_path)
                with open(tmp_path, "r", encoding="utf-8") as f:
                    text = f.read()
            except Exception as e:
                logging.error(f"[Celery] Failed to download/read text for book_id={book_id}: {e}")
                book.error_msg = f"Download/read error: {e}"
                book.status = BookStatus.FAILED
                await session.commit()
                return
            finally:
                os.remove(tmp_path)
            # Generate MP3
            try:
                tts = TTSGenerator()
                audio_path = f"/tmp/{book_id}.mp3"
                # For now, treat the whole text as a single segment
                segment = TextSegment(
                    text=text,
                    speaker_type=SpeakerType.NARRATOR,
                    speaker_name="narrator",
                    sequence_number=1,
                    voice_hint=None,
                    emotion=None,
                    instruction=None,
                )
                chapter = Chapter(
                    chapter_number=1,
                    title=book.title,
                    segments=[segment],
                )
                tts.generate_audio_for_chapter(chapter, response_format="mp3")
                # Find the output file (stitched)
                output_path = os.path.join(tts.output_dir, "chapter_01", "chapter_01_complete.mp3")
                if not os.path.exists(output_path):
                    logging.error(f"[Celery] MP3 not found at {output_path}")
                    book.error_msg = f"MP3 not found at {output_path}"
                    book.status = BookStatus.FAILED
                    await session.commit()
                    return
            except Exception as e:
                logging.error(f"[Celery] TTS generation failed for book_id={book_id}: {e}")
                book.error_msg = f"TTS generation failed: {e}"
                book.status = BookStatus.FAILED
                await session.commit()
                raise  # Let Celery retry
            # Upload MP3 to Spaces
            audio_key = f"audio/{book_id}.mp3"
            try:
                upload_success = upload_file(output_path, audio_key, content_type="audio/mpeg")
                if not upload_success:
                    logging.error(f"[Celery] Audio upload failed for book_id={book_id}")
                    book.error_msg = "Audio upload failed"
                    book.status = BookStatus.FAILED
                    await session.commit()
                    return
                book.audio_key = audio_key
                book.status = BookStatus.READY
                book.error_msg = None
                await session.commit()
                logging.info(f"[Celery] Audio uploaded and DB updated for book_id={book_id}")
            except Exception as e:
                logging.error(f"[Celery] Audio upload/DB update failed for book_id={book_id}: {e}")
                book.error_msg = f"Audio upload/DB update failed: {e}"
                book.status = BookStatus.FAILED
                await session.commit()
                raise  # Let Celery retry 
        except Exception as e:
            if book:
                book.error_msg = str(e)
                book.status = BookStatus.FAILED
                await session.commit()
            raise  # Let Celery handle retry 