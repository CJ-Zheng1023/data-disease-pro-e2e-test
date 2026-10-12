# -*- coding: utf-8 -*-
"""登录模块测试用例。

覆盖点：
1. 登录页元素完整性与空表单校验（前端校验，不触发接口）；
2. 错误账号登录失败提示（使用不存在的账号，避免真实账号触发风控锁定）；
3. 正确账号登录成功并进入主框架、本地保存登录态；
4. 已登录用户访问 /login 自动跳转至首页（路由守卫）。

注意：本文件用例均标记 ``no_auth``，使用未登录的干净浏览器上下文。
"""

from __future__ import annotations

import allure
import pytest

from config.constants import MSG_REQUIRED_PASSWORD, MSG_REQUIRED_USERNAME
from config.settings import settings
from src.pages.login_page import LoginPage

pytestmark = allure.feature("登录")


@allure.story("登录页面")
@pytest.mark.no_auth
class TestLoginPage:
    """登录页基础交互与校验。"""

    @allure.title("登录页元素展示完整")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_login_page_render(self, login_page: LoginPage) -> None:
        """标题、用户名/密码输入框、登录按钮、版权信息均应展示。"""
        with allure.step("校验页面关键元素"):
            assert login_page.heading.is_visible()
            assert login_page.username_input.is_visible()
            assert login_page.password_input.is_visible()
            assert login_page.login_button.is_visible()
            assert login_page.copyright_text.is_visible()

    @allure.title("空表单点击登录提示必填校验")
    @allure.severity(allure.severity_level.NORMAL)
    def test_login_empty_form_validation(self, login_page: LoginPage) -> None:
        """用户名与密码均为空时，应分别提示“请输入用户名/请输入密码”。"""
        login_page.click_login()
        with allure.step("等待并校验两条必填提示"):
            login_page.page.wait_for_function(
                "(msgs) => msgs.every(m => document.body.innerText.includes(m))",
                arg=[MSG_REQUIRED_USERNAME, MSG_REQUIRED_PASSWORD],
            )
            feedback = login_page.form_feedback()
            assert MSG_REQUIRED_USERNAME in feedback
            assert MSG_REQUIRED_PASSWORD in feedback
        assert login_page.is_on_login_page(), "校验失败时不应离开登录页"

    @allure.title("仅填写用户名时提示密码必填")
    @allure.severity(allure.severity_level.NORMAL)
    def test_login_missing_password_validation(self, login_page: LoginPage) -> None:
        """填写用户名但不填密码时，仅提示密码必填。"""
        login_page.fill_form(settings.username, "")
        login_page.click_login()
        login_page.page.wait_for_function(
            "(msg) => document.body.innerText.includes(msg)",
            arg=MSG_REQUIRED_PASSWORD,
        )
        feedback = login_page.form_feedback()
        assert MSG_REQUIRED_PASSWORD in feedback
        assert MSG_REQUIRED_USERNAME not in feedback


@allure.story("账号认证")
@pytest.mark.no_auth
class TestLoginAuthentication:
    """登录成功 / 失败的真实接口校验。"""

    @allure.title("不存在的账号登录失败并提示错误")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_login_with_invalid_account(self, login_page: LoginPage) -> None:
        """使用不存在的用户名登录：提示“用户名或密码错误”，停留在登录页。

        说明：故意使用不存在的账号而不是“正确账号 + 错误密码”，
        避免反复试错触发真实账号的安全锁定策略。
        """
        login_page.submit("e2e_no_such_user", "WrongPass@123")
        with allure.step("校验错误提示与页面状态"):
            message = login_page.expect_login_error()
            assert "用户名或密码错误" in message
            assert login_page.is_on_login_page()

    @allure.title("正确账号登录成功并进入主框架")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.smoke
    def test_login_success(self, page, login_page: LoginPage) -> None:
        """正确账号密码登录：跳转业务页面、主框架渲染、登录态写入本地存储。"""
        login_page.login_successfully()
        with allure.step("校验主框架与用户信息"):
            assert "/login" not in page.url, f"登录成功后不应停留在登录页：{page.url}"
            user_info = login_page.read_local_user_info()
            assert user_info.get("token"), "登录成功后本地应保存 token"
            assert user_info.get("realName"), "登录成功后本地应保存用户姓名"
            assert login_page.page.locator(".nick-name").inner_text().strip() == user_info["realName"]


@allure.story("路由守卫")
class TestLoginGuard:
    """登录态与路由守卫行为。"""

    @allure.title("已登录访问登录页自动跳转首页")
    @allure.severity(allure.severity_level.NORMAL)
    def test_logined_user_visiting_login_redirects(self, page, layout) -> None:
        """携带登录态访问 /login 时，应被重定向到业务首页而非停留在登录页。"""
        page.goto(f"{settings.base_url.rstrip('/')}/login")
        with allure.step("等待重定向完成"):
            page.wait_for_function("() => !location.pathname.startsWith('/login')")
            layout.wait_ready()
        assert "/login" not in page.url
