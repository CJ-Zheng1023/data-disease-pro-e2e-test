# -*- coding: utf-8 -*-
"""专病检索模块页面对象。

覆盖两个页面与一个组件：

- :class:`DatabaseListPage`  —— 专病库列表（搜索、进入、查看统计）；
- :class:`DatabaseStatModal` —— 列表页“查询统计”弹窗；
- :class:`DatabaseDetailPage` —— 专病库详情（患者视图/影像视图、全量数据、
  患者编号搜索、筛选面板、表格/时间线模式）。

说明：本模块用例均为只读校验，不创建/删除任何数据。
"""

from __future__ import annotations

import re

import allure
from playwright.sync_api import Locator
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import expect

from config.constants import ROUTE_DATABASE_LIST
from config.settings import settings
from src.common.base_page import BasePage
from src.common.logger import get_logger

logger = get_logger(__name__)


class DatabaseListPage(BasePage):
    """专病库列表页（/database/list）。"""

    path = ROUTE_DATABASE_LIST

    # ------------------------------------------------------------------ #
    # 定位器
    # ------------------------------------------------------------------ #
    @property
    def search_input(self) -> Locator:
        return self.page.get_by_placeholder("请输入专病库名称")

    @property
    def search_button(self) -> Locator:
        return self.page.get_by_role("button", name="查询", exact=True)

    @property
    def count_tag(self) -> Locator:
        """统计标签，如“共2个专病库”。"""
        return self.page.get_by_text(re.compile(r"共\s*\d+\s*个专病库"))

    @property
    def cards(self) -> Locator:
        """所有专病库卡片。"""
        return self.page.locator(".database-card")

    @property
    def footer_text(self) -> Locator:
        """底部分页说明，如“共 2 条记录，每页显示 12 条数据”。"""
        return self.page.get_by_text(re.compile(r"共\s*\d+\s*条记录"))

    def card(self, name: str) -> Locator:
        """按名称精确定位专病库卡片。"""
        return self.cards.filter(has=self.page.locator(".name", has_text=name)).first

    def first_card_name(self) -> str:
        """读取第一张专病库卡片的名称（用例用于动态选择存量数据）。"""
        return self.cards.first.locator(".name").inner_text().strip()

    def card_names(self) -> list[str]:
        """读取当前页所有专病库名称。"""
        return [text.strip() for text in self.cards.locator(".name").all_inner_texts() if text.strip()]

    # ------------------------------------------------------------------ #
    # 操作
    # ------------------------------------------------------------------ #
    def open(self) -> "DatabaseListPage":
        self.goto(self.path)
        expect(self.search_input).to_be_visible()
        return self

    @allure.step("搜索专病库：{name}")
    def search(self, name: str) -> "DatabaseListPage":
        """输入名称并点击查询，等待列表刷新。"""
        self.search_input.fill(name)
        self.search_button.click()
        self.wait_network_idle()
        return self

    def open_stat_modal(self, name: str) -> "DatabaseStatModal":
        """点击指定专病库卡片的“查看统计”按钮，返回统计弹窗对象。"""
        self.card(name).get_by_role("button", name="查看统计").click()
        modal = DatabaseStatModal(self.page)
        modal.wait_opened()
        return modal

    def enter_database(self, name: str) -> "DatabaseDetailPage":
        """点击指定专病库卡片的“进入”按钮，跳转详情页。"""
        self.card(name).get_by_role("button", name="进入").click()
        self.wait_for_url(re.compile(r".*/database/detail/\d+$"))
        detail = DatabaseDetailPage(self.page)
        detail.wait_ready()
        return detail


class DatabaseStatModal(BasePage):
    """“查询统计”弹窗（列表页 → 查看统计）。"""

    # ------------------------------------------------------------------ #
    # 定位器
    # ------------------------------------------------------------------ #
    @property
    def root(self) -> Locator:
        return self.page.locator(".custom-modal").filter(
            has=self.page.locator(".n-card-header__main", has_text="查询统计")
        ).last

    @property
    def question_tabs(self) -> Locator:
        """检查类型（问题）分页签列表，如：生化全套 / CT检查 …。"""
        return self.root.locator(".stat-picker .list-item")

    @property
    def patient_total(self) -> Locator:
        """患者总数数值。"""
        return self.root.locator(".stat-value-item.primary .number")

    @property
    def case_total(self) -> Locator:
        """病例总数数值。"""
        return self.root.locator(".stat-value-item.success .number")

    @property
    def field_count_text(self) -> Locator:
        """字段填充率统计文案，如“共 24 个字段”。"""
        return self.root.locator(".field-stat-header .sub")

    @property
    def field_items(self) -> Locator:
        """字段填充率条目（字段名 + 百分比）。"""
        return self.root.locator(".field-stat .stat-item")

    # ------------------------------------------------------------------ #
    # 操作
    # ------------------------------------------------------------------ #
    def wait_opened(self) -> "DatabaseStatModal":
        expect(self.root).to_be_visible()
        # 等分页签渲染完成（数据加载完成）
        expect(self.question_tabs.first).to_be_visible()
        return self

    @allure.step("切换检查类型：{name}")
    def select_question(self, name: str) -> None:
        tab = self.question_tabs.filter(has_text=name).first
        tab.scroll_into_view_if_needed()
        tab.click()
        self.wait_network_idle()

    @allure.step("关闭查询统计弹窗")
    def close(self) -> None:
        self.root.get_by_role("button", name="关闭", exact=True).click()
        expect(self.root).to_be_hidden()

    # ------------------------------------------------------------------ #
    # 状态读取
    # ------------------------------------------------------------------ #
    def question_names(self) -> list[str]:
        """返回全部检查类型名称。"""
        return [text.strip() for text in self.question_tabs.all_inner_texts() if text.strip()]

    def patient_total_value(self) -> int:
        """患者总数（整数）。"""
        return int(self.patient_total.inner_text().replace(",", "").strip())

    def case_total_value(self) -> int:
        """病例总数（整数）。"""
        return int(self.case_total.inner_text().replace(",", "").strip())

    def field_names(self) -> list[str]:
        """字段填充率条目中的字段名列表。"""
        return [text.strip() for text in self.field_items.locator(".label").all_inner_texts() if text.strip()]


class DatabaseDetailPage(BasePage):
    """专病库详情页（/database/detail/:id）。"""

    # ------------------------------------------------------------------ #
    # 定位器 —— 页头 / 视图切换
    # ------------------------------------------------------------------ #
    @property
    def back_button(self) -> Locator:
        return self.page.get_by_role("button", name="返回专病库列表")

    @property
    def database_name(self) -> Locator:
        """页头展示的专病库名称。"""
        return self.page.locator(".database-info .caption .name")

    @property
    def database_description(self) -> Locator:
        """页头展示的专病库描述。"""
        return self.page.locator(".database-info .description")

    @property
    def stat_patient_item(self) -> Locator:
        """页头“患者数”统计项。"""
        return self.page.locator(".database-info").get_by_text("患者数")

    @property
    def stat_case_item(self) -> Locator:
        """页头“病例数”统计项。"""
        return self.page.locator(".database-info").get_by_text("病例数")

    @property
    def patient_view_tab(self) -> Locator:
        return self.page.locator(".n-tabs-tab").filter(has_text="患者视图")

    @property
    def image_view_tab(self) -> Locator:
        return self.page.locator(".n-tabs-tab").filter(has_text="影像视图")

    # ------------------------------------------------------------------ #
    # 定位器 —— 患者列表（左侧）
    # ------------------------------------------------------------------ #
    @property
    def patient_search_input(self) -> Locator:
        return self.page.get_by_placeholder("搜索患者编号")

    @property
    def patient_items(self) -> Locator:
        return self.page.locator(".patient-item")

    @property
    def patient_empty_text(self) -> Locator:
        return self.page.locator(".sider").get_by_text("暂无数据")

    @property
    def patient_total_text(self) -> Locator:
        """患者总数文案，如“共10人”。"""
        return self.page.get_by_text(re.compile(r"共\s*\d+\s*人"))

    @property
    def filter_button(self) -> Locator:
        """筛选按钮（触发筛选浮层，执行后变为“已筛选”）。"""
        return self.page.get_by_role("button", name=re.compile(r"^(筛选|已筛选)$"))

    @property
    def filter_popover(self) -> Locator:
        return self.page.locator(".n-popover").filter(has_text="添加筛选条件")

    @property
    def import_button(self) -> Locator:
        """患者列表操作区的“导入”按钮（触发“导入到课题”浮层）。"""
        return self.page.locator(".sider-header").get_by_role("button", name="导入", exact=True)

    @property
    def import_popover(self) -> Locator:
        """“导入到课题”浮层。"""
        return self.page.locator(".n-popover").filter(has_text="导入到课题")

    # ------------------------------------------------------------------ #
    # 定位器 —— 全景数据（右侧）
    # ------------------------------------------------------------------ #
    @property
    def table_mode_button(self) -> Locator:
        return self.page.locator(".button-radio-item").filter(has_text="表格模式")

    @property
    def timeline_mode_button(self) -> Locator:
        return self.page.locator(".button-radio-item").filter(has_text="时间线模式")

    @property
    def table_items(self) -> Locator:
        """表格模式下的数据分组（人口学 / CT检查 / 病理 …）。"""
        return self.page.locator(".table-item")

    @property
    def timeline_items(self) -> Locator:
        """时间线模式下的数据节点。"""
        return self.page.locator(".timeline-item")

    # ------------------------------------------------------------------ #
    # 初始化
    # ------------------------------------------------------------------ #
    def wait_ready(self) -> "DatabaseDetailPage":
        """等待详情页关键区域渲染完成（含患者列表首屏数据）。"""
        expect(self.patient_search_input).to_be_visible(timeout=settings.navigation_timeout_ms)
        expect(self.table_mode_button).to_be_visible()
        self.wait_patients_loaded()
        return self

    def wait_patients_loaded(self, timeout: int | None = None) -> None:
        """等待患者列表加载完成。

        判定依据：出现患者条目，或出现分页统计（`.sider-footer`）。
        对于确无患者的空库，等待超时后静默返回，由用例自行决定是否跳过。
        """
        try:
            self.page.wait_for_selector(".patient-item, .sider-footer", timeout=timeout or settings.navigation_timeout_ms)
        except PlaywrightTimeoutError:
            logger.warning("等待患者列表加载超时（可能为空库）：%s", self.current_url)

    # ------------------------------------------------------------------ #
    # 操作 —— 患者列表
    # ------------------------------------------------------------------ #
    @allure.step("搜索患者编号：{patient_no}")
    def search_patient(self, patient_no: str) -> "DatabaseDetailPage":
        """按患者编号搜索（输入框自带 500ms 防抖，等待列表刷新）。"""
        self.patient_search_input.fill(patient_no)
        self.wait_network_idle()
        return self

    def wait_patient_search_applied(self, patient_no: str, timeout: int | None = None) -> None:
        """等待患者编号搜索生效：列表非空且所有结果均包含该编号。"""
        self.page.wait_for_function(
            "(no) => {"
            "  const items = [...document.querySelectorAll('.patient-item')];"
            "  return items.length > 0 && items.every(el => el.innerText.includes(no));"
            "}",
            arg=patient_no,
            timeout=timeout or settings.default_timeout_ms,
        )

    def wait_table_data_loaded(self, timeout: int | None = None) -> None:
        """等待全景数据（表格模式）加载完成。"""
        expect(self.page.locator(".table-item").first).to_be_visible(timeout=timeout or settings.default_timeout_ms)

    @allure.step("清空患者编号搜索")
    def clear_patient_search(self) -> "DatabaseDetailPage":
        self.patient_search_input.fill("")
        self.wait_network_idle()
        return self

    @allure.step("点击患者：{name}")
    def select_patient_by_name(self, name: str) -> None:
        """点击患者条目，右侧加载该患者全景数据。"""
        self.patient_items.filter(has_text=name).first.click()
        self.wait_network_idle()

    @allure.step("打开筛选面板")
    def open_filter(self) -> None:
        self.filter_button.click()
        expect(self.filter_popover).to_be_visible()

    @allure.step("关闭筛选面板")
    def close_filter(self) -> None:
        self.filter_popover.get_by_title("关闭").click()
        expect(self.filter_popover).to_be_hidden()

    # ------------------------------------------------------------------ #
    # 操作 —— 筛选执行（条件构建 → 搜索）
    # ------------------------------------------------------------------ #
    @allure.step("添加一条筛选条件")
    def add_filter_condition(self) -> None:
        self.filter_popover.get_by_role("button", name="添加筛选条件").click()
        expect(self.filter_popover.locator(".condition-item").first).to_be_visible()

    @allure.step("选择筛选字段：{group_tag}/{field_tag}")
    def select_filter_field(self, group_tag: str, field_tag: str) -> None:
        """通过级联选择器按“分组 → 字段”两级选择筛选字段。"""
        row = self.filter_popover.locator(".condition-item").first
        self.select_cascader_path(row.locator(".field .n-base-selection"), group_tag, field_tag)

    # ------------------------------------------------------------------ #
    # 操作 —— 筛选模板（保存 / 应用 / 删除）
    # ------------------------------------------------------------------ #
    @property
    def save_template_button(self) -> Locator:
        """筛选面板“保存为模板”按钮（需先有筛选条件）。"""
        return self.filter_popover.get_by_role("button", name="保存为模板")

    @property
    def template_panel(self) -> Locator:
        """筛选面板中的“检索模板”区域。"""
        return self.filter_popover.locator(".template")

    def template_item(self, name: str) -> Locator:
        """按名称定位检索模板条目。"""
        return self.template_panel.locator(".template-item").filter(has_text=name).first

    @allure.step("保存筛选模板：{name}")
    def save_filter_template(self, name: str) -> None:
        """筛选面板 → 保存为模板 → 填写名称 → 确定。"""
        self.save_template_button.click()
        modal = self.page.locator(".custom-modal").filter(
            has=self.page.locator(".n-card-header__main", has_text="保存模板")
        ).last
        expect(modal).to_be_visible()
        modal.get_by_placeholder("请输入模板名称").fill(name)
        modal.get_by_role("button", name="确定", exact=True).click()
        expect(modal).to_be_hidden()

    @allure.step("展开检索模板列表")
    def expand_template_list(self) -> None:
        """点击“检索模板”标题展开模板列表（默认折叠）。"""
        header = self.template_panel.locator(".template-header")
        if not self.template_panel.get_attribute("class") or "extended" not in (self.template_panel.get_attribute("class") or ""):
            header.click()
        expect(self.template_panel.locator(".template-body")).to_be_visible()

    @allure.step("应用检索模板：{name}")
    def apply_filter_template(self, name: str) -> None:
        """展开模板列表 → 点击“应用”（条件回填并自动搜索）。"""
        self.expand_template_list()
        item = self.template_item(name)
        expect(item).to_be_visible()
        item.get_by_role("button", name="应用").click()
        self.wait_network_idle()

    @allure.step("删除检索模板：{name}")
    def delete_filter_template(self, name: str) -> None:
        """展开模板列表 → 删除 → 气泡确认。"""
        self.expand_template_list()
        item = self.template_item(name)
        item.get_by_role("button", name="删除").click()
        self.confirm_popconfirm(button_text="确认")
        self.wait_network_idle()

    @allure.step("选择筛选运算符：{op_label}")
    def select_filter_operator(self, op_label: str = "等于") -> None:
        self.select_dropdown_option(self.filter_popover.locator(".condition-item .operation .n-base-selection").first, op_label)

    @allure.step("填写筛选值：{value}")
    def fill_filter_value(self, value: str) -> None:
        """在筛选值输入框中填写文本/数字（文本、数字、日期型字段）。"""
        value_input = self.filter_popover.locator(".condition-item .value input").first
        value_input.fill(value)

    @allure.step("选择筛选项值（下拉型字段）")
    def select_filter_value_option(self, option_text: str | None = None) -> None:
        select = self.filter_popover.locator(".condition-item .value .n-base-selection").first
        select.click()
        menu = self.page.locator(".n-base-select-menu").last
        if option_text:
            option = menu.locator(".n-base-select-option").filter(has_text=option_text).first
        else:
            option = menu.locator(".n-base-select-option").first
        expect(option).to_be_visible()
        option.click()

    @allure.step("执行筛选搜索")
    def click_filter_search(self) -> None:
        self.filter_popover.get_by_role("button", name=re.compile(r"^搜索$")).click()
        self.wait_network_idle()

    @allure.step("重置筛选条件并搜索")
    def reset_filter(self) -> None:
        """打开筛选面板 → 重置条件 → 搜索（恢复全量列表）。"""
        self.open_filter()
        self.filter_popover.get_by_role("button", name="重置").click()
        self.click_filter_search()

    def filter_searched(self) -> bool:
        """当前列表是否处于已筛选状态（筛选按钮变为“已筛选”）。"""
        return self.is_visible(self.page.get_by_role("button", name="已筛选"), timeout=2_000)

    # ------------------------------------------------------------------ #
    # 操作 —— 导入患者到课题
    # ------------------------------------------------------------------ #
    @allure.step("勾选第 {index} 位患者")
    def check_patient(self, index: int = 0) -> None:
        """勾选患者列表中的复选框（用于导入/排除等批量操作）。"""
        self.patient_items.nth(index).locator(".n-checkbox").click()

    @allure.step("打开导入面板并选择课题：{research_name}")
    def open_import_and_select_research(self, research_name: str) -> None:
        """点击“导入”→ 在“导入到课题”浮层中选择目标课题。"""
        self.import_button.click()
        expect(self.import_popover).to_be_visible()
        research_select = self.import_popover.locator(".n-select").first
        self.select_dropdown_option(research_select, research_name)

    @allure.step("导入选中患者")
    def click_import_selected(self) -> None:
        """点击“导入选中(N)”，等待浮层关闭（成功标志）。"""
        self.import_popover.get_by_role("button", name=re.compile(r"^导入选中")).click()
        expect(self.import_popover).to_be_hidden(timeout=30_000)

    def import_selected_patients_to_research(self, research_name: str) -> None:
        """完整导入流程：勾选第一位患者 → 选择课题 → 导入选中。"""
        self.check_patient(0)
        self.open_import_and_select_research(research_name)
        self.click_import_selected()

    # ------------------------------------------------------------------ #
    # 操作 —— 视图切换
    # ------------------------------------------------------------------ #
    @allure.step("切换到影像视图")
    def switch_to_image_view(self) -> None:
        self.image_view_tab.click()

    @allure.step("切换到患者视图")
    def switch_to_patient_view(self) -> None:
        self.patient_view_tab.click()

    @allure.step("切换全景数据为时间线模式")
    def switch_to_timeline_mode(self) -> None:
        self.timeline_mode_button.click()

    @allure.step("切换全景数据为表格模式")
    def switch_to_table_mode(self) -> None:
        self.table_mode_button.click()

    # ------------------------------------------------------------------ #
    # 操作 —— 影像视图（模态页签 / 影像数据筛选 / 导入到数据集）
    # ------------------------------------------------------------------ #
    @property
    def image_panel(self) -> Locator:
        return self.page.locator(".image-data")

    @property
    def image_data_rows(self) -> Locator:
        """影像数据表格行。"""
        return self.image_panel.locator(".n-data-table-tbody .n-data-table-tr")

    @property
    def image_view_filter_button(self) -> Locator:
        """影像视图的筛选按钮。"""
        return self.image_panel.get_by_role("button", name=re.compile(r"^(筛选|已筛选)$"))

    @property
    def image_view_filter_popover(self) -> Locator:
        return self.page.locator(".n-popover").filter(has_text="添加筛选条件")

    @property
    def import_to_dataset_button(self) -> Locator:
        """影像视图“导入”按钮（需先勾选影像数据）。"""
        return self.image_panel.get_by_role("button", name="导入", exact=True)

    @property
    def import_to_dataset_popover(self) -> Locator:
        return self.page.locator(".n-popover").filter(has_text="导入到数据集")

    def image_modality_names(self) -> list[str]:
        """影像视图的模态页签名称（CT / MR / PETCT …）。"""
        return [text.strip() for text in self.image_panel.locator(".n-tabs-tab").all_inner_texts() if text.strip()]

    @allure.step("切换影像模态：{name}")
    def switch_image_modality(self, name: str) -> None:
        self.image_panel.locator(".n-tabs-tab").filter(has_text=name).first.click()
        self.wait_network_idle()

    @allure.step("勾选第 {index} 条影像数据")
    def check_image_row(self, index: int = 0) -> None:
        self.image_data_rows.nth(index).locator(".n-checkbox").first.click()

    @allure.step("打开影像数据筛选面板")
    def open_image_filter(self) -> None:
        self.image_view_filter_button.click()
        expect(self.image_view_filter_popover).to_be_visible()

    @allure.step("关闭影像数据筛选面板")
    def close_image_filter(self) -> None:
        self.image_view_filter_popover.get_by_title("关闭").click()
        expect(self.image_view_filter_popover).to_be_hidden()

    @allure.step("导入选中影像数据到数据集：{research_name}/{dataset_name}")
    def import_image_to_dataset(self, research_name: str, dataset_name: str) -> None:
        """勾选影像数据 → 导入 → 级联选择课题/数据集 → 确定。"""
        self.import_to_dataset_button.click()
        expect(self.import_to_dataset_popover).to_be_visible()
        self.select_cascader_path(
            self.import_to_dataset_popover.locator(".n-cascader .n-base-selection"),
            research_name,
            dataset_name,
        )
        self.import_to_dataset_popover.get_by_role("button", name="确定", exact=True).click()
        expect(self.import_to_dataset_popover).to_be_hidden(timeout=30_000)

    # ------------------------------------------------------------------ #
    # 状态读取
    # ------------------------------------------------------------------ #
    def patient_total(self) -> int:
        """患者总数（从“共N人”文案解析）。"""
        text = self.patient_total_text.inner_text()
        match = re.search(r"\d+", text)
        return int(match.group()) if match else 0

    def first_patient_item_text(self) -> str:
        """第一个患者条目的完整文本（姓名/编号/性别/年龄）。"""
        return self.patient_items.first.inner_text()

    def first_patient_no(self) -> str:
        """从第一个患者条目中解析患者编号（5 位以上数字）。"""
        match = re.search(r"\d{5,}", self.first_patient_item_text())
        assert match, f"未能从患者条目中解析编号：{self.first_patient_item_text()!r}"
        return match.group()

    def section_names(self) -> list[str]:
        """表格模式下全部分组名称（人口学 / CT检查 / 病理 …）。"""
        return [text.strip() for text in self.table_items.locator(".caption .name").all_inner_texts() if text.strip()]

    def active_mode_label(self) -> str:
        """当前激活的全景数据模式文案（表格模式 / 时间线模式）。"""
        return self.page.locator(".button-radio-item.active").inner_text().strip()
