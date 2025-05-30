import sys
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from storytime.worker.tasks import generate_tts
    from storytime.worker.celery_app import celery_app
    logger.info("Successfully imported Celery components")
except ImportError as e:
    logger.error(f"Failed to import Celery components: {e}")
    sys.exit(1)

if __name__ == "__main__":
    logger.info("Testing Celery task execution...")
    
    # Check if task is registered
    registered_tasks = list(celery_app.tasks.keys())
    logger.info(f"Registered tasks: {registered_tasks}")
    
    if "storytime.worker.tasks.generate_tts" not in registered_tasks:
        logger.error("Task not registered!")
        sys.exit(1)
    
    # Send the task
    logger.info("Sending task...")
    result = generate_tts.delay("test-book-123")
    logger.info(f"Task ID: {result.id}")
    logger.info(f"Initial status: {result.status}")
    
    # Wait for result with periodic status checks
    logger.info("Waiting for result...")
    timeout = 15
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        status = result.status
        logger.info(f"Current status: {status}")
        
        if status == "SUCCESS":
            output = result.get()
            logger.info(f"Task completed successfully: {output}")
            break
        elif status == "FAILURE":
            logger.error(f"Task failed: {result.traceback}")
            break
        elif status == "PENDING":
            logger.info("Task still pending...")
        
        time.sleep(2)
    else:
        logger.error(f"Task timed out after {timeout} seconds. Final status: {result.status}")
        sys.exit(1) 