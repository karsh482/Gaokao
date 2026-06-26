"""DataScope 与 DataScopeRegistry：当前数据可用范围的单一事实源。

记录当前哪些 (省份, 年份) 有数据、哪些指标缺失、计划目录与政策 RAG 是否可用。
这是确定性配置数据，AvailabilityGate 据此判断请求是否在范围内。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DataScope:
    """当前数据可用范围（单一事实源）。"""

    available_provinces: frozenset[str]
    available_years: frozenset[int]
    plan_catalog_years: frozenset[int]
    unavailable_metrics: frozenset[str]
    plan_catalog_loaded: bool
    policy_rag_enabled: bool

    def is_province_available(self, province: str) -> bool:
        """省份是否在可用范围内。"""
        return province in self.available_provinces

    def is_year_available(self, year: int) -> bool:
        """年份是否在可用范围内。"""
        return year in self.available_years

    def is_plan_catalog_year_available(self, year: int) -> bool:
        """招生专业目录年份是否在可用范围内。"""
        return self.plan_catalog_loaded and year in self.plan_catalog_years

    def is_metric_unavailable(self, metric: str) -> bool:
        """指标是否属于当前缺失指标集合。"""
        return metric in self.unavailable_metrics


# 默认缺失指标集合：录取均分、实际录取人数、985/211 标签当前不在数据中。
DEFAULT_UNAVAILABLE_METRICS: frozenset[str] = frozenset(
    {"录取均分", "admitted_count", "实际录取人数", "985", "211"}
)


@dataclass(frozen=True)
class DataScopeRegistry:
    """数据范围登记表，提供当前默认的 DataScope。"""

    scope: DataScope = field(
        default_factory=lambda: DataScope(
            available_provinces=frozenset({"贵州"}),
            available_years=frozenset({2025}),
            plan_catalog_years=frozenset({2026}),
            unavailable_metrics=DEFAULT_UNAVAILABLE_METRICS,
            plan_catalog_loaded=True,
            policy_rag_enabled=False,
        )
    )

    def current(self) -> DataScope:
        """返回当前登记的数据范围。"""
        return self.scope
