"""RQ worker entrypoint: python worker.py"""
from redis import Redis
from rq import Queue, SimpleWorker

from app.config import settings

if __name__ == "__main__":
    conn = Redis.from_url(settings.redis_url)
    SimpleWorker([Queue("generation", connection=conn)], connection=conn).work()
