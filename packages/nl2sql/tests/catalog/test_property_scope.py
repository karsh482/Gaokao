# Feature: query-catalog, Property 1: 范围解析忠实回落并标注（全类别参数化）
"""Property 1：ScopeResolver 对任意类别与可选输入忠实回落并标注。"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from gaokao_nl2sql.catalog.classifier import QueryCategory
from gaokao_nl2sql.catalog.scope import ScopeResolver

_PROVINCES = st.one_of(st.none(), st.sampled_from(["贵州", "四川", "云南", "北京"]))
_YEARS = st.one_of(st.none(), st.integers(min_value=2018, max_value=2030))
_CATEGORIES = st.sampled_from(list(QueryCategory))


@settings(max_examples=100)
@given(exam_province=_PROVINCES, plan_year=_YEARS, category=_CATEGORIES)
def test_scope_resolution_faithful_fallback(
    exam_province: str | None,
    plan_year: int | None,
    category: QueryCategory,
) -> None:
    resolver = ScopeResolver()
    scope = resolver.resolve(exam_province, plan_year)

    # 省份：未提供回落默认且标注 used_default=True；已提供原样采用且为 False。
    if exam_province is None:
        assert scope.exam_province == resolver.default_province
        assert scope.used_default_province is True
    else:
        assert scope.exam_province == exam_province
        assert scope.used_default_province is False

    # 年份：同上。
    if plan_year is None:
        assert scope.plan_year == resolver.default_year
        assert scope.used_default_year is True
    else:
        assert scope.plan_year == plan_year
        assert scope.used_default_year is False

    # 解析与查询类别无关：同样输入解析值恒定。
    again = resolver.resolve(exam_province, plan_year)
    assert again == scope
