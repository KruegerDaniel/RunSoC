import logging
import os
import sys
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

try:
    from flask import has_request_context, request, g
except ImportError:
    has_request_context = None
    request = None
    g = None

class WeekRetentionTimedRotatingFileHandler(TimedRotatingFileHandler):

    def __init__(self, *args, max_age_days: int = 5, **kwargs):
        self.max_age_days = max_age_days
        super().__init__(*args, **kwargs)

    def doRollover(self):
        super().doRollover()
        self.delete_old_logs()

    def delete_old_logs(self):
        cuttoff = datetime.now() - timedelta(days=self.max_age_days)
        log_path = Path(self.baseFilename)
        log_dir = log_path.parent
        log_prefix = log_path.name

        for file_path in log_dir.glob(f"{log_prefix}.*"):
            try:
                modified_at = datetime.fromtimestamp(file_path.stat().st_mtime)
                if modified_at < cuttoff:
                    file_path.unlink()
            except OSError:
                pass

class RequestContextFilter(logging.Filter):

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = "-"
        record.remote_addr = "-"
        record.method = "-"
        record.path = "-"

        if has_request_context and has_request_context():
            record.request_id = getattr(g, "request_id", "-")
            record.remote_addr = request.headers.get(
                "X-Forwarded-For",
                request.remote_addr or "-",
            )
            record.method = request.method
            record.path = request.path

        return True

def configure_logging(
        app=None,
        *,
        log_dir: str = "logs",
        log_file: str = "app.log",
        level: str | int |None = None,
        max_age_days: int = 5,
) -> logging.Logger:
    resolved_level = level or os.getenv("LOG_LEVEL", "INFO")

    if isinstance(resolved_level, str):
        resolved_level = resolved_level.upper()

    Path(log_dir).mkdir(parents=True, exist_ok=True)
    file_path = os.path.join(log_dir, log_file)

    formatter = logging.Formatter(
        fmt=(
            "%(asctime)s | %(levelname)s | %(name)s | "
            "%(method)s %(path)s | request_id=%(request_id)s | "
            "remote_addr=%(remote_addr)s | %(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    request_filter = RequestContextFilter()

    file_handler = WeekRetentionTimedRotatingFileHandler(
        filename=file_path,
        when="midnight",
        interval=1,
        backupCount=0,
        encoding="utf-8",
        utc=True,
        max_age_days=max_age_days,
    )

    file_handler.setFormatter(formatter)
    file_handler.addFilter(request_filter)
    file_handler.setLevel(resolved_level)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(resolved_level)
    console_handler.addFilter(request_filter)

    root_logger = logging.getLogger()
    root_logger.setLevel(resolved_level)

    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    if app is not None:
        app.logger.handlers.clear()
        app.logger.propagate = False
        app.logger.setLevel(resolved_level)

    return logging.getLogger(__name__)
