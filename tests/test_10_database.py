# -*- coding: utf-8 -*-
"""专病检索模块测试用例。

覆盖点：
1. 专病库列表加载与卡片信息完整性；
2. 按名称搜索（命中 / 未命中 / 模糊 / 清空恢复）；
3. 列表页“查询统计”弹窗（检查类型切换、患者/病例总数、字段填充率）；
4. 进入专病库详情：患者列表、全景数据分组、表格/时间线模式切换；
5. 患者编号搜索（命中 / 未命中 / 清空恢复）；
6. 患者视图与影像视图切换；
7. 详情页筛选面板的打开与关闭、**条件构建执行筛选 / 重置**；
8. **导入选中患者到课题**（数据落到自建课题，随课题一并清理）；
9. 返回专病库列表。

测试数据保护说明：
- 存量数据只读：除“导入到课题”外不对环境做写操作；
- “导入到课题”目标为 ``research_cleaner`` 创建的自建课题，
  用例结束随课题删除一并清理，不影响存量课题与专病库数据；
- 用例中的专病库名称、患者编号均从页面/接口动态获取，避免硬编码。
"""

from __future__ import annotations

import re

import allure
import pytest
from playwright.sync_api import expect

from src.pages.database_page import DatabaseDetailPage, DatabaseListPage
from src.pages.research_page import ResearchListPage
from src.utils.test_data import build_test_name

pytestmark = allure.feature("专病检索")


@allure.story("专病库列表")
class TestDatabaseList:
    """专病库列表页。"""

    @allure.title("列表加载：卡片、统计数量与操作按钮完整")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.smoke
    def test_list_shows_cards(self, database_list_page: DatabaseListPage) -> None:
        with allure.step("校验统计标签与卡片数量"):
            expect(database_list_page.count_tag).to_be_visible()
            assert database_list_page.cards.count() > 0, "专病库列表应至少存在一个专病库"
        with allure.step("校验首张卡片的关键信息"):
            first_card = database_list_page.cards.first
            assert first_card.locator(".name").inner_text().strip(), "卡片应展示专病库名称"
            assert first_card.get_by_text("患者").is_visible()
            assert first_card.get_by_text("病例").is_visible()
            assert first_card.get_by_role("button", name="查看统计").is_visible()
            assert first_card.get_by_role("button", name="进入").is_visible()
        with allure.step("校验底部分页说明"):
            expect(database_list_page.footer_text).to_be_visible()

    @allure.title("按名称搜索存量专病库：精确命中")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_search_existing_database(self, database_list_page: DatabaseListPage) -> None:
        target = database_list_page.first_card_name()
        with allure.step(f"搜索存量专病库：{target}"):
            database_list_page.search(target)
        with allure.step("校验搜索结果"):
            assert database_list_page.cards.count() >= 1
            assert database_list_page.card(target).is_visible()

    @allure.title("按关键字模糊搜索专病库")
    @allure.severity(allure.severity_level.NORMAL)
    def test_search_database_fuzzy(self, database_list_page: DatabaseListPage) -> None:
        """取存量名称的前两个字符做模糊搜索，结果应全部包含该关键字。"""
        target = database_list_page.first_card_name()
        keyword = target[:2]
        with allure.step(f"使用关键字搜索：{keyword}"):
            database_list_page.search(keyword)
        names = database_list_page.card_names()
        assert names, "模糊搜索应至少命中一条结果"
        assert all(keyword in name for name in names), f"结果应全部包含关键字：{names}"

    @allure.title("搜索不存在的专病库：展示空状态")
    @allure.severity(allure.severity_level.NORMAL)
    def test_search_non_existing_database(self, database_list_page: DatabaseListPage) -> None:
        with allure.step("搜索不存在的名称"):
            database_list_page.search("E2E-AUTO-不存在的专病库-9x9x9")
            expect(database_list_page.page.get_by_text("暂无数据")).to_be_visible()
            assert database_list_page.cards.count() == 0

    @allure.title("搜索后清空关键字恢复全量列表")
    @allure.severity(allure.severity_level.NORMAL)
    def test_search_clear_restores_list(self, database_list_page: DatabaseListPage) -> None:
        with allure.step("等待首屏列表加载完成后记录总数"):
            expect(database_list_page.cards.first).to_be_visible()
            total = database_list_page.cards.count()
            assert total >= 2, "当前环境应至少存在两个存量专病库"
        target = database_list_page.first_card_name()

        with allure.step(f"搜索：{target}（结果收敛）"):
            database_list_page.search(target)
            expect(database_list_page.cards.first).to_be_visible()
            names = database_list_page.card_names()
            assert names and all(target in name for name in names)
            assert len(names) < total, "精确搜索应使结果数量减少"

        with allure.step("清空关键字后应恢复全量"):
            database_list_page.search("")
            expect(database_list_page.cards).to_have_count(total)


@allure.story("查询统计")
class TestDatabaseStat:
    """列表页“查看统计”弹窗。"""

    @allure.title("查询统计弹窗：检查类型、患者/病例总数与字段填充率")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_stat_modal_content(self, database_list_page: DatabaseListPage) -> None:
        target = database_list_page.first_card_name()
        modal = database_list_page.open_stat_modal(target)
        with allure.step("校验检查类型与总量统计"):
            question_names = modal.question_names()
            assert len(question_names) > 0, "查询统计应至少包含一种检查类型"
            assert modal.patient_total_value() >= 0
            assert modal.case_total_value() >= 0
        with allure.step("校验字段填充率区域"):
            expect(modal.field_count_text).to_be_visible()
            assert len(modal.field_names()) > 0, "字段填充率应至少包含一个字段"
        with allure.step("切换检查类型后字段统计联动"):
            if len(question_names) > 1:
                modal.select_question(question_names[1])
                expect(modal.field_count_text).to_be_visible()
        modal.close()
        with allure.step("校验弹窗已关闭"):
            expect(modal.root).to_be_hidden()


@allure.story("专病库详情")
class TestDatabaseDetail:
    """专病库详情页（患者视图）。"""

    @allure.title("进入详情：页头、患者列表与全景数据加载")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.smoke
    def test_enter_detail(self, database_list_page: DatabaseListPage) -> None:
        target = database_list_page.first_card_name()
        detail: DatabaseDetailPage = database_list_page.enter_database(target)
        with allure.step("校验页头信息"):
            expect(detail.database_name).to_contain_text(target)
            assert detail.back_button.is_visible()
            expect(detail.patient_view_tab).to_be_visible()
            expect(detail.image_view_tab).to_be_visible()
        with allure.step("校验患者列表加载"):
            expect(detail.patient_total_text).to_be_visible()
            total = detail.patient_total()
            assert total > 0, "存量专病库应包含患者数据"
            assert detail.patient_items.count() > 0
        with allure.step("校验全景数据默认表格模式加载"):
            expect(detail.table_mode_button).to_be_visible()
            expect(detail.page.locator(".table-item").first).to_be_visible()
            assert len(detail.section_names()) > 0, "全景数据应至少包含一个数据分组"

    @allure.title("患者编号搜索：命中、未命中与清空恢复")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_patient_search(self, database_list_page: DatabaseListPage) -> None:
        detail = database_list_page.enter_database(database_list_page.first_card_name())
        total = detail.patient_total()
        if total == 0:
            pytest.skip("当前专病库无患者数据，跳过患者搜索用例")
        patient_no = detail.first_patient_no()

        with allure.step(f"按存量患者编号搜索：{patient_no}"):
            detail.search_patient(patient_no)
            detail.wait_patient_search_applied(patient_no)
            # 说明：个别专病库可能存在重复编号，这里校验“结果均包含该编号”而非数量断言
            assert patient_no in detail.first_patient_item_text()

        with allure.step("搜索不存在的患者编号：展示空状态"):
            detail.search_patient("999999999")
            expect(detail.patient_empty_text).to_be_visible(timeout=15_000)
            assert detail.patient_items.count() == 0

        with allure.step("清空搜索条件：列表恢复"):
            detail.clear_patient_search()
            expect(detail.patient_items).to_have_count(min(total, 10), timeout=15_000)

    @allure.title("切换患者查看全景数据")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_switch_patient_loads_data(self, database_list_page: DatabaseListPage) -> None:
        detail = database_list_page.enter_database(database_list_page.first_card_name())
        if detail.patient_items.count() < 2:
            pytest.skip("当前专病库患者不足两位，跳过切换患者用例")
        with allure.step("点击第二位患者，全景数据重新加载"):
            detail.patient_items.nth(1).click()
            detail.wait_table_data_loaded()

    @allure.title("全景数据表格模式与时间线模式切换")
    @allure.severity(allure.severity_level.NORMAL)
    def test_switch_data_mode(self, database_list_page: DatabaseListPage) -> None:
        detail = database_list_page.enter_database(database_list_page.first_card_name())
        if detail.patient_items.count() == 0:
            pytest.skip("当前专病库无患者数据，跳过模式切换用例")

        with allure.step("初始为表格模式：记录数据分组"):
            assert "表格模式" in detail.active_mode_label()
            detail.wait_table_data_loaded()
            table_sections = detail.section_names()
            assert len(table_sections) > 0, "表格模式应展示数据分组"

        with allure.step("切换为时间线模式：校验节点内容或空状态"):
            detail.switch_to_timeline_mode()
            assert "时间线模式" in detail.active_mode_label()
            rendered = detail.is_visible(detail.timeline_items.first, 15_000) or detail.page.get_by_text("暂无数据").first.is_visible()
            assert rendered, "时间线模式应渲染数据节点或空状态"
            if detail.timeline_items.count() > 0:
                # 有数据时：每个节点应包含时间文案（如 2021-08-10 20:15:55）
                first_timeline_text = detail.timeline_items.first.inner_text()
                assert re.search(r"\d{4}[-/]\d{2}", first_timeline_text), f"时间线节点应包含时间：{first_timeline_text[:60]}"

        with allure.step("切换回表格模式：数据分组恢复"):
            detail.switch_to_table_mode()
            assert "表格模式" in detail.active_mode_label()
            detail.wait_table_data_loaded()
            assert detail.section_names() == table_sections, "切回表格模式后数据分组应与初始一致"

    @allure.title("患者视图与影像视图切换")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_switch_view(self, database_list_page: DatabaseListPage) -> None:
        detail = database_list_page.enter_database(database_list_page.first_card_name())
        with allure.step("初始为患者视图"):
            expect(detail.patient_search_input).to_be_visible()

        with allure.step("切换到影像视图：渲染模态页签或空状态"):
            detail.switch_to_image_view()
            detail.wait_network_idle()
            image_area = detail.page.locator(".image-data")
            expect(image_area).to_be_visible()
            rendered = (
                image_area.locator(".n-tabs-tab").count() > 0
                or detail.page.locator(".image-data .n-empty").is_visible()
            )
            assert rendered, "影像视图应渲染模态页签或空状态"

        with allure.step("切换回患者视图"):
            detail.switch_to_patient_view()
            expect(detail.patient_search_input).to_be_visible()

    @allure.title("筛选面板打开与关闭")
    @allure.severity(allure.severity_level.NORMAL)
    def test_filter_panel(self, database_list_page: DatabaseListPage) -> None:
        detail = database_list_page.enter_database(database_list_page.first_card_name())
        with allure.step("打开筛选面板并校验关键操作"):
            detail.open_filter()
            popover = detail.filter_popover
            expect(popover.get_by_role("button", name="添加筛选条件")).to_be_visible()
            expect(popover.get_by_role("button", name="重置")).to_be_visible()
            expect(popover.get_by_role("button", name=re.compile(r"^搜索$"))).to_be_visible()
        with allure.step("添加一条筛选条件后删除，不执行搜索"):
            popover.get_by_role("button", name="添加筛选条件").click()
            expect(popover.locator(".condition-item").first).to_be_visible()
            popover.locator("button[title='删除筛选条件']").first.click()
            expect(popover.locator(".condition-item")).to_have_count(0)
        with allure.step("关闭筛选面板"):
            detail.close_filter()
            expect(detail.filter_popover).to_be_hidden()

    @allure.title("返回专病库列表")
    @allure.severity(allure.severity_level.NORMAL)
    def test_back_to_list(self, database_list_page: DatabaseListPage) -> None:
        detail = database_list_page.enter_database(database_list_page.first_card_name())
        with allure.step("点击返回按钮"):
            detail.back_button.click()
            detail.wait_for_url("**/database/list")
            expect(database_list_page.search_input).to_be_visible()


@allure.story("专病库详情-患者操作")
class TestDatabasePatientActions:
    """患者筛选执行与导入课题（写操作仅落在自建课题上）。"""

    @allure.title("执行患者筛选：条件命中、未命中与重置恢复")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.smoke
    def test_execute_patient_filter(self, database_list_page: DatabaseListPage, api_client) -> None:
        """完整筛选链路：添加条件 → 选择字段/运算符/值 → 搜索 → 重置。

        说明：动态选择一个“含 ID 字段（取值为患者编号）”的专病库，
        构造可确定验证的条件：等于存量患者编号 → 命中 1 人；
        等于不存在值 → 空结果；重置后恢复全量。
        """
        candidates = []
        for database in api_client.query_databases_for_select():
            for group in api_client.query_patient_field_tree(database["id"]):
                for field in group.get("children") or []:
                    if field.get("tag") == "ID":
                        candidates.append((database, str(group["tag"]), str(field["tag"])))
        if not candidates:
            pytest.skip("当前环境不存在含 ID 字段的专病库，跳过筛选执行用例")
        database, group_tag, field_tag = candidates[0]

        detail = database_list_page.enter_database(database["name"])
        total = detail.patient_total()
        if total == 0:
            pytest.skip(f"专病库[{database['name']}]无患者数据，跳过筛选执行用例")
        patient_no = detail.first_patient_no()

        with allure.step("构建条件：ID 等于存量患者编号 → 命中 1 人"):
            detail.open_filter()
            detail.add_filter_condition()
            detail.select_filter_field(group_tag, field_tag)
            detail.select_filter_operator("等于")
            detail.fill_filter_value(patient_no)
            detail.click_filter_search()
            assert detail.filter_searched(), "执行筛选后按钮应变为“已筛选”"
            expect(detail.patient_items).to_have_count(1, timeout=15_000)
            assert patient_no in detail.first_patient_item_text()

        with allure.step("修改条件值：ID 等于不存在值 → 空结果"):
            detail.open_filter()
            detail.fill_filter_value("E2E-AUTO-NO-MATCH")
            detail.click_filter_search()
            expect(detail.patient_empty_text).to_be_visible(timeout=15_000)
            assert detail.patient_items.count() == 0

        with allure.step("重置筛选条件：列表恢复全量"):
            detail.reset_filter()
            assert not detail.filter_searched(), "重置后按钮应恢复为“筛选”"
            expect(detail.patient_items).to_have_count(min(total, 10), timeout=15_000)

    @allure.title("导入选中患者到课题：自建课题患者列表可见")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.smoke
    def test_import_patient_to_research(self, database_list_page: DatabaseListPage, research_cleaner) -> None:
        """勾选存量患者 → 导入到自建课题 → 课题患者列表可见该患者。

        数据保护：导入目标为自动化自建课题（随用例清理一并删除），
        专病库存量数据不受影响。
        """
        detail: DatabaseDetailPage = database_list_page.enter_database(database_list_page.first_card_name())
        if detail.patient_items.count() == 0:
            pytest.skip("当前专病库无患者数据，跳过导入课题用例")
        match = re.search(r"/database/detail/(\d+)", detail.current_url)
        assert match, f"未从详情页地址解析出专病库 id：{detail.current_url}"
        database_id = int(match.group(1))
        imported_no = detail.first_patient_no()
        research = research_cleaner["create"](database_id=database_id)

        with allure.step(f"导入选中患者到自建课题：{research['name']}"):
            detail.import_selected_patients_to_research(research["name"])

        with allure.step("进入课题患者管理页签校验导入结果"):
            list_page = ResearchListPage(detail.page).open()
            list_page.search(research["name"])
            research_detail = list_page.enter_detail(research["name"])
            expect(research_detail.patient_items.first).to_be_visible(timeout=20_000)
            assert research_detail.patient_items.count() >= 1
            assert imported_no in research_detail.patient_items.first.inner_text()


@allure.story("专病库详情-影像视图与检索模板")
class TestDatabaseImageAndTemplate:
    """影像视图（模态/筛选/导入到数据集）与患者筛选模板。"""

    @staticmethod
    def _find_database_with_image(api_client) -> dict:
        """动态选择一个含影像数据的专病库（模态非空）。"""
        for database in api_client.query_databases_for_select():
            if api_client.query_modalities(database["id"]):
                return database
        pytest.skip("当前环境不存在含影像数据的专病库，跳过影像视图用例")

    @allure.title("影像视图：模态页签、影像数据加载与筛选面板")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_image_view_modality_and_filter(self, database_list_page: DatabaseListPage, api_client) -> None:
        database = self._find_database_with_image(api_client)
        detail = database_list_page.enter_database(database["name"])
        detail.switch_to_image_view()
        detail.wait_network_idle()

        with allure.step("校验模态页签与默认模态数据加载"):
            modalities = detail.image_modality_names()
            assert modalities, "影像视图应展示模态页签"
            # 数据加载完成判定：表格出现数据行或展示空态
            detail.page.wait_for_function(
                "() => document.querySelector('.image-data .n-data-table-tbody')"
                " || document.querySelector('.image-data .n-empty')",
                timeout=15_000,
            )

        with allure.step("切换模态（存在多个时）"):
            if len(modalities) > 1:
                detail.switch_image_modality(modalities[1])
                assert modalities[1] in detail.image_modality_names()
                detail.switch_image_modality(modalities[0])

        with allure.step("打开并关闭影像数据筛选面板"):
            detail.open_image_filter()
            expect(detail.image_view_filter_popover.get_by_role("button", name="添加筛选条件")).to_be_visible()
            expect(detail.image_view_filter_popover.get_by_role("button", name=re.compile(r"^搜索$"))).to_be_visible()
            detail.close_image_filter()

        with allure.step("切回患者视图"):
            detail.switch_to_patient_view()
            expect(detail.patient_search_input).to_be_visible()

    @allure.title("影像视图：勾选影像数据导入到自建数据集")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.smoke
    def test_import_image_to_dataset(self, database_list_page: DatabaseListPage, api_client, research_cleaner) -> None:
        """数据库影像 → 导入到自建课题的影像数据集 → 数据集中可见。

        数据保护：导入目标为自建课题下的数据集，随课题清理一并删除。
        """
        database = self._find_database_with_image(api_client)
        research = research_cleaner["create"](database_id=database["id"])
        dataset_name = build_test_name("影像数据集", max_length=60)
        page = database_list_page.page

        with allure.step("先在自建课题下创建影像数据集（含收集人角色）"):
            list_page = ResearchListPage(page).open()
            list_page.search(research["name"])
            research_detail = list_page.enter_detail(research["name"])
            research_detail.click_tab("影像管理")
            dataset_modal = research_detail.open_create_dataset()
            dataset_modal.fill(dataset_name, "影像导入目标数据集")
            dataset_modal.select_first_collector()  # 选择当前用户为收集人（导入树依赖该角色）
            dataset_modal.submit()
            dataset_modal.wait_closed()
            expect(research_detail.dataset_item(dataset_name)).to_be_visible()

        with allure.step(f"影像视图勾选一条数据并导入到数据集：{dataset_name}"):
            database_list_page.open()
            detail = database_list_page.enter_database(database["name"])
            detail.switch_to_image_view()
            detail.wait_network_idle()
            if detail.image_data_rows.count() == 0:
                pytest.skip(f"专病库[{database['name']}]当前模态无影像数据，跳过导入用例")
            detail.check_image_row(0)
            detail.import_image_to_dataset(research["name"], dataset_name)

        with allure.step("校验数据集数据列表出现导入的影像数据"):
            detail.switch_to_patient_view()
            research_list = ResearchListPage(page).open()
            research_list.search(research["name"])
            research_detail = research_list.enter_detail(research["name"])
            research_detail.click_tab("影像管理")
            research_detail.select_dataset(dataset_name)
            research_detail.wait_dataset_data_count(1, timeout=30_000)

    @allure.title("筛选模板：保存、应用与删除")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_save_apply_delete_search_template(
        self, database_list_page: DatabaseListPage, api_client, search_template_cleaner
    ) -> None:
        """筛选条件 → 保存为模板 → 应用模板 → 删除模板。

        数据保护：模板创建在共享专病库维度，使用统一标识命名，
        用例内显式删除，并由 ``search_template_cleaner`` 夹具兜底清理。
        """
        candidates = []
        for database in api_client.query_databases_for_select():
            for group in api_client.query_patient_field_tree(database["id"]):
                for field in group.get("children") or []:
                    if field.get("tag") == "ID":
                        candidates.append((database, str(group["tag"]), str(field["tag"])))
        if not candidates:
            pytest.skip("当前环境不存在含 ID 字段的专病库，跳过筛选模板用例")
        database, group_tag, field_tag = candidates[0]

        detail = database_list_page.enter_database(database["name"])
        if detail.patient_total() == 0:
            pytest.skip(f"专病库[{database['name']}]无患者数据，跳过筛选模板用例")
        patient_no = detail.first_patient_no()
        template_name = build_test_name("筛选模板", max_length=50)
        search_template_cleaner["register"](database["id"], template_name)

        with allure.step("无筛选条件时“保存为模板”禁用"):
            detail.open_filter()
            expect(detail.save_template_button).to_be_disabled()

        with allure.step("构建条件并保存为模板"):
            detail.add_filter_condition()
            detail.select_filter_field(group_tag, field_tag)
            detail.select_filter_operator("等于")
            detail.fill_filter_value(patient_no)
            detail.save_filter_template(template_name)

        with allure.step("展开检索模板列表：模板已保存"):
            detail.expand_template_list()
            expect(detail.template_item(template_name)).to_be_visible()

        with allure.step("应用模板并搜索：条件生效命中 1 人"):
            detail.apply_filter_template(template_name)
            detail.click_filter_search()
            assert detail.filter_searched()
            expect(detail.patient_items).to_have_count(1, timeout=15_000)

        with allure.step("删除模板：确认后从列表移除"):
            detail.open_filter()
            detail.delete_filter_template(template_name)
            expect(detail.template_item(template_name)).to_have_count(0)
            detail.close_filter()
