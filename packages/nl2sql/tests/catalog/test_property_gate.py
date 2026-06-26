# Feature: query-catalog, Property 2: 闸门对超范围请求给出正确不可用原因
"""AvailabilityGate 属性测试：超范围、优先级与降级标注。"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from gaokao_nl2sql.catalog.classifier import ClassifiedQuery, QueryCategory
from gaokao_nl2sql.catalog.data_scope import DataScopeRegistry
from gaokao_nl2sql.catalog.gate import AvailabilityGate, UnavailableReason
from gaokao_nl2sql.catalog.scope import QueryScope


def _scope(province: str = "贵州", year: int = 2025) -> QueryScope:
    return QueryScope(
        exam_province=province,
        plan_year=year,
        used_default_province=False,
        used_default_year=False,
    )


@settings(max_examples=100)
@given(province=st.sampled_from(["四川", "云南", "北京", "上海"]))
def test_gate_rejects_out_of_scope_province(province: str) -> None:
    gate = AvailabilityGate()
    data_scope = DataScopeRegistry().current()
    decision = gate.evaluate(
        _scope(province=province),
        ClassifiedQuery(QueryCategory.GENERIC, frozenset()),
        data_scope,
    )

    assert decision.allowed is False
    assert decision.reasons == (UnavailableReason.PROVINCE_OUT_OF_SCOPE,)
    assert "省份数据暂不可用" in decision.message


@settings(max_examples=100)
@given(year=st.integers(min_value=2000, max_value=2035).filter(lambda y: y != 2025))
def test_gate_rejects_out_of_scope_year(year: int) -> None:
    gate = AvailabilityGate()
    data_scope = DataScopeRegistry().current()
    decision = gate.evaluate(
        _scope(year=year),
        ClassifiedQuery(QueryCategory.GENERIC, frozenset()),
        data_scope,
    )

    assert decision.allowed is False
    assert decision.reasons == (UnavailableReason.YEAR_OUT_OF_SCOPE,)
    assert "年份数据暂不可用" in decision.message


@settings(max_examples=100)
@given(
    category=st.sampled_from(
        [
            QueryCategory.TREND,
            QueryCategory.POLICY_EXPLAIN,
            QueryCategory.ADMISSION_PROBABILITY,
            QueryCategory.STATS_RANK,
        ]
    )
)
def test_gate_rejects_unavailable_categories(category: QueryCategory) -> None:
    gate = AvailabilityGate()
    data_scope = DataScopeRegistry().current()
    metrics = frozenset({"录取均分"}) if category is QueryCategory.STATS_RANK else frozenset()
    query = ClassifiedQuery(
        category=category,
        requested_metrics=metrics,
        requires_probability_model=category is QueryCategory.ADMISSION_PROBABILITY,
    )

    decision = gate.evaluate(_scope(), query, data_scope)

    assert decision.allowed is False
    assert decision.reasons
    if category is QueryCategory.TREND:
        assert decision.reasons == (UnavailableReason.TREND_NEEDS_MULTI_YEAR,)
    elif category is QueryCategory.POLICY_EXPLAIN:
        assert decision.reasons == (UnavailableReason.POLICY_RAG_OUT_OF_SCOPE,)
    elif category is QueryCategory.ADMISSION_PROBABILITY:
        assert decision.reasons == (UnavailableReason.PROBABILITY_MODEL_PENDING,)
    else:
        assert decision.reasons == (UnavailableReason.METRIC_UNAVAILABLE,)


def test_gate_rejects_mixed_provinces_as_whole() -> None:
    gate = AvailabilityGate()
    data_scope = DataScopeRegistry().current()
    decision = gate.evaluate(
        _scope(),
        ClassifiedQuery(QueryCategory.GENERIC, frozenset()),
        data_scope,
        request_provinces=frozenset({"贵州", "四川"}),
    )

    assert decision.allowed is False
    assert decision.reasons == (UnavailableReason.PROVINCE_OUT_OF_SCOPE,)
    assert "查询包含暂不可用省份，无法执行" in decision.message


def test_gate_province_priority_over_missing_metric() -> None:
    gate = AvailabilityGate()
    data_scope = DataScopeRegistry().current()
    decision = gate.evaluate(
        _scope(province="四川"),
        ClassifiedQuery(QueryCategory.STATS_RANK, frozenset({"录取均分"})),
        data_scope,
    )

    assert decision.allowed is False
    assert decision.reasons == (UnavailableReason.PROVINCE_OUT_OF_SCOPE,)


def test_gate_ignores_missing_metric_only_for_multi_filter() -> None:
    gate = AvailabilityGate()
    data_scope = DataScopeRegistry().current()
    decision = gate.evaluate(
        _scope(),
        ClassifiedQuery(QueryCategory.MULTI_FILTER, frozenset({"录取均分"})),
        data_scope,
    )

    assert decision.allowed is True
    assert decision.reasons == ()
    assert decision.ignored_metric_conditions == ("录取均分",)


# Feature: query-catalog, Property 4: 依赖招生计划目录的维度降级并显式标注
def test_gate_marks_plan_catalog_required_without_numbers() -> None:
    gate = AvailabilityGate()
    data_scope = DataScopeRegistry().current()
    decision = gate.evaluate(
        _scope(),
        ClassifiedQuery(QueryCategory.ENROLLMENT_PLAN, frozenset()),
        data_scope,
    )

    assert decision.allowed is True
    assert decision.reasons == ()


def test_gate_allows_loaded_plan_catalog_year() -> None:
    gate = AvailabilityGate()
    data_scope = DataScopeRegistry().current()
    decision = gate.evaluate(
        _scope(year=2026),
        ClassifiedQuery(QueryCategory.ENROLLMENT_PLAN, frozenset()),
        data_scope,
    )

    assert decision.allowed is True
    assert decision.reasons == ()


def test_gate_rejects_non_catalog_query_for_plan_catalog_only_year() -> None:
    gate = AvailabilityGate()
    data_scope = DataScopeRegistry().current()
    decision = gate.evaluate(
        _scope(year=2026),
        ClassifiedQuery(QueryCategory.SCORE_RANK_FILTER, frozenset()),
        data_scope,
    )

    assert decision.allowed is False
    assert decision.reasons == (UnavailableReason.YEAR_OUT_OF_SCOPE,)
