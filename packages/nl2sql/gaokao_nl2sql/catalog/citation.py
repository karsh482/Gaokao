"""CitationBuilder：为查询响应生成结构化数据来源标注。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from gaokao_nl2sql.catalog.classifier import QueryCategory
from gaokao_nl2sql.catalog.scope import QueryScope


@dataclass(frozen=True)
class Citation:
    """一次响应引用的数据来源与口径。"""

    source: str
    label: str
    fields: tuple[str, ...]
    exam_province: str
    plan_year: int
    note: str = ""


_ADMISSION_FIELDS = {
    "school_name",
    "source_school_name",
    "major_name",
    "batch",
    "subject_category",
    "admission_track",
    "admission_program",
    "selection_requirements",
    "enrollment_plan_count",
    "filing_count",
    "admitted_count",
    "min_score",
    "min_rank",
    "tuition",
    "duration",
    "source_file_id",
    "source_page",
}
_SCORE_SEGMENT_FIELDS = {
    "score",
    "score_label",
    "score_type",
    "segment_count",
    "cumulative_count",
    "cumulative_ratio",
    "segment_name",
}
_SCHOOL_FIELDS = {
    "school_code",
    "name",
    "city",
    "school_type",
    "education_level",
    "ownership",
    "is_double_first_class",
    "province_id",
}
_PROVINCE_FIELDS = {"province_name", "abbreviation", "code"}

_CATEGORY_SOURCES: dict[QueryCategory, tuple[str, ...]] = {
    QueryCategory.SCHOOL: ("staging.admission_records", "school"),
    QueryCategory.MAJOR: ("staging.admission_records",),
    QueryCategory.SCORE_RANK_FILTER: ("staging.admission_records",),
    QueryCategory.COMPARE: ("staging.admission_records",),
    QueryCategory.STATS_RANK: ("staging.admission_records",),
    QueryCategory.SCORE_RANK_CONVERT: ("staging.score_segments",),
    QueryCategory.ENROLLMENT_PLAN: ("staging.admission_records",),
    QueryCategory.SELECTION_REQ: ("staging.admission_records",),
    QueryCategory.SPECIAL_PROGRAM: ("staging.admission_records",),
    QueryCategory.MULTI_FILTER: ("staging.admission_records", "school"),
    QueryCategory.REGION: ("school", "province"),
    QueryCategory.ADMISSION_PROBABILITY: ("staging.admission_records",),
    QueryCategory.GENERIC: ("staging.admission_records",),
}

_SOURCE_LABELS = {
    "staging.admission_records": "投档录取数据",
    "staging.score_segments": "一分一段/分数段数据",
    "school": "院校主数据",
    "province": "省份主数据",
}


def _row_fields(rows: Sequence[Mapping[str, object]]) -> frozenset[str]:
    fields: set[str] = set()
    for row in rows:
        fields.update(str(key) for key in row)
    return frozenset(fields)


def _fields_for_source(source: str, fields: frozenset[str]) -> tuple[str, ...]:
    if source == "staging.admission_records":
        known = fields & _ADMISSION_FIELDS
    elif source == "staging.score_segments":
        known = fields & _SCORE_SEGMENT_FIELDS
    elif source == "school":
        known = fields & _SCHOOL_FIELDS
    elif source == "province":
        known = fields & _PROVINCE_FIELDS
    else:
        known = frozenset()
    return tuple(sorted(known))


@dataclass(frozen=True)
class CitationBuilder:
    """根据查询类别、返回字段和范围生成数据来源标注。"""

    def build(
        self,
        *,
        category: QueryCategory,
        scope: QueryScope,
        rows: Sequence[Mapping[str, object]],
    ) -> tuple[Citation, ...]:
        fields = _row_fields(rows)
        sources = _CATEGORY_SOURCES.get(category, ("staging.admission_records",))
        citations: list[Citation] = []
        for source in sources:
            source_fields = _fields_for_source(source, fields)
            citations.append(
                Citation(
                    source=source,
                    label=_SOURCE_LABELS[source],
                    fields=source_fields,
                    exam_province=scope.exam_province,
                    plan_year=scope.plan_year,
                    note=self._note(source),
                )
            )
        return tuple(citations)

    @staticmethod
    def _note(source: str) -> str:
        if source == "school":
            return "院校所在地来自院校主数据，不等同于考试/招生省份。"
        if source == "staging.score_segments":
            return "分数与位次换算基于同一省份、年份、科类口径的分数段数据。"
        return ""
