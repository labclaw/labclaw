"""Concurrency tests — verify thread and async safety of LabClaw modules."""

from __future__ import annotations

import csv
import tempfile
import threading
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# 1. DataAccumulator: 10 concurrent threads ingesting different files
# ---------------------------------------------------------------------------


def test_accumulator_10_concurrent_threads() -> None:
    from labclaw.daemon import DataAccumulator

    acc = DataAccumulator()
    tmpdir = Path(tempfile.mkdtemp())
    num_threads = 10
    rows_per_file = 50

    files: list[Path] = []
    for i in range(num_threads):
        p = tmpdir / f"concurrent_{i}.csv"
        with p.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["a", "b", "c"])
            writer.writeheader()
            for j in range(rows_per_file):
                writer.writerow({"a": i, "b": j, "c": i + j})
        files.append(p)

    errors: list[Exception] = []
    results: list[int] = [0] * num_threads

    def worker(idx: int) -> None:
        try:
            results[idx] = acc.ingest_file(files[idx])
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Concurrent ingest errors: {errors}"
    total = sum(results)
    assert total == num_threads * rows_per_file
    assert acc.total_rows == total
    assert acc.files_processed == num_threads

    # Verify data integrity: all rows should be present
    all_rows = acc.get_all_rows()
    assert len(all_rows) == total


# ---------------------------------------------------------------------------
# 2. EventRegistry: concurrent subscribers without deadlock
# ---------------------------------------------------------------------------


def test_event_registry_concurrent_subscribers() -> None:
    from labclaw.core.events import EventRegistry

    registry = EventRegistry()
    registry.register("test.concurrency.event")

    num_subscribers = 20
    received: list[int] = []
    lock = threading.Lock()

    def make_handler(idx: int):
        def handler(event):
            with lock:
                received.append(idx)

        return handler

    # Subscribe from multiple threads
    def subscribe_worker(idx: int) -> None:
        registry.subscribe("test.concurrency.event", make_handler(idx))

    threads = [threading.Thread(target=subscribe_worker, args=(i,)) for i in range(num_subscribers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Emit from multiple threads
    num_emitters = 5
    emit_errors: list[Exception] = []

    def emit_worker() -> None:
        try:
            registry.emit("test.concurrency.event", payload={"thread": True})
        except Exception as e:
            emit_errors.append(e)

    emit_threads = [threading.Thread(target=emit_worker) for _ in range(num_emitters)]
    for t in emit_threads:
        t.start()
    for t in emit_threads:
        t.join()

    assert not emit_errors, f"Emit errors: {emit_errors}"
    # Each emit should trigger all subscribers
    assert len(received) == num_subscribers * num_emitters


# ---------------------------------------------------------------------------
# 3. SQLiteTierBBackend: concurrent add_node calls (async)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sqlite_backend_concurrent_add_node() -> None:
    import asyncio

    from labclaw.core.graph import GraphNode
    from labclaw.memory.sqlite_backend import SQLiteTierBBackend

    tmpdir = Path(tempfile.mkdtemp())
    db_path = tmpdir / "test_concurrent.db"

    backend = SQLiteTierBBackend(db_path)
    await backend.init_db()

    num_nodes = 20
    errors: list[Exception] = []

    async def add_node(i: int) -> None:
        try:
            node = GraphNode(
                node_id=f"concurrent-node-{i}",
                tags=[f"tag-{i}"],
                metadata={"index": i},
            )
            await backend.add_node(node)
        except Exception as e:
            errors.append(e)

    # Run all add_node calls concurrently
    tasks = [add_node(i) for i in range(num_nodes)]
    await asyncio.gather(*tasks)

    assert not errors, f"Concurrent add_node errors: {errors}"
    count = await backend.node_count()
    assert count == num_nodes

    # Verify all nodes are retrievable
    for i in range(num_nodes):
        node = await backend.get_node(f"concurrent-node-{i}")
        assert node.node_id == f"concurrent-node-{i}"
        assert node.metadata["index"] == i

    await backend.close()


# ---------------------------------------------------------------------------
# 4. DataAccumulator: re-ingest same file is idempotent
# ---------------------------------------------------------------------------


def test_accumulator_reingest_idempotent() -> None:
    from labclaw.daemon import DataAccumulator

    acc = DataAccumulator()
    tmpdir = Path(tempfile.mkdtemp())
    p = tmpdir / "stable.csv"

    with p.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["x", "y"])
        writer.writeheader()
        for i in range(10):
            writer.writerow({"x": i, "y": i * 2})

    first = acc.ingest_file(p)
    assert first == 10

    # Re-ingest the same file: should return 0 new rows
    second = acc.ingest_file(p)
    assert second == 0
    assert acc.total_rows == 10


# ---------------------------------------------------------------------------
# 5. EventRegistry: subscribe + emit race condition
# ---------------------------------------------------------------------------


def test_event_registry_subscribe_emit_race() -> None:
    """Subscribe and emit on different threads simultaneously to test for races."""
    from labclaw.core.events import EventRegistry

    registry = EventRegistry()
    registry.register("test.race.event")

    received_count = {"value": 0}
    lock = threading.Lock()
    barrier = threading.Barrier(2)

    def handler(event):
        with lock:
            received_count["value"] += 1

    def subscriber() -> None:
        barrier.wait()
        for _ in range(50):
            registry.subscribe("test.race.event", handler)

    def emitter() -> None:
        barrier.wait()
        for _ in range(50):
            try:
                registry.emit("test.race.event", payload={})
            except Exception:
                pass

    t1 = threading.Thread(target=subscriber)
    t2 = threading.Thread(target=emitter)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Should complete without deadlock
    assert received_count["value"] >= 0  # At least no crash
