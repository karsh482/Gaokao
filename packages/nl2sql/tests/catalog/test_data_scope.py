"""DataScope / DataScopeRegistry 单元测试：断言默认登记值正确。"""

from __future__ import annotations

from gaokao_nl2sql.catalog.data_scope import DataScopeRegistry


def test_default_available_provinces():
    scope = DataScopeRegistry().current()
    assert scope.available_provinces == frozenset({"贵州"})
    assert scope.is_province_available("贵州")
    assert not scope.is_province_available("四川")


def test_default_available_years():
    scope = DataScopeRegistry().current()
    assert scope.available_years == frozenset({2025})
    assert scope.plan_catalog_years == frozenset({2026})
    assert scope.is_year_available(2025)
    assert not scope.is_year_available(2024)
    assert scope.is_plan_catalog_year_available(2026)


def test_default_unavailable_metrics():
    scope = DataScopeRegistry().current()
    for metric in ("录取均分", "admitted_count", "实际录取人数", "985", "211"):
        assert scope.is_metric_unavailable(metric)
    assert not scope.is_metric_unavailable("min_rank")


def test_default_flags_off():
    scope = DataScopeRegistry().current()
    assert scope.plan_catalog_loaded is True
    assert scope.policy_rag_enabled is False
