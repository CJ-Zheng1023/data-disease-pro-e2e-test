# -*- coding: utf-8 -*-
"""统一日志能力。

- 控制台输出由 pytest.ini 的 log_cli 配置托管；
- 本模块额外提供按运行日期切分的文件日志，便于事后追溯失败用例的执行过程。
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime

from config.settings import LOG_DIR

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 文件日志句柄在进程内只初始化一次
_LOG_FILE_READY = False


def _ensure_file_handler() -> None:
    """惰性初始化文件日志（logs/run-yyyyMMdd.log）。"""
    global _LOG_FILE_READY
    if _LOG_FILE_READY:
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"run-{datetime.now():%Y%m%d}.log"

    root = logging.getLogger()
    # 避免重复运行时重复添加 handler
    if not any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", "") == str(log_file) for h in root.handlers):
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
        file_handler.setLevel(logging.DEBUG)
        root.addHandler(file_handler)

    # 控制台兜底（未通过 pytest 运行时也能看到日志）
    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in root.handlers):
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
        root.addHandler(stream_handler)

    root.setLevel(logging.INFO)
    _LOG_FILE_READY = True


def get_logger(name: str) -> logging.Logger:
    """获取带文件落盘能力的 logger。

    :param name: 通常传入 ``__name__``，日志中将体现模块来源。
    """
    _ensure_file_handler()
    return logging.getLogger(name)
