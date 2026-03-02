"""Tests for background task queue."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from labclaw.core.task_queue import (
    ScheduleItem,
    TaskExecutor,
    TaskItem,
    TaskQueue,
    TaskRunner,
    TaskStatus,
)

# ---------------------------------------------------------------------------
# TaskItem schema
# ---------------------------------------------------------------------------


class TestTaskItem:
    def test_defaults(self) -> None:
        t = TaskItem(name="test-task")
        assert t.status == TaskStatus.PENDING
        assert t.priority == 0
        assert t.retry_count == 0
        assert t.max_retries == 3
        assert t.task_id  # UUID generated
        assert t.created_at is not None

    def test_custom_values(self) -> None:
        t = TaskItem(name="high-pri", priority=10, max_retries=5, created_by="user1")
        assert t.priority == 10
        assert t.max_retries == 5
        assert t.created_by == "user1"

    def test_args_default_empty(self) -> None:
        t = TaskItem(name="t")
        assert t.args == {}


class TestScheduleItem:
    def test_defaults(self) -> None:
        s = ScheduleItem(name="daily-check", cron_expr="0 0 * * *")
        assert s.enabled is True
        assert s.last_run is None
        assert s.schedule_id  # UUID generated


# ---------------------------------------------------------------------------
# TaskExecutor Protocol
# ---------------------------------------------------------------------------


class TestTaskExecutorProtocol:
    def test_runtime_checkable(self) -> None:
        class MyExecutor:
            async def execute(
                self, task: TaskItem
            ) -> tuple[bool, dict[str, Any], str | None]:
                return True, {}, None

        assert isinstance(MyExecutor(), TaskExecutor)


# ---------------------------------------------------------------------------
# TaskQueue
# ---------------------------------------------------------------------------


class TestTaskQueue:
    @pytest.mark.asyncio
    async def test_init_and_close(self) -> None:
        q = TaskQueue()
        await q.init_db()
        await q.close()

    @pytest.mark.asyncio
    async def test_not_initialized_raises(self) -> None:
        q = TaskQueue()
        with pytest.raises(RuntimeError, match="not initialized"):
            await q.enqueue(TaskItem(name="fail"))

    @pytest.mark.asyncio
    async def test_enqueue_and_dequeue(self) -> None:
        q = TaskQueue()
        await q.init_db()
        try:
            task = TaskItem(name="my-task")
            task_id = await q.enqueue(task)
            assert task_id == task.task_id

            dequeued = await q.dequeue()
            assert dequeued is not None
            assert dequeued.task_id == task_id
            assert dequeued.name == "my-task"
        finally:
            await q.close()

    @pytest.mark.asyncio
    async def test_dequeue_empty_returns_none(self) -> None:
        q = TaskQueue()
        await q.init_db()
        try:
            assert await q.dequeue() is None
        finally:
            await q.close()

    @pytest.mark.asyncio
    async def test_priority_ordering(self) -> None:
        q = TaskQueue()
        await q.init_db()
        try:
            await q.enqueue(TaskItem(name="low", priority=1))
            await q.enqueue(TaskItem(name="high", priority=10))
            await q.enqueue(TaskItem(name="mid", priority=5))

            first = await q.dequeue()
            assert first is not None
            assert first.name == "high"
        finally:
            await q.close()

    @pytest.mark.asyncio
    async def test_get_task(self) -> None:
        q = TaskQueue()
        await q.init_db()
        try:
            task = TaskItem(name="lookup")
            await q.enqueue(task)
            found = await q.get_task(task.task_id)
            assert found is not None
            assert found.name == "lookup"
        finally:
            await q.close()

    @pytest.mark.asyncio
    async def test_get_task_not_found(self) -> None:
        q = TaskQueue()
        await q.init_db()
        try:
            assert await q.get_task("nonexistent") is None
        finally:
            await q.close()

    @pytest.mark.asyncio
    async def test_list_tasks_all(self) -> None:
        q = TaskQueue()
        await q.init_db()
        try:
            await q.enqueue(TaskItem(name="a"))
            await q.enqueue(TaskItem(name="b"))
            tasks = await q.list_tasks()
            assert len(tasks) == 2
        finally:
            await q.close()

    @pytest.mark.asyncio
    async def test_list_tasks_by_status(self) -> None:
        q = TaskQueue()
        await q.init_db()
        try:
            t1 = TaskItem(name="pending-task")
            await q.enqueue(t1)
            await q.update_status(t1.task_id, TaskStatus.RUNNING)
            t2 = TaskItem(name="another-pending")
            await q.enqueue(t2)

            pending = await q.list_tasks(status=TaskStatus.PENDING)
            assert len(pending) == 1
            assert pending[0].name == "another-pending"
        finally:
            await q.close()

    @pytest.mark.asyncio
    async def test_update_status_running(self) -> None:
        q = TaskQueue()
        await q.init_db()
        try:
            task = TaskItem(name="run-me")
            await q.enqueue(task)
            updated = await q.update_status(task.task_id, TaskStatus.RUNNING)
            assert updated.status == TaskStatus.RUNNING
            assert updated.started_at is not None
        finally:
            await q.close()

    @pytest.mark.asyncio
    async def test_update_status_completed(self) -> None:
        q = TaskQueue()
        await q.init_db()
        try:
            task = TaskItem(name="complete-me")
            await q.enqueue(task)
            updated = await q.update_status(
                task.task_id, TaskStatus.COMPLETED, result={"output": "done"}
            )
            assert updated.status == TaskStatus.COMPLETED
            assert updated.completed_at is not None
            assert updated.result == {"output": "done"}
        finally:
            await q.close()

    @pytest.mark.asyncio
    async def test_update_status_failed_increments_retry(self) -> None:
        q = TaskQueue()
        await q.init_db()
        try:
            task = TaskItem(name="fail-me")
            await q.enqueue(task)
            updated = await q.update_status(
                task.task_id, TaskStatus.FAILED, error="bad input"
            )
            assert updated.status == TaskStatus.FAILED
            assert updated.retry_count == 1
            assert updated.error == "bad input"
        finally:
            await q.close()

    @pytest.mark.asyncio
    async def test_update_status_not_found_raises(self) -> None:
        q = TaskQueue()
        await q.init_db()
        try:
            with pytest.raises(KeyError, match="not found"):
                await q.update_status("ghost", TaskStatus.RUNNING)
        finally:
            await q.close()

    @pytest.mark.asyncio
    async def test_cancel_pending_task(self) -> None:
        q = TaskQueue()
        await q.init_db()
        try:
            task = TaskItem(name="cancel-me")
            await q.enqueue(task)
            cancelled = await q.cancel_task(task.task_id)
            assert cancelled.status == TaskStatus.CANCELLED
        finally:
            await q.close()

    @pytest.mark.asyncio
    async def test_cancel_running_task(self) -> None:
        q = TaskQueue()
        await q.init_db()
        try:
            task = TaskItem(name="cancel-running")
            await q.enqueue(task)
            await q.update_status(task.task_id, TaskStatus.RUNNING)
            cancelled = await q.cancel_task(task.task_id)
            assert cancelled.status == TaskStatus.CANCELLED
        finally:
            await q.close()

    @pytest.mark.asyncio
    async def test_cancel_completed_raises(self) -> None:
        q = TaskQueue()
        await q.init_db()
        try:
            task = TaskItem(name="done")
            await q.enqueue(task)
            await q.update_status(task.task_id, TaskStatus.COMPLETED)
            with pytest.raises(ValueError, match="Cannot cancel"):
                await q.cancel_task(task.task_id)
        finally:
            await q.close()

    @pytest.mark.asyncio
    async def test_cancel_not_found_raises(self) -> None:
        q = TaskQueue()
        await q.init_db()
        try:
            with pytest.raises(KeyError, match="not found"):
                await q.cancel_task("ghost")
        finally:
            await q.close()

    @pytest.mark.asyncio
    async def test_enqueue_emits_event(self) -> None:
        q = TaskQueue()
        await q.init_db()
        captured: list[str] = []
        from labclaw.core.events import event_registry

        def handler(e):  # type: ignore[no-untyped-def]
            captured.append(e.event_name.full)
        event_registry.subscribe("infra.task_queue.enqueued", handler)
        try:
            await q.enqueue(TaskItem(name="event-test"))
            assert "infra.task_queue.enqueued" in captured
        finally:
            event_registry.unsubscribe("infra.task_queue.enqueued", handler)
            await q.close()

    @pytest.mark.asyncio
    async def test_init_db_with_path(self) -> None:
        q = TaskQueue()
        await q.init_db()
        try:
            assert q._db is not None
        finally:
            await q.close()

    @pytest.mark.asyncio
    async def test_init_db_with_file_path(self, tmp_path: Any) -> None:
        db_file = tmp_path / "sub" / "tasks.db"
        q = TaskQueue()
        await q.init_db(path=db_file)
        try:
            assert db_file.parent.exists()
            await q.enqueue(TaskItem(name="file-test"))
            task = await q.dequeue()
            assert task is not None
            assert task.name == "file-test"
        finally:
            await q.close()

    @pytest.mark.asyncio
    async def test_task_with_args(self) -> None:
        q = TaskQueue()
        await q.init_db()
        try:
            task = TaskItem(name="with-args", args={"key": "value", "n": 42})
            await q.enqueue(task)
            found = await q.get_task(task.task_id)
            assert found is not None
            assert found.args == {"key": "value", "n": 42}
        finally:
            await q.close()


# ---------------------------------------------------------------------------
# TaskRunner
# ---------------------------------------------------------------------------


class _SuccessExecutor:
    async def execute(self, task: TaskItem) -> tuple[bool, dict[str, Any], str | None]:
        return True, {"output": "success"}, None


class _FailExecutor:
    async def execute(self, task: TaskItem) -> tuple[bool, dict[str, Any], str | None]:
        return False, {}, "execution failed"


class TestTaskRunner:
    @pytest.mark.asyncio
    async def test_runner_processes_task(self) -> None:
        q = TaskQueue()
        await q.init_db()
        try:
            await q.enqueue(TaskItem(name="run-test"))

            runner = TaskRunner(q, _SuccessExecutor(), poll_interval=0.01)
            await runner.start()
            await asyncio.sleep(0.1)
            await runner.stop()

            tasks = await q.list_tasks(status=TaskStatus.COMPLETED)
            assert len(tasks) == 1
            assert tasks[0].result == {"output": "success"}
        finally:
            await q.close()

    @pytest.mark.asyncio
    async def test_runner_retries_on_failure(self) -> None:
        q = TaskQueue()
        await q.init_db()
        try:
            task = TaskItem(name="retry-test", max_retries=2)
            await q.enqueue(task)

            runner = TaskRunner(
                q, _FailExecutor(), poll_interval=0.01, backoff_base=0.01, max_backoff=0.02
            )
            await runner.start()
            await asyncio.sleep(0.5)
            await runner.stop()

            found = await q.get_task(task.task_id)
            assert found is not None
            # Should have retried up to max_retries
            assert found.retry_count >= 2
        finally:
            await q.close()

    @pytest.mark.asyncio
    async def test_runner_start_stop(self) -> None:
        q = TaskQueue()
        await q.init_db()
        try:
            runner = TaskRunner(q, _SuccessExecutor(), poll_interval=0.01)
            await runner.start()
            assert runner._running is True
            await runner.stop()
            assert runner._running is False
        finally:
            await q.close()

    @pytest.mark.asyncio
    async def test_runner_stop_without_start(self) -> None:
        q = TaskQueue()
        await q.init_db()
        try:
            runner = TaskRunner(q, _SuccessExecutor())
            await runner.stop()  # should not raise
            assert runner._running is False
        finally:
            await q.close()
