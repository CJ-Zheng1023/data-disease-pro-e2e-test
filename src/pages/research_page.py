# -*- coding: utf-8 -*-
"""课题管理模块页面对象。

覆盖两个页面与一个弹窗组件：

- :class:`ResearchListPage` —— 课题列表（创建 / 修改 / 删除 / 搜索 / 范围筛选）；
- :class:`ResearchFormModal` —— 课题创建 / 修改弹窗（名称与研究目标为必填）；
- :class:`ResearchDetailPage` —— 课题详情（课题信息 + 五个业务页签：
  患者管理 / 临床试验 / 影像管理 / 随访管理 / 知识管理）。

注意：根据项目要求，上传/下载及深层数据操作（导入患者、导入影像等）不在
本次范围内，详情页仅校验信息展示、页签切换与各页签的初始渲染状态。
"""

from __future__ import annotations

import re

import allure
from playwright.sync_api import Locator
from playwright.sync_api import expect

from config.constants import (
    MSG_REQUIRED_DATASET_NAME,
    MSG_REQUIRED_RESEARCH_NAME,
    MSG_REQUIRED_RESEARCH_OBJECTIVE,
    ROUTE_RESEARCH_LIST,
)
from config.settings import settings
from src.common.base_page import BasePage
from src.common.logger import get_logger
from src.pages.analysis_page import (
    CREATE_MODAL_TITLE as ANALYSIS_CREATE_TITLE,
)
from src.pages.analysis_page import (
    AnalysisDetailPage,
    AnalysisFormModal,
    FieldConfigModal,
)

logger = get_logger(__name__)

CREATE_MODAL_TITLE = "创建"
EDIT_MODAL_TITLE = "修改"

# 详情页页签（名称 -> 路由片段）
DETAIL_TABS = {
    "患者管理": "patient",
    "临床试验": "analysis/list",
    "影像管理": "dataset",
    "随访管理": "followup",
    "知识管理": "knowledge",
}


class ResearchListPage(BasePage):
    """课题列表页（/research/list）。"""

    path = ROUTE_RESEARCH_LIST

    # ------------------------------------------------------------------ #
    # 定位器
    # ------------------------------------------------------------------ #
    @property
    def search_input(self) -> Locator:
        return self.page.get_by_placeholder("搜索课题名称")

    @property
    def create_button(self) -> Locator:
        """“创建课题”按钮（空数据时文案为“创建第一个课题”）。"""
        return self.page.get_by_role("button", name=re.compile(r"^创建(第一个)?课题$"))

    @property
    def items(self) -> Locator:
        """所有课题卡片。"""
        return self.page.locator(".research-item")

    @property
    def empty_text(self) -> Locator:
        """空数据提示文案。"""
        return self.page.get_by_text("暂无课题")

    @property
    def footer_text(self) -> Locator:
        return self.page.get_by_text(re.compile(r"共\s*\d+\s*条记录"))

    def item(self, name: str) -> Locator:
        """按名称定位课题卡片。"""
        return self.items.filter(has_text=name).first

    def scope_button(self, label: str) -> Locator:
        """范围筛选按钮（所有课题 / 我的课题 / 我参与的课题）。"""
        return self.page.locator(".button-radio-item").filter(has_text=label)

    # ------------------------------------------------------------------ #
    # 操作
    # ------------------------------------------------------------------ #
    def open(self) -> "ResearchListPage":
        self.goto(self.path)
        expect(self.page.get_by_text("课题列表").first).to_be_visible()
        self.wait_network_idle()
        return self

    @allure.step("点击创建课题")
    def click_create(self) -> "ResearchFormModal":
        """打开创建课题弹窗。"""
        self.create_button.click()
        modal = ResearchFormModal(self.page, CREATE_MODAL_TITLE)
        modal.wait_opened()
        return modal

    @allure.step("点击修改课题：{name}")
    def click_edit(self, name: str) -> "ResearchFormModal":
        """打开指定课题的修改弹窗。"""
        self.item(name).locator("button", has_text="修改").click()
        modal = ResearchFormModal(self.page, EDIT_MODAL_TITLE)
        modal.wait_opened()
        return modal

    @allure.step("删除课题：{name}")
    def delete_research(self, name: str) -> None:
        """删除指定课题（气泡确认按钮为“确认”）。"""
        self.item(name).locator("button", has_text="删除").click()
        self.confirm_popconfirm(button_text="确认")
        self.wait_network_idle()

    @allure.step("进入课题详情：{name}")
    def enter_detail(self, name: str) -> "ResearchDetailPage":
        self.item(name).locator("button", has_text="进入").click()
        self.wait_for_url(re.compile(r".*/research/detail/\d+/patient$"))
        detail = ResearchDetailPage(self.page)
        detail.wait_ready()
        return detail

    @allure.step("搜索课题：{name}")
    def search(self, name: str) -> "ResearchListPage":
        """输入名称搜索（前端 500ms 防抖）。"""
        self.search_input.fill(name)
        self.wait_network_idle()
        return self

    @allure.step("按范围筛选：{label}")
    def switch_scope(self, label: str) -> "ResearchListPage":
        self.scope_button(label).click()
        self.wait_network_idle()
        return self

    def refresh(self) -> "ResearchListPage":
        """刷新页面数据。"""
        self.page.reload()
        self.wait_network_idle()
        return self

    # ------------------------------------------------------------------ #
    # 状态读取
    # ------------------------------------------------------------------ #
    def is_empty(self) -> bool:
        """当前列表是否为空状态（无课题引导面板或检索结果为空）。"""
        if self.is_visible(self.empty_text, timeout=1_000):
            return True
        return self.is_visible(self.page.locator(".body .n-empty"), timeout=1_000)

    def research_names(self) -> list[str]:
        """当前列表页所有课题名称。"""
        return [text.strip() for text in self.items.locator(".name .n-ellipsis span, .name span").all_inner_texts() if text.strip()]

    def stat_value(self, name: str, label: str) -> int:
        """读取指定课题卡片上的统计数值（患者 / 临床试验 / 数据集）。"""
        text = self.item(name).locator(".research-item-footer").inner_text()
        match = re.search(rf"{label}\s*(\d+)", text)
        return int(match.group(1)) if match else -1


class ResearchFormModal(BasePage):
    """课题创建 / 修改弹窗（二者共用同一表单，仅标题不同）。"""

    def __init__(self, page, title: str) -> None:
        super().__init__(page)
        self.title = title

    @property
    def root(self) -> Locator:
        return self.page.locator(".custom-modal").filter(
            has=self.page.locator(".n-card-header__main", has_text=re.compile(rf"^{self.title}$"))
        ).last

    def _field(self, label: str) -> Locator:
        """按表单标签定位字段容器（名称 / 研究目标 / 研究内容 / 关键技术和创新）。"""
        return self.root.locator(".n-form-item").filter(has=self.page.locator(".n-form-item-label", has_text=label)).first

    @property
    def name_input(self) -> Locator:
        """名称输入框（单行 input，避免与多行 textarea 的占位符混淆）。"""
        return self.root.locator("input[placeholder='请输入']")

    @property
    def objective_input(self) -> Locator:
        return self._field("研究目标").locator("textarea")

    @property
    def content_input(self) -> Locator:
        return self._field("研究内容").locator("textarea")

    @property
    def technology_input(self) -> Locator:
        return self._field("关键技术和创新").locator("textarea")

    @property
    def ok_button(self) -> Locator:
        return self.root.get_by_role("button", name="确定", exact=True)

    @property
    def close_button(self) -> Locator:
        return self.root.get_by_role("button", name="关闭", exact=True)

    def wait_opened(self) -> "ResearchFormModal":
        expect(self.root).to_be_visible()
        return self

    def wait_closed(self) -> None:
        expect(self.root).to_be_hidden()

    @allure.step("填写课题表单：{name}")
    def fill(
        self,
        name: str = "",
        objective: str = "",
        content: str = "",
        technology: str = "",
    ) -> "ResearchFormModal":
        """填写课题表单（仅填写传入的非空字段）。"""
        if name:
            self.name_input.fill(name)
        if objective:
            self.objective_input.fill(objective)
        if content:
            self.content_input.fill(content)
        if technology:
            self.technology_input.fill(technology)
        return self

    @allure.step("提交课题表单")
    def submit(self) -> None:
        self.ok_button.click()

    @allure.step("关闭课题表单")
    def close(self) -> None:
        self.close_button.click()
        self.wait_closed()

    def form_feedback(self) -> list[str]:
        """读取表单校验错误文案。"""
        return self.form_feedback_texts(self.root)

    def name_value(self) -> str:
        """名称输入框当前值（修改回显断言用）。"""
        return self.name_input.input_value()

    def objective_value(self) -> str:
        """研究目标输入框当前值（修改回显断言用）。"""
        return self.objective_input.input_value()

    # 供用例引用的文案常量
    REQUIRED_NAME_MSG = MSG_REQUIRED_RESEARCH_NAME
    REQUIRED_OBJECTIVE_MSG = MSG_REQUIRED_RESEARCH_OBJECTIVE


class ResearchDetailPage(BasePage):
    """课题详情页（/research/detail/:id/:tab）。"""

    # ------------------------------------------------------------------ #
    # 定位器 —— 课题信息
    # ------------------------------------------------------------------ #
    @property
    def back_button(self) -> Locator:
        return self.page.get_by_role("button", name="返回课题列表")

    @property
    def research_name(self) -> Locator:
        return self.page.locator(".research-info .name")

    @property
    def info_body(self) -> Locator:
        return self.page.locator(".research-info-body")

    @property
    def expand_button(self) -> Locator:
        """信息区展开/折叠按钮（默认折叠）。"""
        return self.page.locator(".research-info-header .extra .icon")

    # ------------------------------------------------------------------ #
    # 定位器 —— 页签区域
    # ------------------------------------------------------------------ #
    def tab(self, label: str) -> Locator:
        """详情页页签（患者管理 / 临床试验 / 影像管理 / 随访管理 / 知识管理）。"""
        return self.page.locator(".n-tabs-tab").filter(has_text=label)

    @property
    def patient_panel(self) -> Locator:
        return self.page.locator(".patient")

    @property
    def followup_panel(self) -> Locator:
        """随访管理区域。"""
        return self.page.locator(".followup")

    # ------------------------------------------------------------------ #
    # 初始化 / 操作
    # ------------------------------------------------------------------ #
    def wait_ready(self) -> "ResearchDetailPage":
        expect(self.research_name).to_be_visible(timeout=settings.navigation_timeout_ms)
        expect(self.patient_panel).to_be_visible()
        return self

    @allure.step("展开课题信息区")
    def expand_info(self) -> "ResearchDetailPage":
        """点击展开按钮，展示课题信息明细（默认折叠）。"""
        if self.info_body.is_visible():
            return self
        self.expand_button.click()
        expect(self.info_body).to_be_visible()
        return self

    @allure.step("切换详情页签：{label}")
    def click_tab(self, label: str) -> "ResearchDetailPage":
        """点击页签并等待路由切换完成。"""
        self.tab(label).click()
        self.page.wait_for_url(re.compile(rf".*/research/detail/\d+/{re.escape(DETAIL_TABS[label])}$"))
        self.wait_network_idle()
        return self

    @allure.step("返回课题列表")
    def back_to_list(self) -> ResearchListPage:
        self.back_button.click()
        self.wait_for_url(re.compile(r".*/research/list$"))
        return ResearchListPage(self.page)

    # ------------------------------------------------------------------ #
    # 状态读取
    # ------------------------------------------------------------------ #
    def info_item_value(self, label: str) -> str:
        """读取课题信息项的值（创建人 / 创建时间 / 课题成员）。"""
        item = self.info_body.locator(".info-item").filter(has=self.page.locator(".label", has_text=label)).first
        return item.locator(".value").inner_text().strip()

    def textarea_content(self, label: str) -> str:
        """读取信息区文本块内容（研究目标 / 研究内容 / 关键技术）。"""
        block = (
            self.info_body.locator(".research-info-textarea")
            .filter(has=self.page.locator(".textarea-header", has_text=label))
            .first
        )
        return block.locator(".textarea-body").inner_text().strip()

    def patient_empty_visible(self) -> bool:
        """患者管理页签是否为空状态。"""
        return self.is_visible(self.patient_panel.get_by_text("暂无数据").first, timeout=3_000)

    # ================================================================== #
    # 患者管理页签（患者列表 / 排除 / 筛选 / 导入到临床试验）
    # ================================================================== #
    @property
    def patient_items(self) -> Locator:
        return self.patient_panel.locator(".patient-item")

    @property
    def patient_data_type_select(self) -> Locator:
        """患者列表 / 排除患者 下拉选择框。"""
        return self.patient_panel.locator(".sider-header .n-select")

    @property
    def patient_total_text(self) -> Locator:
        return self.patient_panel.get_by_text(re.compile(r"共\s*\d+\s*人"))

    @property
    def patient_empty_text(self) -> Locator:
        return self.patient_panel.locator(".sider-body .n-empty")

    @property
    def patient_filter_button(self) -> Locator:
        return self.patient_panel.get_by_role("button", name=re.compile(r"^(筛选|已筛选)$"))

    @property
    def patient_filter_popover(self) -> Locator:
        """患者筛选浮层（含“患者姓名/患者编号/性别”等表单项）。"""
        return self.page.locator(".n-popover").filter(has_text="患者编号")

    @property
    def import_to_analysis_button(self) -> Locator:
        return self.patient_panel.locator("button[title='导入到临床试验']")

    @property
    def import_to_analysis_popover(self) -> Locator:
        return self.page.locator(".n-popover").filter(has_text="导入到临床试验")

    def patient_total(self) -> int:
        """患者总数（从“共N人”文案解析；文案不存在时返回 0）。"""
        if not self.is_visible(self.patient_total_text, timeout=3_000):
            return 0
        match = re.search(r"\d+", self.patient_total_text.inner_text())
        return int(match.group()) if match else 0

    @allure.step("切换患者数据类型：{label}")
    def switch_patient_data_type(self, label: str) -> None:
        """切换“患者列表 / 排除患者”视图。"""
        self.select_dropdown_option(self.patient_data_type_select, label)
        self.wait_network_idle()

    @allure.step("勾选第 {index} 位患者")
    def check_patient(self, index: int = 0) -> None:
        self.patient_items.nth(index).locator(".n-checkbox").click()

    @allure.step("排除选中患者")
    def exclude_selected_patients(self) -> None:
        self.patient_panel.locator("button[title='排除选中']").click()
        self.confirm_popconfirm(button_text="确认")
        self.wait_network_idle()

    @allure.step("恢复选中患者")
    def recover_selected_patients(self) -> None:
        self.patient_panel.locator("button[title='恢复选中']").click()
        self.confirm_popconfirm(button_text="确认")
        self.wait_network_idle()

    @allure.step("排除查询结果（批量排除）")
    def exclude_all_patients(self) -> None:
        """按当前查询条件排除全部患者。"""
        self.patient_panel.locator("button[title='排除查询结果']").click()
        self.confirm_popconfirm(button_text="确认")
        self.wait_network_idle()

    @allure.step("恢复查询结果（批量恢复）")
    def recover_all_patients(self) -> None:
        """按当前查询条件恢复全部被排除患者（需处于“排除患者”视图）。"""
        self.patient_panel.locator("button[title='恢复查询结果']").click()
        self.confirm_popconfirm(button_text="确认")
        self.wait_network_idle()

    @allure.step("打开患者筛选面板")
    def open_patient_filter(self) -> None:
        self.patient_filter_button.click()
        expect(self.patient_filter_popover).to_be_visible()

    @allure.step("按患者编号筛选：{patient_no}")
    def search_patient_by_no(self, patient_no: str) -> None:
        """筛选面板 → 填写患者编号 → 搜索。"""
        self.open_patient_filter()
        self.patient_filter_popover.locator(".n-form-item").filter(
            has=self.page.locator(".n-form-item-label", has_text="患者编号")
        ).locator("input").first.fill(patient_no)
        self.patient_filter_popover.get_by_role("button", name="搜索").click()
        self.wait_network_idle()

    @allure.step("重置患者筛选")
    def reset_patient_filter(self) -> None:
        """筛选面板 → 重置（自动触发搜索恢复全量）。"""
        self.open_patient_filter()
        self.patient_filter_popover.get_by_role("button", name="重置").click()
        self.wait_network_idle()

    def filter_searched_state(self) -> bool:
        """当前患者列表是否处于已筛选状态（筛选按钮变为“已筛选”）。"""
        return self.is_visible(self.patient_panel.get_by_role("button", name="已筛选"), timeout=2_000)

    @allure.step("导入选中患者到临床试验：{analysis_name}")
    def import_selected_to_analysis(self, analysis_name: str) -> None:
        """勾选患者 → 打开“导入到临床试验”浮层 → 选择临床试验 → 导入选中。"""
        self.import_to_analysis_button.click()
        expect(self.import_to_analysis_popover).to_be_visible()
        analysis_select = self.import_to_analysis_popover.locator(".n-select").first
        self.select_dropdown_option(analysis_select, analysis_name)
        self.import_to_analysis_popover.get_by_role("button", name=re.compile(r"^导入选中")).click()
        expect(self.import_to_analysis_popover).to_be_hidden(timeout=30_000)

    # ================================================================== #
    # 影像管理页签（数据集列表 + 数据集详情）
    # ================================================================== #
    @property
    def dataset_panel(self) -> Locator:
        return self.page.locator(".dataset")

    @property
    def dataset_items(self) -> Locator:
        return self.dataset_panel.locator(".dataset-item")

    @property
    def dataset_create_button(self) -> Locator:
        return self.dataset_panel.locator("button[title='创建数据集']")

    @property
    def dataset_delete_selected_button(self) -> Locator:
        """列表头部的“删除选中”按钮（删除数据集）。"""
        return self.dataset_panel.locator(".dataset-list-header button[title='删除选中']")

    @property
    def dataset_content_delete_selected_button(self) -> Locator:
        """详情区数据列表的“删除选中”按钮（删除数据集内影像数据）。"""
        return self.dataset_panel.locator(".dataset-content-header .actions").get_by_role("button", name="删除选中")

    @property
    def dataset_data_list_text(self) -> Locator:
        """详情区“数据列表”标题。"""
        return self.dataset_panel.locator(".dataset-content-header .name")

    @property
    def dataset_info_text(self) -> Locator:
        """详情区数据集信息（名称 / 创建人 / 描述 / 收集人员）。"""
        return self.dataset_panel.locator(".dataset-info")

    def dataset_item(self, name: str) -> Locator:
        """按名称定位数据集条目。"""
        return self.dataset_items.filter(has_text=name).first

    def dataset_info_item_value(self, label: str) -> str:
        """读取数据集详情信息项的值（创建人 / 描述 / 收集人员）。"""
        item = self.dataset_info_text.locator(".info-item").filter(has=self.page.locator(".label", has_text=label)).first
        return item.locator(".value").inner_text().strip()

    def dataset_data_count(self) -> int:
        """读取数据集详情“共N条”的影像数据量。"""
        text = self.dataset_panel.locator(".dataset-content-header").inner_text()
        match = re.search(r"共\s*(\d+)\s*条", text)
        return int(match.group(1)) if match else 0

    def wait_dataset_data_count(self, expected: int, timeout: int | None = None) -> None:
        """轮询等待数据集影像数据量达到预期值（导入为异步处理）。"""
        timeout_ms = timeout or settings.default_timeout_ms
        while timeout_ms > 0:
            try:
                if self.dataset_data_count() == expected:
                    return
            except Exception:  # pragma: no cover - 刷新瞬间可能取不到
                pass
            self.page.wait_for_timeout(300)
            timeout_ms -= 300
        raise AssertionError(f"等待数据集影像数据量达到 {expected} 超时，当前为 {self.dataset_data_count()}")

    def open_create_dataset(self) -> "ResearchDatasetFormModal":
        """打开“创建数据集”弹窗。"""
        self.dataset_create_button.click()
        modal = ResearchDatasetFormModal(self.page, CREATE_MODAL_TITLE)
        modal.wait_opened()
        return modal

    @allure.step("修改数据集：{name}")
    def edit_dataset(self, name: str) -> "ResearchDatasetFormModal":
        item = self.dataset_item(name)
        item.hover()  # 条目操作按钮默认隐藏，悬浮后显示
        item.locator("button[title='修改']").click()
        modal = ResearchDatasetFormModal(self.page, EDIT_MODAL_TITLE)
        modal.wait_opened()
        return modal

    @allure.step("删除数据集：{name}")
    def delete_dataset(self, name: str) -> None:
        item = self.dataset_item(name)
        item.hover()  # 条目操作按钮默认隐藏，悬浮后显示
        item.locator("button[title='删除']").click()
        self.confirm_popconfirm(button_text="确认")
        self.wait_network_idle()

    @allure.step("创建数据集：{name}")
    def create_dataset(self, name: str, description: str = "") -> None:
        """完整创建流程：打开弹窗 → 填写 → 提交 → 等待列表刷新。"""
        modal = self.open_create_dataset()
        modal.fill(name, description)
        modal.submit()
        modal.wait_closed()
        self.wait_network_idle()

    @allure.step("切换选中数据集：{name}")
    def select_dataset(self, name: str) -> None:
        """点击数据集条目，右侧详情联动切换。"""
        self.dataset_item(name).click()
        self.wait_network_idle()

    @allure.step("勾选数据集：{name}")
    def check_dataset(self, name: str) -> None:
        """勾选数据集条目复选框（用于删除选中）。"""
        item = self.dataset_item(name)
        item.hover()
        item.locator(".n-checkbox").first.click()

    @allure.step("删除选中的数据集")
    def delete_selected_datasets(self) -> None:
        """点击列表头部“删除选中”并确认。"""
        self.dataset_delete_selected_button.click()
        self.confirm_popconfirm(button_text="确认")
        self.wait_network_idle()

    @property
    def dataset_filter_button(self) -> Locator:
        """数据集列表筛选按钮。"""
        return self.dataset_panel.locator(".dataset-list-header").get_by_role("button", name=re.compile(r"^(筛选|已筛选)$"))

    @property
    def dataset_filter_popover(self) -> Locator:
        return self.page.locator(".n-popover").filter(has_text="数据集名称")

    @allure.step("按名称筛选数据集：{name}")
    def filter_datasets(self, name: str) -> None:
        """打开数据集筛选面板 → 填写名称 → 搜索。"""
        self.dataset_filter_button.click()
        expect(self.dataset_filter_popover).to_be_visible()
        self.dataset_filter_popover.locator("input").first.fill(name)
        self.dataset_filter_popover.get_by_role("button", name="搜索").click()
        self.wait_network_idle()

    @allure.step("重置数据集筛选")
    def reset_dataset_filter(self) -> None:
        self.dataset_filter_button.click()
        expect(self.dataset_filter_popover).to_be_visible()
        self.dataset_filter_popover.get_by_role("button", name="重置").click()
        self.wait_network_idle()

    # ================================================================== #
    # 临床试验页签（列表：创建 / 修改 / 删除 / 发布 / 字段配置 / 进入详情）
    # ================================================================== #
    @property
    def analysis_panel(self) -> Locator:
        return self.page.locator(".analysis-list")

    @property
    def analysis_items(self) -> Locator:
        return self.page.locator(".analysis-item")

    @property
    def analysis_create_button(self) -> Locator:
        return self.analysis_panel.get_by_role("button", name="创建", exact=True)

    @property
    def analysis_search_input(self) -> Locator:
        return self.analysis_panel.get_by_placeholder("搜索临床试验名称")

    @property
    def analysis_status_select(self) -> Locator:
        """状态筛选下拉（未发布 / 发布）。

        说明：naive-ui 选择值后占位符元素会被移除，因此按结构定位
        （分析列表搜索区仅有一个下拉框）。
        """
        return self.analysis_panel.locator(".n-select").first

    @allure.step("按名称搜索临床试验：{name}")
    def search_analysis(self, name: str) -> None:
        """输入名称搜索（前端 500ms 防抖）。"""
        self.analysis_search_input.fill(name)
        self.wait_network_idle()

    @allure.step("按状态筛选临床试验：{label}")
    def filter_analysis_by_status(self, label: str) -> None:
        """选择状态下拉选项（精确匹配，避免“发布/未发布”相互误配）。"""
        self.analysis_status_select.click()
        menu = self.page.locator(".n-base-select-menu").last
        option = menu.locator(".n-base-select-option").filter(has_text=re.compile(rf"^{re.escape(label)}$")).first
        expect(option).to_be_visible()
        option.click()
        self.wait_network_idle()

    def analysis_item(self, name: str) -> Locator:
        """按名称定位临床试验条目。"""
        return self.analysis_items.filter(has_text=name).first

    def open_create_analysis(self) -> AnalysisFormModal:
        """打开“创建”临床试验弹窗。"""
        self.analysis_create_button.click()
        modal = AnalysisFormModal(self.page, ANALYSIS_CREATE_TITLE)
        modal.wait_opened()
        return modal

    @allure.step("修改临床试验：{name}")
    def edit_analysis(self, name: str) -> AnalysisFormModal:
        """点击条目的“修改”图标（DOM 中第一个 title=修改 的按钮）。"""
        self.analysis_item(name).locator("button[title='修改']").first.click()
        modal = AnalysisFormModal(self.page, EDIT_MODAL_TITLE)
        modal.wait_opened()
        return modal

    @allure.step("删除临床试验：{name}")
    def delete_analysis(self, name: str) -> None:
        """点击条目的删除按钮（源组件该按钮 title 同为“修改”，按错误按钮样式区分）。"""
        self.analysis_item(name).locator("button.n-button--error-type[title='修改']").click()
        self.confirm_popconfirm(button_text="确认")
        self.wait_network_idle()

    @allure.step("发布临床试验：{name}")
    def publish_analysis(self, name: str) -> None:
        self.analysis_item(name).locator("button[title='发布']").click()
        self.confirm_popconfirm(button_text="确认")
        self.wait_network_idle()

    @allure.step("取消发布临床试验：{name}")
    def unpublish_analysis(self, name: str) -> None:
        self.analysis_item(name).locator("button[title='取消发布']").click()
        self.confirm_popconfirm(button_text="确认")
        self.wait_network_idle()

    @allure.step("打开临床试验字段配置：{name}")
    def open_analysis_field_config(self, name: str) -> FieldConfigModal:
        self.analysis_item(name).locator("button[title='字段配置']").click()
        modal = FieldConfigModal(self.page)
        modal.wait_opened()
        return modal

    @allure.step("进入临床试验详情：{name}")
    def enter_analysis_detail(self, name: str) -> AnalysisDetailPage:
        self.analysis_item(name).locator("button[title='进入']").click()
        self.wait_for_url(re.compile(r".*/research/detail/\d+/analysis/detail/\d+$"))
        detail = AnalysisDetailPage(self.page)
        detail.wait_ready()
        return detail

    def analysis_status_text(self, name: str) -> str:
        """读取临床试验发布状态（已发布 / 未发布）。"""
        item = self.analysis_item(name)
        for status in ("已发布", "未发布"):
            if item.get_by_text(status, exact=True).count() > 0:
                return status
        return ""

    def analysis_patient_count(self, name: str) -> int:
        """读取条目的患者总数。"""
        text = self.analysis_item(name).locator(".analysis-item-footer").inner_text()
        match = re.search(r"患者总数\s*(\d+)", text)
        return int(match.group(1)) if match else -1

    # ================================================================== #
    # 随访管理页签
    # ================================================================== #
    def _followup_field(self, label: str) -> Locator:
        return self.followup_panel.locator(".n-form-item").filter(has=self.page.locator(".n-form-item-label", has_text=label)).first

    @property
    def followup_create_button(self) -> Locator:
        return self.followup_panel.get_by_role("button", name="创建任务")

    @property
    def followup_reset_button(self) -> Locator:
        return self.followup_panel.get_by_role("button", name="重置")

    @property
    def followup_name_input(self) -> Locator:
        return self._followup_field("随访任务名称").locator("input").first

    @property
    def followup_remark_input(self) -> Locator:
        return self._followup_field("备注").locator("textarea").first

    @property
    def followup_patient_select(self) -> Locator:
        return self._followup_field("患者姓名").locator(".n-base-selection").first

    @property
    def followup_table_rows(self) -> Locator:
        """随访任务表格行。"""
        return self.followup_panel.locator(".n-data-table-tbody .n-data-table-tr")

    @property
    def followup_delete_selected_button(self) -> Locator:
        return self.followup_panel.get_by_role("button", name="删除选中")

    @property
    def followup_search_patient_input(self) -> Locator:
        return self.followup_panel.get_by_placeholder("患者姓名")

    @property
    def followup_status_select(self) -> Locator:
        """随访状态筛选下拉。

        说明：选择值后占位符会被移除，因此按“搜索表单”结构定位：
        搜索表单内依次为“数据范围/随访状态”两个下拉框，随访状态为最后一个。
        （不能直接用 ``.content`` 作用域：外层布局也存在同名容器）
        """
        search_form = self.followup_panel.locator("form").filter(has=self.page.get_by_placeholder("患者姓名")).first
        return search_form.locator(".n-select").last

    @allure.step("点击日历选择随访日期")
    def click_followup_calendar_day(self) -> None:
        """点击左侧日历中本月的第一个可选日期（自动回填随访时间）。"""
        day = self.followup_panel.locator(".n-date-panel-date:not(.n-date-panel-date--excluded)").first
        expect(day).to_be_visible()
        day.click()
        self.wait_network_idle()

    @allure.step("创建随访任务：{task_name}")
    def create_followup(self, task_name: str, remark: str = "") -> str:
        """完整创建流程：选患者 → 填名称 → 日历选日期 → 创建任务。

        :return: 选中的患者姓名（用于后续断言）。
        """
        # 等待患者下拉选项加载完成（下拉处于 loading 时点击会得到空面板）
        loading = self.followup_patient_select.locator(".n-base-loading")
        try:
            loading.wait_for(state="hidden", timeout=15_000)
        except Exception:  # pragma: no cover - 无 loading 状态时直接继续
            pass
        patient_name = self.select_first_dropdown_option(self.followup_patient_select)
        self.followup_name_input.fill(task_name)
        if remark:
            self.followup_remark_input.fill(remark)
        self.click_followup_calendar_day()
        self.followup_create_button.click()
        self.wait_network_idle()
        return patient_name

    @allure.step("删除选中的随访任务")
    def delete_selected_followups(self, index: int = 0) -> None:
        """勾选第 index 行 → 删除选中 → 确认，并校验行被移除。

        说明：列表刷新与勾选状态存在竞态（刷新可能重置勾选），
        这里做有限重试：只要最终行被真实删除，即视为通过。
        """
        for _ in range(3):
            if self.followup_table_rows.count() <= index:
                return
            row = self.followup_table_rows.nth(index)
            row.locator(".n-checkbox").first.click()
            try:
                expect(row.locator(".n-checkbox--checked")).to_be_visible(timeout=5_000)
            except AssertionError:
                continue
            self.followup_delete_selected_button.click()
            self.confirm_popconfirm(button_text="确认")
            self.wait_network_idle()
            try:
                expect(self.followup_table_rows).to_have_count(index, timeout=8_000)
                return
            except AssertionError:
                continue
        raise AssertionError("随访任务删除失败：选中行未能移除")

    # ================================================================== #
    # 知识管理页签（创建为文件上传，按范围仅校验空提交拦截）
    # ================================================================== #
    @property
    def knowledge_search_input(self) -> Locator:
        return self.page.get_by_placeholder("搜索文件名称")

    @property
    def knowledge_create_button(self) -> Locator:
        return self.page.get_by_role("button", name="创建", exact=True)

    @property
    def knowledge_modal(self) -> Locator:
        return self.page.locator(".custom-modal").filter(
            has=self.page.locator(".n-card-header__main", has_text=re.compile(r"^创建$"))
        ).last

    @allure.step("切换知识管理模式：{label}")
    def switch_knowledge_mode(self, label: str) -> None:
        self.page.locator(".button-radio-item").filter(has_text=label).click()
        self.wait_network_idle()

    @allure.step("搜索知识文件：{name}")
    def search_knowledge(self, name: str) -> None:
        self.knowledge_search_input.fill(name)
        self.wait_network_idle()

    def wait_analysis_patient_count(self, name: str, expected: int, timeout: int | None = None) -> None:
        """轮询等待条目的患者总数达到预期值（导入到临床试验为异步处理）。"""
        timeout = timeout or settings.default_timeout_ms
        deadline_ms = timeout
        interval = 300
        while deadline_ms > 0:
            try:
                if self.analysis_patient_count(name) == expected:
                    return
            except Exception:  # pragma: no cover - 列表刷新瞬间可能取不到
                pass
            self.page.wait_for_timeout(interval)
            deadline_ms -= interval
        raise AssertionError(f"等待临床试验[{name}]患者总数达到 {expected} 超时，当前为 {self.analysis_patient_count(name)}")


class ResearchDatasetFormModal(BasePage):
    """影像管理（数据集）创建 / 修改弹窗。"""

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

    def wait_opened(self) -> "ResearchDatasetFormModal":
        expect(self.root).to_be_visible()
        return self

    def wait_closed(self) -> None:
        expect(self.root).to_be_hidden()

    @allure.step("选择收集人员（第一个选项）")
    def select_first_collector(self) -> str:
        """在“收集人员”多选下拉中选择第一个用户（通常为当前登录用户）。

        说明：影像数据集需要“收集人”角色才会出现在“导入到数据集”的候选树中。
        """
        select = self._field("收集人员").locator(".n-select .n-base-selection").first
        text = self.select_first_dropdown_option(select)
        self.page.keyboard.press("Escape")  # 关闭多选下拉面板
        return text

    @allure.step("填写数据集表单：{name}")
    def fill(self, name: str = "", description: str = "") -> "ResearchDatasetFormModal":
        if name:
            self.name_input.fill(name)
        if description:
            self.description_input.fill(description)
        return self

    @allure.step("提交数据集表单")
    def submit(self) -> None:
        self.ok_button.click()

    @allure.step("关闭数据集表单")
    def close(self) -> None:
        self.close_button.click()
        self.wait_closed()

    def form_feedback(self) -> list[str]:
        return self.form_feedback_texts(self.root)

    def name_value(self) -> str:
        return self.name_input.input_value()

    def description_value(self) -> str:
        return self.description_input.input_value()

    REQUIRED_NAME_MSG = MSG_REQUIRED_DATASET_NAME
