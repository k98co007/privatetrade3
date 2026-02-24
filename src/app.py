from __future__ import annotations

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from uag.bootstrap import create_app


def _configure_logging() -> None:
    level_name = os.getenv("UAG_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    log_dir = Path("runtime") / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "uag.log"

    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    has_stream = any(isinstance(handler, logging.StreamHandler) for handler in root_logger.handlers)
    if not has_stream:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(level)
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)

    has_daily_file = any(
        isinstance(handler, TimedRotatingFileHandler) and getattr(handler, "baseFilename", "") == str(log_path.resolve())
        for handler in root_logger.handlers
    )
    if not has_daily_file:
        file_handler = TimedRotatingFileHandler(
            filename=log_path,
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        file_handler.suffix = "%Y-%m-%d"
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


_configure_logging()

app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)