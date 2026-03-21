"""Task Queue — async job processing with in-memory queue + optional Celery.

Provides:
- In-memory task queue for development/testing
- Task status tracking (pending, running, completed, failed)
- Priority ordering
- Result storage
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    id: str
    name: str
    args: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0  # higher = more important
    result: Any = None
    error: str = ""
    created_at: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0
    tenant_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "priority": self.priority,
            "created_at": self.created_at,
        }
        if self.started_at:
            d["started_at"] = self.started_at
        if self.completed_at:
            d["completed_at"] = self.completed_at
            d["duration_s"] = round(self.completed_at - self.started_at, 2)
        if self.error:
            d["error"] = self.error
        if self.tenant_id:
            d["tenant_id"] = self.tenant_id
        return d


class TaskQueue:
    """In-memory task queue with synchronous execution for dev/test."""

    def __init__(self) -> None:
        self._tasks: Dict[str, Task] = {}
        self._handlers: Dict[str, Callable[..., Any]] = {}

    def register_handler(self, task_name: str, handler: Callable[..., Any]) -> None:
        """Register a handler function for a task type."""
        self._handlers[task_name] = handler

    def submit(self, name: str, args: Optional[Dict[str, Any]] = None,
               priority: int = 0, tenant_id: str = "") -> Task:
        """Submit a new task to the queue."""
        task = Task(
            id=uuid.uuid4().hex[:12],
            name=name,
            args=args or {},
            priority=priority,
            created_at=time.time(),
            tenant_id=tenant_id,
        )
        self._tasks[task.id] = task
        return task

    def execute(self, task_id: str) -> Task:
        """Execute a task synchronously."""
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        if task.status != TaskStatus.PENDING:
            return task

        handler = self._handlers.get(task.name)
        if not handler:
            task.status = TaskStatus.FAILED
            task.error = f"No handler registered for task: {task.name}"
            return task

        task.status = TaskStatus.RUNNING
        task.started_at = time.time()

        try:
            task.result = handler(**task.args)
            task.status = TaskStatus.COMPLETED
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            logger.exception(f"Task {task.id} ({task.name}) failed: {e}")
        finally:
            task.completed_at = time.time()

        return task

    def process_next(self) -> Optional[Task]:
        """Process the highest-priority pending task."""
        pending = [t for t in self._tasks.values() if t.status == TaskStatus.PENDING]
        if not pending:
            return None
        pending.sort(key=lambda t: (-t.priority, t.created_at))
        return self.execute(pending[0].id)

    def process_all(self) -> List[Task]:
        """Process all pending tasks."""
        results = []
        while True:
            task = self.process_next()
            if task is None:
                break
            results.append(task)
        return results

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
            return True
        return False

    def list_tasks(self, status: Optional[TaskStatus] = None,
                   tenant_id: str = "") -> List[Task]:
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        if tenant_id:
            tasks = [t for t in tasks if t.tenant_id == tenant_id]
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks

    def metrics(self) -> Dict[str, Any]:
        counts: Dict[str, int] = {}
        for t in self._tasks.values():
            counts[t.status.value] = counts.get(t.status.value, 0) + 1
        completed = [t for t in self._tasks.values() if t.status == TaskStatus.COMPLETED]
        avg_duration = 0.0
        if completed:
            avg_duration = sum(t.completed_at - t.started_at for t in completed) / len(completed)
        return {
            "total_tasks": len(self._tasks),
            "status_counts": counts,
            "avg_duration_s": round(avg_duration, 3),
        }

    @property
    def pending_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status == TaskStatus.PENDING)


_queue: Optional[TaskQueue] = None


def get_task_queue() -> TaskQueue:
    global _queue
    if _queue is None:
        _queue = TaskQueue()
    return _queue


def set_task_queue(q: TaskQueue) -> None:
    global _queue
    _queue = q
