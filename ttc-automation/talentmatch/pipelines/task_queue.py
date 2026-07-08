"""Simple Redis-backed task queue for async processing"""
from __future__ import annotations
import json
import os
import uuid
import time
from typing import Optional, Callable
from loguru import logger

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class TaskQueue:
    """Redis-based task queue with progress tracking"""

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        self._redis = None
        self._available = REDIS_AVAILABLE

    @property
    def redis(self):
        if self._redis is None and self._available:
            try:
                self._redis = redis.from_url(self.redis_url, decode_responses=True)
                self._redis.ping()
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}, using in-memory queue")
                self._available = False
        return self._redis

    def enqueue(self, queue_name: str, task_data: dict) -> str:
        """Add task to queue, return task_id"""
        task_id = task_data.get("task_id") or str(uuid.uuid4())
        task_data["task_id"] = task_id
        task_data["enqueued_at"] = time.time()

        if self._available and self.redis:
            self.redis.rpush(f"queue:{queue_name}", json.dumps(task_data, ensure_ascii=False))
            self._set_task_status(task_id, "pending")
        else:
            # In-memory fallback
            if not hasattr(self, "_mem_queue"):
                self._mem_queue = {}
            self._mem_queue.setdefault(queue_name, []).append(task_data)

        return task_id

    def dequeue(self, queue_name: str, timeout: int = 5) -> Optional[dict]:
        """Get next task from queue"""
        if self._available and self.redis:
            result = self.redis.blpop(f"queue:{queue_name}", timeout=timeout)
            if result:
                return json.loads(result[1])
            return None
        else:
            if hasattr(self, "_mem_queue") and self._mem_queue.get(queue_name):
                return self._mem_queue[queue_name].pop(0)
            return None

    def _set_task_status(self, task_id: str, status: str, progress: float = 0.0, message: str = ""):
        if self._available and self.redis:
            self.redis.hset(f"task:{task_id}", mapping={
                "status": status,
                "progress": progress,
                "message": message,
                "updated_at": time.time()
            })
            # Auto-expire after 1 hour
            self.redis.expire(f"task:{task_id}", 3600)

    def get_task_status(self, task_id: str) -> dict:
        if self._available and self.redis:
            data = self.redis.hgetall(f"task:{task_id}")
            return data if data else {"status": "unknown"}
        return {"status": "unknown"}

    def update_progress(self, task_id: str, progress: float, message: str = ""):
        self._set_task_status(task_id, "processing", progress, message)

    def complete_task(self, task_id: str, result: dict = None):
        if self._available and self.redis:
            mapping = {"status": "done", "progress": 1.0, "message": "完成", "updated_at": time.time()}
            if result:
                mapping["result"] = json.dumps(result, ensure_ascii=False)
            self.redis.hset(f"task:{task_id}", mapping=mapping)

    def fail_task(self, task_id: str, error: str = ""):
        self._set_task_status(task_id, "failed", 0.0, error)
