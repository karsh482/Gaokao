"""API 路由测试，直接注入假 pipeline（无需 DB / LLM）。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from gaokao_nl2sql import (
    AvailabilityInfo,
    CatalogPipeline,
    CatalogResult,
    Citation,
    Nl2SqlPipeline,
    QueryCategory,
    SqlGenerator,
    UnsafeSqlError,
)

from app.models import QueryRequest
from app.routers.query import query


class FakePipeline:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error

    def run(
        self,
        question: str,
        *,
        exam_province: str | None = None,
        plan_year: int | None = None,
    ):
        if self._error:
            raise self._error
        return self._result


class FakeModel:
    def __init__(self, sql: str = "SELECT 1 AS ok") -> None:
        self.sql = sql
        self.calls = 0

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        return self.sql


class FakeExecutor:
    def __init__(self, rows):
        self.rows = rows
        self.calls = 0

    def run(self, sql: str):
        self.calls += 1
        return self.rows


def test_query_happy_path():
    result = CatalogResult(
        question="位次一万能上哪些学校？",
        sql="SELECT school_name FROM staging.admission_records LIMIT 200",
        rows=[{"school_name": "四川大学"}],
        row_count=1,
        summary="当前条件下共返回 1 条可参考记录。",
        answer="四川大学可作为参考。",
        exam_province="贵州",
        plan_year=2025,
        subject_category=None,
        availability=AvailabilityInfo(True, (), ""),
        notes=("查询范围：考试/招生省份=贵州，招生年份=2025。",),
        citations=(
            Citation(
                source="staging.admission_records",
                label="投档录取数据",
                fields=("school_name",),
                exam_province="贵州",
                plan_year=2025,
            ),
        ),
        coverage_warnings=(),
        category=QueryCategory.SCORE_RANK_FILTER,
        applied_filters={"exam_province": "贵州", "plan_year": 2025},
    )
    response = query(
        QueryRequest(question="位次一万能上哪些学校？"),
        pipeline=FakePipeline(result=result),
    )

    assert response.row_count == 1
    assert response.summary == "当前条件下共返回 1 条可参考记录。"
    assert response.answer == "四川大学可作为参考。"
    assert response.rows[0]["school_name"] == "四川大学"
    assert response.sql is not None
    assert "limit" in response.sql.lower()
    assert response.exam_province == "贵州"
    assert response.plan_year == 2025
    assert response.availability.available is True
    assert response.citations[0].source == "staging.admission_records"
    assert response.coverage_warnings == []
    assert response.template_name is None


def test_query_out_of_scope_short_circuit_response():
    result = CatalogResult(
        question="四川省 2025 年有哪些学校？",
        sql=None,
        rows=[],
        row_count=0,
        summary="该省份数据暂不可用（当前仅支持贵州）。",
        answer=None,
        exam_province="贵州",
        plan_year=2025,
        subject_category=None,
        availability=AvailabilityInfo(
            False,
            ("province_out_of_scope",),
            "该省份数据暂不可用（当前仅支持贵州）。",
        ),
        notes=("该省份数据暂不可用（当前仅支持贵州）。",),
        citations=(),
        coverage_warnings=(),
        category=QueryCategory.GENERIC,
        applied_filters={},
    )
    response = query(
        QueryRequest(question="四川省 2025 年有哪些学校？"),
        pipeline=FakePipeline(result=result),
    )

    assert response.sql is None
    assert response.row_count == 0
    assert response.summary == "该省份数据暂不可用（当前仅支持贵州）。"
    assert response.rows == []
    assert response.availability.available is False
    assert response.availability.reasons == ["province_out_of_scope"]
    assert response.citations == []
    assert response.coverage_warnings == []
    assert response.template_name is None


def test_query_unsafe_sql_returns_400():
    with pytest.raises(HTTPException) as exc_info:
        query(
            QueryRequest(question="删表"),
            pipeline=FakePipeline(error=UnsafeSqlError("blocked")),
        )

    assert exc_info.value.status_code == 400


def test_query_empty_question_returns_422():
    with pytest.raises(ValueError):
        QueryRequest(question="")


def test_query_route_with_catalog_pipeline_rejects_trend_without_llm():
    model = FakeModel()
    executor = FakeExecutor(rows=[{"ok": 1}])
    catalog_pipeline = CatalogPipeline(
        nl2sql_pipeline=Nl2SqlPipeline(
            generator=SqlGenerator(model=model),
            executor=executor,
        )
    )

    response = query(
        QueryRequest(question="近几年贵州大学投档线趋势"),
        pipeline=catalog_pipeline,
    )

    assert response.sql is None
    assert response.rows == []
    assert response.row_count == 0
    assert response.availability.available is False
    assert response.availability.reasons == ["trend_needs_multi_year"]
    assert model.calls == 0
    assert executor.calls == 0
    assert response.template_name is None


def test_query_route_happy_path_contract():
    result = CatalogResult(
        question="贵州 2025 正常查询",
        sql="SELECT school_name FROM staging.admission_records LIMIT 200",
        rows=[{"school_name": "贵州大学"}],
        row_count=1,
        summary="当前查询共返回 1 条记录。",
        answer=None,
        exam_province="贵州",
        plan_year=2025,
        subject_category=None,
        availability=AvailabilityInfo(True, (), ""),
        notes=("查询范围：考试/招生省份=贵州，招生年份=2025。",),
        citations=(
            Citation(
                source="staging.admission_records",
                label="投档录取数据",
                fields=("school_name",),
                exam_province="贵州",
                plan_year=2025,
            ),
        ),
        coverage_warnings=(),
        category=QueryCategory.GENERIC,
        applied_filters={"exam_province": "贵州", "plan_year": 2025},
    )
    response = query(
        QueryRequest(question="贵州 2025 正常查询"),
        pipeline=FakePipeline(result=result),
    )

    assert response.row_count == 1
    assert response.summary == "当前查询共返回 1 条记录。"
    assert response.exam_province == "贵州"
    assert response.plan_year == 2025
    assert response.availability.available is True
    assert response.template_name is None


def test_query_route_out_of_scope_and_trend_short_circuit_contract():
    model = FakeModel()
    executor = FakeExecutor(rows=[{"ok": 1}])
    catalog_pipeline = CatalogPipeline(
        nl2sql_pipeline=Nl2SqlPipeline(
            generator=SqlGenerator(model=model),
            executor=executor,
        )
    )
    province_response = query(
        QueryRequest(question="四川省 2025 年有哪些学校"),
        pipeline=catalog_pipeline,
    )
    trend_response = query(
        QueryRequest(question="近几年贵州大学投档线趋势"),
        pipeline=catalog_pipeline,
    )

    assert province_response.availability.available is False
    assert province_response.availability.reasons == ["province_out_of_scope"]
    assert province_response.sql is None

    assert trend_response.availability.available is False
    assert trend_response.availability.reasons == ["trend_needs_multi_year"]
    assert trend_response.sql is None
    assert model.calls == 0
    assert executor.calls == 0
    assert province_response.template_name is None
    assert trend_response.template_name is None


def test_query_route_template_hit_exposes_template_name():
    model = FakeModel()
    executor = FakeExecutor(rows=[{"school_name": "贵州大学", "min_rank": 10000}])
    catalog_pipeline = CatalogPipeline(
        nl2sql_pipeline=Nl2SqlPipeline(
            generator=SqlGenerator(model=model),
            executor=executor,
        )
    )

    response = query(
        QueryRequest(question="物理类 位次 10000 能上哪些学校"),
        pipeline=catalog_pipeline,
    )

    assert response.template_name == "admission_search_lookup"
    assert response.sql is not None
    assert "min_rank >= 10000" in response.sql
    assert model.calls == 0
    assert executor.calls == 1


def test_query_route_multi_filter_template_hit():
    model = FakeModel()
    executor = FakeExecutor(rows=[{"school_name": "测试大学", "min_rank": 30000}])
    catalog_pipeline = CatalogPipeline(
        nl2sql_pipeline=Nl2SqlPipeline(
            generator=SqlGenerator(model=model),
            executor=executor,
        )
    )

    response = query(
        QueryRequest(question="物理类 位次 30000 公办 学费 8000 以下的计算机专业有哪些学校"),
        pipeline=catalog_pipeline,
    )

    assert response.template_name == "multi_filter_lookup"
    assert response.availability.available is True
    assert response.sql is not None
    assert "min_rank <= 30000" in response.sql
    assert model.calls == 0
    assert executor.calls == 1


def test_query_route_selection_requirement_exposes_coverage_warning():
    model = FakeModel()
    executor = FakeExecutor(rows=[])
    catalog_pipeline = CatalogPipeline(
        nl2sql_pipeline=Nl2SqlPipeline(
            generator=SqlGenerator(model=model),
            executor=executor,
        )
    )

    response = query(
        QueryRequest(question="计算机专业选科要求是什么"),
        pipeline=catalog_pipeline,
    )

    assert response.template_name == "selection_requirement_lookup"
    assert response.coverage_warnings
    assert response.coverage_warnings[0].field == "selection_requirements"
    assert "字段暂无数据" in response.coverage_warnings[0].message
