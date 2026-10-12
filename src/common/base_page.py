# -*- coding: utf-8 -*-
"""页面对象基类。

设计说明：
- 所有页面对象（Page Object）继承 :class:`BasePage`，只关注“如何操作界面、
  如何读取界面状态”，不在页面对象中写业务断言；
- 全局提示（naive-ui message）、确认弹窗（n-dialog / n-popconfirm）、
  失败截图等高频共性操作在此统一封装，子类直接复用，保证用例代码简洁；
- 页面对象之间通过组合（而非继承）互相引用，便于扩展与替换。
"""

from __future__ import annotations

import json
import re

import allure
from playwright.sync_api import Locator, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import expect

from config.settings import settings
from src.common.logger import get_logger

logger = get_logger(__name__)


class BasePage:
    """所有页面对象的基类。

    子类通过覆盖 :attr:`path` 声明自身路由；实例方法默认返回 ``self``
    或子页面对象，便于链式调用。
    """

    #: 页面路由（子类覆盖），例如 ``/login``
    path: str = "/"

    def __init__(self, page: Page) -> None:
        self.page = page
        # 统一超时配置：元素等待 20s、页面跳转 60s（AI 场景单独放长）
        self.page.set_default_timeout(settings.default_timeout_ms)
        self.page.set_default_navigation_timeout(settings.navigation_timeout_ms)

    # ====================================================================== #
    # 导航
    # ====================================================================== #
    @allure.step("打开地址：{path}")
    def goto(self, path: str = "") -> "BasePage":
        """打开相对路径（自动拼接环境地址），空字符串表示目标地址首页。"""
        url = f"{settings.base_url.rstrip('/')}{path}"
        logger.info("打开页面：%s", url)
        self.page.goto(url)
        return self

    def open(self) -> "BasePage":
        """打开当前页面对象声明的默认路由。"""
        return self.goto(self.path)

    def wait_for_url(self, pattern: str | re.Pattern, timeout: int | None = None) -> None:
        """等待浏览器地址匹配指定通配符/正则。"""
        self.page.wait_for_url(pattern, timeout=timeout or settings.navigation_timeout_ms)

    @property
    def current_url(self) -> str:
        return self.page.url

    def wait_network_idle(self) -> None:
        """等待网络相对空闲（列表/详情数据加载完成），最多等 10s 防止超时。"""
        try:
            self.page.wait_for_load_state("networkidle", timeout=10_000)
        except PlaywrightTimeoutError:
            logger.debug("networkidle 等待超时（可忽略，页面可能仍在轮询）")

    # ====================================================================== #
    # 全局提示（naive-ui message）
    # ====================================================================== #
    def toast_texts(self) -> list[str]:
        """返回当前页面上所有可见全局提示的文本。"""
        return [text.strip() for text in self.page.locator(".n-message__content").all_inner_texts() if text.strip()]

    @allure.step("等待提示信息包含：{keyword}")
    def wait_for_toast(self, keyword: str, timeout: int | None = None) -> str:
        """等待出现包含 ``keyword`` 的全局提示，并返回完整提示文本。

        naive-ui 的 message 数秒后自动消失，因此采用 ``wait_for_function``
        高频轮询，避免用例执行较慢时错过短暂出现的提示。
        """
        js = (
            "(kw) => [...document.querySelectorAll('.n-message__content')]"
            ".some(el => (el.textContent || '').includes(kw))"
        )
        try:
            self.page.wait_for_function(js, arg=keyword, timeout=timeout or settings.default_timeout_ms)
        except PlaywrightTimeoutError:
            raise AssertionError(f"等待包含「{keyword}」的提示超时，当前页面提示：{self.toast_texts()}") from None
        # 提示可能在等待完成瞬间消失，取不到时回退 keyword 本身
        return next((text for text in self.toast_texts() if keyword in text), keyword)

    def has_toast(self, keyword: str) -> bool:
        """当前是否存在包含 ``keyword`` 的提示（不等待）。"""
        return any(keyword in text for text in self.toast_texts())

    # ====================================================================== #
    # 确认弹窗（window.$dialog.warning / n-popconfirm）
    # ====================================================================== #
    @allure.step("点击确认弹窗按钮：{button_text}")
    def confirm_dialog(self, button_text: str = "确定") -> None:
        """处理 ``window.$dialog`` 生成的确认对话框（例如“确定要删除该会话吗？”）。"""
        dialog = self.page.locator(".n-dialog").last
        expect(dialog).to_be_visible()
        dialog.get_by_role("button", name=button_text, exact=True).click()

    @allure.step("点击气泡确认按钮：{button_text}")
    def confirm_popconfirm(self, button_text: str = "确定") -> None:
        """处理 ``n-popconfirm`` 气泡确认（例如标注任务卡片上的删除按钮）。"""
        popconfirm = self.page.locator(".n-popconfirm").last
        expect(popconfirm).to_be_visible()
        popconfirm.get_by_role("button", name=button_text, exact=True).click()

    # ====================================================================== #
    # 表单 / 元素工具
    # ====================================================================== #
    @staticmethod
    def form_feedback_texts(scope: Locator) -> list[str]:
        """读取表单校验错误文案（naive-ui form 的反馈行）。"""
        return [text.strip() for text in scope.locator(".n-form-item-feedback__line").all_inner_texts() if text.strip()]

    def wait_visible(self, locator: Locator, timeout: int | None = None) -> Locator:
        """等待元素可见并返回该定位器。"""
        expect(locator).to_be_visible(timeout=timeout or settings.default_timeout_ms)
        return locator

    def wait_hidden(self, locator: Locator, timeout: int | None = None) -> None:
        """等待元素隐藏（例如弹窗关闭）。"""
        expect(locator).to_be_hidden(timeout=timeout or settings.default_timeout_ms)

    def is_visible(self, locator: Locator, timeout: int = 2_000) -> bool:
        """在指定时间内探测元素是否可见（用于“可能存在也可能不存在”的场景）。"""
        try:
            locator.first.wait_for(state="visible", timeout=timeout)
            return True
        except PlaywrightTimeoutError:
            return False

    def scroll_into_view_and_click(self, locator: Locator) -> None:
        """滚动到元素位置后点击（长列表中避免被浮动元素遮挡）。"""
        locator.scroll_into_view_if_needed()
        locator.click()

    @allure.step("选择下拉框选项：{option_text}")
    def select_dropdown_option(self, select: Locator, option_text: str) -> None:
        """点击 naive-ui 下拉框（n-select）并选择包含指定文本的选项。

        下拉面板由 naive-ui 挂载到 body 上，因此统一在全局范围内
        定位最后一个 ``.n-base-select-menu`` 面板。
        """
        select.click()
        menu = self.page.locator(".n-base-select-menu").last
        option = menu.locator(".n-base-select-option").filter(has_text=option_text).first
        expect(option).to_be_visible()
        option.click()

    @allure.step("选择下拉框第一个选项")
    def select_first_dropdown_option(self, select: Locator) -> str:
        """点击 naive-ui 下拉框并选择第一个选项，返回选项文本。"""
        select.click()
        menu = self.page.locator(".n-base-select-menu").last
        option = menu.locator(".n-base-select-option").first
        expect(option).to_be_visible()
        text = option.inner_text().strip()
        option.click()
        return text

    @allure.step("级联选择：{group_label} / {leaf_label}")
    def select_cascader_path(self, trigger: Locator, group_label: str, leaf_label: str) -> None:
        """操作 naive-ui 级联选择器（n-cascader）：先选第一列分组，再选第二列叶子。

        当前版本 DOM：面板 ``.n-cascader-menu`` 内每列为 ``.n-cascader-submenu``，
        选项为 ``.n-cascader-option``。
        """
        trigger.click()
        submenus = self.page.locator(".n-cascader-submenu")
        group = (
            submenus.nth(0)
            .locator(".n-cascader-option")
            .filter(has_text=re.compile(rf"^{re.escape(group_label)}$"))
            .first
        )
        expect(group).to_be_visible()
        group.click()
        leaf = (
            submenus.nth(1)
            .locator(".n-cascader-option")
            .filter(has_text=re.compile(rf"^{re.escape(leaf_label)}$"))
            .first
        )
        expect(leaf).to_be_visible()
        leaf.click()

    # ====================================================================== #
    # 调试与报告
    # ====================================================================== #
    def attach_screenshot(self, name: str = "截图") -> None:
        """把当前页面截图附加到 Allure 报告中。"""
        try:
            allure.attach(
                self.page.screenshot(full_page=True),
                name=name,
                attachment_type=allure.attachment_type.PNG,
            )
        except Exception as exc:  # pragma: no cover - 截图失败不应影响用例结论
            logger.warning("附加截图失败：%s", exc)

    def attach_page_source(self, name: str = "页面源码") -> None:
        """把当前页面 HTML 附加到 Allure 报告中，便于失败排查。"""
        try:
            allure.attach(self.page.content(), name=name, attachment_type=allure.attachment_type.HTML)
        except Exception as exc:  # pragma: no cover
            logger.warning("附加页面源码失败：%s", exc)

    # ====================================================================== #
    # 登录态
    # ====================================================================== #
    def read_local_user_info(self) -> dict:
        """读取 localStorage 中的用户信息（key 与前端约定：dmd-pro-userInfo）。

        前端存储结构：``{"value": {"realName": ..., "token": ...}, "timestamp": null}``
        该方法用于在用例中获取真实姓名、Token 等上下文信息，避免硬编码。
        """
        raw = self.page.evaluate("() => localStorage.getItem('dmd-pro-userInfo')")
        if not raw:
            return {}
        try:
            return json.loads(raw).get("value") or {}
        except (ValueError, AttributeError):  # pragma: no cover - 存储损坏时返回空
            return {}
