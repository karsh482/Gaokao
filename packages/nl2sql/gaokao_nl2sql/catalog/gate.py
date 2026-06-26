"""AvailabilityGate：核心安全关键组件，确定性判定请求是否在数据范围内。

给定 QueryScope、ClassifiedQuery 与 DataScope，按固定优先级判定请求是否在范围内；
超范围则产出结构化 GateDecision（含明确原因与面向用户的中文提示），阻止进入 LLM。
判定不交给 LLM，从源头保证诚实反馈：范围外请求绝不产出未经数据支撑的数值。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from gaokao_nl2sql.catalog.classifier import ClassifiedQuery, QueryCategory
from gaokao_nl2sql.catalog.data_scope import DataScope
from gaokao_nl2sql.catalog.scope import QueryScope


class UnavailableReason(Enum):
    """请求超出数据范围的成因。"""

    PROVINCE_OUT_OF_SCOPE = "province_out_of_scope"
    YEAR_OUT_OF_SCOPE = "year_out_of_scope"
    METRIC_UNAVAILABLE = "metric_unavailable"
    TREND_NEEDS_MULTI_YEAR = "trend_needs_multi_year"
    PLAN_CATALOG_REQUIRED = "plan_catalog_required"
    POLICY_RAG_OUT_OF_SCOPE = "policy_rag_out_of_scope"
    PROBABILITY_MODEL_PENDING = "probability_model_pending"


# 各原因对应的面向用户中文提示。
_REASON_MESSAGES: dict[UnavailableReason, str] = {
    UnavailableReason.PROVINCE_OUT_OF_SCOPE: "该省份数据暂不可用（当前仅支持贵州）。",
    UnavailableReason.YEAR_OUT_OF_SCOPE: "该年份数据暂不可用（当前仅支持 2025）。",
    UnavailableReason.METRIC_UNAVAILABLE: "该指标数据暂不可用（如录取均分、985/211、实际录取人数）。",
    UnavailableReason.TREND_NEEDS_MULTI_YEAR: "跨年度趋势查询需多年数据，当前仅有单一年份，暂不可用。",
    UnavailableReason.PLAN_CATALOG_REQUIRED: "该信息需招生计划目录数据，暂不可用。",
    UnavailableReason.POLICY_RAG_OUT_OF_SCOPE: "政策与解释类查询请使用 /policy/query RAG 检索接口，当前 /query 仅处理结构化数据查询。",
    UnavailableReason.PROBABILITY_MODEL_PENDING: "概率模型为后续增强能力，当前暂不可用。",
}


@dataclass(frozen=True)
class GateDecision:
    """闸门判定结果。allowed=False 时 reasons 非空、message 为明确提示。"""

    allowed: bool
    reasons: tuple[UnavailableReason, ...]
    message: str
    ignored_metric_conditions: tuple[str, ...] = ()


def _build_message(reasons: tuple[UnavailableReason, ...]) -> str:
    """按原因顺序拼接面向用户的提示文案。"""
    return " ".join(_REASON_MESSAGES[r] for r in reasons)


@dataclass(frozen=True)
class AvailabilityGate:
    """可用性闸门：确定性判定请求是否在当前数据范围内。"""

    def evaluate(
        self,
        scope: QueryScope,
        query: ClassifiedQuery,
        data_scope: DataScope,
        *,
        request_provinces: frozenset[str] | None = None,
    ) -> GateDecision:
        """按固定优先级判定可用性。

        request_provinces 为请求中涉及的全部考试/招生省份（用于混合省份整体拒绝）；
        未提供时回落为 scope.exam_province 单省份。
        优先级：省份 > 年份 > 趋势 > 政策 > 概率 > 缺失指标(主输出) > 计划目录。
        """
        provinces = request_provinces or frozenset({scope.exam_province})

        # 1. 省份优先级最高：任一涉及省份超范围即整体拒绝（混合省份不返回部分结果）。
        if any(not data_scope.is_province_available(p) for p in provinces):
            reasons = (UnavailableReason.PROVINCE_OUT_OF_SCOPE,)
            if len(provinces) > 1:
                message = "查询包含暂不可用省份，无法执行（当前仅支持贵州）。"
            else:
                message = _build_message(reasons)
            return GateDecision(False, reasons, message)

        # 2. 年份。招生计划目录与投档事实是不同数据面，分别判断年份可用性。
        if query.category is QueryCategory.ENROLLMENT_PLAN:
            if not (
                data_scope.is_year_available(scope.plan_year)
                or data_scope.is_plan_catalog_year_available(scope.plan_year)
            ):
                reasons = (UnavailableReason.YEAR_OUT_OF_SCOPE,)
                return GateDecision(False, reasons, _build_message(reasons))
        elif not data_scope.is_year_available(scope.plan_year):
            reasons = (UnavailableReason.YEAR_OUT_OF_SCOPE,)
            return GateDecision(False, reasons, _build_message(reasons))

        # 3. 趋势类（单年数据无法满足跨年度趋势）。
        if query.category is QueryCategory.TREND:
            reasons = (UnavailableReason.TREND_NEEDS_MULTI_YEAR,)
            return GateDecision(False, reasons, _build_message(reasons))

        # 4. 政策解释类交由 /policy/query 处理，避免误入 SQL 生成。
        if (
            query.category is QueryCategory.POLICY_EXPLAIN
            and not data_scope.policy_rag_enabled
        ):
            reasons = (UnavailableReason.POLICY_RAG_OUT_OF_SCOPE,)
            return GateDecision(False, reasons, _build_message(reasons))

        # 5. 录取概率（精确概率模型未实现；冲稳保参考评估不在此短路）。
        if (
            query.category is QueryCategory.ADMISSION_PROBABILITY
            and query.requires_probability_model
        ):
            reasons = (UnavailableReason.PROBABILITY_MODEL_PENDING,)
            return GateDecision(False, reasons, _build_message(reasons))

        # 6. 缺失指标的双重语义。
        missing = frozenset(
            m for m in query.requested_metrics if data_scope.is_metric_unavailable(m)
        )
        if missing:
            if query.category is QueryCategory.MULTI_FILTER:
                # 多条件筛选中的过滤条件：不短路，忽略该条件并交由标注器显式标注。
                return GateDecision(
                    True,
                    (),
                    "",
                    ignored_metric_conditions=tuple(sorted(missing)),
                )
            # 缺失指标作为主要输出：整体短路。
            reasons = (UnavailableReason.METRIC_UNAVAILABLE,)
            return GateDecision(False, reasons, _build_message(reasons))

        # 7. 计划目录维度未入库且请求整体依赖它。
        if (
            query.category is QueryCategory.ENROLLMENT_PLAN
            and not data_scope.is_year_available(scope.plan_year)
            and not data_scope.is_plan_catalog_year_available(scope.plan_year)
        ):
            reasons = (UnavailableReason.PLAN_CATALOG_REQUIRED,)
            return GateDecision(False, reasons, _build_message(reasons))

        # 8. 通过。
        return GateDecision(True, (), "")
