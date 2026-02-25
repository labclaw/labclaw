"""Unit tests for labclaw.logging_config — JSON formatter and configure_logging."""

from __future__ import annotations

import json
import logging

from labclaw.logging_config import JSONFormatter, configure_logging


class TestJSONFormatter:
    def _make_record(
        self,
        message: str = "hello",
        level: int = logging.INFO,
        name: str = "test.logger",
        exc_info: tuple | None = None,
        extra_data: object | None = None,
    ) -> logging.LogRecord:
        record = logging.LogRecord(
            name=name,
            level=level,
            pathname="",
            lineno=0,
            msg=message,
            args=(),
            exc_info=exc_info,
        )
        if extra_data is not None:
            record.extra_data = extra_data  # type: ignore[attr-defined]
        return record

    def test_output_is_valid_json(self) -> None:
        formatter = JSONFormatter()
        record = self._make_record()
        output = formatter.format(record)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_contains_required_keys(self) -> None:
        formatter = JSONFormatter()
        record = self._make_record("test message")
        parsed = json.loads(formatter.format(record))
        assert "timestamp" in parsed
        assert "level" in parsed
        assert "logger" in parsed
        assert "message" in parsed

    def test_message_content(self) -> None:
        formatter = JSONFormatter()
        record = self._make_record("specific message here")
        parsed = json.loads(formatter.format(record))
        assert parsed["message"] == "specific message here"

    def test_level_name(self) -> None:
        formatter = JSONFormatter()
        record = self._make_record(level=logging.WARNING)
        parsed = json.loads(formatter.format(record))
        assert parsed["level"] == "WARNING"

    def test_logger_name(self) -> None:
        formatter = JSONFormatter()
        record = self._make_record(name="labclaw.core")
        parsed = json.loads(formatter.format(record))
        assert parsed["logger"] == "labclaw.core"

    def test_timestamp_is_iso8601(self) -> None:
        from datetime import datetime

        formatter = JSONFormatter()
        record = self._make_record()
        parsed = json.loads(formatter.format(record))
        # Should not raise
        datetime.fromisoformat(parsed["timestamp"])

    def test_no_exception_key_when_no_exc(self) -> None:
        formatter = JSONFormatter()
        record = self._make_record()
        parsed = json.loads(formatter.format(record))
        assert "exception" not in parsed

    def test_exception_included_when_exc_info(self) -> None:
        formatter = JSONFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            exc_info = sys.exc_info()
        record = self._make_record(exc_info=exc_info)
        parsed = json.loads(formatter.format(record))
        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]

    def test_extra_data_included(self) -> None:
        formatter = JSONFormatter()
        record = self._make_record(extra_data={"key": "value", "count": 3})
        parsed = json.loads(formatter.format(record))
        assert "data" in parsed
        assert parsed["data"]["key"] == "value"

    def test_no_data_key_when_no_extra_data(self) -> None:
        formatter = JSONFormatter()
        record = self._make_record()
        parsed = json.loads(formatter.format(record))
        assert "data" not in parsed

    def test_exc_info_none_tuple_not_included(self) -> None:
        """exc_info=(None, None, None) should NOT add exception key."""
        formatter = JSONFormatter()
        record = self._make_record(exc_info=(None, None, None))
        parsed = json.loads(formatter.format(record))
        assert "exception" not in parsed


class TestConfigureLogging:
    def test_configure_json_output_attaches_json_formatter(self) -> None:
        configure_logging(level="DEBUG", json_output=True)
        root = logging.getLogger()
        assert any(isinstance(h.formatter, JSONFormatter) for h in root.handlers)

    def test_configure_plain_output_uses_plain_formatter(self) -> None:
        configure_logging(level="INFO", json_output=False)
        root = logging.getLogger()
        assert not any(isinstance(h.formatter, JSONFormatter) for h in root.handlers)

    def test_level_is_set(self) -> None:
        configure_logging(level="WARNING")
        assert logging.getLogger().level == logging.WARNING

    def test_debug_level_is_set(self) -> None:
        configure_logging(level="DEBUG")
        assert logging.getLogger().level == logging.DEBUG

    def test_repeated_configure_does_not_duplicate_handlers(self) -> None:
        configure_logging(level="INFO")
        count_before = len(logging.getLogger().handlers)
        configure_logging(level="INFO")
        count_after = len(logging.getLogger().handlers)
        assert count_after == count_before

    def test_default_args(self) -> None:
        """configure_logging() with defaults should not raise."""
        configure_logging()
        root = logging.getLogger()
        assert root.level == logging.INFO
