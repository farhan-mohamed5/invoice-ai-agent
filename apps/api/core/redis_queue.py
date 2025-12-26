from redis import Redis
from apps.api.core.config import settings

redis_client = Redis.from_url(settings.REDIS_URL)

def enqueue_task(task_name: str, payload: dict):
    """
    Push a job to Celery/Redis queue.
    Worker will process this and call the invoice ingestion pipeline.
    """
    job = {
        "task": task_name,
        "payload": payload,
    }
    redis_client.lpush("invoice_tasks", str(job))