from __future__ import annotations

from pathlib import Path

from watchdog.events import FileCreatedEvent, FileModifiedEvent

from labclaw.core.events import event_registry
from labclaw.daemon import DataAccumulator
from labclaw.edge.watcher import FileDetectedHandler


def test_file_detected_handler_tracks_modified_files(tmp_path: Path) -> None:
    if not event_registry.is_registered("hardware.file.detected"):
        event_registry.register("hardware.file.detected")

    csv_path = tmp_path / "capture.csv"
    csv_path.write_text("x,y\n", encoding="utf-8")

    handler = FileDetectedHandler(device_id="rig-01")
    handler.on_created(FileCreatedEvent(str(csv_path)))
    handler.on_modified(FileModifiedEvent(str(csv_path)))

    detected = handler.detected_files
    assert len(detected) == 2
    assert detected[0].path == csv_path
    assert detected[1].path == csv_path


def test_late_written_file_ingests_after_modified_event(tmp_path: Path) -> None:
    if not event_registry.is_registered("hardware.file.detected"):
        event_registry.register("hardware.file.detected")

    csv_path = tmp_path / "late.csv"
    csv_path.write_text("latency,accuracy\n", encoding="utf-8")

    acc = DataAccumulator()
    handler = FileDetectedHandler(
        device_id="rig-01",
        callbacks=[lambda file_ref: acc.ingest_file(file_ref.path)],
    )

    handler.on_created(FileCreatedEvent(str(csv_path)))
    assert acc.total_rows == 0
    assert acc.files_processed == 0

    csv_path.write_text("latency,accuracy\n10.1,0.92\n", encoding="utf-8")
    handler.on_modified(FileModifiedEvent(str(csv_path)))

    assert acc.total_rows == 1
    assert acc.files_processed == 1
