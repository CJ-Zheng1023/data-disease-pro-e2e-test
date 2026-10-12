# -*- coding: utf-8 -*-
"""测试数据工厂。

所有用例创建的测试数据统一由本模块生成，保证：

1. **可识别**：名称必含 :data:`config.constants.TEST_DATA_MARKER`（``E2E-AUTO``），
   人工或自动化都能一眼区分“测试数据”与真实业务数据；
2. **唯一**：名称追加时间戳 + 随机后缀，支持并发运行、历史残留排查；
3. **可清理**：清理逻辑依据统一标识精确删除，绝不影响存量数据。
"""

from __future__ import annotations

import random
import string
from datetime import datetime

from config.constants import TEST_DATA_MARKER


def random_suffix(length: int = 4) -> str:
    """生成小写字母+数字的随机后缀。"""
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choices(alphabet, k=length))


def build_test_name(base: str, *, with_marker: bool = True, max_length: int | None = None) -> str:
    """生成带统一标识的唯一测试数据名称。

    :param base: 业务含义，例如 ``标注任务``、``会话``；
    :param with_marker: 是否携带统一测试标识（默认携带）；
    :param max_length: 名称长度上限（与页面输入框 maxlength 对齐），
        超长时自动切换更紧凑的时间戳格式并压缩 base。

    形如：``E2E-AUTO_标注任务_20261010-153012-ab12``
    """
    prefix = f"{TEST_DATA_MARKER}_" if with_marker else ""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"{prefix}{base}_{timestamp}-{random_suffix()}"
    if max_length is None or len(name) <= max_length:
        return name

    # 超长时使用紧凑时间戳（年份仅保留后两位），并逐步压缩 base
    compact_timestamp = datetime.now().strftime("%y%m%d%H%M%S")
    while True:
        name = f"{prefix}{base}_{compact_timestamp}-{random_suffix()}"
        if len(name) <= max_length or len(base) <= 1:
            return name[:max_length]
        base = base[:-1]


def build_test_message(base: str = "你好") -> str:
    """生成带统一标识的聊天消息文本，供会话内容断言与数据清理识别。"""
    return f"[{TEST_DATA_MARKER}] {base} {random_suffix(6)}"
