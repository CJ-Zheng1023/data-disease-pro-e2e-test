# -*- coding: utf-8 -*-
"""密码工具：RSA 加密与接口级密码恢复。

背景：平台前端对“修改密码”有安全策略校验（长度/大小写/数字/特殊字符），
而测试账号的初始密码可能是历史遗留的弱密码（如 ``123456``）。
因此当自动化用例把密码临时修改为强密码后，**无法再通过界面改回弱密码**，
必须调用同一套接口（RSA 加密提交）完成恢复，既绕开前端策略限制，
又保证与业务一致。

RSA 公钥与前端 ``src/utils/lib.ts`` 中的公钥保持一致（PKCS#1 v1.5）。
"""

from __future__ import annotations

import base64
from typing import cast

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from playwright.sync_api import Page

from config.settings import settings
from src.common.logger import get_logger

logger = get_logger(__name__)

# 与前端一致的 RSA 公钥（修改密码 / 登录共用）
PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDGxuxrtLtqPUSX47mCZjwGoNdG
E9sFsNu94qSI7uSu4dWzgfSZmEOpb6fRH8ZE/D0XOb1KcrXbmnhDY7uTtITuNxqR
qPzoSoAEKRPJbWITxy4nNAGRWg3e9NyhpO6Xu9p/5bkDRjggEV6Qs8mi+UQFodAB
G3dhp4ly7wPojy5rfwIDAQAB
-----END PUBLIC KEY-----"""

_PUBLIC_KEY = cast(RSAPublicKey, serialization.load_pem_public_key(PUBLIC_KEY_PEM.encode()))


def rsa_encrypt(plain_text: str) -> str:
    """RSA(PKCS#1 v1.5) 加密并返回 Base64 字符串（与前端 encryptByRSA 等价）。"""
    cipher = _PUBLIC_KEY.encrypt(plain_text.encode("utf-8"), padding.PKCS1v15())
    return base64.b64encode(cipher).decode()


def read_token(page: Page) -> str:
    """读取当前浏览器上下文中保存的登录 token。"""
    return page.evaluate(
        "() => { const raw = localStorage.getItem('dmd-pro-userInfo');"
        " return raw ? (JSON.parse(raw).value || {}).token || '' : ''; }"
    )


def reset_password_via_api(page: Page, target_password: str) -> None:
    """通过接口把当前登录用户的密码重置为 ``target_password``。

    前置条件：``page`` 所属上下文必须处于登录态（接口需要 token）。
    """
    token = read_token(page)
    if not token:
        raise AssertionError("未找到登录 token，无法执行接口密码恢复")
    response = page.request.post(
        settings.base_url.rstrip("/") + "/api/admin/user/password/reset",
        headers={"token": token},
        data={"password": rsa_encrypt(target_password)},
    )
    try:
        body = response.json()
    except Exception as exc:  # pragma: no cover - 服务异常时给出可读错误
        raise AssertionError(f"密码重置接口返回非 JSON：{response.text()[:200]}") from exc
    if body.get("code") != 200:
        raise AssertionError(f"密码重置接口业务失败：{body}")
    logger.warning("已通过接口将账号密码恢复为初始密码")
