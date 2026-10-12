# -*- coding: utf-8 -*-
"""pytest 全局夹具（fixtures）与钩子。

夹具设计说明：

1. **登录态复用**：``auth_storage_state``（session 级）通过 UI 登录一次并保存
   storage_state 文件，其后每个用例的新浏览器上下文直接复用该登录态，
   既贴近真实用户又大幅缩短执行时间；
2. **按用例隔离**：``context`` / ``page`` 均为函数级，用例之间互不影响；
   标记 ``@pytest.mark.no_auth`` 的用例（登录/退出/修改密码）使用干净的
   未登录上下文，自行完成登录步骤；
3. **测试数据保护**：``annotation_cleaner`` / ``conversation_cleaner`` 两个
   夹具负责“创建带 E2E-AUTO 标识的数据 + 用例结束兜底清理”，
   即使用例失败也不会在环境中残留测试数据，更不会触碰存量数据；
4. **失败可追溯**：用例失败时自动截图并附加页面源码到 Allure 报告，
   同时在 screenshots/ 目录留存图片文件。
"""

from __future__ import annotations

import re
from typing import Any, Callable, Iterator

import allure
import pytest
from playwright.sync_api import Browser, Page, Playwright

from config.settings import (
    ALLURE_RESULTS_DIR,
    RUNTIME_DIR,
    SCREENSHOT_DIR,
    STORAGE_STATE_FILE,
    settings,
)
from src.api.client import ApiClient, build_api_client
from src.common.logger import get_logger
from src.pages.annotation_page import AnnotationListPage
from src.pages.chat_page import ChatPage
from src.pages.database_page import DatabaseDetailPage, DatabaseListPage
from src.pages.layout_page import LayoutHeader
from src.pages.login_page import LoginPage
from src.pages.password_modal import PasswordModal
from src.pages.research_page import ResearchListPage
from src.utils.test_data import build_test_name

logger = get_logger(__name__)


# ======================================================================== #
# 运行期环境准备
# ======================================================================== #
@pytest.fixture(scope="session", autouse=True)
def prepare_runtime_dirs() -> None:
    """创建运行期目录并写入 Allure 环境信息。"""
    for directory in (RUNTIME_DIR, SCREENSHOT_DIR, ALLURE_RESULTS_DIR, ALLURE_RESULTS_DIR.parent / "logs"):
        directory.mkdir(parents=True, exist_ok=True)
    # Allure 报告首页展示的环境信息
    env_file = ALLURE_RESULTS_DIR / "environment.properties"
    env_file.write_text(
        "\n".join(
            [
                f"Environment={settings.base_url}",
                f"Account={settings.username}",
                "Browser=Chromium (pytest-playwright)",
                f"Viewport={settings.viewport_width}x{settings.viewport_height}",
            ]
        ),
        encoding="utf-8",
    )


def pytest_report_header(config) -> str:  # pragma: no cover - 仅用于控制台展示
    """在测试会话开始时输出目标环境信息。"""
    return f"E2E 目标环境: {settings.base_url} | 账号: {settings.username}"


# ======================================================================== #
# 登录态（session 级）
# ======================================================================== #
@pytest.fixture(scope="session")
def auth_storage_state(browser: Browser) -> str:
    """通过真实 UI 登录一次，保存登录态供全部用例复用。

    登录成功后平台会把 token 写入 localStorage（dmd-pro-userInfo），
    Playwright 的 storage_state 会一并保存 localStorage，从而免去重复登录。
    """
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    context = browser.new_context(
        viewport={"width": settings.viewport_width, "height": settings.viewport_height},
        locale="zh-CN",
    )
    page = context.new_page()
    try:
        login_page = LoginPage(page)
        login_page.open()
        login_page.login_successfully()
        context.storage_state(path=str(STORAGE_STATE_FILE))
        logger.info("登录态已保存：%s", STORAGE_STATE_FILE)
    finally:
        context.close()
    return str(STORAGE_STATE_FILE)


# ======================================================================== #
# 浏览器上下文 / 页面
# ======================================================================== #
@pytest.fixture
def context(browser: Browser, request: pytest.FixtureRequest, auth_storage_state: str, browser_context_args: dict):
    """为每个用例创建独立上下文。

    - 默认注入已保存的登录态（模拟“已登录用户”）；
    - 标记 ``@pytest.mark.no_auth`` 的用例使用干净上下文（未登录）。
    """
    no_auth = request.node.get_closest_marker("no_auth") is not None
    args: dict[str, Any] = dict(browser_context_args)
    if args.get("viewport") is None:
        args["viewport"] = {"width": settings.viewport_width, "height": settings.viewport_height}
    if args.get("locale") is None:
        args["locale"] = "zh-CN"
    args["storage_state"] = None if no_auth else auth_storage_state

    ctx = browser.new_context(**args)
    ctx.set_default_timeout(settings.default_timeout_ms)
    ctx.set_default_navigation_timeout(settings.navigation_timeout_ms)
    yield ctx
    ctx.close()


# ======================================================================== #
# 业务夹具（页面对象）
# ======================================================================== #
@pytest.fixture
def login_page(page: Page) -> LoginPage:
    """登录页对象（已打开并渲染完成）。"""
    return LoginPage(page).open()


@pytest.fixture
def layout(page: Page) -> LayoutHeader:
    """主框架对象（菜单 / 用户下拉）。"""
    return LayoutHeader(page)


@pytest.fixture
def database_list_page(page: Page) -> DatabaseListPage:
    """专病库列表页对象（已打开）。"""
    return DatabaseListPage(page).open()


@pytest.fixture
def database_detail_page(page: Page) -> DatabaseDetailPage:
    """专病库详情页对象（需用例先导航，此处仅负责等待就绪）。"""
    return DatabaseDetailPage(page)


@pytest.fixture
def chat_page(page: Page) -> ChatPage:
    """灵犀问答页面对象（已打开新会话引导页）。"""
    return ChatPage(page).open()


@pytest.fixture
def annotation_list_page(page: Page) -> AnnotationListPage:
    """标注任务列表页对象（已打开）。"""
    return AnnotationListPage(page).open()


@pytest.fixture
def research_list_page(page: Page) -> ResearchListPage:
    """课题列表页对象（已打开）。"""
    return ResearchListPage(page).open()


@pytest.fixture
def password_modal(page: Page) -> Callable[[], PasswordModal]:
    """打开“修改密码”弹窗的工厂夹具（由用例显式调用以控制时机）。"""

    def _open() -> PasswordModal:
        modal = LayoutHeader(page).open_password_modal()
        return modal

    return _open


# ======================================================================== #
# 接口客户端（前置准备 / 兜底清理）
# ======================================================================== #
@pytest.fixture(scope="session")
def api_client(playwright: Playwright, auth_storage_state: str) -> Iterator[ApiClient]:
    """基于已保存登录态的接口客户端。"""
    client, request_context = build_api_client(playwright, auth_storage_state)
    yield client
    request_context.dispose()


# ======================================================================== #
# 测试数据管理（统一标识 + 自动清理）
# ======================================================================== #
@pytest.fixture
def annotation_cleaner(api_client: ApiClient) -> Iterator[dict[str, Callable]]:
    """标注任务测试数据管理器。

    - ``create``：通过接口创建带统一标识的任务，并登记清理；
    - ``register``：登记通过 UI 创建的任务名称，用例结束后兜底删除。

    清理逻辑：按名称精确检索（名称含随机后缀，全局唯一）后删除，
    只可能命中自动化创建的数据，不会影响存量数据。
    """
    created_names: list[str] = []

    def create(description: str = "E2E 自动化创建") -> dict:
        name = build_test_name("标注任务")
        api_client.create_annotation(name, description)
        created_names.append(name)
        return {"name": name}

    def register(name: str) -> None:
        created_names.append(name)

    yield {"create": create, "register": register}

    # ---- 兜底清理：无论用例成功与否都执行 ---- #
    for name in reversed(created_names):
        try:
            rows = api_client.query_annotations(name=name)
            for row in rows:
                if row.get("name") == name:
                    api_client.delete_annotation(row["id"])
        except Exception as exc:  # pragma: no cover - 清理失败仅告警，不掩盖用例结果
            logger.warning("清理标注任务失败：%s（%s）", name, exc)


@pytest.fixture
def conversation_cleaner(api_client: ApiClient) -> Iterator[dict[str, Callable]]:
    """AI 会话测试数据管理器。

    - ``create``：通过接口创建会话，并登记清理；
    - ``register``：登记通过 UI 创建的会话 id（可从 URL 中解析），用例结束后兜底删除。
    """
    created_ids: list[str] = []

    def create() -> dict:
        conversation = api_client.create_conversation()
        created_ids.append(str(conversation.get("id")))
        return conversation

    def register(conversation_id: str | None) -> None:
        if conversation_id:
            created_ids.append(str(conversation_id))

    yield {"create": create, "register": register}

    for conversation_id in reversed(created_ids):
        try:
            api_client.delete_conversation(conversation_id)
        except Exception as exc:  # pragma: no cover
            logger.warning("清理会话失败：%s（%s）", conversation_id, exc)


@pytest.fixture
def research_cleaner(api_client: ApiClient) -> Iterator[dict[str, Callable]]:
    """课题测试数据管理器。

    - ``create``：通过接口创建带统一标识的课题（可选绑定专病库），
      并回查主键（部分用例需要课题 id 做后续造数），登记清理；
    - ``register``：登记通过 UI 创建的课题名称，用例结束后兜底删除。

    清理逻辑：按名称精确检索（名称含随机后缀，全局唯一）后删除，
    只可能命中自动化创建的数据，不会影响存量数据。
    """
    created_names: list[str] = []

    def create(
        objective: str = "E2E 自动化研究目标",
        content: str = "E2E 自动化研究内容",
        technology: str = "E2E 自动化关键技术",
        database_id=None,
    ) -> dict:
        name = build_test_name("课题")
        row = api_client.create_research_and_get(
            name,
            objective=objective,
            content=content,
            technology=technology,
            database_id=database_id,
        )
        created_names.append(name)
        return {"name": name, "objective": objective, "id": row.get("id")}

    def register(name: str) -> None:
        created_names.append(name)

    yield {"create": create, "register": register}

    # ---- 兜底清理：无论用例成功与否都执行 ---- #
    for name in reversed(created_names):
        try:
            rows = api_client.query_researches(name=name)
            for row in rows:
                if row.get("name") == name:
                    api_client.delete_research(row["id"])
        except Exception as exc:  # pragma: no cover - 清理失败仅告警，不掩盖用例结果
            logger.warning("清理课题失败：%s（%s）", name, exc)


@pytest.fixture
def analysis_cleaner(api_client: ApiClient) -> Iterator[dict[str, Callable]]:
    """临床试验（组学分析）测试数据管理器。

    - ``create``：在指定课题下创建临床试验并回查主键，登记清理；
    - ``register``：登记通过 UI 创建的临床试验（课题 id + 名称），用例结束后兜底删除。

    清理逻辑：按“课题 id + 精确名称”检索后删除；课题本身被删除时其下
    临床试验会级联清理，这里的兜底保证即使课题清理异常也能清干净。
    """
    created: list[tuple[Any, str]] = []

    def create(research_id, description: str = "E2E 自动化创建") -> dict:
        name = build_test_name("临床试验")
        api_client.create_analysis(research_id, name, description)
        rows = api_client.query_analyses(research_id, name=name)
        analysis_id = next((row["id"] for row in rows if row.get("name") == name), None)
        created.append((research_id, name))
        return {"id": analysis_id, "name": name, "research_id": research_id}

    def register(research_id, name: str) -> None:
        created.append((research_id, name))

    yield {"create": create, "register": register}

    for research_id, name in reversed(created):
        try:
            for row in api_client.query_analyses(research_id, name=name):
                if row.get("name") == name:
                    api_client.delete_analysis(row["id"])
        except Exception as exc:  # pragma: no cover
            logger.warning("清理临床试验失败：%s（%s）", name, exc)


@pytest.fixture
def search_template_cleaner(api_client: ApiClient) -> Iterator[dict[str, Callable]]:
    """专病库“患者筛选模板”测试数据管理器。

    筛选模板保存在专病库维度（不在自建课题内），因此必须显式清理：
    - ``register``：登记（专病库 id, 模板名称）；
    - 用例结束后按“专病库 + 精确名称”检索并删除，仅清理自建模板。
    """
    created: list[tuple[Any, str]] = []

    def register(database_id, name: str) -> None:
        created.append((database_id, name))

    yield {"register": register}

    for database_id, name in reversed(created):
        try:
            templates = api_client.query_patient_search_templates(database_id)
            hit_ids = [row["id"] for row in templates if row.get("name") == name]
            if hit_ids:
                api_client.delete_patient_search_templates(hit_ids)
        except Exception as exc:  # pragma: no cover
            logger.warning("清理筛选模板失败：%s（%s）", name, exc)


# ======================================================================== #
# 失败现场留存
# ======================================================================== #
@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item: pytest.Item, call):
    """记录每个阶段的执行结果，供失败截图夹具读取。"""
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)


@pytest.fixture(autouse=True)
def attach_artifacts_on_failure(request: pytest.FixtureRequest):
    """用例失败时自动截图并附加页面源码到 Allure 报告。"""
    yield
    report = getattr(request.node, "rep_call", None)
    if report is None or not report.failed:
        return
    page = _try_get_page(request)
    if page is None:
        return
    safe_name = re.sub(r"[\\/:*?\"<>|\s]+", "_", request.node.nodeid)
    try:
        screenshot_bytes = page.screenshot(full_page=True)
        (SCREENSHOT_DIR / f"{safe_name}.png").write_bytes(screenshot_bytes)
        allure.attach(screenshot_bytes, name="失败截图", attachment_type=allure.attachment_type.PNG)
    except Exception as exc:  # pragma: no cover
        logger.warning("失败截图生成异常：%s", exc)
    try:
        allure.attach(page.content(), name="失败现场页面源码", attachment_type=allure.attachment_type.HTML)
    except Exception as exc:  # pragma: no cover
        logger.warning("失败页面源码附加异常：%s", exc)


def _try_get_page(request: pytest.FixtureRequest) -> Page | None:
    """尽力从夹具缓存中获取 page 对象（用例失败时可能尚未创建）。"""
    for name in ("page",):
        try:
            page = request.getfixturevalue(name)
            if isinstance(page, Page):
                return page
        except Exception:  # pragma: no cover - 夹具不存在或创建失败
            continue
    return None


# ======================================================================== #
# 通用工具
# ======================================================================== #
@pytest.fixture
def expect_no_toast_error(page: Page) -> Callable[[], None]:
    """断言当前页面没有出现错误提示（业务接口失败的统一表现）。"""

    def _check() -> None:
        texts = [t.strip() for t in page.locator(".n-message__content").all_inner_texts() if t.strip()]
        errors = [t for t in texts if "失败" in t or "错误" in t]
        assert not errors, f"页面出现错误提示：{errors}"

    return _check
