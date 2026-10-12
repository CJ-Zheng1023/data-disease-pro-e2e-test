# -*- coding: utf-8 -*-
"""退出登录模块测试用例。

覆盖点：
1. 用户下拉包含“修改密码 / 退出登录”入口；
2. 退出登录后回到登录页，且本地登录态被清除；
3. 退出后访问受保护路由会被重定向回登录页（路由守卫）；
4. 未登录状态访问任意业务路由均重定向登录页。

注意：本文件用例均标记 ``no_auth``，自行完成登录步骤。
"""

from __future__ import annotations

import allure
import pytest
from playwright.sync_api import Page
from playwright.sync_api import expect

from config.settings import settings
from src.pages.layout_page import LayoutHeader
from src.pages.login_page import LoginPage

pytestmark = [pytest.mark.no_auth, allure.feature("退出登录")]


@allure.story("退出登录")
class TestLogout:
    """退出登录链路。"""

    @allure.title("退出登录：跳转登录页并清除本地登录态")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.smoke
    def test_logout_from_dropdown(self, page: Page, login_page: LoginPage) -> None:
        login_page.login_successfully()
        layout = LayoutHeader(page)

        with allure.step("展开用户下拉，校验入口完整"):
            layout.open_user_dropdown()
            dropdown_text = layout.user_dropdown.inner_text()
            assert "修改密码" in dropdown_text
            assert "退出登录" in dropdown_text

        with allure.step("点击退出登录"):
            layout.logout()
            expect(login_page.heading).to_be_visible()

        with allure.step("校验本地登录态已清除"):
            assert page.evaluate("() => localStorage.getItem('dmd-pro-userInfo')") is None

        with allure.step("校验退出后访问受保护路由被重定向回登录页"):
            page.goto(f"{settings.base_url.rstrip('/')}/database/list")
            page.wait_for_url("**/login")
            expect(login_page.login_button).to_be_visible()


@allure.story("路由守卫")
class TestRouteGuard:
    """未登录状态的路由拦截。"""

    @allure.title("未登录访问业务路由重定向登录页")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.parametrize(
        "path",
        ["/database/list", "/chat", "/annotation/list"],
        ids=["专病检索", "灵犀问答", "智能标注"],
    )
    def test_protected_routes_redirect(self, page: Page, path: str) -> None:
        """未登录时访问各业务模块路由，应统一重定向到登录页。"""
        with allure.step(f"未登录访问：{path}"):
            page.goto(f"{settings.base_url.rstrip('/')}{path}")
            page.wait_for_url("**/login")
        with allure.step("校验登录页展示"):
            assert "/login" in page.url
            expect(page.get_by_role("button", name="登录", exact=True)).to_be_visible()
