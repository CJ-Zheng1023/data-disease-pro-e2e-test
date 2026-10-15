# -*- coding: utf-8 -*-
"""灵犀问答模块页面对象（/chat）。

页面结构：

- 左侧会话栏：``新会话`` 按钮、按日期/置顶分组的会话列表；
- 右侧内容区：无会话时展示引导页（欢迎语 + 推荐提示词 + 输入框）；
  有会话时展示消息列表 + 输入框；
- 输入框为富文本 contenteditable 组件（vue-element-plus-x XSender），
  通过键盘输入、Enter 发送。

会话的下拉操作（置顶/修改/删除）通过悬浮会话条目后出现的 “...” 按钮触发。
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

import allure
from playwright.sync_api import Locator
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import expect

from config.settings import settings
from src.common.base_page import BasePage
from src.common.logger import get_logger

logger = get_logger(__name__)

# 会话分组名称
GROUP_PINNED = "置顶"


class ChatPage(BasePage):
    """灵犀问答页面。"""

    # ================================================================== #
    # 侧边栏
    # ================================================================== #
    @property
    def nav_create_button(self) -> Locator:
        """侧边栏“新会话”按钮。"""
        return self.page.locator(".create-btn")

    @property
    def conversation_items(self) -> Locator:
        """侧边栏所有会话条目。"""
        return self.page.locator(".conversation-item")

    @property
    def group_labels(self) -> Locator:
        """会话分组标题（置顶 / 日期）。"""
        return self.page.locator(".group-label")

    @property
    def active_conversation_item(self) -> Locator:
        """当前打开的会话条目（高亮态）。"""
        return self.page.locator(".conversation-item.active")

    def conversation_item(self, label: str) -> Locator:
        """按名称定位会话条目。"""
        return self.conversation_items.filter(has_text=label).first

    def conversation_labels(self) -> list[str]:
        """读取侧边栏所有会话名称。"""
        return [text.strip() for text in self.conversation_items.locator(".n-ellipsis span").all_inner_texts() if text.strip()]

    def group_labels_text(self) -> list[str]:
        """读取当前所有分组标题。"""
        return [text.strip() for text in self.group_labels.all_inner_texts() if text.strip()]

    def group_of(self, item: Locator) -> str:
        """读取某个会话条目所在的分组标题。"""
        label = item.locator("xpath=ancestor::div[contains(@class,'group')][1]//div[contains(@class,'group-label')]")
        return label.first.inner_text().strip()

    # ================================================================== #
    # 输入区
    # ================================================================== #
    @property
    def editor(self) -> Locator:
        """富文本输入框（contenteditable）。"""
        return self.page.locator(".elx-x-sender div[contenteditable='true']")

    @property
    def editor_placeholder(self) -> Locator:
        return self.page.locator(".chat-placeholder-wrap")

    @property
    def clear_button(self) -> Locator:
        return self.page.get_by_role("button", name="清空")

    @property
    def analysis_selector_button(self) -> Locator:
        """“选择临床试验”按钮（关联分析数据）。"""
        return self.page.locator("button[title='选择临床试验']")

    def editor_text(self) -> str:
        """读取输入框当前文本（contenteditable 清空后会残留零宽字符，需要清洗）。"""
        return self.editor.inner_text().replace("\ufeff", "").strip()

    @allure.step("输入消息内容")
    def input_text(self, text: str) -> "ChatPage":
        """向富文本输入框写入内容（整段写入 + 校验重试）。

        说明：XSender 为 contenteditable 富文本组件，逐字模拟键盘输入时
        内部模型异步同步，快速输入后立即提交可能出现“尾部字符丢失”。
        因此这里通过 ``execCommand('insertText')`` 一次性写入整段文本
        （触发原生 input 事件，模型一次性同步），并校验写入结果，
        必要时清空重试，保证提交内容与预期完全一致。
        """
        js = """(text) => {
            const el = document.querySelector(".elx-x-sender div[contenteditable='true']");
            el.focus();
            document.execCommand("selectAll", false, null);
            document.execCommand("insertText", false, text);
        }"""
        # 写入后等待编辑器内容与目标完全一致
        verify_js = (
            "(expected) => {"
            " const el = document.querySelector(\".elx-x-sender div[contenteditable='true']\");"
            " return !!el && el.innerText.replace(/\\ufeff/g, '').trim() === expected;"
            "}"
        )
        for _ in range(3):
            self.page.evaluate(js, text)
            try:
                self.page.wait_for_function(verify_js, arg=text, timeout=3_000)
                return self
            except PlaywrightTimeoutError:
                # 写入不完整时清空重试
                self.clear_button.click()
        raise AssertionError(f"输入框内容与预期不一致，最后一次写入：{self.editor_text()!r}")

    @allure.step("发送消息：{text}")
    def send_message(self, text: str) -> "ChatPage":
        """输入内容后按 Enter 发送，并等待跳转到会话消息页。"""
        self.input_text(text)
        self.page.keyboard.press("Enter")
        # 发送成功后路由带上会话 id：/chat?id=xxx
        self.page.wait_for_url(re.compile(r".*chat\?id=.+"))
        return self

    @allure.step("清空输入框")
    def clear_input(self) -> "ChatPage":
        self.clear_button.click()
        return self

    @allure.step("打开“选择临床试验”下拉")
    def open_analysis_dropdown(self) -> Locator:
        """点击“选择临床试验”并等待下拉面板出现，返回面板定位器。

        说明：当账号下无分析数据时，下拉面板为空面板（没有尺寸），
        Playwright 的可见性判断会认为其“不可见”，因此这里以
        DOM 挂载 + ``offsetParent`` 作为展示依据；同时做有限次重试，
        避免首次点击落在选项加载过程中而失效。
        """
        js = (
            "() => { const list = [...document.querySelectorAll('.n-dropdown')];"
            " const d = list[list.length - 1]; return !!d && d.offsetParent !== null; }"
        )
        for _ in range(3):
            self.analysis_selector_button.click()
            try:
                self.page.wait_for_function(js, timeout=3_000)
                return self.page.locator(".n-dropdown").last
            except PlaywrightTimeoutError:
                continue
        raise AssertionError("“选择临床试验”下拉面板未能打开")

    @allure.step("关闭“选择临床试验”下拉")
    def close_analysis_dropdown(self) -> None:
        self.page.keyboard.press("Escape")
        self.page.wait_for_function(
            "() => ![...document.querySelectorAll('.n-dropdown')].some(d => d.offsetParent !== null)"
        )

    @allure.step("选择临床试验：{research_name} / {analysis_name}")
    def select_analysis(self, research_name: str, analysis_name: str) -> None:
        """打开下拉 → 悬浮课题分组 → 选择临床试验（树形下拉两级选择）。"""
        menu = self.open_analysis_dropdown()
        folder = menu.locator(".n-dropdown-option").filter(has_text=research_name).first
        expect(folder).to_be_visible(timeout=settings.default_timeout_ms)
        folder.hover()
        # 子级选项需精确匹配标签文本，避免匹配到包含子级的父级选项
        option = self.page.locator(".n-dropdown-option-body__label").filter(
            has_text=re.compile(rf"^{re.escape(analysis_name)}$")
        ).first
        expect(option).to_be_visible()
        option.click()

    @property
    def attached_analysis_tag(self) -> Locator:
        """输入区已挂载的临床试验标签（AnalysisViewer）。"""
        return self.page.locator(".elx-x-sender .n-tag")

    @allure.step("移除已挂载的临床试验")
    def remove_attached_analysis(self) -> None:
        self.attached_analysis_tag.locator(".n-tag__close").click()

    @allure.step("点击推荐提示词：{title}")
    def click_prompt(self, title: str) -> "ChatPage":
        """点击引导页推荐提示词，自动填充输入框。"""
        self.page.locator(".prompt-item").filter(has_text=title).first.click()
        return self

    # ================================================================== #
    # 消息区
    # ================================================================== #
    @property
    def user_messages(self) -> Locator:
        """用户消息（右侧气泡）。"""
        return self.page.locator(".message-item.end")

    @property
    def ai_messages(self) -> Locator:
        """AI 消息（左侧气泡）。"""
        return self.page.locator(".message-item.start")

    def user_message(self, text: str) -> Locator:
        """按内容定位用户消息。"""
        return self.user_messages.filter(has_text=text).first

    @allure.step("等待 AI 生成结束")
    def wait_ai_answer(self, timeout: int | None = None) -> str:
        """等待 AI 生成结束，返回回答文本。

        判定结束的依据：AI 消息上的“思考中/输入中”动画（icon-thinking）消失。
        超时时间默认取配置中的 AI 超时（120s）。
        若内容为空，会结合页面错误提示给出明确诊断（区分 AI 服务故障与用例问题）。
        当前仅消息操作类用例用它等待生成“落定”，不再断言回答内容质量。
        """
        timeout = timeout or settings.ai_timeout_ms
        ai_message = self.ai_messages.last
        expect(ai_message).to_be_visible(timeout=timeout)
        # 等待加载/输入动画消失：出现时可见，结束后从 DOM 中移除该类名
        expect(self.page.locator(".message-item.start .icon-thinking")).to_have_count(0, timeout=timeout)
        text = ai_message.locator(".message-item-content").inner_text().strip()
        if not text:
            error = next((t for t in self.toast_texts() if "Fail" in t or "失败" in t), "")
            detail = f"（页面错误提示：{error}）" if error else ""
            raise AssertionError(f"AI 回答内容为空{detail}，请检查 AI 服务状态")
        return text

    def hover_message(self, message: Locator) -> Locator:
        """悬浮消息，显示其操作按钮（复制 / 删除），返回操作区定位器。"""
        message.hover()
        actions = message.locator(".message-item-actions")
        expect(actions.locator("button").first).to_be_visible()
        return actions

    @allure.step("删除消息")
    def delete_message(self, message: Locator) -> None:
        """悬浮消息 → 点击删除 → 确认弹窗（删除后不可恢复）。

        说明：消息列表使用虚拟滚动（vue-recycle-scroller），条目外层容器
        可能拦截指针事件导致 Playwright 普通点击超时，这里改用事件派发
        直接触发按钮的点击逻辑。
        """
        actions = self.hover_message(message)
        actions.locator("button[title='删除']").dispatch_event("click")
        self.confirm_dialog()

    def has_copy_button(self, message: Locator) -> bool:
        """消息操作区是否提供复制按钮。"""
        actions = self.hover_message(message)
        return actions.locator("button[title='复制']").count() > 0

    # ================================================================== #
    # 导航 / 会话定位
    # ================================================================== #
    def open(self) -> "ChatPage":
        """打开灵犀问答（新会话引导页）。"""
        self.goto("/chat")
        expect(self.editor).to_be_visible()
        # 等待提示词、会话列表等首屏数据加载完成，避免发送时组件尚未就绪
        self.wait_network_idle()
        return self

    def wait_ready(self) -> "ChatPage":
        expect(self.editor).to_be_visible()
        return self

    def open_conversation(self, conversation_id: str) -> "ChatPage":
        """通过 URL 直接打开指定会话（用于精确定位 API 创建的测试会话）。"""
        self.goto(f"/chat?id={conversation_id}")
        expect(self.active_conversation_item).to_be_visible()
        return self

    def current_conversation_id(self) -> str | None:
        """从当前 URL 解析会话 id。"""
        query = parse_qs(urlparse(self.current_url).query)
        values = query.get("id")
        return values[0] if values else None

    @allure.step("点击新会话")
    def click_new_conversation(self) -> "ChatPage":
        self.nav_create_button.click()
        expect(self.page.get_by_text("需要灵犀帮你做什么吗？")).to_be_visible()
        return self

    # ================================================================== #
    # 会话下拉操作（置顶 / 修改 / 删除）
    # ================================================================== #
    def _open_conversation_menu(self, item: Locator) -> None:
        """悬浮会话条目并展开其操作下拉菜单。"""
        item.hover()
        item.locator("button.actions").hover()
        option = self.page.locator(".n-dropdown-option").first
        expect(option).to_be_visible()

    def _click_conversation_menu_option(self, option_text: str) -> None:
        """点击会话下拉菜单中的选项。"""
        option = self.page.locator(".n-dropdown-option").filter(has_text=option_text).first
        expect(option).to_be_visible()
        option.click()

    @allure.step("重命名会话为：{new_label}")
    def rename_conversation(self, item: Locator, new_label: str) -> None:
        """会话下拉 → 修改 → 填写新名称 → 确定。"""
        self._open_conversation_menu(item)
        self._click_conversation_menu_option("修改")
        modal = self.page.locator(".custom-modal").filter(
            has=self.page.locator(".n-card-header__main", has_text="修改会话名称")
        ).last
        expect(modal).to_be_visible()
        modal.get_by_placeholder("请输入", exact=True).fill(new_label)
        modal.get_by_role("button", name="确定", exact=True).click()
        expect(modal).to_be_hidden()

    @allure.step("置顶会话")
    def pin_conversation(self, item: Locator) -> None:
        self._open_conversation_menu(item)
        self._click_conversation_menu_option("置顶")
        self.wait_network_idle()

    @allure.step("取消置顶会话")
    def unpin_conversation(self, item: Locator) -> None:
        self._open_conversation_menu(item)
        self._click_conversation_menu_option("取消置顶")
        self.wait_network_idle()

    @allure.step("删除会话")
    def delete_conversation(self, item: Locator) -> None:
        """会话下拉 → 删除 → 确认弹窗。"""
        self._open_conversation_menu(item)
        self._click_conversation_menu_option("删除")
        self.confirm_dialog()

    # ================================================================== #
    # 侧边栏折叠
    # ================================================================== #
    @allure.step("收起会话侧边栏")
    def collapse_sidebar(self) -> None:
        self.page.get_by_role("button", name="收起").click()
        self.wait_sidebar_width(max_width=1)

    @allure.step("展开会话侧边栏")
    def expand_sidebar(self) -> None:
        self.page.get_by_role("button", name="展开").click()
        self.wait_sidebar_width(min_width=100)

    def sidebar_width(self) -> float:
        """侧边栏当前渲染宽度（收起后为 0，展开后为 260）。"""
        return self.page.locator(".app-container .nav").first.evaluate("el => el.getBoundingClientRect().width")

    def wait_sidebar_width(self, min_width: float = 0, max_width: float | None = None) -> None:
        """等待侧边栏宽度进入期望区间（折叠动画 0.4s 结束后生效）。"""
        js = (
            "(limits) => { const el = document.querySelector('.app-container .nav');"
            " if (!el) return false;"
            " const width = el.getBoundingClientRect().width;"
            " return width >= limits[0] && width <= limits[1]; }"
        )
        self.page.wait_for_function(js, arg=[min_width, max_width if max_width is not None else 10_000])

    def sidebar_visible(self) -> bool:
        """侧边栏当前是否展开（宽度大于 0，用于折叠/展开断言）。"""
        return self.sidebar_width() > 1
