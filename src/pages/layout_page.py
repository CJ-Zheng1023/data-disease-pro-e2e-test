# -*- coding: utf-8 -*-
"""登录后的全局框架对象（组件对象）。

负责左侧一级菜单、右上角用户下拉（修改密码 / 退出登录）等跨页面公共区域，
被登录、退出、修改密码以及各业务模块用例组合复用。
"""

from __future__ import annotations

import re

import allure
from playwright.sync_api import Locator
from playwright.sync_api import expect

from config.constants import ROUTE_LOGIN
from config.settings import settings
from src.common.base_page import BasePage
from src.common.logger import get_logger
from src.pages.password_modal import PasswordModal

logger = get_logger(__name__)


class LayoutHeader(BasePage):
    """主框架公共区域（顶部 + 左侧菜单 + 用户下拉）。"""

    # ------------------------------------------------------------------ #
    # 定位器
    # ------------------------------------------------------------------ #
    @property
    def menu(self) -> Locator:
        """左侧一级菜单（专病检索 / 课题管理 / 灵犀问答 / 智能标注 / 模型训练）。"""
        return self.page.get_by_role("menu")

    @property
    def user_trigger(self) -> Locator:
        """右上角用户信息区域（头像 + 姓名 + 下拉箭头）。

        点击/悬浮该区域会弹出 naive-ui 下拉菜单（默认 hover 触发）。
        """
        return self.page.locator(".nick-name")

    @property
    def user_dropdown(self) -> Locator:
        """用户下拉面板（挂载在 body 上的 teleport 节点）。"""
        return self.page.locator(".n-dropdown").last

    def user_name(self) -> str:
        """读取右上角展示的用户姓名。"""
        return self.user_trigger.locator("span").first.inner_text().strip()

    # ------------------------------------------------------------------ #
    # 操作
    # ------------------------------------------------------------------ #
    def wait_ready(self) -> "LayoutHeader":
        """等待主框架渲染完成（菜单 + 用户信息可见）。"""
        expect(self.menu).to_be_visible(timeout=settings.navigation_timeout_ms)
        expect(self.user_trigger).to_be_visible()
        return self

    @allure.step("通过左侧菜单进入：{label}")
    def click_menu(self, label: str) -> None:
        """点击一级菜单项（link 元素）。"""
        self.page.get_by_role("link", name=label, exact=True).click()

    @allure.step("展开用户下拉菜单")
    def open_user_dropdown(self) -> None:
        """悬浮（hover 触发）并等待用户下拉菜单展示。"""
        self.user_trigger.hover()
        expect(self.user_dropdown).to_be_visible()

    def _select_dropdown_option(self, label: str) -> None:
        """点击下拉菜单中的选项。"""
        option = self.user_dropdown.locator(".n-dropdown-option").filter(has_text=label).first
        expect(option).to_be_visible()
        option.click()

    @allure.step("打开修改密码弹窗")
    def open_password_modal(self) -> PasswordModal:
        """用户下拉 → 修改密码。"""
        self.open_user_dropdown()
        self._select_dropdown_option("修改密码")
        modal = PasswordModal(self.page)
        modal.wait_opened()
        return modal

    @allure.step("执行退出登录")
    def logout(self) -> None:
        """用户下拉 → 退出登录，等待回到登录页。"""
        self.open_user_dropdown()
        self._select_dropdown_option("退出登录")
        self.wait_for_url(re.compile(r".*" + re.escape(ROUTE_LOGIN) + r"$"))
        logger.info("已退出登录，当前地址：%s", self.current_url)
