# -*- coding: utf-8 -*-
"""智能标注模块测试用例。

覆盖点：
1. 标注任务列表：加载、空状态、底部统计；
2. 创建任务：弹窗必填校验、成功创建（自建数据）并出现在列表；
3. 修改任务：回显校验 + 名称/描述修改生效；
4. 删除任务：气泡确认弹窗 + 列表移除（仅删除自建数据）；
5. 名称搜索（命中 / 未命中）；
6. 任务范围筛选（我的任务 / 所有任务 / 我参与的任务）；
7. 任务详情：任务信息（创建人/创建时间/成员/描述）与标注集列表；
8. 创建标注集弹窗：必填校验（按项目要求不涉及上传/下载，仅校验表单规则）。

测试数据保护说明：
- 新建任务名称统一携带 E2E-AUTO 标识；
- 无论用例成功与否，``annotation_cleaner`` 夹具都会在用例结束后
  按“精确名称”检索并删除自建任务（修改类用例会同时登记新名称），
  绝不会误删存量数据。
"""

from __future__ import annotations

import allure
import pytest
from playwright.sync_api import expect

from src.pages.annotation_page import AnnotationDetailPage, AnnotationListPage
from src.utils.test_data import build_test_name

pytestmark = [allure.feature("智能标注"), pytest.mark.data_cleanup]


@allure.story("标注任务列表")
class TestAnnotationList:
    """列表加载 / 搜索 / 范围筛选。"""

    @allure.title("标注任务列表加载（空状态或数据列表）")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.smoke
    def test_list_loads(self, annotation_list_page: AnnotationListPage) -> None:
        with allure.step("校验页头操作区"):
            expect(annotation_list_page.create_button).to_be_visible()
        if annotation_list_page.is_empty():
            with allure.step("空状态：展示引导文案与创建入口"):
                expect(annotation_list_page.empty_text).to_be_visible()
                assert "创建第一个任务" in annotation_list_page.create_button.inner_text()
        else:
            with allure.step("数据状态：展示搜索框、任务卡片与分页统计"):
                expect(annotation_list_page.search_input).to_be_visible()
                assert annotation_list_page.items.count() > 0
                expect(annotation_list_page.footer_text).to_be_visible()

    @allure.title("按名称搜索任务：命中与未命中")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_search_task(self, annotation_cleaner, annotation_list_page: AnnotationListPage) -> None:
        task = annotation_cleaner["create"](description="搜索用例-描述")
        annotation_list_page.refresh()

        with allure.step(f"搜索自建任务：{task['name']}"):
            annotation_list_page.search(task["name"])
            expect(annotation_list_page.item(task["name"])).to_be_visible()

        with allure.step("搜索不存在的任务名称：展示空状态"):
            annotation_list_page.search("E2E-AUTO-不存在的任务-8z8z8")
            expect(annotation_list_page.page.get_by_text("暂无数据")).to_be_visible()

        with allure.step("清空搜索恢复列表"):
            annotation_list_page.search("")
            expect(annotation_list_page.item(task["name"])).to_be_visible()

    @allure.title("任务范围筛选：我的任务 / 所有任务 / 我参与的任务")
    @allure.severity(allure.severity_level.NORMAL)
    def test_scope_filter(self, annotation_cleaner, annotation_list_page: AnnotationListPage) -> None:
        task = annotation_cleaner["create"](description="范围筛选用例-描述")
        annotation_list_page.refresh()

        with allure.step("筛选“我的任务”：包含自建任务"):
            annotation_list_page.switch_scope("我的任务")
            expect(annotation_list_page.item(task["name"])).to_be_visible()

        with allure.step("筛选“所有任务”：包含自建任务"):
            annotation_list_page.switch_scope("所有任务")
            expect(annotation_list_page.item(task["name"])).to_be_visible()

        with allure.step("筛选“我参与的任务”：列表正常渲染（可能为空）"):
            annotation_list_page.switch_scope("我参与的任务")
            # 页面必须稳定处于“有数据”或“空状态”之一，而不能停留在加载中
            annotation_list_page.page.wait_for_function(
                "() => document.querySelector('.annotation-item')"
                " || document.querySelector('.body .n-empty')"
                " || document.querySelector('.empty')",
                timeout=10_000,
            )

        with allure.step("恢复“所有任务”范围"):
            annotation_list_page.switch_scope("所有任务")
            expect(annotation_list_page.item(task["name"])).to_be_visible()


@allure.story("创建标注任务")
class TestCreateAnnotation:
    """创建任务弹窗与数据创建。"""

    @allure.title("创建任务弹窗：名称为必填项")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_create_modal_required_validation(self, annotation_list_page: AnnotationListPage) -> None:
        modal = annotation_list_page.click_create()
        with allure.step("空表单提交：提示名称必填"):
            modal.submit()
            expect(modal.root.locator(".n-form-item-feedback__line").first).to_be_visible()
            assert modal.REQUIRED_NAME_MSG in modal.form_feedback(), f"应提示：{modal.REQUIRED_NAME_MSG}"
        with allure.step("关闭弹窗且不产生数据"):
            modal.close()

    @allure.title("创建带统一标识的自建任务并出现在列表")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.smoke
    def test_create_task(self, annotation_cleaner, annotation_list_page: AnnotationListPage) -> None:
        name = build_test_name("标注任务")
        description = "E2E 自动化创建的任务描述"
        annotation_cleaner["register"](name)  # 先登记，防止创建成功但断言失败时残留数据

        modal = annotation_list_page.click_create()
        with allure.step(f"填写并提交：{name}"):
            modal.fill(name, description)
            modal.submit()
            modal.wait_closed()

        with allure.step("列表中可检索到新任务，且展示描述与初始数据集数量"):
            annotation_list_page.search(name)
            item = annotation_list_page.item(name)
            expect(item).to_be_visible()
            expect(item).to_contain_text(description)
            assert annotation_list_page.task_dataset_count(name) == 0


@allure.story("修改标注任务")
class TestEditAnnotation:
    """修改任务弹窗与回显。"""

    @allure.title("修改任务：回显正确且修改后生效")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_edit_task(self, annotation_cleaner, annotation_list_page: AnnotationListPage) -> None:
        task = annotation_cleaner["create"](description="修改前描述")
        annotation_list_page.refresh()
        new_name = build_test_name("标注任务-已修改")
        new_description = "修改后描述"
        annotation_cleaner["register"](new_name)  # 名称变化后同样需要兜底清理

        with allure.step("打开修改弹窗并校验回显（等待接口回显完成）"):
            annotation_list_page.search(task["name"])
            modal = annotation_list_page.click_edit(task["name"])
            expect(modal.name_input).to_have_value(task["name"])
            expect(modal.description_input).to_have_value("修改前描述")

        with allure.step(f"修改名称与描述：{new_name}"):
            modal.fill(new_name, new_description)
            modal.submit()
            modal.wait_closed()

        with allure.step("校验修改结果"):
            annotation_list_page.search(new_name)
            item = annotation_list_page.item(new_name)
            expect(item).to_be_visible()
            expect(item).to_contain_text(new_description)
            expect(annotation_list_page.item(task["name"])).to_have_count(0)


@allure.story("删除标注任务")
class TestDeleteAnnotation:
    """删除任务（自建数据）。"""

    @allure.title("删除自建任务：确认弹窗后从列表移除")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_delete_task(self, annotation_cleaner, annotation_list_page: AnnotationListPage) -> None:
        task = annotation_cleaner["create"](description="待删除任务")
        annotation_list_page.refresh()
        annotation_list_page.search(task["name"])
        expect(annotation_list_page.item(task["name"])).to_be_visible()

        with allure.step("点击删除并确认"):
            annotation_list_page.delete_task(task["name"])

        with allure.step("校验任务已从列表移除"):
            annotation_list_page.wait_network_idle()
            expect(annotation_list_page.item(task["name"])).to_have_count(0)


@allure.story("标注任务详情")
class TestAnnotationDetail:
    """任务详情页。"""

    @allure.title("任务详情：信息展示与标注集空状态")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_detail_info(self, annotation_cleaner, annotation_list_page: AnnotationListPage) -> None:
        task = annotation_cleaner["create"](description="详情用例-描述")
        annotation_list_page.refresh()
        annotation_list_page.search(task["name"])
        detail: AnnotationDetailPage = annotation_list_page.enter_detail(task["name"])

        with allure.step("校验任务信息"):
            expect(detail.task_name).to_have_text(task["name"])
            expect(detail.task_description).to_contain_text("详情用例-描述")
            current_user = detail.read_local_user_info().get("realName", "")
            assert detail.info_item_value("创建人") == current_user
            assert detail.info_item_value("成员") == "-", "未添加成员时成员应展示为 -"
            expect(detail.info_body.locator("time").first).to_be_visible()

        with allure.step("校验标注集列表为空状态与操作按钮"):
            expect(detail.dataset_panel_title.first).to_be_visible()
            expect(detail.dataset_empty_text).to_be_visible()
            expect(detail.create_dataset_button).to_be_visible()
            assert detail.delete_selected_button.is_disabled(), "未勾选数据集时删除按钮应禁用"

    @allure.title("创建标注集弹窗：名称为必填项")
    @allure.severity(allure.severity_level.NORMAL)
    def test_create_dataset_modal_validation(self, annotation_cleaner, annotation_list_page: AnnotationListPage) -> None:
        task = annotation_cleaner["create"](description="标注集弹窗用例")
        annotation_list_page.refresh()
        annotation_list_page.search(task["name"])
        detail = annotation_list_page.enter_detail(task["name"])

        modal = detail.open_create_dataset_modal()
        with allure.step("校验弹窗结构（名称/描述/标注人员/审核人员）"):
            expect(modal.name_input).to_be_visible()
            expect(modal.description_input).to_be_visible()
            expect(modal.root.get_by_text("标注人员")).to_be_visible()
            expect(modal.root.get_by_text("审核人员")).to_be_visible()
        with allure.step("空表单提交：提示名称必填"):
            modal.submit()
            expect(modal.root.locator(".n-form-item-feedback__line").first).to_be_visible()
            assert modal.REQUIRED_NAME_MSG in modal.form_feedback()
        with allure.step("关闭弹窗"):
            modal.close()

    @allure.title("详情页返回任务列表")
    @allure.severity(allure.severity_level.NORMAL)
    def test_back_to_list(self, annotation_cleaner, annotation_list_page: AnnotationListPage) -> None:
        task = annotation_cleaner["create"](description="返回用例")
        annotation_list_page.refresh()
        annotation_list_page.search(task["name"])
        detail = annotation_list_page.enter_detail(task["name"])
        with allure.step("点击返回按钮"):
            list_page = detail.back_to_list()
            expect(list_page.search_input).to_be_visible()
        with allure.step("校验返回后仍可检索到任务"):
            list_page.search(task["name"])
            expect(list_page.item(task["name"])).to_be_visible()


@allure.story("标注集管理")
class TestAnnotationDataset:
    """标注任务详情-标注集（数据集）增删改查与从数据集导入。

    数据保护说明：
    - 标注集创建在 ``annotation_cleaner`` 自建任务下，随任务清理一并删除；
    - “从数据集导入”依赖环境中存在已转换的影像数据集（本环境可能为空）：
      树为空时仅校验弹窗交互与禁用态；树非空时勾选首个数据集并提交导入。
    """

    def _enter_task_detail(self, annotation_cleaner, annotation_list_page: AnnotationListPage, description: str):
        """创建自建标注任务并进入任务详情。"""
        task = annotation_cleaner["create"](description=description)
        annotation_list_page.refresh()
        annotation_list_page.search(task["name"])
        return task, annotation_list_page.enter_detail(task["name"])

    @allure.title("标注集增删改查：创建、详情展示、修改、删除")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.smoke
    def test_dataset_crud(self, annotation_cleaner, annotation_list_page: AnnotationListPage) -> None:
        _, detail = self._enter_task_detail(annotation_cleaner, annotation_list_page, "标注集用例")
        name = build_test_name("标注集", max_length=30)
        description = "E2E 自动化创建的标注集描述"

        with allure.step(f"创建标注集：{name}"):
            detail.create_dataset(name, description)
            expect(detail.dataset_item(name)).to_be_visible()

        with allure.step("详情区联动展示标注集信息与数据列表初始状态"):
            current_user = detail.read_local_user_info().get("realName", "")
            info_text = detail.dataset_info_text.inner_text()
            assert name in info_text
            assert current_user in info_text
            assert description in info_text
            expect(detail.dataset_data_list_text.first).to_be_visible()
            assert detail.dataset_data_count() == 0

        with allure.step("修改标注集名称与描述"):
            new_name = build_test_name("标注集-已改", max_length=30)
            modal = detail.edit_dataset(name)
            expect(modal.name_input).to_have_value(name)
            modal.fill(new_name, "修改后描述")
            modal.submit()
            modal.wait_closed()
            expect(detail.dataset_item(new_name)).to_be_visible()
            assert "修改后描述" in detail.dataset_info_text.inner_text()

        with allure.step("删除标注集：确认后从列表移除"):
            detail.delete_dataset(new_name)
            expect(detail.dataset_item(new_name)).to_have_count(0)
            expect(detail.dataset_empty_text).to_be_visible()

    @allure.title("从数据集导入：弹窗交互与导入提交")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_import_from_dataset(self, annotation_cleaner, annotation_list_page: AnnotationListPage) -> None:
        _, detail = self._enter_task_detail(annotation_cleaner, annotation_list_page, "从数据集导入用例")
        detail.create_dataset(build_test_name("标注集", max_length=30), "导入目标标注集")

        with allure.step("打开“从数据集导入”弹窗：校验结构与禁用态"):
            modal = detail.open_import_modal()
            expect(modal.search_input).to_be_visible()
            expect(modal.tip_text).to_be_visible()
            expect(modal.start_button).to_be_disabled()

        with allure.step("勾选数据集并开始导入（环境无数据集时仅关闭弹窗）"):
            if modal.tree_nodes.count() > 0:
                modal.check_first_node()
                expect(modal.start_button).to_be_enabled()
                modal.start_import()
            else:
                modal.close_button.click()
                modal.wait_closed()

    @allure.title("标注集筛选、删除选中与详情信息")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_dataset_filter_delete_selected_and_info(
        self, annotation_cleaner, annotation_list_page: AnnotationListPage
    ) -> None:
        _, detail = self._enter_task_detail(annotation_cleaner, annotation_list_page, "标注集补充用例")
        first = build_test_name("标注集", max_length=30)
        second = build_test_name("标注集", max_length=30)
        detail.create_dataset(first, "筛选删除用例-A")
        detail.create_dataset(second, "筛选删除用例-B")
        expect(detail.dataset_items).to_have_count(2)

        with allure.step("按名称筛选：仅命中目标标注集"):
            detail.filter_datasets(first)
            expect(detail.dataset_items).to_have_count(1)
            expect(detail.dataset_item(first)).to_be_visible()

        with allure.step("重置筛选：恢复全部"):
            detail.reset_dataset_filter()
            expect(detail.dataset_items).to_have_count(2)

        with allure.step("详情信息：标注人员/审核人员为空占位"):
            detail.select_dataset(first)
            assert detail.dataset_info_item_value("标注人员") in ("-", ""), "未设置标注人员时应展示占位符"
            assert detail.dataset_info_item_value("审核人员") in ("-", ""), "未设置审核人员时应展示占位符"

        with allure.step("勾选并删除选中：仅目标标注集被移除"):
            detail.check_dataset(first)
            detail.delete_selected_datasets()
            expect(detail.dataset_item(first)).to_have_count(0)
            expect(detail.dataset_item(second)).to_be_visible()
