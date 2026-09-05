"""Structured logging setup.

Uses stdlib logging with a JSON-ish formatter so logs are greppable and can be
shipped to any log aggregator without code changes. Every request gets a
request_id (see main.py middleware) that is threaded through log lines to make
diagnosing a single conversation turn possible.
"""
import logging
import sys
import time


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {
            "ts": round(time.time(), 3),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("request_id", "session_id", "provider", "event"):
            if hasattr(record, key):
                base[key] = getattr(record, key)
        if record.exc_info:
            base["exc_info"] = self.formatException(record.exc_info)
        return " ".join(f"{k}={v!r}" for k, v in base.items())


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    # Quiet noisy libraries down to WARNING unless debugging.
    for noisy in ("httpx", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel("WARNING")
