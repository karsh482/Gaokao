"""实体归一化：把语义帧补齐为当前数据范围可执行的查询条件。"""

from __future__ import annotations

from dataclasses import dataclass

from gaokao_nl2sql.catalog.scope import QueryScope
from gaokao_nl2sql.catalog.semantic import (
    CandidateProfile,
    QueryFilters,
    QueryOutput,
    SemanticFrame,
)


@dataclass(frozen=True, slots=True)
class EntityResolver:
    """轻量实体归一化器。

    当前先做确定性标准化；后续可接学校/专业别名表，不改变 Pipeline 接口。
    """

    def resolve(self, frame: SemanticFrame, scope: QueryScope) -> SemanticFrame:
        filters = frame.filters
        subject_category = filters.subject_category
        if subject_category == "物理":
            subject_category = "物理类"
        elif subject_category == "历史":
            subject_category = "历史类"

        return SemanticFrame(
            route=frame.route,
            task=frame.task,
            exam_province=frame.exam_province or scope.exam_province,
            year=frame.year or scope.plan_year,
            candidate=CandidateProfile(
                rank=frame.candidate.rank,
                score=frame.candidate.score,
            ),
            filters=QueryFilters(
                school_name=_clean_text(filters.school_name),
                major_name=_clean_text(filters.major_name),
                subject_category=subject_category,
                city=_clean_text(filters.city),
                ownership=filters.ownership,
                tuition_max=filters.tuition_max,
                special_program=_clean_text(filters.special_program),
                batch=_clean_text(filters.batch),
            ),
            output=QueryOutput(
                target=frame.output.target,
                group_by=frame.output.group_by,
                sort=frame.output.sort,
                limit=max(1, min(frame.output.limit, 200)),
            ),
            missing_required=frame.missing_required,
            confidence=frame.confidence,
        )


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
