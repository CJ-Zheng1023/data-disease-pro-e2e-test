# -*- coding: utf-8 -*-
"""临床试验（组学分析）模块页面对象。

覆盖：

- :class:`AnalysisFormModal` —— 临床试验创建 / 修改弹窗；
- :class:`FieldConfigModal` —— 字段配置弹窗（添加系统/自定义字段）；
- :class:`AnalysisDetailPage` —— 临床试验详情（临床数据增删改、单元格编辑、
  批量确认、发布/取消发布、填充率统计等）。

列表区域（创建/修改/删除/发布/进入）的操作方法挂在
:class:`src.pages.research_page.ResearchDetailPage` 上（其“临床试验”页签）。
"""

from __future__ import annotations

import re

import allure
from playwright.sync_api import Locator
from playwright.sync_api import expect

from config.settings import settings
from src.common.base_page import BasePage
from src.common.logger import get_logger

logger = get_logger(__name__)

CREATE_MODAL_TITLE = "创建"
EDIT_MODAL_TITLE = "修改"
REQUIRED_ANALYSIS_NAME_MSG = "请输入临床试验名称"
REQUIRED_ANALYSIS_DATA_MSG = "请输入名称"
INCOMPLETE_FIELD_CONFIG_MSG = "字段配置填写不完整"


class AnalysisFormModal(BasePage):
    """临床试验创建 / 修改弹窗。"""

    def __init__(self, page, title: str) -> None:
        super().__init__(page)
        self.title = title

    @property
    def root(self) -> Locator:
        return self.page.locator(".custom-modal").filter(
            has=self.page.locator(".n-card-header__main", has_text=re.compile(rf"^{self.title}$"))
        ).last

    def _field(self, label: str) -> Locator:
        return self.root.locator(".n-form-item").filter(has=self.page.locator(".n-form-item-label", has_text=label)).first

    @property
    def name_input(self) -> Locator:
        return self._field("名称").locator("input").first

    @property
    def description_input(self) -> Locator:
        return self._field("描述").locator("textarea").first

    @property
    def ok_button(self) -> Locator:
        return self.root.get_by_role("button", name="确定", exact=True)

    @property
    def close_button(self) -> Locator:
        return self.root.get_by_role("button", name="关闭", exact=True)

    def wait_opened(self) -> "AnalysisFormModal":
        expect(self.root).to_be_visible()
        return self

    def wait_closed(self) -> None:
        expect(self.root).to_be_hidden()

    @allure.step("填写临床试验表单：{name}")
    def fill(self, name: str = "", description: str = "") -> "AnalysisFormModal":
        if name:
            self.name_input.fill(name)
        if description:
            self.description_input.fill(description)
        return self

    @allure.step("提交临床试验表单")
    def submit(self) -> None:
        self.ok_button.click()

    @allure.step("关闭临床试验弹窗")
    def close(self) -> None:
        self.close_button.click()
        self.wait_closed()

    def form_feedback(self) -> list[str]:
        return self.form_feedback_texts(self.root)

    def name_value(self) -> str:
        return self.name_input.input_value()

    def description_value(self) -> str:
        return self.description_input.input_value()

    REQUIRED_NAME_MSG = REQUIRED_ANALYSIS_NAME_MSG


class FieldConfigModal(BasePage):
    """字段配置弹窗（列表页与详情页共用同一组件）。"""

    @property
    def root(self) -> Locator:
        return self.page.locator(".custom-modal").filter(
            has=self.page.locator(".n-card-header__main", has_text="字段配置")
        ).last

    @property
    def empty_text(self) -> Locator:
        return self.root.get_by_text("请添加系统字段或自定义字段")

    @property
    def add_system_button(self) -> Locator:
        return self.root.get_by_role("button", name="添加系统字段").first

    @property
    def add_custom_button(self) -> Locator:
        return self.root.get_by_role("button", name="添加自定义字段").first

    @property
    def rows(self) -> Locator:
        """字段配置表格行（不含表头）。"""
        return self.root.locator(".field-config-table .tr:not(.header)")

    @property
    def ok_button(self) -> Locator:
        return self.root.get_by_role("button", name="确定", exact=True)

    @property
    def close_button(self) -> Locator:
        return self.root.get_by_role("button", name="关闭", exact=True)

    def wait_opened(self) -> "FieldConfigModal":
        expect(self.root).to_be_visible()
        return self

    def wait_closed(self) -> None:
        expect(self.root).to_be_hidden()

    @allure.step("添加自定义字段：{field_name}")
    def add_custom_field(self, field_name: str) -> "FieldConfigModal":
        """点击“添加自定义字段”，在新增行中填写字段名。"""
        self.add_custom_button.click()
        row = self.rows.last
        expect(row).to_be_visible()
        row.locator("input").first.fill(field_name)
        return self

    @allure.step("提交字段配置")
    def submit(self) -> None:
        self.ok_button.click()

    @allure.step("关闭字段配置弹窗")
    def close(self) -> None:
        self.close_button.click()
        self.wait_closed()

    def custom_field_names(self) -> list[str]:
        """读取当前所有自定义字段名称（行内输入框的值）。"""
        values = self.rows.locator("input").evaluate_all("els => els.map(el => el.value)")
        return [value.strip() for value in values if value and value.strip()]


class AnalysisDetailPage(BasePage):
    """临床试验详情页（/research/detail/:rid/analysis/detail/:aid）。"""

    # ------------------------------------------------------------------ #
    # 定位器 —— 页头 / 结构
    # ------------------------------------------------------------------ #
    @property
    def back_button(self) -> Locator:
        return self.page.get_by_role("button", name="返回临床试验列表")

    @property
    def analysis_name(self) -> Locator:
        return self.page.locator(".analysis-detail-info .name")

    @property
    def analysis_description(self) -> Locator:
        return self.page.locator(".analysis-detail-info .description")

    @property
    def table_panel(self) -> Locator:
        """临床数据表格区域。"""
        return self.page.locator(".analysis-detail-table")

    @property
    def stat_panel(self) -> Locator:
        """右侧“填充率统计”面板。"""
        return self.page.locator(".analysis-detail-stat")

    @property
    def empty_fields_text(self) -> Locator:
        return self.table_panel.get_by_text("暂无字段")

    @property
    def add_row_button(self) -> Locator:
        return self.table_panel.get_by_role("button", name="添加一行")

    @property
    def delete_selected_button(self) -> Locator:
        return self.table_panel.get_by_role("button", name="删除选中")

    @property
    def publish_button(self) -> Locator:
        return self.table_panel.get_by_role("button", name="发布", exact=True)

    @property
    def unpublish_button(self) -> Locator:
        return self.table_panel.get_by_role("button", name="取消发布")

    @property
    def field_config_button(self) -> Locator:
        """空字段状态下的“字段配置”按钮。"""
        return self.table_panel.get_by_role("button", name="字段配置")

    @property
    def data_rows(self) -> Locator:
        """数据表格中的行。"""
        return self.page.locator(".analysis-detail-table-list .n-data-table-tbody .n-data-table-tr")

    @property
    def row_delete_buttons(self) -> Locator:
        """数据行内的删除按钮（发布后隐藏）。"""
        return self.table_panel.locator("button[title='删除']")

    @property
    def row_audit_buttons(self) -> Locator:
        """数据行内的“批量确认”按钮（发布后隐藏）。"""
        return self.table_panel.locator("button[title='批量确认']")

    def cell_edit_icon(self, index: int = 0, column: int = 1) -> Locator:
        """单元格“编辑”图标定位器（悬浮单元格后可见；发布后不渲染）。"""
        cell = self.row(index).locator(".n-data-table-td").nth(column)
        cell.hover()
        return cell.locator("i[title='编辑']")

    def cell_edit_enabled(self, index: int = 0, column: int = 1) -> bool:
        """点击单元格后是否进入编辑态（出现输入框即视为可编辑）。

        发布后的数据列表点击单元格应无任何编辑响应；取消发布后点击应出现输入框。
        进入编辑态时会失焦退出（值未变化不会触发保存）。
        """
        cell = self.row(index).locator(".n-data-table-td").nth(column)
        cell.click()
        editing = self.is_visible(cell.locator("input"), timeout=2_000)
        if editing:
            # 点击表格标题使其失焦取消编辑（值未修改不会保存）
            self.table_panel.locator(".caption").click()
        return editing

    @property
    def next_button(self) -> Locator:
        """信息区“下一个”导航按钮（title 形如“下一个：xxx”）。"""
        return self.page.locator(".analysis-detail-info button[title^='下一个']")

    @property
    def previous_button(self) -> Locator:
        """信息区“上一个”导航按钮（title 形如“上一个：xxx”）。"""
        return self.page.locator(".analysis-detail-info button[title^='上一个']")

    @property
    def attr_config_button(self) -> Locator:
        """自定义字段列头“属性配置”按钮。"""
        return self.table_panel.locator("button[title='属性配置']").first

    # ------------------------------------------------------------------ #
    # 初始化
    # ------------------------------------------------------------------ #
    def wait_ready(self) -> "AnalysisDetailPage":
        expect(self.analysis_name).to_be_visible(timeout=settings.navigation_timeout_ms)
        expect(self.table_panel).to_be_visible()
        return self

    # ------------------------------------------------------------------ #
    # 操作 —— 字段配置 / 添加行
    # ------------------------------------------------------------------ #
    @allure.step("打开字段配置弹窗")
    def open_field_config(self) -> FieldConfigModal:
        """点击空字段状态下的“字段配置”按钮并等待弹窗打开。"""
        self.field_config_button.click()
        modal = FieldConfigModal(self.page)
        modal.wait_opened()
        return modal

    @allure.step("打开“添加一行”弹窗")
    def open_add_row_modal(self) -> "AnalysisFormModal":
        self.add_row_button.click()
        modal = AnalysisFormModal(self.page, CREATE_MODAL_TITLE)
        modal.wait_opened()
        return modal

    @allure.step("填写并提交一行数据")
    def add_row_with_values(self, values: dict[str, str]) -> None:
        """在“添加一行”弹窗中按“字段名 -> 值”填写并提交。"""
        modal = self.open_add_row_modal()
        for field_name, value in values.items():
            form_item = modal.root.locator(".n-form-item").filter(has_text=field_name).first
            form_item.locator("input").first.fill(value)
        modal.submit()
        modal.wait_closed()

    # ------------------------------------------------------------------ #
    # 操作 —— 数据行
    # ------------------------------------------------------------------ #
    def row(self, index: int = 0) -> Locator:
        """第 index 行数据。"""
        return self.data_rows.nth(index)

    @allure.step("编辑第 {index} 行第 {column} 列单元格为：{value}")
    def edit_cell(self, value: str, index: int = 0, column: int = 1) -> None:
        """点击单元格编辑图标，写入新值并失焦保存。

        :param column: 数据列序号（0 为选择列，1 为第一个字段列）。
        """
        cell = self.row(index).locator(".n-data-table-td").nth(column)
        cell.hover()
        cell.locator("i[title='编辑']").first.click()
        cell.locator("input").first.fill(value)
        # 点击表格标题区域使输入框失焦，触发保存
        self.table_panel.locator(".caption").click()
        self.page.wait_for_timeout(300)

    @allure.step("批量确认第 {index} 行数据")
    def audit_row(self, index: int = 0) -> None:
        self.row(index).locator("button[title='批量确认']").click()
        self.confirm_popconfirm(button_text="确认")

    @allure.step("删除第 {index} 行数据")
    def delete_row(self, index: int = 0) -> None:
        self.row(index).locator("button[title='删除']").click()
        self.confirm_popconfirm(button_text="确认")

    @allure.step("勾选第 {index} 行")
    def check_row(self, index: int = 0) -> None:
        self.row(index).locator(".n-checkbox").first.click()

    @allure.step("删除选中数据")
    def delete_selected(self) -> None:
        self.delete_selected_button.click()
        self.confirm_popconfirm(button_text="确认")

    # ------------------------------------------------------------------ #
    # 操作 —— 导航 / 属性配置 / 修改记录 / 患者全景数据
    # ------------------------------------------------------------------ #
    @allure.step("跳转到下一条临床试验")
    def go_next(self) -> str:
        """点击“下一个”，等待标题切换为下一条名称，返回新名称。"""
        title = self.next_button.get_attribute("title") or ""
        next_name = title.split("：", 1)[-1]
        self.next_button.click()
        expect(self.analysis_name).to_have_text(next_name, timeout=15_000)
        return next_name

    @allure.step("跳转到上一条临床试验")
    def go_previous(self) -> str:
        """点击“上一个”，等待标题切换为上一条名称，返回新名称。"""
        title = self.previous_button.get_attribute("title") or ""
        previous_name = title.split("：", 1)[-1]
        self.previous_button.click()
        expect(self.analysis_name).to_have_text(previous_name, timeout=15_000)
        return previous_name

    @allure.step("修改字段属性描述：{description}")
    def update_field_attribute(self, field_name: str, description: str) -> None:
        """打开字段“属性配置”→ 填写描述 → 确定 → 选择“保留原有数据”。

        说明：保存时组件会询问“清空原有数据 / 保留原有数据”，
        本用例选择“保留”以避免影响已有数据行。
        """
        self.attr_config_button.click()
        modal = self.page.locator(".custom-modal").filter(
            has=self.page.locator(".n-card-header__main", has_text=f"{field_name}属性配置")
        ).last
        expect(modal).to_be_visible()
        description_input = modal.locator(".n-form-item").filter(
            has=self.page.locator(".n-form-item-label", has_text="字段描述")
        ).locator("textarea").first
        description_input.fill(description)
        modal.get_by_role("button", name="确定", exact=True).click()
        expect(modal).to_be_hidden()
        # 数据处置确认弹窗：保留原有数据
        dialog = self.page.locator(".n-dialog").last
        expect(dialog).to_be_visible()
        dialog.get_by_role("button", name="保留", exact=True).click()
        self.page.wait_for_timeout(300)

    def field_attribute_description(self, field_name: str) -> str:
        """打开属性配置弹窗读取字段描述后关闭。"""
        self.attr_config_button.click()
        modal = self.page.locator(".custom-modal").filter(
            has=self.page.locator(".n-card-header__main", has_text=f"{field_name}属性配置")
        ).last
        expect(modal).to_be_visible()
        description_input = modal.locator(".n-form-item").filter(
            has=self.page.locator(".n-form-item-label", has_text="字段描述")
        ).locator("textarea").first
        value = description_input.input_value()
        modal.get_by_role("button", name="关闭", exact=True).click()
        expect(modal).to_be_hidden()
        return value

    @allure.step("查看单元格修改记录")
    def open_cell_update_log(self, index: int = 0, column: int = 1) -> Locator:
        """悬浮单元格 → 点击“修改记录”图标 → 返回记录气泡。"""
        cell = self.row(index).locator(".n-data-table-td").nth(column)
        cell.hover()
        cell.locator("i[title='修改记录']").first.click()
        popover = self.page.locator(".n-popover").filter(has=self.page.locator(".n-timeline, .n-empty")).last
        expect(popover).to_be_visible()
        return popover

    @allure.step("打开患者全景数据弹窗")
    def open_patient_overview(self, index: int = 0) -> Locator:
        """点击行内“患者全景数据”按钮，打开全景数据弹窗。"""
        self.row(index).locator("button[title='患者全景数据']").click()
        modal = self.page.locator(".custom-modal").filter(
            has=self.page.locator(".n-card-header__main", has_text="全景数据")
        ).last
        expect(modal).to_be_visible()
        return modal

    @allure.step("关闭弹窗")
    def close_modal(self, modal: Locator) -> None:
        modal.get_by_role("button", name="关闭", exact=True).click()
        expect(modal).to_be_hidden()

    @allure.step("发布临床试验")
    def publish(self) -> None:
        self.publish_button.click()
        self.confirm_popconfirm(button_text="确认")
        self.wait_network_idle()

    @allure.step("取消发布临床试验")
    def unpublish(self) -> None:
        self.unpublish_button.click()
        self.confirm_popconfirm(button_text="确认")
        self.wait_network_idle()

    # ------------------------------------------------------------------ #
    # 状态读取
    # ------------------------------------------------------------------ #
    def data_count(self) -> int:
        """读取“共N条数据”中的数量；无字段时返回 0。"""
        if self.is_visible(self.empty_fields_text, timeout=1_000):
            return 0
        text = self.table_panel.locator(".caption .name").first.inner_text()
        match = re.search(r"共\s*(\d+)\s*条数据", text)
        return int(match.group(1)) if match else 0

    def first_row_text(self) -> str:
        return self.row(0).inner_text()
