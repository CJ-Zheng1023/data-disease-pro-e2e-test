# -*- coding: utf-8 -*-
"""智能标注模块页面对象。

覆盖两个页面：

- :class:`AnnotationListPage` —— 标注任务列表（创建 / 修改 / 删除 / 搜索 / 范围筛选）；
- :class:`AnnotationDetailPage` —— 标注任务详情（任务信息 + 标注集列表）。

注意：根据项目要求，涉及上传/下载的用例不在本次范围内，
因此本模块只校验创建标注集弹窗的表单规则，不执行真正的数据上传。
"""

from __future__ import annotations

import re

import allure
from playwright.sync_api import Locator
from playwright.sync_api import expect

from config.constants import MSG_REQUIRED_TASK_NAME, ROUTE_ANNOTATION_LIST
from config.settings import settings
from src.common.base_page import BasePage
from src.common.logger import get_logger

logger = get_logger(__name__)

CREATE_MODAL_TITLE = "创建"
EDIT_MODAL_TITLE = "修改"


class AnnotationListPage(BasePage):
    """标注任务列表页（/annotation/list）。"""

    path = ROUTE_ANNOTATION_LIST

    # ------------------------------------------------------------------ #
    # 定位器
    # ------------------------------------------------------------------ #
    @property
    def search_input(self) -> Locator:
        return self.page.get_by_placeholder("搜索标注任务名称")

    @property
    def create_button(self) -> Locator:
        """“创建任务”按钮（空数据时文案为“创建第一个任务”）。"""
        return self.page.get_by_role("button", name=re.compile(r"^创建(第一个)?任务$"))

    @property
    def items(self) -> Locator:
        """所有标注任务卡片。"""
        return self.page.locator(".annotation-item")

    @property
    def empty_text(self) -> Locator:
        """空数据提示文案。"""
        return self.page.get_by_text("暂无标注任务")

    @property
    def footer_text(self) -> Locator:
        return self.page.get_by_text(re.compile(r"共\s*\d+\s*条记录"))

    def item(self, name: str) -> Locator:
        """按名称定位标注任务卡片。"""
        return self.items.filter(has_text=name).first

    def scope_button(self, label: str) -> Locator:
        """范围筛选按钮（所有任务 / 我的任务 / 我参与的任务）。"""
        return self.page.locator(".button-radio-item").filter(has_text=label)

    # ------------------------------------------------------------------ #
    # 操作
    # ------------------------------------------------------------------ #
    def open(self) -> "AnnotationListPage":
        self.goto(self.path)
        # 面包屑与内容标题均含“标注任务列表”，这里取第一个可见元素避免严格模式冲突
        expect(self.page.get_by_text("标注任务列表").first).to_be_visible()
        self.wait_network_idle()
        return self

    @allure.step("点击创建任务")
    def click_create(self) -> "AnnotationFormModal":
        """打开创建任务弹窗。"""
        self.create_button.click()
        modal = AnnotationFormModal(self.page, CREATE_MODAL_TITLE)
        modal.wait_opened()
        return modal

    @allure.step("点击修改任务：{name}")
    def click_edit(self, name: str) -> "AnnotationFormModal":
        """打开指定任务的修改弹窗。"""
        self.item(name).locator("button[title='修改']").click()
        modal = AnnotationFormModal(self.page, EDIT_MODAL_TITLE)
        modal.wait_opened()
        return modal

    @allure.step("删除任务：{name}")
    def delete_task(self, name: str) -> None:
        """删除指定任务（气泡确认按钮为“确认”）。"""
        self.item(name).locator("button[title='删除']").click()
        self.confirm_popconfirm(button_text="确认")
        self.wait_network_idle()

    @allure.step("进入任务详情：{name}")
    def enter_detail(self, name: str) -> "AnnotationDetailPage":
        self.item(name).locator("button[title='进入']").click()
        self.wait_for_url(re.compile(r".*/annotation/detail/\d+$"))
        detail = AnnotationDetailPage(self.page)
        detail.wait_ready()
        return detail

    @allure.step("搜索标注任务：{name}")
    def search(self, name: str) -> "AnnotationListPage":
        """输入名称搜索（前端 500ms 防抖）。"""
        self.search_input.fill(name)
        self.wait_network_idle()
        return self

    @allure.step("按范围筛选：{label}")
    def switch_scope(self, label: str) -> "AnnotationListPage":
        self.scope_button(label).click()
        self.wait_network_idle()
        return self

    def refresh(self) -> "AnnotationListPage":
        """刷新页面数据。"""
        self.page.reload()
        self.wait_network_idle()
        return self

    # ------------------------------------------------------------------ #
    # 状态读取
    # ------------------------------------------------------------------ #
    def task_names(self) -> list[str]:
        """当前列表页所有任务名称。"""
        return [text.strip() for text in self.items.locator(".name .n-ellipsis span, .name span").all_inner_texts() if text.strip()]

    def is_empty(self) -> bool:
        """当前列表是否为空状态（无任务引导面板或检索结果为空）。"""
        if self.is_visible(self.empty_text, timeout=1_000):
            return True
        return self.is_visible(self.page.locator(".body .n-empty"), timeout=1_000)

    def task_dataset_count(self, name: str) -> int:
        """读取指定任务卡片上的“数据集”数量。"""
        footer = self.item(name).locator(".annotation-item-footer")
        value_text = footer.get_by_text(re.compile(r"^\d+$")).first.inner_text()
        return int(value_text.strip())


class AnnotationFormModal(BasePage):
    """标注任务创建 / 修改弹窗（二者共用同一表单，仅标题不同）。"""

    def __init__(self, page, title: str) -> None:
        super().__init__(page)
        self.title = title

    @property
    def root(self) -> Locator:
        return self.page.locator(".custom-modal").filter(
            has=self.page.locator(".n-card-header__main", has_text=re.compile(rf"^{self.title}$"))
        ).last

    @property
    def name_input(self) -> Locator:
        return self.root.get_by_placeholder("请输入", exact=True)

    @property
    def description_input(self) -> Locator:
        return self.root.locator("textarea")

    @property
    def ok_button(self) -> Locator:
        return self.root.get_by_role("button", name="确定", exact=True)

    @property
    def close_button(self) -> Locator:
        return self.root.get_by_role("button", name="关闭", exact=True)

    def wait_opened(self) -> "AnnotationFormModal":
        expect(self.root).to_be_visible()
        return self

    def wait_closed(self) -> None:
        expect(self.root).to_be_hidden()

    @allure.step("填写标注任务表单：{name}")
    def fill(self, name: str = "", description: str = "") -> "AnnotationFormModal":
        if name:
            self.name_input.fill(name)
        if description:
            self.description_input.fill(description)
        return self

    @allure.step("提交标注任务表单")
    def submit(self) -> None:
        self.ok_button.click()

    @allure.step("关闭标注任务表单")
    def close(self) -> None:
        self.close_button.click()
        self.wait_closed()

    def form_feedback(self) -> list[str]:
        """读取表单校验错误文案。"""
        return self.form_feedback_texts(self.root)

    def name_value(self) -> str:
        """名称输入框当前值（修改回显断言用）。"""
        return self.name_input.input_value()

    def description_value(self) -> str:
        """描述输入框当前值（修改回显断言用）。"""
        return self.description_input.input_value()

    # 供用例引用的文案常量
    REQUIRED_NAME_MSG = MSG_REQUIRED_TASK_NAME


class AnnotationDetailPage(BasePage):
    """标注任务详情页（/annotation/detail/:id）。"""

    # ------------------------------------------------------------------ #
    # 定位器 —— 任务信息
    # ------------------------------------------------------------------ #
    @property
    def back_button(self) -> Locator:
        return self.page.get_by_role("button", name="返回标注任务列表")

    @property
    def task_name(self) -> Locator:
        return self.page.locator(".annotation-info .name")

    @property
    def task_description(self) -> Locator:
        return self.page.locator(".annotation-info .description")

    @property
    def info_body(self) -> Locator:
        return self.page.locator(".annotation-info .annotation-info-body")

    # ------------------------------------------------------------------ #
    # 定位器 —— 标注集列表
    # ------------------------------------------------------------------ #
    @property
    def dataset_panel_title(self) -> Locator:
        return self.page.get_by_text("标注集列表")

    @property
    def create_dataset_button(self) -> Locator:
        return self.page.get_by_role("button", name="创建数据集")

    @property
    def delete_selected_button(self) -> Locator:
        return self.page.get_by_role("button", name="删除选中")

    @property
    def dataset_empty_text(self) -> Locator:
        return self.page.locator(".dataset-list").get_by_text("暂无数据")

    # ------------------------------------------------------------------ #
    # 初始化 / 操作
    # ------------------------------------------------------------------ #
    def wait_ready(self) -> "AnnotationDetailPage":
        expect(self.task_name).to_be_visible(timeout=settings.navigation_timeout_ms)
        expect(self.dataset_panel_title).to_be_visible()
        return self

    @allure.step("返回标注任务列表")
    def back_to_list(self) -> AnnotationListPage:
        self.back_button.click()
        self.wait_for_url(re.compile(r".*/annotation/list$"))
        return AnnotationListPage(self.page)

    # ------------------------------------------------------------------ #
    # 标注集（数据集）列表：增删改查
    # ------------------------------------------------------------------ #
    @property
    def dataset_items(self) -> Locator:
        """标注集条目。"""
        return self.page.locator(".dataset-list .dataset-item")

    @property
    def dataset_info_text(self) -> Locator:
        """右侧标注集详情信息区（名称 / 创建人 / 描述 / 标注人员 / 审核人员）。"""
        return self.page.locator(".dataset-info")

    @property
    def dataset_data_list_text(self) -> Locator:
        """详情区“数据列表”标题。"""
        return self.page.locator(".dataset-content-header .name")

    def dataset_item(self, name: str) -> Locator:
        """按名称定位标注集条目。"""
        return self.dataset_items.filter(has_text=name).first

    @allure.step("创建标注集：{name}")
    def create_dataset(self, name: str, description: str = "") -> None:
        """完整创建流程：打开弹窗 → 填写 → 提交 → 等待列表刷新。"""
        modal = self.open_create_dataset_modal()
        modal.fill(name, description)
        modal.submit()
        modal.wait_closed()
        self.wait_network_idle()

    @allure.step("修改标注集：{name}")
    def edit_dataset(self, name: str) -> AnnotationFormModal:
        item = self.dataset_item(name)
        item.hover()  # 条目操作按钮默认隐藏，悬浮后显示
        item.locator("button[title='修改']").click()
        modal = AnnotationFormModal(self.page, EDIT_MODAL_TITLE)
        modal.wait_opened()
        return modal

    @allure.step("删除标注集：{name}")
    def delete_dataset(self, name: str) -> None:
        item = self.dataset_item(name)
        item.hover()  # 条目操作按钮默认隐藏，悬浮后显示
        item.locator("button[title='删除']").click()
        self.confirm_popconfirm(button_text="确认")
        self.wait_network_idle()

    @allure.step("切换选中标注集：{name}")
    def select_dataset(self, name: str) -> None:
        """点击标注集条目，右侧详情联动切换。"""
        self.dataset_item(name).click()
        self.wait_network_idle()

    @allure.step("勾选标注集：{name}")
    def check_dataset(self, name: str) -> None:
        """勾选标注集条目复选框（用于删除选中）。"""
        item = self.dataset_item(name)
        item.hover()
        item.locator(".n-checkbox").first.click()

    @property
    def dataset_delete_selected_button(self) -> Locator:
        """标注集列表头部的“删除选中”按钮。"""
        return self.page.locator(".dataset-list .dataset-list-header button[title='删除选中']")

    @allure.step("删除选中的标注集")
    def delete_selected_datasets(self) -> None:
        self.dataset_delete_selected_button.click()
        self.confirm_popconfirm(button_text="确认")
        self.wait_network_idle()

    @property
    def dataset_filter_button(self) -> Locator:
        """标注集列表筛选按钮。"""
        return self.page.locator(".dataset-list .dataset-list-header").get_by_role("button", name=re.compile(r"^(筛选|已筛选)$"))

    @property
    def dataset_filter_popover(self) -> Locator:
        return self.page.locator(".n-popover").filter(has_text="数据集名称")

    @allure.step("按名称筛选标注集：{name}")
    def filter_datasets(self, name: str) -> None:
        self.dataset_filter_button.click()
        expect(self.dataset_filter_popover).to_be_visible()
        self.dataset_filter_popover.locator("input").first.fill(name)
        self.dataset_filter_popover.get_by_role("button", name="搜索").click()
        self.wait_network_idle()

    @allure.step("重置标注集筛选")
    def reset_dataset_filter(self) -> None:
        self.dataset_filter_button.click()
        expect(self.dataset_filter_popover).to_be_visible()
        self.dataset_filter_popover.get_by_role("button", name="重置").click()
        self.wait_network_idle()

    @allure.step("打开“从数据集导入”弹窗")
    def open_import_modal(self) -> "AnnotationDatasetImportModal":
        """打开标注集详情区的“从数据集导入”弹窗。"""
        self.page.get_by_role("button", name="从数据集导入").click()
        modal = AnnotationDatasetImportModal(self.page)
        modal.wait_opened()
        return modal

    @allure.step("打开创建数据集弹窗")
    def open_create_dataset_modal(self) -> "AnnotationFormModal":
        """打开创建数据集弹窗（表单规则与标注任务一致）。"""
        self.create_dataset_button.click()
        modal = AnnotationFormModal(self.page, CREATE_MODAL_TITLE)
        modal.wait_opened()
        return modal

    # ------------------------------------------------------------------ #
    # 状态读取
    # ------------------------------------------------------------------ #
    def info_item_value(self, label: str) -> str:
        """读取任务信息项的值（创建人 / 创建时间 / 成员）。"""
        item = self.info_body.locator(".info-item").filter(has=self.page.locator(".label", has_text=label)).first
        return item.locator(".value").inner_text().strip()

    def dataset_info_item_value(self, label: str) -> str:
        """读取标注集详情信息项的值（创建人 / 描述 / 标注人员 / 审核人员）。"""
        item = self.dataset_info_text.locator(".info-item").filter(has=self.page.locator(".label", has_text=label)).first
        return item.locator(".value").inner_text().strip()

    def dataset_data_count(self) -> int:
        """读取标注集“共N条”中的数据量。"""
        text = self.page.locator(".dataset-content-header").inner_text()
        match = re.search(r"共\s*(\d+)\s*条", text)
        return int(match.group(1)) if match else 0


class AnnotationDatasetImportModal(BasePage):
    """“从数据集导入数据”弹窗（标注集从课题影像数据集批量转换导入）。"""

    @property
    def root(self) -> Locator:
        return self.page.locator(".custom-modal").filter(
            has=self.page.locator(".n-card-header__main", has_text="从数据集导入数据")
        ).last

    @property
    def search_input(self) -> Locator:
        """数据集名称搜索框。"""
        return self.root.get_by_placeholder("数据集名称")

    @property
    def tree_nodes(self) -> Locator:
        """数据集树节点（文件夹 = 课题，叶子 = 数据集）。"""
        return self.root.locator(".n-tree-node")

    @property
    def start_button(self) -> Locator:
        return self.root.get_by_role("button", name="开始导入")

    @property
    def close_button(self) -> Locator:
        return self.root.get_by_role("button", name="关闭", exact=True)

    @property
    def tip_text(self) -> Locator:
        return self.root.get_by_text("导入需要转换数据格式")

    def wait_opened(self) -> "AnnotationDatasetImportModal":
        expect(self.root).to_be_visible()
        return self

    def wait_closed(self, timeout: int = 60_000) -> None:
        expect(self.root).to_be_hidden(timeout=timeout)

    @allure.step("勾选第一个数据集节点")
    def check_first_node(self) -> None:
        """勾选数据集中第一个节点（级联勾选其下数据集）。"""
        expect(self.tree_nodes.first).to_be_visible()
        self.tree_nodes.first.locator(".n-checkbox").click()

    @allure.step("点击开始导入")
    def start_import(self) -> None:
        """点击“开始导入”，等待弹窗关闭（导入任务已提交）。"""
        self.start_button.click()
        self.wait_closed()

    def dataset_options(self) -> list[str]:
        """当前树中可选节点文本（用于判断是否有可用数据集）。"""
        return [text.strip() for text in self.tree_nodes.all_inner_texts() if text.strip()]
