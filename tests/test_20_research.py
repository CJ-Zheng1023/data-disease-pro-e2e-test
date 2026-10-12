# -*- coding: utf-8 -*-
"""课题管理模块测试用例（含患者管理、影像管理、临床试验）。

覆盖点：
1. 课题列表：加载、搜索、范围筛选、创建（双必填校验）、修改、删除；
2. 课题详情：信息展示、五个业务页签切换、返回列表；
3. 患者管理：排除/恢复、筛选、导入到临床试验；
4. 影像管理：数据集增删改查（列表 + 详情联动）、数据集详情面板；
5. 临床试验：列表增删改查、发布/取消发布、字段配置；详情页空态与字段配置、
   数据行操作（添加一行/单元格编辑/批量确认/删除行/删除选中）、发布与返回。

测试数据保护说明：
- 所有数据均创建在 ``research_cleaner`` 自建课题下（含其下临床试验、影像数据集），
  随课题清理一并删除，不触碰存量数据；
- “导入到课题 / 导入到临床试验”目标均为自建数据；
- 上传/下载等数据搬运功能不在本次范围内（仅校验入口渲染，不执行操作）。
"""

from __future__ import annotations

import re

import allure
import pytest
from playwright.sync_api import expect

from src.pages.analysis_page import INCOMPLETE_FIELD_CONFIG_MSG
from src.pages.research_page import ResearchDetailPage, ResearchListPage
from src.utils.test_data import build_test_name

pytestmark = [pytest.mark.data_cleanup]


@allure.feature("课题管理")
@allure.story("课题列表")
class TestResearchList:
    """列表加载 / 搜索 / 范围筛选。"""

    @allure.title("课题列表加载（空状态或数据列表）")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.smoke
    def test_list_loads(self, research_list_page: ResearchListPage) -> None:
        with allure.step("校验页头操作区"):
            expect(research_list_page.create_button).to_be_visible()
        if research_list_page.is_empty():
            with allure.step("空状态：展示引导文案与创建入口"):
                expect(research_list_page.empty_text).to_be_visible()
                assert "创建第一个课题" in research_list_page.create_button.inner_text()
        else:
            with allure.step("数据状态：展示搜索框、课题卡片与分页统计"):
                expect(research_list_page.search_input).to_be_visible()
                assert research_list_page.items.count() > 0
                expect(research_list_page.footer_text).to_be_visible()

    @allure.title("按名称搜索课题：命中、未命中与清空恢复")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_search_research(self, research_cleaner, research_list_page: ResearchListPage) -> None:
        research = research_cleaner["create"](objective="搜索用例-研究目标")
        research_list_page.refresh()

        with allure.step(f"搜索自建课题：{research['name']}"):
            research_list_page.search(research["name"])
            expect(research_list_page.item(research["name"])).to_be_visible()

        with allure.step("搜索不存在的课题名称：展示空状态"):
            research_list_page.search("E2E-AUTO-不存在的课题-7y7y7")
            expect(research_list_page.page.get_by_text("暂无数据")).to_be_visible()

        with allure.step("清空搜索恢复列表"):
            research_list_page.search("")
            expect(research_list_page.item(research["name"])).to_be_visible()

    @allure.title("课题范围筛选：我的课题 / 所有课题 / 我参与的课题")
    @allure.severity(allure.severity_level.NORMAL)
    def test_scope_filter(self, research_cleaner, research_list_page: ResearchListPage) -> None:
        research = research_cleaner["create"](objective="范围筛选用例-研究目标")
        research_list_page.refresh()

        with allure.step("筛选“我的课题”：包含自建课题"):
            research_list_page.switch_scope("我的课题")
            expect(research_list_page.item(research["name"])).to_be_visible()

        with allure.step("筛选“所有课题”：包含自建课题"):
            research_list_page.switch_scope("所有课题")
            expect(research_list_page.item(research["name"])).to_be_visible()

        with allure.step("筛选“我参与的课题”：列表正常渲染（可能为空）"):
            research_list_page.switch_scope("我参与的课题")
            # 页面必须稳定处于“有数据”或“空状态”之一，而不能停留在加载中
            research_list_page.page.wait_for_function(
                "() => document.querySelector('.research-item')"
                " || document.querySelector('.body .n-empty')"
                " || document.querySelector('.empty')",
                timeout=10_000,
            )

        with allure.step("恢复“所有课题”范围"):
            research_list_page.switch_scope("所有课题")
            expect(research_list_page.item(research["name"])).to_be_visible()


@allure.feature("课题管理")
@allure.story("创建课题")
class TestCreateResearch:
    """创建课题弹窗与数据创建。"""

    @allure.title("创建课题弹窗：名称与研究目标必填")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_create_modal_required_validation(self, research_list_page: ResearchListPage) -> None:
        modal = research_list_page.click_create()

        with allure.step("空表单提交：同时提示名称与研究目标必填"):
            modal.submit()
            # 两条校验文案异步渲染，使用自动重试断言等待其全部出现
            expect(modal.root.get_by_text(modal.REQUIRED_NAME_MSG)).to_be_visible()
            expect(modal.root.get_by_text(modal.REQUIRED_OBJECTIVE_MSG)).to_be_visible()

        with allure.step("仅填写名称提交：仍提示研究目标必填"):
            modal.fill(name=build_test_name("课题-校验"))
            modal.submit()
            expect(modal.root.get_by_text(modal.REQUIRED_OBJECTIVE_MSG)).to_be_visible()
            expect(modal.root.get_by_text(modal.REQUIRED_NAME_MSG)).to_have_count(0)

        with allure.step("关闭弹窗且不产生数据"):
            modal.close()

    @allure.title("创建带统一标识的自建课题并出现在列表")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.smoke
    def test_create_research(self, research_cleaner, research_list_page: ResearchListPage) -> None:
        name = build_test_name("课题")
        objective = "E2E 自动化创建的研究目标"
        content = "E2E 自动化创建的研究内容"
        technology = "E2E 自动化创建的创新技术"
        research_cleaner["register"](name)  # 先登记，防止创建成功但断言失败时残留数据

        modal = research_list_page.click_create()
        with allure.step(f"填写并提交：{name}"):
            modal.fill(name, objective, content, technology)
            modal.submit()
            modal.wait_closed()

        with allure.step("列表中可检索到新课题，卡片信息完整"):
            research_list_page.search(name)
            item = research_list_page.item(name)
            expect(item).to_be_visible()
            expect(item).to_contain_text("我的课题")
            expect(item).to_contain_text("研究目标：")
            expect(item).to_contain_text(objective)
            current_user = research_list_page.read_local_user_info().get("realName", "")
            expect(item).to_contain_text(current_user)

        with allure.step("新课题统计数值初始为 0"):
            assert research_list_page.stat_value(name, "患者") == 0
            assert research_list_page.stat_value(name, "临床试验") == 0
            assert research_list_page.stat_value(name, "数据集") == 0


@allure.feature("课题管理")
@allure.story("修改课题")
class TestEditResearch:
    """修改课题弹窗与回显。"""

    @allure.title("修改课题：回显正确且修改后生效")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_edit_research(self, research_cleaner, research_list_page: ResearchListPage) -> None:
        research = research_cleaner["create"](objective="修改前研究目标")
        new_name = build_test_name("课题-已修改")
        new_objective = "修改后研究目标"
        research_cleaner["register"](new_name)  # 名称变化后同样需要兜底清理
        research_list_page.refresh()

        with allure.step("打开修改弹窗并校验回显（等待接口回显完成）"):
            research_list_page.search(research["name"])
            modal = research_list_page.click_edit(research["name"])
            expect(modal.name_input).to_have_value(research["name"])
            expect(modal.objective_input).to_have_value("修改前研究目标")

        with allure.step(f"修改名称与研究目标：{new_name}"):
            modal.fill(new_name, new_objective)
            modal.submit()
            modal.wait_closed()

        with allure.step("校验修改结果"):
            research_list_page.search(new_name)
            item = research_list_page.item(new_name)
            expect(item).to_be_visible()
            expect(item).to_contain_text(new_objective)
            expect(research_list_page.item(research["name"])).to_have_count(0)


@allure.feature("课题管理")
@allure.story("删除课题")
class TestDeleteResearch:
    """删除课题（自建数据）。"""

    @allure.title("删除自建课题：确认弹窗后从列表移除")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_delete_research(self, research_cleaner, research_list_page: ResearchListPage) -> None:
        research = research_cleaner["create"](objective="待删除课题")
        research_list_page.refresh()
        research_list_page.search(research["name"])
        expect(research_list_page.item(research["name"])).to_be_visible()

        with allure.step("点击删除并确认"):
            research_list_page.delete_research(research["name"])

        with allure.step("校验课题已从列表移除"):
            research_list_page.wait_network_idle()
            expect(research_list_page.item(research["name"])).to_have_count(0)


@allure.feature("课题管理")
@allure.story("课题详情")
class TestResearchDetail:
    """课题详情页信息与页签。"""

    @allure.title("课题详情：信息展示与患者管理空状态")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.smoke
    def test_enter_detail(self, research_cleaner, research_list_page: ResearchListPage) -> None:
        research = research_cleaner["create"](objective="详情用例-研究目标", content="详情用例-研究内容", technology="详情用例-关键技术")
        research_list_page.refresh()
        research_list_page.search(research["name"])
        detail: ResearchDetailPage = research_list_page.enter_detail(research["name"])

        with allure.step("校验详情页地址与课题名称"):
            assert f"/research/detail/" in detail.current_url
            expect(detail.research_name).to_have_text(research["name"])

        with allure.step("展开信息区，校验基础信息与研究三要素"):
            detail.expand_info()
            current_user = detail.read_local_user_info().get("realName", "")
            assert detail.info_item_value("创建人") == current_user
            assert detail.info_item_value("课题成员") == "-", "未添加成员时成员应展示为 -"
            expect(detail.info_body.locator("time").first).to_be_visible()
            assert detail.textarea_content("研究目标") == "详情用例-研究目标"
            assert detail.textarea_content("研究内容") == "详情用例-研究内容"
            assert detail.textarea_content("关键技术") == "详情用例-关键技术"

        with allure.step("校验患者管理页签空状态与全景数据区域"):
            expect(detail.page.get_by_text("患者列表").first).to_be_visible()
            expect(detail.page.get_by_text("全景数据")).to_be_visible()
            expect(detail.page.get_by_text("表格模式")).to_be_visible()
            expect(detail.page.get_by_text("时间线模式")).to_be_visible()
            assert detail.patient_empty_visible(), "新课题患者列表应为空状态"

    @allure.title("课题详情：五个业务页签切换与初始渲染")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_detail_tabs_switch(self, research_cleaner, research_list_page: ResearchListPage) -> None:
        research = research_cleaner["create"](objective="页签切换用例")
        research_list_page.refresh()
        research_list_page.search(research["name"])
        detail = research_list_page.enter_detail(research["name"])

        with allure.step("临床试验页签：搜索与创建入口、空状态"):
            detail.click_tab("临床试验")
            expect(detail.analysis_panel).to_be_visible()
            expect(detail.page.get_by_placeholder("搜索临床试验名称")).to_be_visible()
            expect(detail.analysis_panel.get_by_role("button", name="创建", exact=True)).to_be_visible()
            expect(detail.analysis_panel.get_by_text("暂无数据")).to_be_visible()

        with allure.step("影像管理页签：数据集列表空状态"):
            detail.click_tab("影像管理")
            expect(detail.dataset_panel).to_be_visible()
            expect(detail.page.get_by_text("数据集列表").first).to_be_visible()
            expect(detail.dataset_panel.get_by_text("暂无数据").first).to_be_visible()

        with allure.step("随访管理页签：日历与新建随访任务表单"):
            detail.click_tab("随访管理")
            expect(detail.followup_panel).to_be_visible()
            expect(detail.followup_panel.locator(".n-date-picker")).to_be_visible()
            expect(detail.page.get_by_text("新建随访任务")).to_be_visible()
            expect(detail.page.get_by_role("button", name="创建任务")).to_be_visible()
            expect(detail.page.get_by_role("button", name="删除选中")).to_be_visible()

        with allure.step("知识管理页签：搜索与创建入口"):
            detail.click_tab("知识管理")
            expect(detail.page.get_by_placeholder("搜索文件名称")).to_be_visible()
            expect(detail.page.get_by_text("表格式")).to_be_visible()
            expect(detail.page.get_by_text("图标式")).to_be_visible()
            expect(detail.page.get_by_role("button", name="创建", exact=True)).to_be_visible()
            expect(detail.page.get_by_role("button", name="删除选中")).to_be_visible()

        with allure.step("切回患者管理页签"):
            detail.click_tab("患者管理")
            expect(detail.patient_panel).to_be_visible()
            expect(detail.page.get_by_text("全景数据")).to_be_visible()

    @allure.title("详情页返回课题列表")
    @allure.severity(allure.severity_level.NORMAL)
    def test_back_to_list(self, research_cleaner, research_list_page: ResearchListPage) -> None:
        research = research_cleaner["create"](objective="返回用例")
        research_list_page.refresh()
        research_list_page.search(research["name"])
        detail = research_list_page.enter_detail(research["name"])

        with allure.step("点击返回按钮"):
            list_page: ResearchListPage = detail.back_to_list()
            expect(list_page.search_input).to_be_visible()

        with allure.step("校验返回后仍可检索到课题"):
            list_page.search(research["name"])
            expect(list_page.item(research["name"])).to_be_visible()


@allure.feature("课题管理")
@allure.story("课题详情-患者管理操作")
class TestResearchPatientActions:
    """患者管理页签：排除/恢复、筛选、导入到临床试验。

    造数说明：通过接口把“存量专病库患者”导入到自建课题（与界面导入同接口），
    患者副本随自建课题一并清理，不影响专病库存量数据。
    """

    @staticmethod
    def _prepare_research_with_patients(api_client, research_cleaner, patient_count: int = 2) -> dict:
        """创建自建课题并从第一个专病库导入若干患者。"""
        databases = api_client.query_databases_for_select()
        assert databases, "当前账号无可访问的专病库，无法准备患者数据"
        database_id = databases[0]["id"]
        source_patients = api_client.query_database_patients(database_id, page_size=patient_count)
        assert len(source_patients) >= 1, "专病库无患者数据，无法准备患者数据"
        research = research_cleaner["create"](database_id=database_id)
        patient_ids = [p["id"] for p in source_patients[:patient_count]]
        api_client.import_patients_to_research(database_id, patient_ids, research["id"])
        research["patients"] = source_patients[:patient_count]
        return research

    def _enter_patient_tab(self, research_cleaner, research_list_page: ResearchListPage, api_client, patient_count: int = 2):
        research = self._prepare_research_with_patients(api_client, research_cleaner, patient_count)
        research_list_page.refresh()
        research_list_page.search(research["name"])
        detail = research_list_page.enter_detail(research["name"])
        expect(detail.patient_items.first).to_be_visible(timeout=20_000)
        return research, detail

    @allure.title("排除选中患者并在“排除患者”列表可见，随后恢复")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_exclude_and_recover_patient(self, api_client, research_cleaner, research_list_page: ResearchListPage) -> None:
        research, detail = self._enter_patient_tab(research_cleaner, research_list_page, api_client, patient_count=1)
        patient_no = research["patients"][0]["patientNo"]

        with allure.step("排除选中患者"):
            detail.check_patient(0)
            detail.exclude_selected_patients()

        with allure.step("切换到“排除患者”列表：可见被排除患者"):
            detail.switch_patient_data_type("排除患者")
            expect(detail.patient_items.first).to_be_visible(timeout=15_000)
            assert patient_no in detail.patient_items.first.inner_text()

        with allure.step("恢复选中患者"):
            detail.check_patient(0)
            detail.recover_selected_patients()

        with allure.step("切回“患者列表”：患者恢复可见"):
            detail.switch_patient_data_type("患者列表")
            expect(detail.patient_items.first).to_be_visible(timeout=15_000)
            assert patient_no in detail.patient_items.first.inner_text()

    @allure.title("患者筛选：按编号命中与重置恢复")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_patient_filter(self, api_client, research_cleaner, research_list_page: ResearchListPage) -> None:
        research, detail = self._enter_patient_tab(research_cleaner, research_list_page, api_client, patient_count=2)
        patient_no = research["patients"][0]["patientNo"]

        with allure.step(f"按患者编号筛选：{patient_no} → 命中 1 人"):
            detail.search_patient_by_no(patient_no)
            expect(detail.patient_items).to_have_count(1, timeout=15_000)
            assert detail.filter_searched_state(), "执行筛选后按钮应变为“已筛选”"

        with allure.step("重置筛选：恢复全量患者"):
            detail.reset_patient_filter()
            expect(detail.patient_items).to_have_count(2, timeout=15_000)
            assert not detail.filter_searched_state()

    @allure.title("导入选中患者到临床试验：条目患者总数联动")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.smoke
    def test_import_patients_to_analysis(
        self, api_client, research_cleaner, analysis_cleaner, research_list_page: ResearchListPage
    ) -> None:
        research, detail = self._enter_patient_tab(research_cleaner, research_list_page, api_client, patient_count=1)
        analysis = analysis_cleaner["create"](research["id"], description="患者导入目标试验")
        # 说明：临床试验需要先配置字段，导入的患者数据才会被提取成数据行（患者总数联动）
        api_client.save_analysis_custom_field(analysis["id"], build_test_name("文本字段", max_length=60))

        with allure.step(f"勾选患者并导入到临床试验：{analysis['name']}"):
            detail.check_patient(0)
            detail.import_selected_to_analysis(analysis["name"])

        with allure.step("切换到临床试验页签：患者总数联动为 1"):
            detail.click_tab("临床试验")
            expect(detail.analysis_item(analysis["name"])).to_be_visible()
            detail.wait_analysis_patient_count(analysis["name"], 1, timeout=20_000)

    @allure.title("批量排除查询结果与恢复查询结果")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_exclude_all_and_recover_all(self, api_client, research_cleaner, research_list_page: ResearchListPage) -> None:
        _, detail = self._enter_patient_tab(research_cleaner, research_list_page, api_client, patient_count=2)

        with allure.step("排除查询结果：患者列表清空"):
            detail.exclude_all_patients()
            expect(detail.patient_empty_text).to_be_visible(timeout=15_000)

        with allure.step("切换“排除患者”视图：两位患者均在排除列表"):
            detail.switch_patient_data_type("排除患者")
            expect(detail.patient_items).to_have_count(2, timeout=15_000)

        with allure.step("恢复查询结果：排除列表清空"):
            detail.recover_all_patients()
            expect(detail.patient_empty_text).to_be_visible(timeout=15_000)

        with allure.step("切回“患者列表”：患者恢复为 2 人"):
            detail.switch_patient_data_type("患者列表")
            expect(detail.patient_items).to_have_count(2, timeout=15_000)


def _enter_dataset_tab(research_cleaner, research_list_page: ResearchListPage) -> ResearchDetailPage:
    """创建自建课题并进入“影像管理”页签。"""
    research = research_cleaner["create"](objective="影像管理用例")
    research_list_page.refresh()
    research_list_page.search(research["name"])
    detail = research_list_page.enter_detail(research["name"])
    detail.click_tab("影像管理")
    return detail


@allure.feature("影像管理")
@allure.story("影像管理-数据集列表")
class TestResearchDataset:
    """数据集增删改查（列表 + 详情）。"""

    @allure.title("影像管理页签初始为空状态")
    @allure.severity(allure.severity_level.NORMAL)
    def test_dataset_tab_empty(self, research_cleaner, research_list_page: ResearchListPage) -> None:
        detail = _enter_dataset_tab(research_cleaner, research_list_page)
        with allure.step("校验数据集列表空状态与操作入口"):
            expect(detail.dataset_panel).to_be_visible()
            expect(detail.page.get_by_text("数据集列表").first).to_be_visible()
            expect(detail.dataset_panel.get_by_text("暂无数据").first).to_be_visible()
            expect(detail.dataset_create_button).to_be_visible()

    @allure.title("创建数据集弹窗：名称为必填项")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_create_dataset_validation(self, research_cleaner, research_list_page: ResearchListPage) -> None:
        detail = _enter_dataset_tab(research_cleaner, research_list_page)
        modal = detail.open_create_dataset()

        with allure.step("空表单提交：提示名称必填"):
            modal.submit()
            expect(modal.root.locator(".n-form-item-feedback__line").first).to_be_visible()
            assert modal.REQUIRED_NAME_MSG in modal.form_feedback(), f"应提示：{modal.REQUIRED_NAME_MSG}"

        with allure.step("关闭弹窗且不产生数据"):
            modal.close()
            expect(detail.dataset_items).to_have_count(0)

    @allure.title("数据集增删改查全链路（列表 + 详情联动）")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.smoke
    def test_dataset_crud(self, research_cleaner, research_list_page: ResearchListPage) -> None:
        detail = _enter_dataset_tab(research_cleaner, research_list_page)
        name = build_test_name("影像数据集", max_length=60)
        description = "E2E 自动化创建的数据集描述"

        with allure.step(f"创建数据集：{name}"):
            detail.create_dataset(name, description)
            expect(detail.dataset_item(name)).to_be_visible()

        with allure.step("详情区联动展示数据集信息"):
            current_user = detail.read_local_user_info().get("realName", "")
            info_text = detail.dataset_info_text.inner_text()
            assert name in info_text
            assert current_user in info_text
            assert description in info_text

        with allure.step("修改数据集名称与描述"):
            new_name = build_test_name("影像数据集-已改", max_length=60)
            modal = detail.edit_dataset(name)
            expect(modal.name_input).to_have_value(name)
            expect(modal.description_input).to_have_value(description)
            modal.fill(new_name, "修改后描述")
            modal.submit()
            modal.wait_closed()
            expect(detail.dataset_item(new_name)).to_be_visible()
            assert "修改后描述" in detail.dataset_info_text.inner_text()

        with allure.step("删除数据集：确认后从列表移除"):
            detail.delete_dataset(new_name)
            expect(detail.dataset_item(new_name)).to_have_count(0)

    @allure.title("数据集详情：信息区与数据列表初始状态")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_dataset_detail_panel(self, research_cleaner, research_list_page: ResearchListPage) -> None:
        detail = _enter_dataset_tab(research_cleaner, research_list_page)
        name = build_test_name("影像数据集", max_length=60)
        detail.create_dataset(name, "详情面板用例")
        detail.select_dataset(name)

        with allure.step("校验数据列表区域与统计"):
            expect(detail.dataset_data_list_text).to_have_text("数据列表")
            expect(detail.dataset_panel.get_by_text("共0条").first).to_be_visible()
            assert detail.dataset_content_delete_selected_button.is_disabled(), "无数据时“删除选中”应禁用"

        with allure.step("校验数据搬运入口渲染（按范围不执行操作）"):
            # 上传按钮仅收集人有权限；创建人视角校验导出/下载入口即可
            expect(detail.dataset_panel.get_by_role("button", name="导出", exact=True)).to_be_visible()
            download_button = detail.dataset_panel.get_by_role("button", name="下载", exact=True)
            expect(download_button).to_be_visible()
            assert download_button.is_disabled(), "无数据时下载按钮应禁用"

        with allure.step("校验详情信息项：收集人员为空展示占位"):
            assert detail.dataset_info_item_value("收集人员") in ("-", ""), "未设置收集人员时应展示占位符"

    @allure.title("数据集筛选与删除选中")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_dataset_filter_and_delete_selected(self, research_cleaner, research_list_page: ResearchListPage) -> None:
        detail = _enter_dataset_tab(research_cleaner, research_list_page)
        first = build_test_name("影像数据集", max_length=60)
        second = build_test_name("影像数据集", max_length=60)
        detail.create_dataset(first, "筛选删除用例-A")
        detail.create_dataset(second, "筛选删除用例-B")
        expect(detail.dataset_items).to_have_count(2)

        with allure.step("按名称筛选：仅命中目标数据集"):
            detail.filter_datasets(first)
            expect(detail.dataset_items).to_have_count(1)
            expect(detail.dataset_item(first)).to_be_visible()

        with allure.step("重置筛选：恢复全部"):
            detail.reset_dataset_filter()
            expect(detail.dataset_items).to_have_count(2)

        with allure.step("勾选并删除选中：仅目标数据集被移除"):
            detail.check_dataset(first)
            detail.delete_selected_datasets()
            expect(detail.dataset_item(first)).to_have_count(0)
            expect(detail.dataset_item(second)).to_be_visible()


def _enter_analysis_tab(research_cleaner, research_list_page: ResearchListPage) -> tuple[dict, ResearchDetailPage]:
    """创建自建课题并进入“临床试验”页签。"""
    research = research_cleaner["create"](objective="临床试验用例")
    research_list_page.refresh()
    research_list_page.search(research["name"])
    detail = research_list_page.enter_detail(research["name"])
    detail.click_tab("临床试验")
    return research, detail


def _open_analysis_tab_with_analysis(
    research_cleaner, analysis_cleaner, research_list_page: ResearchListPage, description: str = "E2E 用例"
) -> tuple[dict, dict, ResearchDetailPage]:
    """造数：自建课题 + 临床试验（列表挂载前就绪），进入“临床试验”页签。"""
    research = research_cleaner["create"](objective="临床试验用例")
    analysis = analysis_cleaner["create"](research["id"], description=description)
    research_list_page.refresh()
    research_list_page.search(research["name"])
    detail = research_list_page.enter_detail(research["name"])
    detail.click_tab("临床试验")
    expect(detail.analysis_item(analysis["name"])).to_be_visible()
    return research, analysis, detail


def _prepare_analysis_with_field(
    api_client, research_cleaner, analysis_cleaner, research_list_page: ResearchListPage
) -> tuple[dict, dict, str, ResearchDetailPage]:
    """造数：自建课题 + 临床试验 + （接口）文本型自定义字段，进入详情页。"""
    research = research_cleaner["create"](objective="临床试验详情用例")
    analysis = analysis_cleaner["create"](research["id"], description="详情功能用例")
    field_name = build_test_name("文本字段", max_length=60)
    api_client.save_analysis_custom_field(analysis["id"], field_name)

    research_list_page.refresh()
    research_list_page.search(research["name"])
    detail = research_list_page.enter_detail(research["name"])
    detail.click_tab("临床试验")
    expect(detail.analysis_item(analysis["name"])).to_be_visible()
    return research, analysis, field_name, detail


@allure.feature("临床试验")
@allure.story("临床试验-列表")
class TestAnalysisList:
    """临床试验列表增删改查与发布。"""

    @allure.title("创建弹窗：名称为必填项")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_create_modal_validation(self, research_cleaner, research_list_page: ResearchListPage) -> None:
        _, detail = _enter_analysis_tab(research_cleaner, research_list_page)
        modal = detail.open_create_analysis()

        with allure.step("空表单提交：提示名称必填"):
            modal.submit()
            expect(modal.root.locator(".n-form-item-feedback__line").first).to_be_visible()
            assert modal.REQUIRED_NAME_MSG in modal.form_feedback(), f"应提示：{modal.REQUIRED_NAME_MSG}"

        with allure.step("关闭弹窗且不产生数据"):
            modal.close()
            expect(detail.analysis_items).to_have_count(0)

    @allure.title("创建临床试验：默认未发布、统计为零")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.smoke
    def test_create_analysis(self, research_cleaner, analysis_cleaner, research_list_page: ResearchListPage) -> None:
        research, detail = _enter_analysis_tab(research_cleaner, research_list_page)
        name = build_test_name("临床试验")
        description = "E2E 自动化创建的临床试验描述"
        analysis_cleaner["register"](research["id"], name)  # 先登记，防止断言失败残留

        modal = detail.open_create_analysis()
        with allure.step(f"填写并提交：{name}"):
            modal.fill(name, description)
            modal.submit()
            modal.wait_closed()

        with allure.step("校验条目信息与初始统计"):
            item = detail.analysis_item(name)
            expect(item).to_be_visible()
            expect(item).to_contain_text(description)
            assert detail.analysis_status_text(name) == "未发布"
            assert detail.analysis_patient_count(name) == 0

    @allure.title("修改临床试验：回显正确且修改后生效")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_edit_analysis(self, research_cleaner, analysis_cleaner, research_list_page: ResearchListPage) -> None:
        _, analysis, detail = _open_analysis_tab_with_analysis(
            research_cleaner, analysis_cleaner, research_list_page, description="修改前描述"
        )
        new_name = build_test_name("临床试验-已修改")
        analysis_cleaner["register"](analysis["research_id"], new_name)

        with allure.step("打开修改弹窗并校验回显（等待接口回显完成）"):
            modal = detail.edit_analysis(analysis["name"])
            expect(modal.name_input).to_have_value(analysis["name"])
            expect(modal.description_input).to_have_value("修改前描述")

        with allure.step("修改名称与描述"):
            modal.fill(new_name, "修改后描述")
            modal.submit()
            modal.wait_closed()

        with allure.step("校验修改结果"):
            item = detail.analysis_item(new_name)
            expect(item).to_be_visible()
            expect(item).to_contain_text("修改后描述")
            expect(detail.analysis_item(analysis["name"])).to_have_count(0)

    @allure.title("发布与取消发布：状态联动 + 发布后详情数据列表不可编辑")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_publish_and_unpublish(
        self, api_client, research_cleaner, analysis_cleaner, research_list_page: ResearchListPage
    ) -> None:
        _, analysis, detail = _open_analysis_tab_with_analysis(
            research_cleaner, analysis_cleaner, research_list_page, description="发布用例"
        )
        # 发布前置条件：临床试验需至少配置一个字段（后端对无字段的发布请求会拦截）
        field_name = build_test_name("文本字段", max_length=60)
        api_client.save_analysis_custom_field(analysis["id"], field_name)
        detail.page.reload()
        detail.wait_network_idle()
        expect(detail.analysis_item(analysis["name"])).to_be_visible(timeout=15_000)

        with allure.step("未发布时添加一行数据（用于校验发布后的不可编辑状态）"):
            analysis_detail = detail.enter_analysis_detail(analysis["name"])
            analysis_detail.add_row_with_values({field_name: "发布前数据"})
            expect(analysis_detail.data_rows).to_have_count(1)
            analysis_detail.back_button.click()
            analysis_detail.wait_for_url("**/analysis/list")
            expect(detail.analysis_item(analysis["name"])).to_be_visible()

        with allure.step("列表发布：状态变为已发布"):
            detail.publish_analysis(analysis["name"])
            expect(detail.analysis_item(analysis["name"]).get_by_text("已发布")).to_be_visible(timeout=15_000)

        with allure.step("进入已发布详情：数据列表不可编辑"):
            analysis_detail = detail.enter_analysis_detail(analysis["name"])
            expect(analysis_detail.data_rows).to_have_count(1, timeout=15_000)
            expect(analysis_detail.unpublish_button).to_be_visible()
            assert analysis_detail.add_row_button.count() == 0, "发布后不应出现“添加一行”"
            assert analysis_detail.delete_selected_button.count() == 0, "发布后不应出现“删除选中”"
            assert analysis_detail.row_delete_buttons.count() == 0, "发布后行删除按钮应隐藏"
            assert analysis_detail.row_audit_buttons.count() == 0, "发布后“批量确认”应隐藏"
            assert analysis_detail.cell_edit_icon(0, 1).count() == 0, "发布后单元格编辑图标应隐藏"
            assert not analysis_detail.cell_edit_enabled(0, 1), "发布后点击单元格不应进入编辑态"
            analysis_detail.back_button.click()
            analysis_detail.wait_for_url("**/analysis/list")

        with allure.step("取消发布：状态恢复未发布，详情恢复可编辑"):
            detail.unpublish_analysis(analysis["name"])
            expect(detail.analysis_item(analysis["name"]).get_by_text("未发布")).to_be_visible(timeout=15_000)
            analysis_detail = detail.enter_analysis_detail(analysis["name"])
            expect(analysis_detail.add_row_button).to_be_visible()
            expect(analysis_detail.delete_selected_button).to_be_visible()
            expect(analysis_detail.row_audit_buttons).to_have_count(1)
            expect(analysis_detail.row_delete_buttons).to_have_count(1)
            assert analysis_detail.cell_edit_enabled(0, 1), "取消发布后点击单元格应可进入编辑态"

    @allure.title("字段配置：不完整拦截 + 自定义字段持久化")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_field_config(self, research_cleaner, analysis_cleaner, research_list_page: ResearchListPage) -> None:
        _, analysis, detail = _open_analysis_tab_with_analysis(
            research_cleaner, analysis_cleaner, research_list_page, description="字段配置用例"
        )
        field_name = build_test_name("文本字段", max_length=60)

        with allure.step("打开字段配置：初始为空状态"):
            modal = detail.open_analysis_field_config(analysis["name"])
            expect(modal.empty_text).to_be_visible()

        with allure.step("添加自定义字段但不填写名称：提交被拦截"):
            modal.add_custom_button.click()
            modal.submit()
            modal.page.wait_for_function(
                "(msg) => document.body.innerText.includes(msg)",
                arg=INCOMPLETE_FIELD_CONFIG_MSG,
            )
            assert modal.root.is_visible(), "填写不完整时弹窗应保持打开"

        with allure.step(f"填写字段名称并提交：{field_name}"):
            modal.rows.last.locator("input").first.fill(field_name)
            modal.submit()
            modal.wait_closed()

        with allure.step("重新打开字段配置：字段已持久化"):
            modal = detail.open_analysis_field_config(analysis["name"])
            assert field_name in modal.custom_field_names()
            modal.close()

    @allure.title("删除临床试验：确认后从列表移除")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_delete_analysis(self, research_cleaner, analysis_cleaner, research_list_page: ResearchListPage) -> None:
        _, analysis, detail = _open_analysis_tab_with_analysis(
            research_cleaner, analysis_cleaner, research_list_page, description="待删除临床试验"
        )

        with allure.step("点击删除并确认"):
            detail.delete_analysis(analysis["name"])

        with allure.step("校验已从列表移除"):
            expect(detail.analysis_item(analysis["name"])).to_have_count(0)

    @allure.title("临床试验搜索与发布状态筛选")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_search_and_status_filter(
        self, api_client, research_cleaner, analysis_cleaner, research_list_page: ResearchListPage
    ) -> None:
        research = research_cleaner["create"](objective="搜索筛选用例")
        published = analysis_cleaner["create"](research["id"], description="已发布项")
        unpublished = analysis_cleaner["create"](research["id"], description="未发布项")
        # 发布前置条件：需配置字段
        api_client.save_analysis_custom_field(published["id"], build_test_name("文本字段", max_length=60))
        api_client.publish_analysis(published["id"])

        research_list_page.refresh()
        research_list_page.search(research["name"])
        detail = research_list_page.enter_detail(research["name"])
        detail.click_tab("临床试验")
        expect(detail.analysis_item(published["name"])).to_be_visible()
        expect(detail.analysis_item(unpublished["name"])).to_be_visible()

        with allure.step("按名称搜索：仅命中目标项"):
            detail.search_analysis(unpublished["name"])
            expect(detail.analysis_item(unpublished["name"])).to_be_visible()
            expect(detail.analysis_item(published["name"])).to_have_count(0)

        with allure.step("清空名称搜索：恢复全部"):
            detail.search_analysis("")
            expect(detail.analysis_item(published["name"])).to_be_visible()
            expect(detail.analysis_item(unpublished["name"])).to_be_visible()

        with allure.step("状态筛选“发布”：仅显示已发布项"):
            detail.filter_analysis_by_status("发布")
            expect(detail.analysis_item(published["name"])).to_be_visible()
            expect(detail.analysis_item(unpublished["name"])).to_have_count(0)

        with allure.step("状态筛选“未发布”：仅显示未发布项"):
            detail.filter_analysis_by_status("未发布")
            expect(detail.analysis_item(unpublished["name"])).to_be_visible()
            expect(detail.analysis_item(published["name"])).to_have_count(0)


@allure.feature("临床试验")
@allure.story("临床试验-详情")
class TestAnalysisDetail:
    """临床试验详情页功能。"""

    @allure.title("详情页：空字段引导、字段配置与字段列渲染")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.smoke
    def test_detail_empty_and_field_config(
        self, research_cleaner, analysis_cleaner, research_list_page: ResearchListPage
    ) -> None:
        _, analysis, detail = _open_analysis_tab_with_analysis(
            research_cleaner, analysis_cleaner, research_list_page, description="详情空态用例"
        )
        field_name = build_test_name("文本字段", max_length=60)
        analysis_detail = detail.enter_analysis_detail(analysis["name"])

        with allure.step("校验页头与空字段引导"):
            expect(analysis_detail.analysis_name).to_have_text(analysis["name"])
            expect(analysis_detail.analysis_description).to_contain_text("详情空态用例")
            expect(analysis_detail.empty_fields_text).to_be_visible()
            expect(analysis_detail.stat_panel.get_by_text("填充率统计")).to_be_visible()

        with allure.step("通过空态引导完成字段配置"):
            field_config = analysis_detail.open_field_config()
            field_config.add_custom_field(field_name)
            field_config.submit()
            field_config.wait_closed()

        with allure.step("校验字段列与添加入口出现"):
            expect(analysis_detail.table_panel.get_by_text(field_name)).to_be_visible(timeout=15_000)
            expect(analysis_detail.add_row_button).to_be_visible()
            assert analysis_detail.data_count() == 0

    @allure.title("详情页数据操作：添加一行、单元格编辑、批量确认、删除行")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_row_operations(
        self, api_client, research_cleaner, analysis_cleaner, research_list_page: ResearchListPage
    ) -> None:
        _, analysis, field_name, detail = _prepare_analysis_with_field(
            api_client, research_cleaner, analysis_cleaner, research_list_page
        )
        analysis_detail = detail.enter_analysis_detail(analysis["name"])
        first_value = build_test_name("值")
        edited_value = build_test_name("值-已编辑")

        with allure.step("添加一行数据"):
            analysis_detail.add_row_with_values({field_name: first_value})
            expect(analysis_detail.data_rows).to_have_count(1)
            assert analysis_detail.data_count() == 1
            assert first_value in analysis_detail.first_row_text()

        with allure.step("编辑单元格：修改并失焦保存"):
            analysis_detail.edit_cell(edited_value, index=0, column=1)
            expect(analysis_detail.row(0)).to_contain_text(edited_value)

        with allure.step("批量确认该行数据"):
            analysis_detail.audit_row(0)
            expect(analysis_detail.data_rows).to_have_count(1)

        with allure.step("删除该行数据"):
            analysis_detail.delete_row(0)
            expect(analysis_detail.data_rows).to_have_count(0)
            assert analysis_detail.data_count() == 0

    @allure.title("详情页：删除选中、发布/取消发布（数据不可编辑）与返回列表")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_delete_selected_publish_and_back(
        self, api_client, research_cleaner, analysis_cleaner, research_list_page: ResearchListPage
    ) -> None:
        _, analysis, field_name, detail = _prepare_analysis_with_field(
            api_client, research_cleaner, analysis_cleaner, research_list_page
        )
        analysis_detail = detail.enter_analysis_detail(analysis["name"])
        expect(analysis_detail.add_row_button).to_be_visible()

        with allure.step("添加两行数据"):
            analysis_detail.add_row_with_values({field_name: build_test_name("值A")})
            analysis_detail.add_row_with_values({field_name: build_test_name("值B")})
            expect(analysis_detail.data_rows).to_have_count(2)

        with allure.step("勾选第一行并删除选中"):
            analysis_detail.check_row(0)
            analysis_detail.delete_selected()
            expect(analysis_detail.data_rows).to_have_count(1)

        with allure.step("详情页发布：数据列表整体不可编辑"):
            analysis_detail.publish()
            expect(analysis_detail.unpublish_button).to_be_visible(timeout=15_000)
            assert analysis_detail.add_row_button.count() == 0, "发布后不应出现“添加一行”"
            assert analysis_detail.delete_selected_button.count() == 0, "发布后不应出现“删除选中”"
            assert analysis_detail.row_delete_buttons.count() == 0, "发布后行删除按钮应隐藏"
            assert analysis_detail.row_audit_buttons.count() == 0, "发布后“批量确认”应隐藏"
            assert analysis_detail.cell_edit_icon(0, 1).count() == 0, "发布后单元格编辑图标应隐藏"
            assert not analysis_detail.cell_edit_enabled(0, 1), "发布后点击单元格不应进入编辑态"

        with allure.step("取消发布：数据列表恢复可编辑"):
            analysis_detail.unpublish()
            expect(analysis_detail.add_row_button).to_be_visible(timeout=15_000)
            expect(analysis_detail.row_audit_buttons).to_have_count(1)
            expect(analysis_detail.row_delete_buttons).to_have_count(1)
            assert analysis_detail.cell_edit_enabled(0, 1), "取消发布后点击单元格应可进入编辑态"

        with allure.step("返回列表：状态为未发布且数据保留"):
            analysis_detail.back_button.click()
            analysis_detail.wait_for_url("**/analysis/list")
            expect(detail.analysis_item(analysis["name"])).to_be_visible()
            assert detail.analysis_status_text(analysis["name"]) == "未发布"

    @allure.title("详情页上一条/下一条导航切换")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_detail_navigation(
        self, research_cleaner, analysis_cleaner, research_list_page: ResearchListPage
    ) -> None:
        research = research_cleaner["create"](objective="详情导航用例")
        first = analysis_cleaner["create"](research["id"], description="导航-第一条")
        second = analysis_cleaner["create"](research["id"], description="导航-第二条")
        research_list_page.refresh()
        research_list_page.search(research["name"])
        detail = research_list_page.enter_detail(research["name"])
        detail.click_tab("临床试验")
        expect(detail.analysis_item(first["name"])).to_be_visible()
        expect(detail.analysis_item(second["name"])).to_be_visible()

        with allure.step("进入第一条，点击“下一个”跳转并返回“上一个”"):
            analysis_detail = detail.enter_analysis_detail(first["name"])
            current_name = analysis_detail.analysis_name.inner_text().strip()
            assert current_name == first["name"]

            # 列表顺序不固定：目标条目可能排在“下一个”或“上一个”方向
            if analysis_detail.next_button.is_enabled():
                moved_name = analysis_detail.go_next()
                assert moved_name == second["name"]
                back_name = analysis_detail.go_previous()
                assert back_name == first["name"]
            else:
                moved_name = analysis_detail.go_previous()
                assert moved_name == second["name"]
                back_name = analysis_detail.go_next()
                assert back_name == first["name"]

    @allure.title("详情页：字段属性配置与单元格修改记录")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_attr_config_and_update_log(
        self, api_client, research_cleaner, analysis_cleaner, research_list_page: ResearchListPage
    ) -> None:
        _, analysis, field_name, detail = _prepare_analysis_with_field(
            api_client, research_cleaner, analysis_cleaner, research_list_page
        )
        analysis_detail = detail.enter_analysis_detail(analysis["name"])

        with allure.step("添加一行并编辑单元格（产生修改记录）"):
            analysis_detail.add_row_with_values({field_name: build_test_name("值")})
            expect(analysis_detail.data_rows).to_have_count(1)
            analysis_detail.edit_cell(build_test_name("值-已改"), index=0, column=1)

        with allure.step("打开单元格“修改记录”并关闭"):
            popover = analysis_detail.open_cell_update_log(index=0, column=1)
            expect(popover).to_be_visible()
            analysis_detail.table_panel.locator(".caption").click()  # 点击空白关闭气泡

        with allure.step("打开字段“属性配置”并保存描述"):
            analysis_detail.update_field_attribute(field_name, "E2E 属性描述")
            assert analysis_detail.field_attribute_description(field_name) == "E2E 属性描述"

    @allure.title("详情页：患者全景数据弹窗（表格/时间线）")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_patient_overview_modal(
        self, api_client, research_cleaner, analysis_cleaner, research_list_page: ResearchListPage
    ) -> None:
        # 造数：自建课题（绑定专病库）→ 临床试验 + 字段 → 导入 1 位患者（生成系统来源数据行）
        databases = api_client.query_databases_for_select()
        assert databases, "当前账号无可访问的专病库"
        database_id = databases[0]["id"]
        source_patients = api_client.query_database_patients(database_id, page_size=1)
        assert source_patients, "专病库无患者数据"
        research = research_cleaner["create"](database_id=database_id)
        analysis = analysis_cleaner["create"](research["id"], description="全景数据用例")
        api_client.save_analysis_custom_field(analysis["id"], build_test_name("文本字段", max_length=60))
        api_client.import_patients_to_research(database_id, [source_patients[0]["id"]], research["id"])
        api_client.import_patients_to_analysis(analysis["id"], [source_patients[0]["id"]])

        research_list_page.refresh()
        research_list_page.search(research["name"])
        detail = research_list_page.enter_detail(research["name"])
        detail.click_tab("临床试验")
        expect(detail.analysis_item(analysis["name"])).to_be_visible()
        analysis_detail = detail.enter_analysis_detail(analysis["name"])
        expect(analysis_detail.data_rows).to_have_count(1, timeout=15_000)

        with allure.step("点击“患者全景数据”打开弹窗并校验内容"):
            modal = analysis_detail.open_patient_overview(0)
            expect(modal.get_by_text("表格模式")).to_be_visible()
            expect(modal.get_by_text("时间线模式")).to_be_visible()
            # 数据加载完成判定：出现数据分组或空态
            analysis_detail.page.wait_for_function(
                "() => { const m = [...document.querySelectorAll('.custom-modal')].find(e => e.innerText.includes('全景数据'));"
                " return !!m && (m.querySelector('.table-item') || m.querySelector('.n-empty')); }",
                timeout=15_000,
            )

        with allure.step("关闭全景数据弹窗"):
            analysis_detail.close_modal(modal)


@allure.feature("课题管理")
@allure.story("课题详情-随访管理")
class TestFollowupTab:
    """随访管理页签：新建随访任务、搜索、删除选中。

    数据保护：随访任务创建在 ``research_cleaner`` 自建课题下，随课题清理一并删除。
    """

    def _enter_followup_tab(self, api_client, research_cleaner, research_list_page: ResearchListPage):
        """造数：自建课题 + 导入 1 位患者，进入随访管理页签。"""
        databases = api_client.query_databases_for_select()
        assert databases, "当前账号无可访问的专病库"
        database_id = databases[0]["id"]
        source_patients = api_client.query_database_patients(database_id, page_size=1)
        assert source_patients, "专病库无患者数据"
        research = research_cleaner["create"](database_id=database_id)
        api_client.import_patients_to_research(database_id, [source_patients[0]["id"]], research["id"])
        research_list_page.refresh()
        research_list_page.search(research["name"])
        detail = research_list_page.enter_detail(research["name"])
        detail.click_tab("随访管理")
        return research, detail

    @allure.title("随访任务：表单校验、新建、搜索与删除选中")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.smoke
    def test_followup_create_search_delete(
        self, api_client, research_cleaner, research_list_page: ResearchListPage
    ) -> None:
        _, detail = self._enter_followup_tab(api_client, research_cleaner, research_list_page)
        task_name = build_test_name("随访任务", max_length=30)

        with allure.step("空表单点击创建：三项必填校验"):
            detail.followup_create_button.click()
            expect(detail.followup_panel.get_by_text("请选择患者")).to_be_visible()
            expect(detail.followup_panel.get_by_text("请输入随访任务名称")).to_be_visible()
            expect(detail.followup_panel.get_by_text("请选择随访时间")).to_be_visible()
            detail.followup_reset_button.click()

        with allure.step(f"填写表单创建随访任务：{task_name}"):
            patient_name = detail.create_followup(task_name, remark="E2E 自动化随访备注")
            expect(detail.followup_table_rows.first).to_be_visible(timeout=15_000)
            expect(detail.followup_table_rows.first).to_contain_text(task_name)

        with allure.step("按患者姓名搜索：任务仍可见"):
            detail.followup_search_patient_input.fill(patient_name)
            detail.wait_network_idle()
            expect(detail.followup_table_rows.first).to_contain_text(task_name)

        with allure.step("按状态筛选“未完成”：任务可见"):
            detail.select_dropdown_option(detail.followup_status_select, "未完成")
            detail.wait_network_idle()
            expect(detail.followup_table_rows.first).to_contain_text(task_name)

        with allure.step("删除选中随访任务：列表清空"):
            detail.delete_selected_followups(0)
            expect(detail.followup_table_rows).to_have_count(0, timeout=15_000)


@allure.feature("课题管理")
@allure.story("课题详情-知识管理")
class TestKnowledgeTab:
    """知识管理页签：搜索、表格/图标模式切换与创建弹窗校验。

    说明：知识创建依赖文件上传（按范围排除），仅校验空提交拦截，不执行上传。
    """

    def _enter_knowledge_tab(self, research_cleaner, research_list_page: ResearchListPage):
        research = research_cleaner["create"](objective="知识管理用例")
        research_list_page.refresh()
        research_list_page.search(research["name"])
        detail = research_list_page.enter_detail(research["name"])
        detail.click_tab("知识管理")
        return research, detail

    @allure.title("知识管理：搜索、模式切换与创建弹窗校验")
    @allure.severity(allure.severity_level.NORMAL)
    def test_knowledge_search_mode_and_create_validation(
        self, research_cleaner, research_list_page: ResearchListPage
    ) -> None:
        _, detail = self._enter_knowledge_tab(research_cleaner, research_list_page)

        with allure.step("搜索不存在的知识文件：展示空数据"):
            detail.search_knowledge("E2E-AUTO-不存在的知识文件")
            expect(detail.page.get_by_text("无数据").first).to_be_visible()

        with allure.step("切换图标式/表格式视图"):
            detail.switch_knowledge_mode("图标式")
            expect(detail.page.locator(".button-radio-item.active")).to_contain_text("图标式")
            detail.switch_knowledge_mode("表格式")
            expect(detail.page.locator(".button-radio-item.active")).to_contain_text("表格式")

        with allure.step("打开创建弹窗：空提交提示需选择文件"):
            detail.knowledge_create_button.click()
            expect(detail.knowledge_modal).to_be_visible()
            detail.knowledge_modal.get_by_role("button", name="确定", exact=True).click()
            detail.wait_for_toast("请选择要上传的文件")
            detail.knowledge_modal.get_by_role("button", name="关闭", exact=True).click()
            expect(detail.knowledge_modal).to_be_hidden()
