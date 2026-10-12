# -*- coding: utf-8 -*-
"""全局环境与账号配置。

配置读取优先级（从高到低）：
1. 操作系统环境变量 / 命令行注入（例如：``set E2E_BASE_URL=...`` 后运行 pytest）；
2. 项目根目录下的 ``.env`` 文件（可选，便于本地保存个人配置，不纳入版本管理）；
3. 本文件中的默认值。

如此设计可以在不修改任何代码的情况下，把同一套用例切换到不同测试环境。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# --------------------------------------------------------------------------- #
# 目录定义
# --------------------------------------------------------------------------- #
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ALLURE_RESULTS_DIR = PROJECT_ROOT / "allure-results"      # Allure 原始结果
RUNTIME_DIR = PROJECT_ROOT / ".runtime"                   # 运行期缓存（登录态等）
STORAGE_STATE_FILE = RUNTIME_DIR / "storage_state.json"   # 复用登录态存储文件
LOG_DIR = PROJECT_ROOT / "logs"                           # 运行日志
SCREENSHOT_DIR = PROJECT_ROOT / "screenshots"             # 失败截图


def _load_dotenv() -> None:
    """极简 .env 加载器（避免额外依赖 python-dotenv）。

    仅解析 ``KEY=VALUE`` 形式，已存在于环境变量中的 KEY 不会被覆盖。
    """
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv()


def _env(key: str, default: str) -> str:
    return os.getenv(key, default)


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:  # 配置非法时回退默认值，避免整个测试进程启动失败
        return default


@dataclass(frozen=True)
class Settings:
    """测试运行期配置（进程启动时一次性读取）。"""

    # ---------------- 目标环境与账号（默认：开发联调环境） ---------------- #
    base_url: str = _env("E2E_BASE_URL", "http://10.13.37.154/")
    username: str = _env("E2E_USERNAME", "zhengchj1")
    password: str = _env("E2E_PASSWORD", "123456")

    # ---------------- 超时配置（单位：毫秒） ---------------- #
    default_timeout_ms: int = _env_int("E2E_DEFAULT_TIMEOUT_MS", 20_000)     # 元素等待
    navigation_timeout_ms: int = _env_int("E2E_NAV_TIMEOUT_MS", 60_000)     # 页面跳转
    ai_timeout_ms: int = _env_int("E2E_AI_TIMEOUT_MS", 120_000)             # AI 流式回答

    # ---------------- 浏览器视口 ---------------- #
    # 平台为桌面端布局，使用较大视口避免元素被折叠/截断。
    viewport_width: int = _env_int("E2E_VIEWPORT_WIDTH", 1920)
    viewport_height: int = _env_int("E2E_VIEWPORT_HEIGHT", 1080)


settings = Settings()
