# -*- coding: utf-8 -*-
"""轻量级接口客户端（基于 Playwright APIRequestContext）。

用途说明：
- 本项目的 E2E 断言全部通过 UI 完成；
- 接口客户端只用于 **测试前置数据准备** 与 **用例结束后的兜底清理**，
  例如：为“重命名会话”用例快速创建一条会话数据、在用例失败时仍然兜底删除
  自建数据。这样既保证界面交互的真实性，又让数据清理不依赖 UI 是否可用。

鉴权方式与前端一致：请求头携带 ``token``（登录后从 localStorage 获取）。
"""

from __future__ import annotations

import json
from typing import Any

from playwright.sync_api import APIRequestContext, APIResponse

from config.settings import settings
from src.common.logger import get_logger

logger = get_logger(__name__)

# 与前端 axios 拦截器约定一致：业务成功码为 200
SUCCESS_CODE = 200


def extract_token_from_storage_state(storage_state_path: str) -> str:
    """从 Playwright 保存的 storage_state 文件中提取登录 Token。

    storage_state 结构：``{"cookies": [...], "origins": [{"localStorage": [...]}]}``，
    平台把用户信息（含 token）保存在 localStorage 的 ``dmd-pro-userInfo`` 键中。
    """
    with open(storage_state_path, encoding="utf-8") as fp:
        state = json.load(fp)
    for origin in state.get("origins", []):
        for item in origin.get("localStorage", []):
            if item.get("name") == "dmd-pro-userInfo":
                return (json.loads(item.get("value") or "{}").get("value") or {}).get("token", "")
    return ""


class ApiClient:
    """业务接口客户端（仅覆盖测试所需的前置准备 / 清理接口）。

    注意：Playwright 的 APIRequestContext 在 ``base_url`` 与 ``/`` 开头路径
    拼接时会丢弃 base_url 的路径部分（URL 语义），因此这里不使用 base_url，
    而是每次请求显式拼接 ``<环境地址>/api`` 前缀，避免踩坑。
    """

    def __init__(self, request: APIRequestContext) -> None:
        self._request = request
        self._api_base = settings.base_url.rstrip("/") + "/api"

    # ------------------------------------------------------------------ #
    # 基础请求
    # ------------------------------------------------------------------ #
    def _check(self, response: APIResponse, action: str) -> dict[str, Any]:
        """校验业务响应码并返回响应体。"""
        try:
            body = response.json()
        except Exception as exc:  # pragma: no cover - 非 JSON 响应说明服务异常
            raise AssertionError(f"接口[{action}]返回非 JSON 内容：{response.text()[:200]}") from exc
        if body.get("code") != SUCCESS_CODE:
            raise AssertionError(f"接口[{action}]业务失败：code={body.get('code')}, msg={body.get('msg')}")
        return body

    def _post(self, path: str, data: Any = None, action: str = "") -> dict[str, Any]:
        response = self._request.post(self._api_base + path, data=data if data is not None else {})
        return self._check(response, action or path)

    def _get(self, path: str, params: dict | None = None, action: str = "") -> dict[str, Any]:
        response = self._request.get(self._api_base + path, params=params or {})
        return self._check(response, action or path)

    # ------------------------------------------------------------------ #
    # 灵犀问答（会话）
    # ------------------------------------------------------------------ #
    def create_conversation(self) -> dict[str, Any]:
        """创建一条 AI 会话，返回 ``{"id": ..., "label": ...}``。"""
        body = self._post("/ai/answer/chat/create", action="创建会话")
        logger.info("接口创建会话：%s", body.get("data"))
        return body.get("data") or {}

    def delete_conversation(self, conversation_id: int | str) -> None:
        """删除指定会话（清理自建测试数据）。"""
        self._post("/ai/answer/chat/delete", {"id": conversation_id}, action="删除会话")
        logger.info("接口删除会话：%s", conversation_id)

    def query_conversations(self) -> list[dict[str, Any]]:
        """查询当前用户全部会话列表。"""
        return self._get("/ai/answer/chat/list", action="查询会话列表").get("data") or []

    # ------------------------------------------------------------------ #
    # 智能标注（标注任务）
    # ------------------------------------------------------------------ #
    def create_annotation(self, name: str, description: str = "") -> dict[str, Any]:
        """创建标注任务，返回 ``{"id": ...}``。"""
        body = self._post(
            "/primary/annotation/create",
            {"name": name, "description": description, "userIds": None},
            action="创建标注任务",
        )
        logger.info("接口创建标注任务：%s -> %s", name, body.get("data"))
        return body.get("data") or {}

    def delete_annotation(self, annotation_id: int | str) -> None:
        """删除指定标注任务（清理自建测试数据）。"""
        self._post("/primary/annotation/delete", [annotation_id], action="删除标注任务")
        logger.info("接口删除标注任务：%s", annotation_id)

    def query_annotations(self, name: str = "", scope: str = "related", page_size: int = 100) -> list[dict[str, Any]]:
        """按名称模糊查询标注任务列表（用于校验清理结果）。"""
        body = self._get(
            "/primary/annotation/page",
            {"pageNo": 1, "pageSize": page_size, "name": name, "scope": scope},
            action="查询标注任务列表",
        )
        data = body.get("data") or {}
        return data.get("list") or []

    # ------------------------------------------------------------------ #
    # 课题管理
    # ------------------------------------------------------------------ #
    def create_research(
        self,
        name: str,
        objective: str = "",
        content: str = "",
        technology: str = "",
        database_id: Any = None,
        user_ids: Any = None,
    ) -> None:
        """创建课题（创建接口不返回业务数据，清理时按名称检索）。"""
        self._post(
            "/primary/research/create",
            {
                "name": name,
                "objective": objective,
                "content": content,
                "technology": technology,
                "databaseId": database_id,
                "userIds": user_ids,
            },
            action="创建课题",
        )
        logger.info("接口创建课题：%s", name)

    def delete_research(self, research_id: int | str) -> None:
        """删除指定课题（清理自建测试数据）。"""
        self._post("/primary/research/delete", [research_id], action="删除课题")
        logger.info("接口删除课题：%s", research_id)

    def query_researches(self, name: str = "", scope: str = "related", page_size: int = 100) -> list[dict[str, Any]]:
        """按名称模糊查询课题列表（用于校验清理结果）。"""
        body = self._get(
            "/primary/research/page",
            {"pageNo": 1, "pageSize": page_size, "name": name, "scope": scope},
            action="查询课题列表",
        )
        data = body.get("data") or {}
        return data.get("list") or []

    def create_research_and_get(
        self,
        name: str,
        objective: str = "",
        content: str = "",
        technology: str = "",
        database_id: Any = None,
    ) -> dict[str, Any]:
        """创建课题并回查主键（创建接口不返回 id，需要列表检索）。"""
        self.create_research(
            name,
            objective=objective,
            content=content,
            technology=technology,
            database_id=database_id,
        )
        rows = self.query_researches(name=name)
        for row in rows:
            if row.get("name") == name:
                return row
        return {}

    # ------------------------------------------------------------------ #
    # 课题患者 / 课题患者导入
    # ------------------------------------------------------------------ #
    def query_research_patients(self, research_id: int | str, page_size: int = 50) -> dict[str, Any]:
        """查询课题下的患者列表（返回 ``{"list": [...], "pagination": {...}}``）。"""
        body = self._get(
            "/primary/research/patient/page",
            {
                "pageNo": 1,
                "pageSize": page_size,
                "researchId": research_id,
                "patientNo": "",
                "name": "",
                "disableFlag": False,
            },
            action="查询课题患者",
        )
        return body.get("data") or {}

    def import_patients_to_research(
        self, database_id: int | str, patient_ids: list[str], research_id: int | str
    ) -> None:
        """把专病库患者导入到课题（夹具造数用，与界面“导入到课题”同接口）。"""
        self._post(
            "/fdn/database/patient/import",
            {"databaseId": database_id, "patientIds": patient_ids, "researchId": research_id},
            action="导入患者到课题",
        )
        logger.info("接口导入 %d 位患者到课题 %s", len(patient_ids), research_id)

    def import_patients_to_analysis(
        self, analysis_id: int | str, patient_ids: list[str], pick: str = "earliest"
    ) -> None:
        """把课题患者导入到临床试验（夹具造数用，需要临床试验已配置字段）。"""
        self._post(
            "/primary/research/patient/import",
            {"analysisId": analysis_id, "patientIds": patient_ids, "pick": pick},
            action="导入患者到临床试验",
        )
        logger.info("接口导入 %d 位患者到临床试验 %s", len(patient_ids), analysis_id)

    def query_database_patients(self, database_id: int | str, page_size: int = 10) -> list[dict[str, Any]]:
        """查询专病库患者列表（夹具造数：取患者 id）。"""
        body = self._post(
            "/fdn/database/patient/page",
            {
                "pageNo": 1,
                "pageSize": page_size,
                "databaseId": database_id,
                "query": {"id": "fixture", "logic": "and", "level": 1, "items": [], "type": "group"},
                "patientNo": "",
            },
            action="查询专病库患者",
        )
        data = body.get("data") or {}
        return data.get("list") or []

    def query_patient_field_tree(self, database_id: int | str) -> list[dict[str, Any]]:
        """查询患者筛选字段树（用于界面筛选用例选择字段）。"""
        body = self._get("/admin/question/field/tree", {"databaseId": database_id}, action="查询患者字段树")
        return body.get("data") or []

    def query_modalities(self, database_id: int | str) -> list[str]:
        """查询专病库影像模态列表（CT/MR/PETCT…），用于选择含影像数据的库。"""
        body = self._get("/fdn/database/series/modality/list", {"databaseId": database_id}, action="查询影像模态")
        return body.get("data") or []

    def query_databases_for_select(self) -> list[dict[str, Any]]:
        """查询用户可访问的专病库列表（用于夹具造数：拿数据库 id）。"""
        body = self._get("/admin/database/list", action="查询专病库列表")
        return body.get("data") or []

    def query_patient_search_templates(self, database_id: int | str) -> list[dict[str, Any]]:
        """查询专病库的患者筛选模板列表。"""
        body = self._get(
            "/fdn/database/patient/query/template/list",
            {"databaseId": database_id},
            action="查询患者筛选模板",
        )
        return body.get("data") or []

    def delete_patient_search_templates(self, template_ids: list[Any]) -> None:
        """删除患者筛选模板（清理自建测试数据）。"""
        self._post(
            "/fdn/database/patient/query/template/delete",
            template_ids,
            action="删除患者筛选模板",
        )
        logger.info("接口删除患者筛选模板：%s", template_ids)

    # ------------------------------------------------------------------ #
    # 临床试验（组学分析）
    # ------------------------------------------------------------------ #
    def create_analysis(self, research_id: int | str, name: str, description: str = "") -> None:
        """创建临床试验（创建接口不返回业务数据，清理时按名称检索）。"""
        self._post(
            "/primary/research/analysis/create",
            {"name": name, "description": description, "researchId": research_id},
            action="创建临床试验",
        )
        logger.info("接口创建临床试验：%s", name)

    def delete_analysis(self, analysis_id: int | str) -> None:
        """删除指定临床试验（清理自建测试数据）。"""
        self._post("/primary/research/analysis/delete", [analysis_id], action="删除临床试验")
        logger.info("接口删除临床试验：%s", analysis_id)

    def publish_analysis(self, analysis_id: int | str) -> None:
        """发布指定临床试验（夹具造数用，如状态筛选用例准备已发布数据）。"""
        self._post("/primary/research/analysis/status/publish", {"id": analysis_id}, action="发布临床试验")
        logger.info("接口发布临床试验：%s", analysis_id)

    def query_analyses(self, research_id: int | str, name: str = "", page_size: int = 100) -> list[dict[str, Any]]:
        """查询课题下的临床试验列表。"""
        body = self._get(
            "/primary/research/analysis/page",
            {"pageNo": 1, "pageSize": page_size, "researchId": research_id, "name": name},
            action="查询临床试验列表",
        )
        data = body.get("data") or {}
        return data.get("list") or []

    def save_analysis_custom_field(self, analysis_id: int | str, field_name: str) -> None:
        """为临床试验配置一个“文本型”自定义字段（夹具造数用，与界面字段配置同接口）。"""
        field = {
            "name": field_name,
            "source": "custom",
            "searchType": "text",
            "attributes": {
                "unit": "",
                "maxLimit": None,
                "minLimit": None,
                "format": None,
                "options": [],
                "description": "",
                "originFields": None,
            },
            "fieldId": None,
            "analysisId": analysis_id,
            "changed": True,
        }
        self._post(
            "/primary/research/analysis/field/save",
            {"fieldList": [field], "deleteIdList": []},
            action="保存临床试验字段配置",
        )
        logger.info("接口为临床试验 %s 配置自定义字段：%s", analysis_id, field_name)


def build_api_client(playwright, storage_state_path: str) -> tuple[ApiClient, APIRequestContext]:
    """根据已保存的登录态构建接口客户端。

    :param playwright: pytest-playwright 提供的 ``playwright`` fixture；
    :param storage_state_path: UI 登录后保存的 storage_state 文件路径；
    :return: ``(ApiClient 实例, APIRequestContext)``，调用方负责关闭 context。
    """
    token = extract_token_from_storage_state(storage_state_path)
    request_context = playwright.request.new_context(
        extra_http_headers={"token": token},
        timeout=settings.default_timeout_ms,
    )
    return ApiClient(request_context), request_context
