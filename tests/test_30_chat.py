# -*- coding: utf-8 -*-
"""灵犀问答模块测试用例。

覆盖点：
1. 引导页：欢迎语、推荐提示词、输入区按钮完整性；
2. 推荐提示词点击填充与清空；
3. 发送消息 → 新建会话 → AI 流式回答完成（核心链路）；
4. 生成过程中“停止”按钮可用并中断回答；
5. 会话重命名；
6. 会话置顶 / 取消置顶（分组变化）；
7. 会话删除（自建数据，含确认弹窗）；
8. 消息删除（自建数据，含确认弹窗）；
9. 会话侧边栏收起 / 展开；
10. “选择临床试验”下拉交互。

测试数据保护说明：
- 用例创建的会话名称/消息内容均携带 E2E-AUTO 标识；
- 通过 ``conversation_cleaner`` 夹具登记所有自建会话，
  用例结束（无论成败）后统一通过接口兜底删除，不影响存量数据。
"""

from __future__ import annotations

import allure
import pytest
from playwright.sync_api import expect

from src.pages.chat_page import GROUP_PINNED, ChatPage
from src.utils.test_data import build_test_message, build_test_name

pytestmark = [allure.feature("灵犀问答"), pytest.mark.data_cleanup]

# AI 响应可能因环境负载出现的“请求已取消”占位文案（点击停止后的预期）
CANCELLED_TEXT = "请求已取消"


@allure.story("引导页")
class TestChatWelcome:
    """新会话引导页。"""

    @allure.title("引导页元素展示完整")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.smoke
    def test_welcome_panel(self, chat_page: ChatPage) -> None:
        with allure.step("校验欢迎语与输入区"):
            expect(chat_page.page.get_by_text("需要灵犀帮你做什么吗？")).to_be_visible()
            expect(chat_page.editor).to_be_visible()
            expect(chat_page.editor_placeholder).to_be_visible()
            expect(chat_page.clear_button).to_be_visible()
            expect(chat_page.page.get_by_role("button", name="语音")).to_be_visible()
        with allure.step("校验推荐提示词"):
            prompt_items = chat_page.page.locator(".prompt-item")
            assert prompt_items.count() >= 1, "引导页应展示推荐提示词"
        with allure.step("校验底部声明"):
            expect(chat_page.page.get_by_text("AI生成，仅供参考")).to_be_visible()

    @allure.title("点击推荐提示词填充输入框并可清空")
    @allure.severity(allure.severity_level.NORMAL)
    def test_prompt_fill_and_clear(self, chat_page: ChatPage) -> None:
        first_prompt = chat_page.page.locator(".prompt-item").first
        prompt_title = first_prompt.inner_text().strip()

        with allure.step(f"点击提示词：{prompt_title}（自动填充完整提问内容）"):
            expect(chat_page.editor_placeholder).to_be_visible()
            first_prompt.click()
            expect(chat_page.editor_placeholder).to_be_hidden()
            assert chat_page.editor_text(), "点击提示词后输入框应自动填充内容"

        with allure.step("点击清空按钮"):
            chat_page.clear_input()
            expect(chat_page.editor_placeholder).to_be_visible()
            assert chat_page.editor_text() == ""

    @allure.title("选择临床试验下拉可打开并关闭")
    @allure.severity(allure.severity_level.NORMAL)
    def test_analysis_selector_dropdown(self, chat_page: ChatPage) -> None:
        with allure.step("点击“选择临床试验”，下拉面板展示"):
            chat_page.open_analysis_dropdown()
        with allure.step("按 Esc 关闭下拉"):
            chat_page.close_analysis_dropdown()

    @allure.title("选择临床试验：挂载分析并移除")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_attach_analysis_to_input(
        self, api_client, research_cleaner, analysis_cleaner, chat_page: ChatPage
    ) -> None:
        """在输入区挂载自建临床试验（选→展示→移除）。

        造数：自建课题 + 临床试验；刷新页面使下拉选项包含新数据。
        """
        research = research_cleaner["create"](objective="聊天挂载用例")
        analysis = analysis_cleaner["create"](research["id"], description="聊天挂载目标")
        chat_page.page.reload()
        chat_page.wait_ready()

        with allure.step("打开下拉并选择临床试验"):
            chat_page.select_analysis(research["name"], analysis["name"])

        with allure.step("校验分析已挂载到输入区（标签展示名称）"):
            tag = chat_page.attached_analysis_tag
            expect(tag).to_be_visible()
            expect(tag).to_contain_text(analysis["name"])

        with allure.step("移除挂载的分析"):
            chat_page.remove_attached_analysis()
            expect(tag).to_have_count(0)


@allure.story("会话消息")
class TestChatMessage:
    """消息发送 / AI 回答 / 消息操作。"""

    @allure.title("发送消息创建会话并获得 AI 回答")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.smoke
    def test_send_message_and_receive_ai_answer(self, chat_page: ChatPage, conversation_cleaner) -> None:
        message = build_test_message("请用一句话介绍你自己")

        with allure.step(f"发送消息：{message}"):
            chat_page.send_message(message)
            # 会话已在服务端创建，登记 id 用于兜底清理
            conversation_cleaner["register"](chat_page.current_conversation_id())

        with allure.step("校验用户消息气泡"):
            expect(chat_page.user_message(message)).to_be_visible()
            assert chat_page.user_message(message).inner_text().strip() == message

        with allure.step("等待 AI 回答完成（按需求等待 1 分钟）"):
            answer = chat_page.wait_ai_answer(timeout=60_000)
            assert answer, "AI 回答内容不应为空"

        with allure.step("校验会话出现在侧边栏且为激活态"):
            expect(chat_page.active_conversation_item).to_be_visible()

    @allure.title("AI 生成过程中可停止回答")
    @allure.severity(allure.severity_level.NORMAL)
    def test_stop_generating(self, chat_page: ChatPage, conversation_cleaner) -> None:
        message = build_test_message("请详细介绍一下肺癌的靶向治疗")
        chat_page.send_message(message)
        conversation_cleaner["register"](chat_page.current_conversation_id())

        with allure.step("等待停止按钮出现并点击"):
            if not chat_page.is_visible(chat_page.stop_button, timeout=10_000):
                pytest.skip("AI 生成速度过快，未捕获到停止按钮（环境响应极快）")
            chat_page.stop_generating()

        with allure.step("校验回答已中断"):
            ai_message = chat_page.ai_messages.last
            expect(ai_message).to_contain_text(CANCELLED_TEXT, timeout=10_000)

    @allure.title("删除自建消息（确认弹窗 + 列表移除）")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_delete_message(self, chat_page: ChatPage, conversation_cleaner) -> None:
        message = build_test_message("这是一条待删除的测试消息")
        chat_page.send_message(message)
        conversation_cleaner["register"](chat_page.current_conversation_id())
        chat_page.wait_ai_answer()

        user_message = chat_page.user_message(message)
        with allure.step("删除用户消息并确认"):
            expect(user_message).to_be_visible()
            chat_page.delete_message(user_message)

        with allure.step("校验消息已从列表移除"):
            expect(chat_page.user_message(message)).to_have_count(0)
        with allure.step("校验 AI 回答仍然保留"):
            assert chat_page.ai_messages.count() >= 1

    @allure.title("复制消息内容到剪贴板")
    @allure.severity(allure.severity_level.NORMAL)
    def test_copy_message(self, chat_page: ChatPage, conversation_cleaner) -> None:
        message = build_test_message("这是一条待复制的测试消息")
        chat_page.send_message(message)
        conversation_cleaner["register"](chat_page.current_conversation_id())
        chat_page.wait_ai_answer()

        with allure.step("悬浮用户消息并点击“复制”按钮"):
            actions = chat_page.hover_message(chat_page.user_message(message))
            copy_button = actions.locator("button[title='复制']")
            expect(copy_button).to_be_visible()
            # 消息列表为虚拟滚动容器，普通点击可能被条目容器拦截，改为事件派发
            copy_button.dispatch_event("click")

        with allure.step("校验复制成功提示"):
            text = chat_page.wait_for_toast("复制")
            assert "成功" in text, f"复制应成功：{text}"


@allure.story("会话管理")
class TestChatConversation:
    """会话重命名 / 置顶 / 删除 / 侧边栏折叠。"""

    @allure.title("重命名自建会话")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_rename_conversation(self, chat_page: ChatPage, conversation_cleaner) -> None:
        conversation = conversation_cleaner["create"]()
        chat_page.open_conversation(str(conversation["id"]))
        # 会话名称输入框 maxlength=30，测试名称需控制在 30 字符内
        new_name = build_test_name("会话", max_length=30)

        with allure.step(f"重命名会话为：{new_name}"):
            chat_page.rename_conversation(chat_page.active_conversation_item, new_name)

        with allure.step("校验侧边栏名称已更新"):
            expect(chat_page.conversation_item(new_name)).to_be_visible()
            assert new_name in chat_page.conversation_labels()

    @allure.title("会话置顶与取消置顶")
    @allure.severity(allure.severity_level.NORMAL)
    def test_pin_and_unpin_conversation(self, chat_page: ChatPage, conversation_cleaner) -> None:
        conversation = conversation_cleaner["create"]()
        chat_page.open_conversation(str(conversation["id"]))
        item = chat_page.active_conversation_item

        with allure.step("置顶会话：进入“置顶”分组"):
            chat_page.pin_conversation(item)
            expect(chat_page.page.locator(".group-label").filter(has_text=GROUP_PINNED)).to_be_visible()
            assert chat_page.group_of(item) == GROUP_PINNED

        with allure.step("取消置顶：离开“置顶”分组"):
            chat_page.unpin_conversation(item)
            expect(chat_page.page.locator(".group-label").filter(has_text=GROUP_PINNED)).to_have_count(0)
            expect(item).to_be_visible()

    @allure.title("删除自建会话（确认弹窗 + 跳转新会话页）")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_delete_conversation(self, chat_page: ChatPage, conversation_cleaner) -> None:
        conversation = conversation_cleaner["create"]()
        chat_page.open_conversation(str(conversation["id"]))
        item = chat_page.active_conversation_item
        before_count = chat_page.conversation_items.count()

        with allure.step("删除会话并确认"):
            chat_page.delete_conversation(item)

        with allure.step("校验会话已删除且跳转到新会话页"):
            expect(chat_page.conversation_items).to_have_count(before_count - 1)
            expect(chat_page.page.get_by_text("需要灵犀帮你做什么吗？")).to_be_visible()

    @allure.title("会话侧边栏收起与展开")
    @allure.severity(allure.severity_level.MINOR)
    def test_sidebar_collapse_expand(self, chat_page: ChatPage) -> None:
        with allure.step("收起侧边栏"):
            chat_page.collapse_sidebar()
            expect(chat_page.page.get_by_role("button", name="展开")).to_be_visible()
            assert not chat_page.sidebar_visible(), "收起后侧边栏应不可见"

        with allure.step("展开侧边栏"):
            chat_page.expand_sidebar()
            expect(chat_page.nav_create_button).to_be_visible()
            assert chat_page.sidebar_visible()

    @allure.title("新建会话按钮返回引导页")
    @allure.severity(allure.severity_level.MINOR)
    def test_new_conversation_button(self, chat_page: ChatPage, conversation_cleaner) -> None:
        conversation = conversation_cleaner["create"]()
        chat_page.open_conversation(str(conversation["id"]))
        with allure.step("点击“新会话”回到引导页"):
            chat_page.click_new_conversation()
            assert chat_page.current_conversation_id() is None
