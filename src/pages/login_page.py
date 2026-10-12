# -*- coding: utf-8 -*-
"""登录页对象（/login）。"""

from __future__ import annotations

import allure
from playwright.sync_api import Locator
from playwright.sync_api import expect

from config.constants import MSG_LOGIN_ERROR, MSG_REQUIRED_PASSWORD, MSG_REQUIRED_USERNAME, ROUTE_LOGIN
from config.settings import settings
from src.common.base_page import BasePage
from src.common.logger import get_logger

logger = get_logger(__name__)


class LoginPage(BasePage):
    """登录页。

    页面元素（naive-ui 组件渲染结果）：

    - 标题：``专病数据科研平台``；
    - 用户名输入框占位符：``请输入用户名``；
    - 密码输入框占位符：``请输入密码``；
    - 登录按钮：``登录``。

    注意：前端会对密码做 RSA 加密后再提交，加密过程发生在浏览器内，
    因此用例只需填写明文密码并点击登录，无需关心加密细节。
    """

    path = ROUTE_LOGIN

    # ------------------------------------------------------------------ #
    # 定位器
    # ------------------------------------------------------------------ #
    @property
    def heading(self) -> Locator:
        """页面主标题。"""
        return self.page.get_by_role("heading", name="专病数据科研平台")

    @property
    def username_input(self) -> Locator:
        return self.page.get_by_placeholder("请输入用户名")

    @property
    def password_input(self) -> Locator:
        return self.page.get_by_placeholder("请输入密码")

    @property
    def login_button(self) -> Locator:
        return self.page.get_by_role("button", name="登录", exact=True)

    @property
    def copyright_text(self) -> Locator:
        return self.page.get_by_text("以数据赋能科研")

    # ------------------------------------------------------------------ #
    # 操作
    # ------------------------------------------------------------------ #
    def open(self) -> "LoginPage":
        self.goto(self.path)
        self.wait_page_ready()
        return self

    def wait_page_ready(self) -> "LoginPage":
        """等待登录页渲染完成。"""
        expect(self.heading).to_be_visible()
        expect(self.login_button).to_be_visible()
        return self

    @allure.step("填写登录表单：{username}")
    def fill_form(self, username: str, password: str) -> "LoginPage":
        """填写用户名与密码（允许空串，用于必填校验用例）。"""
        self.username_input.fill(username)
        self.password_input.fill(password)
        return self

    @allure.step("点击登录按钮")
    def click_login(self) -> None:
        self.login_button.click()

    def submit(self, username: str, password: str) -> None:
        """填写表单并提交（不等待结果，供负向用例自行断言）。"""
        self.fill_form(username, password)
        self.click_login()

    @allure.step("使用账号 {username} 登录成功")
    def login_successfully(self, username: str = settings.username, password: str = settings.password) -> None:
        """执行登录并等待进入主框架。

        登录成功后路由守卫会拉取菜单并把 URL 重定向到第一个有权访问的页面，
        因此这里以“离开 /login 且左侧菜单渲染完成”作为成功标志。
        """
        self.submit(username, password)
        # 等待离开登录页（跳转到业务页面）
        self.page.wait_for_function("() => !location.pathname.startsWith('/login')")
        # 左侧菜单渲染完成，说明动态路由与主框架已经就绪
        expect(self.page.get_by_role("menu")).to_be_visible(timeout=settings.navigation_timeout_ms)
        logger.info("登录成功，当前地址：%s", self.current_url)

    # ------------------------------------------------------------------ #
    # 状态读取
    # ------------------------------------------------------------------ #
    def form_feedback(self) -> list[str]:
        """读取登录表单的校验错误文案（用于必填校验断言）。"""
        return self.form_feedback_texts(self.page.locator("form"))

    def expect_login_error(self) -> str:
        """等待并返回登录失败提示（用户名或密码错误）。"""
        return self.wait_for_toast(MSG_LOGIN_ERROR)

    def is_on_login_page(self) -> bool:
        """当前是否停留在登录页。"""
        return "/login" in self.current_url

    # 校验文案常量（用例中引用，避免魔法字符串）
    REQUIRED_USERNAME_MSG = MSG_REQUIRED_USERNAME
    REQUIRED_PASSWORD_MSG = MSG_REQUIRED_PASSWORD
