from __future__ import annotations

import json
import logging

import pytest
import structlog.contextvars
from pythonjsonlogger.jsonlogger import JsonFormatter

from ..logging import StructlogContextFilter


def _record(msg: str = "hello") -> logging.LogRecord:
    return logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg=msg, args=(), exc_info=None)


class TestStructlogContextFilter:
    def test_injects_context_vars_into_record(self) -> None:
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id="req-123", user_id="user-456", branch_id="branch-789")
        record = _record()
        StructlogContextFilter().filter(record)
        assert (record.request_id, record.user_id, record.branch_id) == ("req-123", "user-456", "branch-789")

    def test_uses_empty_string_when_context_missing(self) -> None:
        structlog.contextvars.clear_contextvars()
        record = _record()
        StructlogContextFilter().filter(record)
        assert (record.request_id, record.user_id, record.branch_id) == ("", "", "")


class TestJsonFormatter:
    def test_outputs_valid_json(self) -> None:
        formatter = JsonFormatter("%(asctime)s %(levelname)s %(name)s %(request_id)s %(message)s")
        record = _record("event")
        record.request_id = "req-abc"
        parsed = json.loads(formatter.format(record))
        assert parsed["levelname"] == "INFO"
        assert parsed["name"] == "test"
        assert parsed["request_id"] == "req-abc"
        assert parsed["message"] == "event"
        assert "asctime" in parsed
