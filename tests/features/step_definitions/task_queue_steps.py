"""BDD step definitions for background task queue (L2 Scheduling)."""

from __future__ import annotations

import asyncio
from typing import Any

from pytest_bdd import given, parsers, then, when

from labclaw.core.events import event_registry
from labclaw.core.schemas import LabEvent
from labclaw.core.task_queue import TaskItem, TaskQueue, TaskStatus


def _run_async(coro: Any) -> Any:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _EventCapture:
    def __init__(self) -> None:
        self.events: list[LabEvent] = []
        self.names: list[str] = []

    def __call__(self, event: LabEvent) -> None:
        self.events.append(event)
        self.names.append(event.event_name.full)


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given("an initialized task queue", target_fixture="tq_ctx")
def initialized_queue() -> Any:
    q = TaskQueue()
    _run_async(q.init_db())
    yield {"queue": q, "task_id": None}
    _run_async(q.close())


@given(
    parsers.parse('a task named "{name}" is enqueued'),
    target_fixture="tq_ctx",
)
def task_enqueued(tq_ctx: dict[str, Any], name: str) -> dict[str, Any]:
    q = tq_ctx["queue"]
    task = TaskItem(name=name)
    tid = _run_async(q.enqueue(task))
    tq_ctx["task_id"] = tid
    return tq_ctx


@given(
    parsers.parse('a completed task named "{name}"'),
    target_fixture="tq_ctx",
)
def completed_task(tq_ctx: dict[str, Any], name: str) -> dict[str, Any]:
    q = tq_ctx["queue"]
    task = TaskItem(name=name)
    tid = _run_async(q.enqueue(task))
    _run_async(q.update_status(tid, TaskStatus.COMPLETED))
    tq_ctx["task_id"] = tid
    return tq_ctx


@given("an initialized task queue with event capture", target_fixture="tq_ctx")
def queue_with_capture() -> Any:
    q = TaskQueue()
    _run_async(q.init_db())
    cap = _EventCapture()
    event_registry.subscribe("infra.task_queue.enqueued", cap)
    yield {"queue": q, "task_id": None, "capture": cap}
    event_registry.unsubscribe("infra.task_queue.enqueued", cap)
    _run_async(q.close())


@given(
    parsers.parse('tasks "{a}" and "{b}" are enqueued'),
    target_fixture="tq_ctx",
)
def two_tasks_enqueued(tq_ctx: dict[str, Any], a: str, b: str) -> dict[str, Any]:
    q = tq_ctx["queue"]
    t1 = TaskItem(name=a)
    t2 = TaskItem(name=b)
    tq_ctx["task_id_a"] = _run_async(q.enqueue(t1))
    tq_ctx["task_id_b"] = _run_async(q.enqueue(t2))
    return tq_ctx


@given(
    parsers.parse('task "{name}" is set to running'),
    target_fixture="tq_ctx",
)
def task_set_running(tq_ctx: dict[str, Any], name: str) -> dict[str, Any]:
    q = tq_ctx["queue"]
    tid = tq_ctx.get("task_id_a") if name == "a" else tq_ctx.get("task_id_b")
    _run_async(q.update_status(tid, TaskStatus.RUNNING))
    return tq_ctx


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I enqueue a task named "{name}"'),
    target_fixture="tq_result",
)
def enqueue_task(tq_ctx: dict[str, Any], name: str) -> dict[str, Any]:
    q = tq_ctx["queue"]
    task = TaskItem(name=name)
    tid = _run_async(q.enqueue(task))
    return {**tq_ctx, "task_id": tid}


@when("I dequeue from the empty queue", target_fixture="tq_result")
def dequeue_empty(tq_ctx: dict[str, Any]) -> dict[str, Any]:
    q = tq_ctx["queue"]
    result = _run_async(q.dequeue())
    return {**tq_ctx, "dequeued": result}


@when(
    parsers.parse("I enqueue tasks with priorities {p1:d}, {p2:d}, and {p3:d}"),
    target_fixture="tq_result",
)
def enqueue_priorities(tq_ctx: dict[str, Any], p1: int, p2: int, p3: int) -> dict[str, Any]:
    q = tq_ctx["queue"]
    _run_async(q.enqueue(TaskItem(name="p1", priority=p1)))
    _run_async(q.enqueue(TaskItem(name="p2", priority=p2)))
    _run_async(q.enqueue(TaskItem(name="p3", priority=p3)))
    return tq_ctx


@when(
    parsers.parse('I update the task status to "{status}"'),
    target_fixture="tq_result",
)
def update_status(tq_ctx: dict[str, Any], status: str) -> dict[str, Any]:
    q = tq_ctx["queue"]
    _run_async(q.update_status(tq_ctx["task_id"], TaskStatus(status)))
    task = _run_async(q.get_task(tq_ctx["task_id"]))
    return {**tq_ctx, "task": task}


@when(
    parsers.parse('I complete the task with result "{result}"'),
    target_fixture="tq_result",
)
def complete_task(tq_ctx: dict[str, Any], result: str) -> dict[str, Any]:
    q = tq_ctx["queue"]
    _run_async(q.update_status(tq_ctx["task_id"], TaskStatus.COMPLETED, result={"output": result}))
    task = _run_async(q.get_task(tq_ctx["task_id"]))
    return {**tq_ctx, "task": task}


@when(
    parsers.parse('I fail the task with error "{error}"'),
    target_fixture="tq_result",
)
def fail_task(tq_ctx: dict[str, Any], error: str) -> dict[str, Any]:
    q = tq_ctx["queue"]
    _run_async(q.update_status(tq_ctx["task_id"], TaskStatus.FAILED, error=error))
    task = _run_async(q.get_task(tq_ctx["task_id"]))
    return {**tq_ctx, "task": task}


@when("I cancel the task", target_fixture="tq_result")
def cancel_task(tq_ctx: dict[str, Any]) -> dict[str, Any]:
    q = tq_ctx["queue"]
    task = _run_async(q.cancel_task(tq_ctx["task_id"]))
    return {**tq_ctx, "task": task}


@when("I try to cancel the completed task", target_fixture="tq_result")
def try_cancel_completed(tq_ctx: dict[str, Any]) -> dict[str, Any]:
    q = tq_ctx["queue"]
    try:
        _run_async(q.cancel_task(tq_ctx["task_id"]))
        return {**tq_ctx, "cancel_error": None}
    except ValueError as exc:
        return {**tq_ctx, "cancel_error": exc}


@when("I list pending tasks", target_fixture="tq_result")
def list_pending(tq_ctx: dict[str, Any]) -> dict[str, Any]:
    q = tq_ctx["queue"]
    tasks = _run_async(q.list_tasks(status=TaskStatus.PENDING))
    return {**tq_ctx, "pending_tasks": tasks}


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then(parsers.parse('I can dequeue the task named "{name}"'))
def check_dequeued_name(tq_result: dict[str, Any], name: str) -> None:
    q = tq_result["queue"]
    task = _run_async(q.dequeue())
    assert task is not None
    assert task.name == name


@then("no task is returned")
def check_no_task(tq_result: dict[str, Any]) -> None:
    assert tq_result["dequeued"] is None


@then(parsers.parse("the first dequeued task has priority {priority:d}"))
def check_priority(tq_ctx: dict[str, Any], priority: int) -> None:
    q = tq_ctx["queue"]
    task = _run_async(q.dequeue())
    assert task is not None
    assert task.priority == priority


@then(parsers.parse('the task status is "{status}"'))
def check_task_status(tq_result: dict[str, Any], status: str) -> None:
    assert tq_result["task"].status == TaskStatus(status)


@then("the task has a started_at timestamp")
def check_started_at(tq_result: dict[str, Any]) -> None:
    assert tq_result["task"].started_at is not None


@then("the task has a completed_at timestamp")
def check_completed_at(tq_result: dict[str, Any]) -> None:
    assert tq_result["task"].completed_at is not None


@then(parsers.parse("the task retry count is {count:d}"))
def check_retry_count(tq_result: dict[str, Any], count: int) -> None:
    assert tq_result["task"].retry_count == count


@then("a ValueError is raised for cancel")
def check_cancel_error(tq_result: dict[str, Any]) -> None:
    assert isinstance(tq_result["cancel_error"], ValueError)


@then(parsers.parse('the event "{event_name}" was emitted'))
def check_event_emitted(tq_result: dict[str, Any], event_name: str) -> None:
    cap = tq_result.get("capture")
    assert cap is not None
    assert event_name in cap.names


@then(parsers.parse('only task "{name}" is in the pending list'))
def check_pending_list(tq_result: dict[str, Any], name: str) -> None:
    tasks = tq_result["pending_tasks"]
    assert len(tasks) == 1
    assert tasks[0].name == name
