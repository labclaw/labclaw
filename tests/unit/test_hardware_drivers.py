"""Tests for hardware drivers and file-based interface.

Covers:
- src/labclaw/hardware/drivers/plate_reader_csv.py
- src/labclaw/hardware/drivers/qpcr_export.py
- src/labclaw/hardware/drivers/file_watcher.py
- src/labclaw/hardware/interfaces/file_based.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from labclaw.core.schemas import DeviceStatus
from labclaw.hardware.drivers.plate_reader_csv import PlateReaderCSVDriver
from labclaw.hardware.drivers.qpcr_export import QPCRExportDriver, _find_col
from labclaw.hardware.interfaces.file_based import FileBasedDriver

# ---------------------------------------------------------------------------
# PlateReaderCSVDriver
# ---------------------------------------------------------------------------


class TestPlateReaderCSV:
    def _write_plate_csv(self, path: Path, content: str) -> Path:
        csv_file = path / "plate.csv"
        csv_file.write_text(content, encoding="utf-8")
        return csv_file

    def test_parse_standard_96well(self, tmp_path: Path) -> None:
        csv_content = (
            "Instrument,SpectraMax\n"
            "Date,2026-01-15\n"
            "A,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0,1.1,1.2\n"
            "B,0.21,0.22,0.23,0.24,0.25,0.26,0.27,0.28,0.29,0.30,0.31,0.32\n"
        )
        csv_file = self._write_plate_csv(tmp_path, csv_content)
        driver = PlateReaderCSVDriver("pr-1", "plate_reader", tmp_path)
        result = driver.parse_file(csv_file)

        assert result["metadata"]["Instrument"] == "SpectraMax"
        assert result["metadata"]["Date"] == "2026-01-15"
        assert result["wells"]["A1"] == pytest.approx(0.1)
        assert result["wells"]["A12"] == pytest.approx(1.2)
        assert result["wells"]["B1"] == pytest.approx(0.21)
        assert len(result["wells"]) == 24  # 2 rows * 12 cols

    def test_parse_missing_wells(self, tmp_path: Path) -> None:
        """Rows with fewer than 12 values should parse only available columns."""
        csv_content = "A,0.1,0.2,0.3\n"
        csv_file = self._write_plate_csv(tmp_path, csv_content)
        driver = PlateReaderCSVDriver("pr-2", "plate_reader", tmp_path)
        result = driver.parse_file(csv_file)

        assert len(result["wells"]) == 3
        assert "A1" in result["wells"]
        assert "A4" not in result["wells"]

    def test_parse_non_numeric_values(self, tmp_path: Path) -> None:
        """Non-numeric values should be stored as strings."""
        csv_content = "A,0.1,N/A,ERR,0.4,0.5,0.6,0.7,0.8,0.9,1.0,1.1,1.2\n"
        csv_file = self._write_plate_csv(tmp_path, csv_content)
        driver = PlateReaderCSVDriver("pr-3", "plate_reader", tmp_path)
        result = driver.parse_file(csv_file)

        assert result["wells"]["A1"] == pytest.approx(0.1)
        assert result["wells"]["A2"] == "N/A"
        assert result["wells"]["A3"] == "ERR"

    def test_parse_lowercase_row_letters(self, tmp_path: Path) -> None:
        csv_content = "a,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0,1.1,1.2\n"
        csv_file = self._write_plate_csv(tmp_path, csv_content)
        driver = PlateReaderCSVDriver("pr-4", "plate_reader", tmp_path)
        result = driver.parse_file(csv_file)

        assert "A1" in result["wells"]

    def test_empty_csv(self, tmp_path: Path) -> None:
        csv_file = self._write_plate_csv(tmp_path, "")
        driver = PlateReaderCSVDriver("pr-5", "plate_reader", tmp_path)
        result = driver.parse_file(csv_file)
        assert result["wells"] == {}
        assert result["metadata"] == {}

    def test_file_path_in_result(self, tmp_path: Path) -> None:
        row_data = "A,1.0,2.0,3.0,4.0,5.0,6.0,7.0,8.0,9.0,10.0,11.0,12.0\n"
        csv_file = self._write_plate_csv(tmp_path, row_data)
        driver = PlateReaderCSVDriver("pr-6", "plate_reader", tmp_path)
        result = driver.parse_file(csv_file)
        assert result["file"] == str(csv_file)


# ---------------------------------------------------------------------------
# QPCRExportDriver
# ---------------------------------------------------------------------------


class TestQPCRExport:
    def _write_qpcr_file(self, path: Path, content: str, ext: str = ".txt") -> Path:
        f = path / f"qpcr{ext}"
        f.write_text(content, encoding="utf-8")
        return f

    def test_parse_standard_tsv(self, tmp_path: Path) -> None:
        content = (
            "Experiment Name\tMyExperiment\n"
            "Operator\tJohn\n"
            "\n"
            "Well\tSample Name\tDetector Name\tCt\n"
            "A1\tSample1\tGAPDH\t22.4\n"
            "A2\tSample2\tGAPDH\t23.1\n"
            "B1\tSample1\tACTB\t18.7\n"
        )
        qpcr_file = self._write_qpcr_file(tmp_path, content)
        driver = QPCRExportDriver("qpcr-1", "qpcr", tmp_path)
        result = driver.parse_file(qpcr_file)

        assert result["metadata"]["Experiment Name"] == "MyExperiment"
        assert result["metadata"]["Operator"] == "John"
        assert len(result["samples"]) == 3
        assert result["samples"][0]["well"] == "A1"
        assert result["samples"][0]["ct"] == pytest.approx(22.4)
        assert result["samples"][0]["detector"] == "GAPDH"

    def test_parse_csv_format(self, tmp_path: Path) -> None:
        content = (
            "Experiment Name,MyExperiment\n"
            "Well,Sample Name,Detector Name,Ct\n"
            "A1,Sample1,GAPDH,22.4\n"
        )
        qpcr_file = self._write_qpcr_file(tmp_path, content, ext=".csv")
        driver = QPCRExportDriver("qpcr-2", "qpcr", tmp_path)
        result = driver.parse_file(qpcr_file)

        assert len(result["samples"]) == 1
        assert result["samples"][0]["ct"] == pytest.approx(22.4)

    def test_undetermined_ct(self, tmp_path: Path) -> None:
        content = "Well\tSample Name\tCt\nA1\tSample1\tUndetermined\nA2\tSample2\tN/A\n"
        qpcr_file = self._write_qpcr_file(tmp_path, content)
        driver = QPCRExportDriver("qpcr-3", "qpcr", tmp_path)
        result = driver.parse_file(qpcr_file)

        assert result["samples"][0]["ct"] == "Undetermined"
        assert result["samples"][1]["ct"] == "N/A"

    def test_alternative_column_names(self, tmp_path: Path) -> None:
        """Test with 'Well Position' and 'Cycle Threshold' columns."""
        content = "Well Position\tSample\tTarget Name\tCycle Threshold\nA1\tCtrl\tGAPDH\t20.0\n"
        qpcr_file = self._write_qpcr_file(tmp_path, content)
        driver = QPCRExportDriver("qpcr-4", "qpcr", tmp_path)
        result = driver.parse_file(qpcr_file)

        assert len(result["samples"]) == 1
        assert result["samples"][0]["well"] == "A1"
        assert result["samples"][0]["ct"] == pytest.approx(20.0)

    def test_empty_file(self, tmp_path: Path) -> None:
        qpcr_file = self._write_qpcr_file(tmp_path, "")
        driver = QPCRExportDriver("qpcr-5", "qpcr", tmp_path)
        result = driver.parse_file(qpcr_file)
        assert result["samples"] == []
        assert result["metadata"] == {}

    def test_blank_line_ends_results(self, tmp_path: Path) -> None:
        content = (
            "Well\tSample Name\tCt\n"
            "A1\tSample1\t22.0\n"
            "\n"
            "A2\tSample2\t23.0\n"  # Should NOT be parsed (after blank line)
        )
        qpcr_file = self._write_qpcr_file(tmp_path, content)
        driver = QPCRExportDriver("qpcr-6", "qpcr", tmp_path)
        result = driver.parse_file(qpcr_file)
        assert len(result["samples"]) == 1


class TestFindCol:
    def test_finds_matching_column(self) -> None:
        header = ["Name", "Well", "Ct"]
        assert _find_col(header, {"well"}) == 1

    def test_case_insensitive(self) -> None:
        header = ["Name", "WELL POSITION", "Ct"]
        assert _find_col(header, {"well position"}) == 1

    def test_no_match(self) -> None:
        header = ["Name", "Value"]
        assert _find_col(header, {"well"}) is None


# ---------------------------------------------------------------------------
# FileWatcherDriver
# ---------------------------------------------------------------------------


class TestFileWatcherDriver:
    def test_initialization(self, tmp_path: Path) -> None:
        from labclaw.hardware.drivers.file_watcher import FileWatcherDriver

        driver = FileWatcherDriver("fw-1", "watcher", tmp_path)
        assert driver.device_id == "fw-1"
        assert driver.device_type == "watcher"

    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self, tmp_path: Path) -> None:
        from labclaw.hardware.drivers.file_watcher import FileWatcherDriver

        driver = FileWatcherDriver("fw-2", "watcher", tmp_path)
        ok = await driver.connect()
        assert ok is True

        status = await driver.status()
        assert status == DeviceStatus.ONLINE

        await driver.disconnect()
        status = await driver.status()
        assert status == DeviceStatus.OFFLINE

    @pytest.mark.asyncio
    async def test_connect_nonexistent_path(self, tmp_path: Path) -> None:
        from labclaw.hardware.drivers.file_watcher import FileWatcherDriver

        driver = FileWatcherDriver("fw-3", "watcher", tmp_path / "nonexistent")
        ok = await driver.connect()
        assert ok is False

    @pytest.mark.asyncio
    async def test_read_without_connect(self, tmp_path: Path) -> None:
        from labclaw.hardware.drivers.file_watcher import FileWatcherDriver

        driver = FileWatcherDriver("fw-4", "watcher", tmp_path)
        result = await driver.read()
        assert result["new_files"] == []
        assert result["data"] is None


# ---------------------------------------------------------------------------
# FileBasedDriver (base class)
# ---------------------------------------------------------------------------


class TestFileBasedDriver:
    @pytest.mark.asyncio
    async def test_connect_valid_path(self, tmp_path: Path) -> None:
        driver = FileBasedDriver("fb-1", "generic", tmp_path)
        ok = await driver.connect()
        assert ok is True

    @pytest.mark.asyncio
    async def test_connect_nonexistent_path(self, tmp_path: Path) -> None:
        driver = FileBasedDriver("fb-2", "generic", tmp_path / "missing")
        ok = await driver.connect()
        assert ok is False

    @pytest.mark.asyncio
    async def test_connect_file_not_dir(self, tmp_path: Path) -> None:
        f = tmp_path / "file.txt"
        f.write_text("hello")
        driver = FileBasedDriver("fb-3", "generic", f)
        ok = await driver.connect()
        assert ok is False

    @pytest.mark.asyncio
    async def test_disconnect(self, tmp_path: Path) -> None:
        driver = FileBasedDriver("fb-4", "generic", tmp_path)
        await driver.connect()
        await driver.disconnect()
        status = await driver.status()
        assert status == DeviceStatus.OFFLINE

    @pytest.mark.asyncio
    async def test_read_detects_new_files(self, tmp_path: Path) -> None:
        driver = FileBasedDriver("fb-5", "generic", tmp_path, ["*.csv"])
        await driver.connect()

        # Create a new file after connect
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("col1,col2\nval1,val2\n", encoding="utf-8")

        result = await driver.read()
        assert len(result["new_files"]) == 1
        assert result["data"] is not None
        assert result["data"]["row_count"] == 1

    @pytest.mark.asyncio
    async def test_read_no_new_files(self, tmp_path: Path) -> None:
        # Create file before connect
        csv_file = tmp_path / "existing.csv"
        csv_file.write_text("col1\nval1\n", encoding="utf-8")

        driver = FileBasedDriver("fb-6", "generic", tmp_path, ["*.csv"])
        await driver.connect()

        result = await driver.read()
        assert result["new_files"] == []
        assert result["data"] is None

    @pytest.mark.asyncio
    async def test_write_returns_false(self, tmp_path: Path) -> None:
        from labclaw.hardware.schemas import HardwareCommand

        driver = FileBasedDriver("fb-7", "generic", tmp_path)
        cmd = HardwareCommand(device_id="fb-7", action="start")
        result = await driver.write(cmd)
        assert result is False

    @pytest.mark.asyncio
    async def test_status_online_when_connected(self, tmp_path: Path) -> None:
        driver = FileBasedDriver("fb-8", "generic", tmp_path)
        await driver.connect()
        status = await driver.status()
        assert status == DeviceStatus.ONLINE

    @pytest.mark.asyncio
    async def test_status_offline_when_not_connected(self, tmp_path: Path) -> None:
        driver = FileBasedDriver("fb-9", "generic", tmp_path)
        status = await driver.status()
        assert status == DeviceStatus.OFFLINE

    def test_parse_csv_default(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("name,value\nAlice,42\nBob,99\n", encoding="utf-8")
        driver = FileBasedDriver("fb-10", "generic", tmp_path)
        result = driver.parse_file(csv_file)
        assert result["row_count"] == 2
        assert result["rows"][0]["name"] == "Alice"
        assert result["rows"][0]["value"] == "42"

    def test_parse_tsv_default(self, tmp_path: Path) -> None:
        tsv_file = tmp_path / "test.tsv"
        tsv_file.write_text("name\tvalue\nAlice\t42\n", encoding="utf-8")
        driver = FileBasedDriver("fb-11", "generic", tmp_path)
        result = driver.parse_file(tsv_file)
        assert result["row_count"] == 1
        assert result["rows"][0]["name"] == "Alice"

    def test_device_properties(self, tmp_path: Path) -> None:
        driver = FileBasedDriver("fb-12", "camera", tmp_path)
        assert driver.device_id == "fb-12"
        assert driver.device_type == "camera"

    def test_default_file_patterns(self, tmp_path: Path) -> None:
        driver = FileBasedDriver("fb-13", "generic", tmp_path)
        assert driver._file_patterns == ["*.csv", "*.tsv"]

    def test_custom_file_patterns(self, tmp_path: Path) -> None:
        driver = FileBasedDriver("fb-14", "generic", tmp_path, ["*.tiff"])
        assert driver._file_patterns == ["*.tiff"]
