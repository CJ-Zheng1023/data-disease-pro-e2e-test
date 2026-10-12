# -*- coding: utf-8 -*-
"""修改密码弹窗（组件对象）。

入口：主框架右上角用户下拉 → ``修改密码``。
前端实现：``src/layouts/header/passwordModal.vue``：

- 两个输入框：``新密码``、``确认密码``；
- 新密码聚焦时弹出密码强度气泡（5 条策略实时校验）；
- 提交时前端先做策略校验与一致性校验，通过后再 RSA 加密提交接口。
"""

from __future__ import annotations

import allure
from playwright.sync_api import Locator
from playwright.sync_api import expect

from src.common.base_page import BasePage

MODAL_TITLE = "修改密码"


class PasswordModal(BasePage):
    """修改密码弹窗。"""

    # ------------------------------------------------------------------ #
    # 定位器
    # ------------------------------------------------------------------ #
    @property
    def root(self) -> Locator:
        """弹窗根节点：通过标题精确定位，避免与其他弹窗混淆。"""
        return self.page.locator(".custom-modal").filter(
            has=self.page.locator(".n-card-header__main", has_text=MODAL_TITLE)
        ).last

    @property
    def new_password_input(self) -> Locator:
        """新密码输入框（占位符为空，匹配“请输入”精确文本）。"""
        return self.root.get_by_placeholder("请输入", exact=True)

    @property
    def confirm_password_input(self) -> Locator:
        return self.root.get_by_placeholder("请再次输入新密码")

    @property
    def ok_button(self) -> Locator:
        return self.root.get_by_role("button", name="确定", exact=True)

    @property
    def close_button(self) -> Locator:
        return self.root.get_by_role("button", name="关闭", exact=True)

    @property
    def strength_popover(self) -> Locator:
        """密码强度气泡（聚焦新密码输入框时出现）。"""
        return self.page.locator(".n-popover", has_text="密码强度")

    # ------------------------------------------------------------------ #
    # 操作
    # ------------------------------------------------------------------ #
    def wait_opened(self) -> "PasswordModal":
        expect(self.root).to_be_visible()
        return self

    def wait_closed(self) -> None:
        expect(self.root).to_be_hidden()

    @allure.step("填写新密码与确认密码")
    def fill(self, password: str, confirm_password: str) -> "PasswordModal":
        self.new_password_input.fill(password)
        self.confirm_password_input.fill(confirm_password)
        return self

    @allure.step("聚焦新密码输入框")
    def focus_new_password(self) -> "PasswordModal":
        self.new_password_input.click()
        return self

    @allure.step("提交修改密码")
    def submit(self) -> None:
        self.ok_button.click()

    @allure.step("关闭修改密码弹窗")
    def close(self) -> None:
        self.close_button.click()
        self.wait_closed()

    # ------------------------------------------------------------------ #
    # 状态读取
    # ------------------------------------------------------------------ #
    def form_feedback(self) -> list[str]:
        """读取弹窗内的表单校验错误文案。"""
        return self.form_feedback_texts(self.root)

    def strategy_hint_texts(self) -> list[str]:
        """读取密码强度气泡中的 5 条策略文案。"""
        expect(self.strength_popover).to_be_visible()
        return [text.strip() for text in self.strength_popover.locator(".result-item .content").all_inner_texts() if text.strip()]
