"""Background task queue — async task execution with priority and retry.

Provides persistent task storage (aiosqlite), priority-based dequeue,
retry logic with exponential backoff, and event-driven state transitions.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import aiosqlite
from pydantic import BaseModel, Field

from labclaw.core.events import event_registry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Register events
# ---------------------------------------------------------------------------

_TASK_QUEUE_EVENTS = [
    "infra.task_queue.enqueued",
    "infra.task_queue.started",
    "infra.task_queue.completed",
    "infra.task_queue.failed",
    "infra.task_queue.cancelled",
]
for _evt in _TASK_QUEUE_EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


# ---------------------------------------------------------------------------
# Enums and schemas
# ---------------------------------------------------------------------------


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class TaskItem(BaseModel):
    """A unit of work in the task queue."""

    task_id: str = Field(default_factory=_uuid)
    name: str
    command: str = ""
    args: dict[str, Any] = Field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0
    created_at: datetime = Field(default_factory=_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    created_by: str = ""


class ScheduleItem(BaseModel):
    """A recurring task schedule."""

    schedule_id: str = Field(default_factory=_uuid)
    name: str
    cron_expr: str
    task_template: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    last_run: datetime | None = None
    next_run: datetime | None = None


# ---------------------------------------------------------------------------
# TaskExecutor Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class TaskExecutor(Protocol):
    """Protocol for executing tasks. Implementations define the actual work."""

    async def execute(self, task: TaskItem) -> tuple[bool, dict[str, Any], str | None]:
        """Execute a task.

        Returns:
            Tuple of (success, result_dict, error_message_or_none).
        """
        ...


# ---------------------------------------------------------------------------
# TaskQueue — aiosqlite-backed persistent queue
# ---------------------------------------------------------------------------


class TaskQueue:
    """Async task queue backed by SQLite."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or Path(":memory:")
        self._db: aiosqlite.Connection | None = None

    async def init_db(self, path: Path | None = None) -> None:
        """Initialize the database and create tables."""
        if path is not None:
            self._db_path = path
        if self._db_path != Path(":memory:"):
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._db_path))
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                command TEXT NOT NULL DEFAULT '',
                args_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'pending',
                priority INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                result_json TEXT,
                error TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                max_retries INTEGER NOT NULL DEFAULT 3,
                created_by TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
            CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority DESC);
        """)
        await self._db.commit()

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    def _db_or_raise(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("TaskQueue not initialized — call init_db() first")
        return self._db

    def _row_to_task(self, row: aiosqlite.Row) -> TaskItem:
        return TaskItem(
            task_id=row["task_id"],
            name=row["name"],
            command=row["command"],
            args=json.loads(row["args_json"]),
            status=TaskStatus(row["status"]),
            priority=row["priority"],
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=(datetime.fromisoformat(row["started_at"]) if row["started_at"] else None),
            completed_at=(
                datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None
            ),
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            error=row["error"],
            retry_count=row["retry_count"],
            max_retries=row["max_retries"],
            created_by=row["created_by"],
        )

    async def enqueue(self, task: TaskItem) -> str:
        """Add a task to the queue. Returns the task_id."""
        db = self._db_or_raise()
        await db.execute(
            "INSERT INTO tasks "
            "(task_id, name, command, args_json, status, priority, "
            "created_at, started_at, completed_at, result_json, error, "
            "retry_count, max_retries, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                task.task_id,
                task.name,
                task.command,
                json.dumps(task.args),
                task.status.value,
                task.priority,
                task.created_at.isoformat(),
                task.started_at.isoformat() if task.started_at else None,
                task.completed_at.isoformat() if task.completed_at else None,
                json.dumps(task.result) if task.result else None,
                task.error,
                task.retry_count,
                task.max_retries,
                task.created_by,
            ),
        )
        await db.commit()
        event_registry.emit(
            "infra.task_queue.enqueued",
            payload={"task_id": task.task_id, "name": task.name, "priority": task.priority},
        )
        return task.task_id

    async def dequeue(self) -> TaskItem | None:
        """Get the highest-priority pending task. Returns None if empty."""
        db = self._db_or_raise()
        async with db.execute(
            "SELECT * FROM tasks WHERE status = ? ORDER BY priority DESC, created_at ASC LIMIT 1",
            (TaskStatus.PENDING.value,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return self._row_to_task(row)

    async def update_status(
        self,
        task_id: str,
        status: TaskStatus,
        *,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> TaskItem:
        """Atomically update task status with optional result/error."""
        db = self._db_or_raise()
        task = await self.get_task(task_id)
        if task is None:
            raise KeyError(f"Task {task_id!r} not found")

        now = datetime.now(UTC)
        started_at = task.started_at
        completed_at = task.completed_at
        retry_count = task.retry_count

        if status == TaskStatus.PENDING:
            started_at = None
            completed_at = None
            error = None
        elif status == TaskStatus.RUNNING:
            started_at = now
        elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            completed_at = now
        if status == TaskStatus.FAILED:
            retry_count = task.retry_count + 1

        await db.execute(
            "UPDATE tasks SET status = ?, started_at = ?, completed_at = ?, "
            "result_json = ?, error = ?, retry_count = ? WHERE task_id = ?",
            (
                status.value,
                started_at.isoformat() if started_at else None,
                completed_at.isoformat() if completed_at else None,
                json.dumps(result) if result is not None else None,
                error,
                retry_count,
                task_id,
            ),
        )
        await db.commit()

        event_name = f"infra.task_queue.{status.value}"
        if event_registry.is_registered(event_name):
            event_registry.emit(
                event_name,
                payload={"task_id": task_id, "name": task.name},
            )

        return await self.get_task(task_id)  # type: ignore[return-value]

    async def get_task(self, task_id: str) -> TaskItem | None:
        """Get a task by ID. Returns None if not found."""
        db = self._db_or_raise()
        async with db.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return self._row_to_task(row)

    async def list_tasks(self, status: TaskStatus | None = None) -> list[TaskItem]:
        """List tasks, optionally filtered by status."""
        db = self._db_or_raise()
        if status:
            sql = "SELECT * FROM tasks WHERE status = ? ORDER BY priority DESC, created_at ASC"
            params: tuple[str, ...] = (status.value,)
        else:
            sql = "SELECT * FROM tasks ORDER BY priority DESC, created_at ASC"
            params = ()
        async with db.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return [self._row_to_task(row) for row in rows]

    async def cancel_task(self, task_id: str) -> TaskItem:
        """Cancel a pending or running task."""
        task = await self.get_task(task_id)
        if task is None:
            raise KeyError(f"Task {task_id!r} not found")
        if task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
            raise ValueError(f"Cannot cancel task in {task.status!r} status")
        return await self.update_status(task_id, TaskStatus.CANCELLED)


# ---------------------------------------------------------------------------
# TaskRunner — polling loop with retry
# ---------------------------------------------------------------------------


class TaskRunner:
    """Runs tasks from the queue using a TaskExecutor with retry logic."""

    def __init__(
        self,
        queue: TaskQueue,
        executor: TaskExecutor,
        *,
        poll_interval: float = 1.0,
        backoff_base: float = 2.0,
        max_backoff: float = 60.0,
    ) -> None:
        self._queue = queue
        self._executor = executor
        self._poll_interval = poll_interval
        self._backoff_base = backoff_base
        self._max_backoff = max_backoff
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the polling loop."""
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Stop the polling loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            task = await self._queue.dequeue()
            if task is None:
                await asyncio.sleep(self._poll_interval)
                continue
            await self._execute_task(task)

    async def _execute_task(self, task: TaskItem) -> None:
        """Execute a single task with retry logic."""
        await self._queue.update_status(task.task_id, TaskStatus.RUNNING)

        try:
            success, result, error = await self._executor.execute(task)
        except Exception:
            logger.exception("Executor raised for task %s", task.task_id)
            success, result, error = False, {}, f"executor exception: {task.task_id}"

        if success:
            await self._queue.update_status(task.task_id, TaskStatus.COMPLETED, result=result)
        else:
            updated = await self._queue.update_status(task.task_id, TaskStatus.FAILED, error=error)
            if updated.retry_count < updated.max_retries:
                backoff = min(
                    self._backoff_base**updated.retry_count,
                    self._max_backoff,
                )
                await asyncio.sleep(backoff)
                await self._queue.update_status(task.task_id, TaskStatus.PENDING)
