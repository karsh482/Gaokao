"""ResultAnnotator：查询结果口径、可用性与降级信息标注。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from gaokao_nl2sql.catalog.classifier import QueryCategory
from gaokao_nl2sql.catalog.gate import GateDecision
from gaokao_nl2sql.catalog.scope import QueryScope


@dataclass(frozen=True)
class AvailabilityInfo:
    """面向 API 的可用性信息。"""

    available: bool
    reasons: tuple[str, ...]
    message: str
    ignored_metric_conditions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResultAnnotation:
    """一次查询响应需要携带的标注信息。"""

    exam_province: str
    plan_year: int
    subject_category: str | None
    availability: AvailabilityInfo
    notes: tuple[str, ...]
    applied_filters: Mapping[str, Any]


_EMPTY_MESSAGES: dict[QueryCategory, str] = {
    QueryCategory.SCHOOL: "该院校在指定省份与年份下暂无数据。",
    QueryCategory.MAJOR: "暂无该专业数据。",
    QueryCategory.ENROLLMENT_PLAN: "暂无招生计划数据。",
    QueryCategory.SELECTION_REQ: "该专业暂无选科要求数据。",
    QueryCategory.SPECIAL_PROGRAM: "暂无该专项招生数据。",
    QueryCategory.REGION: "该地域暂无匹配院校。",
    QueryCategory.MULTI_FILTER: "无符合全部条件的结果。",
}


def _availability_from_decision(decision: GateDecision) -> AvailabilityInfo:
    return AvailabilityInfo(
        available=decision.allowed,
        reasons=tuple(reason.value for reason in decision.reasons),
        message=decision.message,
        ignored_metric_conditions=decision.ignored_metric_conditions,
    )


def _infer_subject_category(question: str) -> str | None:
    if "物理类" in question:
        return "物理类"
    if "历史类" in question:
        return "历史类"
    return None


def _needs_subject_note(category: QueryCategory, question: str) -> bool:
    if category not in {
        QueryCategory.SCORE_RANK_FILTER,
        QueryCategory.SCORE_RANK_CONVERT,
        QueryCategory.MULTI_FILTER,
    }:
        return False
    has_score_or_rank = any(token in question for token in ("分", "位次", "排名"))
    return has_score_or_rank and _infer_subject_category(question) is None


@dataclass(frozen=True)
class ResultAnnotator:
    """为查询结果附加范围、口径、筛选条件与部分可用说明。"""

    def unavailable(
        self,
        scope: QueryScope,
        decision: GateDecision,
    ) -> ResultAnnotation:
        """构造不可用短路响应的标注。"""
        return ResultAnnotation(
            exam_province=scope.exam_province,
            plan_year=scope.plan_year,
            subject_category=None,
            availability=_availability_from_decision(decision),
            notes=(decision.message,),
            applied_filters={},
        )

    def annotate(
        self,
        *,
        scope: QueryScope,
        decision: GateDecision,
        question: str,
        category: QueryCategory,
        rows: Sequence[Mapping[str, Any]],
        applied_filters: Mapping[str, Any] | None = None,
    ) -> ResultAnnotation:
        """为可执行查询的结果附加确定性标注。"""
        filters = dict(applied_filters or {})
        filters.setdefault("exam_province", scope.exam_province)
        filters.setdefault("plan_year", scope.plan_year)

        subject_category = _infer_subject_category(question)
        if subject_category is not None:
            filters.setdefault("subject_category", subject_category)

        notes: list[str] = [
            f"查询范围：考试/招生省份={scope.exam_province}，招生年份={scope.plan_year}。"
        ]
        if scope.used_default_province:
            notes.append(f"未指定考试/招生省份，已使用默认值：{scope.exam_province}。")
        if scope.used_default_year:
            notes.append(f"未指定招生年份，已使用默认值：{scope.plan_year}。")

        if subject_category is not None:
            notes.append(f"科类口径：{subject_category}。")
        elif _needs_subject_note(category, question):
            notes.append("提供分数或位次时需要 subject_category，以保证位次口径一致。")

        for metric in decision.ignored_metric_conditions:
            notes.append(f"该筛选指标当前无数据、已被忽略：{metric}。")

        if not rows:
            notes.append(_EMPTY_MESSAGES.get(category, "当前范围内暂无数据。"))

        return ResultAnnotation(
            exam_province=scope.exam_province,
            plan_year=scope.plan_year,
            subject_category=subject_category,
            availability=_availability_from_decision(decision),
            notes=tuple(notes),
            applied_filters=filters,
        )

    def annotate_requested_items(
        self,
        *,
        requested_items: Sequence[str],
        available_items: Sequence[str],
    ) -> tuple[str, ...]:
        """对部分可用的对比项逐项标注缺失项。"""
        available = set(available_items)
        return tuple(
            f"{item}：暂无数据。"
            for item in requested_items
            if item not in available
        )
