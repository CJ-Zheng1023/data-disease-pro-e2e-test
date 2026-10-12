# -*- coding: utf-8 -*-
"""修改密码模块测试用例。

覆盖点：
1. 弹窗结构：新密码 / 确认密码 / 关闭 / 确定；
2. 密码强度提示气泡（5 条安全策略实时校验）；
3. 弱密码提交：提示“不符合密码安全策略”（不修改密码）；
4. 两次密码不一致：提示“两次输入密码不一致”（不修改密码）；
5. 完整修改闭环：原密码 → 新密码（验证新密码可登录）→ 恢复原密码
   （验证原密码可登录）。

数据保护说明（重要）：
- 测试账号的初始密码可能是历史遗留的弱密码（不满足现行安全策略），
  因此 **无法通过界面把密码改回初始值**——界面校验会拦截弱密码。
  ``password_restorer`` 夹具在用例结束（含失败/异常）后，
  通过“接口 + RSA 加密”方式把密码恢复为初始值（详见 src/utils/password_tools.py）；
- 为规避真实账号安全锁定策略，用例中不执行“故意用错误密码登录”的探针。

注意：本文件用例均标记 ``no_auth``，自行完成登录步骤。
"""

from __future__ import annotations

import allure
import pytest
from playwright.sync_api import Browser, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from config.constants import (
    MSG_PASSWORD_MISMATCH,
    MSG_PASSWORD_POLICY,
    NEW_PASSWORD,
    PASSWORD_STRATEGY_HINTS,
    WEAK_PASSWORD,
)
from config.settings import settings
from src.common.logger import get_logger
from src.pages.layout_page import LayoutHeader
from src.pages.login_page import LoginPage
from src.pages.password_modal import PasswordModal
from src.utils.password_tools import reset_password_via_api

logger = get_logger(__name__)

pytestmark = [pytest.mark.no_auth, allure.feature("修改密码")]


# ======================================================================== #
# 数据保护夹具
# ======================================================================== #
def _try_login(page: Page, password: str, timeout: int = 20_000) -> bool:
    """尝试使用指定密码登录，返回是否成功（用于密码恢复流程）。"""
    login_page = LoginPage(page)
    login_page.open()
    login_page.fill_form(settings.username, password)
    login_page.click_login()
    try:
        page.wait_for_function("() => !location.pathname.startsWith('/login')", timeout=timeout)
        return True
    except PlaywrightTimeoutError:
        return False


@pytest.fixture
def password_restorer(browser: Browser):
    """密码恢复守卫：用例显式标记 changed 后，结束时兜底恢复初始密码。

    恢复流程：
    1. 用“新密码”登录（若成功，说明修改生效中）；
    2. 调用修改密码接口（RSA 加密，绕过前端弱密码策略）恢复初始密码；
    3. 用初始密码重新登录验证；两步都失败则显式报错提醒人工介入。
    """
    state = {"changed": False}
    yield state

    if not state["changed"]:
        return

    logger.warning("检测到密码已被修改，开始执行密码恢复流程……")
    context = browser.new_context(
        viewport={"width": settings.viewport_width, "height": settings.viewport_height},
        locale="zh-CN",
    )
    page = context.new_page()
    try:
        if _try_login(page, NEW_PASSWORD):
            reset_password_via_api(page, settings.password)
        if not _try_login(page, settings.password):
            raise RuntimeError("密码恢复失败：无法使用初始密码登录，请人工检查账号状态！")
        logger.warning("密码已恢复为初始密码并通过登录验证")
    finally:
        context.close()


# ======================================================================== #
# 用例
# ======================================================================== #
@allure.story("修改密码弹窗")
class TestPasswordModal:
    """弹窗结构与前端校验（不触发真实修改）。"""

    @allure.title("修改密码弹窗：结构与密码强度提示")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_modal_structure_and_strength_hints(self, page: Page, login_page: LoginPage) -> None:
        login_page.login_successfully()
        modal: PasswordModal = LayoutHeader(page).open_password_modal()

        with allure.step("校验弹窗结构"):
            assert modal.new_password_input.is_visible()
            assert modal.confirm_password_input.is_visible()
            assert modal.ok_button.is_visible()
            assert modal.close_button.is_visible()

        with allure.step("聚焦新密码输入框，校验 5 条安全策略提示"):
            modal.focus_new_password()
            hints = modal.strategy_hint_texts()
            for expected in PASSWORD_STRATEGY_HINTS:
                assert expected in hints, f"密码强度提示缺少：{expected}"

        modal.close()

    @allure.title("弱密码提交：提示不符合密码安全策略")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_weak_password_rejected(self, page: Page, login_page: LoginPage) -> None:
        login_page.login_successfully()
        modal = LayoutHeader(page).open_password_modal()

        with allure.step(f"提交不满足策略的密码：{WEAK_PASSWORD}"):
            modal.fill(WEAK_PASSWORD, WEAK_PASSWORD)
            modal.submit()
            page.wait_for_function(
                "(msg) => document.body.innerText.includes(msg)",
                arg=MSG_PASSWORD_POLICY,
            )
            assert MSG_PASSWORD_POLICY in modal.form_feedback()

        with allure.step("弹窗保持打开（修改未提交）"):
            assert modal.ok_button.is_visible()
        modal.close()

    @allure.title("两次输入不一致：提示两次输入密码不一致")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_password_mismatch_rejected(self, page: Page, login_page: LoginPage) -> None:
        login_page.login_successfully()
        modal = LayoutHeader(page).open_password_modal()

        with allure.step("提交不一致的确认密码"):
            modal.fill(NEW_PASSWORD, NEW_PASSWORD + "x")
            modal.submit()
            page.wait_for_function(
                "(msg) => document.body.innerText.includes(msg)",
                arg=MSG_PASSWORD_MISMATCH,
            )
            assert MSG_PASSWORD_MISMATCH in modal.form_feedback()

        modal.close()


@allure.story("修改密码闭环")
class TestPasswordChangeCycle:
    """真实修改密码并恢复（核心链路）。"""

    @allure.title("修改密码闭环：新密码生效并恢复初始密码成功")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.smoke
    def test_change_password_and_restore(self, page: Page, login_page: LoginPage, password_restorer) -> None:
        # ---------------- 第 1 步：使用初始密码登录 ---------------- #
        login_page.login_successfully()

        # ---------------- 第 2 步：修改为强密码（界面操作） ---------------- #
        with allure.step("通过用户下拉打开修改密码弹窗并提交新密码"):
            modal = LayoutHeader(page).open_password_modal()
            modal.fill(NEW_PASSWORD, NEW_PASSWORD)
            modal.submit()
            modal.wait_closed()
            password_restorer["changed"] = True

        # ---------------- 第 3 步：退出并使用新密码重新登录（验证生效） ---------------- #
        with allure.step("退出登录并使用新密码重新登录"):
            LayoutHeader(page).logout()
            assert _try_login(page, NEW_PASSWORD), "修改密码后应能使用新密码登录"
            logger.info("新密码登录成功")

        # ---------------- 第 4 步：通过接口恢复初始密码（界面不允许弱密码） ---------------- #
        with allure.step("通过接口恢复初始密码并验证登录"):
            reset_password_via_api(page, settings.password)
            password_restorer["changed"] = False  # 已恢复，关闭守卫

            LayoutHeader(page).logout()
            assert _try_login(page, settings.password), "恢复后应能使用初始密码登录"

        with allure.step("校验登录态与用户信息正常"):
            user_info = LoginPage(page).read_local_user_info()
            assert user_info.get("token"), "登录后本地应保存 token"
