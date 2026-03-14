from __future__ import annotations

import multiprocessing
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from labclaw.memory.markdown import MemoryEntry, TierABackend


def test_append_memory_is_lossless_under_concurrent_writers(tmp_path: Path) -> None:
    root = tmp_path / "memory"
    backend_a = TierABackend(root=root)
    backend_b = TierABackend(root=root)

    worker_count = 8
    rounds = 20
    expected_entries = worker_count * rounds
    entity_id = "lab_001"
    details: list[str] = []
    barrier = threading.Barrier(worker_count)
    errors: list[BaseException] = []
    errors_lock = threading.Lock()

    def _worker(worker_idx: int) -> None:
        backend = backend_a if worker_idx % 2 == 0 else backend_b
        for round_idx in range(rounds):
            detail = f"detail;worker={worker_idx};round={round_idx};"
            try:
                barrier.wait()
                backend.append_memory(
                    entity_id,
                    MemoryEntry(
                        timestamp=datetime(2026, 1, 1, tzinfo=UTC)
                        + timedelta(seconds=(worker_idx * rounds) + round_idx),
                        category=f"worker-{worker_idx}",
                        detail=detail,
                    ),
                )
            except BaseException as exc:
                with errors_lock:
                    errors.append(exc)
                barrier.abort()
                return
            with errors_lock:
                details.append(detail)

    threads = [
        threading.Thread(target=_worker, args=(worker_idx,), daemon=True)
        for worker_idx in range(worker_count)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert all(not thread.is_alive() for thread in threads), "worker thread timed out"
    assert not errors
    assert len(details) == expected_entries

    doc = backend_a.read_memory(entity_id)
    section_count = sum(1 for line in doc.content.splitlines() if line.startswith("## "))
    assert section_count == expected_entries

    for detail in details:
        assert doc.content.count(detail) == 1


def _append_memory_from_process(
    root: str,
    entity_id: str,
    worker_idx: int,
    rounds: int,
    barrier: Any,
    errors: Any,
) -> None:
    try:
        backend = TierABackend(root=Path(root))
        barrier.wait(timeout=10)
        for round_idx in range(rounds):
            backend.append_memory(
                entity_id,
                MemoryEntry(
                    timestamp=datetime(2026, 1, 2, tzinfo=UTC)
                    + timedelta(seconds=(worker_idx * rounds) + round_idx),
                    category=f"proc-{worker_idx}",
                    detail=f"detail;proc={worker_idx};round={round_idx};",
                ),
            )
    except BaseException as exc:
        errors.put(f"{type(exc).__name__}: {exc}")


def test_append_memory_is_lossless_under_spawned_process_writers(tmp_path: Path) -> None:
    root = tmp_path / "memory"
    entity_id = "lab_proc_001"
    worker_count = 4
    rounds = 25
    expected_entries = worker_count * rounds

    ctx = multiprocessing.get_context("spawn")
    barrier = ctx.Barrier(worker_count)
    errors = ctx.Queue()
    processes = [
        ctx.Process(
            target=_append_memory_from_process,
            args=(str(root), entity_id, worker_idx, rounds, barrier, errors),
        )
        for worker_idx in range(worker_count)
    ]

    for proc in processes:
        proc.start()
    for proc in processes:
        proc.join(timeout=20)

    drained_errors: list[str] = []
    while not errors.empty():
        drained_errors.append(errors.get())

    assert all(not proc.is_alive() for proc in processes), "worker process timed out"
    assert all(proc.exitcode == 0 for proc in processes), [proc.exitcode for proc in processes]
    assert not drained_errors, drained_errors

    backend = TierABackend(root=root)
    doc = backend.read_memory(entity_id)
    section_count = sum(1 for line in doc.content.splitlines() if line.startswith("## "))
    assert section_count == expected_entries

    for worker_idx in range(worker_count):
        for round_idx in range(rounds):
            detail = f"detail;proc={worker_idx};round={round_idx};"
            assert doc.content.count(detail) == 1
