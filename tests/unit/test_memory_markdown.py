from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

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
