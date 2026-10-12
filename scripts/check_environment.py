# -*- coding: utf-8 -*-
"""环境自检脚本：验证测试运行后环境无残留（可重复执行）。"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]  # Windows 控制台中文输出

# 将项目根目录加入 sys.path，保证可导入 config / src 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright

from src.api.client import build_api_client
from src.utils.password_tools import rsa_encrypt


def main() -> None:
    with sync_playwright() as p:
        # 1) 账号密码可正常登录（原始密码）
        req = p.request.new_context()
        resp = req.post(
            "http://10.13.37.154/api/admin/user/login",
            data={"username": "zhengchj1", "password": rsa_encrypt("123456")},
        )
        body = resp.json()
        print("1) 原始密码登录:", body.get("code"), body.get("msg"))
        req.dispose()

        # 2) 会话残留检查
        client, ctx = build_api_client(p, r".runtime\storage_state.json")
        conversations = client.query_conversations()
        leftover_conversations = [c for c in conversations if "E2E-AUTO" in str(c.get("label"))]
        print(f"2) 会话总数: {len(conversations)}，含 E2E-AUTO 标识的残留: {len(leftover_conversations)}")

        # 3) 标注任务残留检查
        annotations = client.query_annotations(name="E2E-AUTO")
        leftover_annotations = [a for a in annotations if str(a.get("name", "")).startswith("E2E-AUTO")]
        print(f"3) 标注任务总数: {len(annotations)}，含 E2E-AUTO 标识的残留: {len(leftover_annotations)}")
        for a in leftover_annotations:
            print("   -", a.get("id"), a.get("name"))

        # 4) 课题残留检查
        researches = client.query_researches(name="E2E-AUTO")
        leftover_researches = [r for r in researches if str(r.get("name", "")).startswith("E2E-AUTO")]
        print(f"4) 课题总数: {len(researches)}，含 E2E-AUTO 标识的残留: {len(leftover_researches)}")
        for r in leftover_researches:
            print("   -", r.get("id"), r.get("name"))

        ctx.dispose()

        ok = (
            body.get("code") == 200
            and not leftover_conversations
            and not leftover_annotations
            and not leftover_researches
        )
        print("\n环境自检结果:", "通过 ✔" if ok else "存在残留 ✘")


if __name__ == "__main__":
    main()
