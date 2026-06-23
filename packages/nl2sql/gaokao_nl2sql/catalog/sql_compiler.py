"""从 SemanticFrame 编译确定性 SQL。"""

from __future__ import annotations

from dataclasses import dataclass

from gaokao_nl2sql.catalog.planner import QueryPlan
from gaokao_nl2sql.catalog.semantic import SemanticFrame


def sql_literal(value: str) -> str:
    """生成 SQL 字符串字面量；所有外部文本必须转义单引号。"""

    return "'" + value.replace("'", "''") + "'"


@dataclass(frozen=True, slots=True)
class SqlCompiler:
    """将受控语义帧编译成只读 SQL。"""

    def compile(self, frame: SemanticFrame) -> QueryPlan | None:
        if frame.route != "sql":
            return None
        if frame.task in {"admission_search", "admission_feasibility"}:
            return self._compile_admission(frame)
        return None

    def _compile_admission(self, frame: SemanticFrame) -> QueryPlan | None:
        if not frame.has_candidate_metric:
            return None

        filters = [
            f"ar.exam_province = {sql_literal(frame.exam_province or '贵州')}",
            f"ar.plan_year = {int(frame.year or 2025)}",
        ]
        f = frame.filters
        if f.school_name:
            filters.append(f"ar.school_name ILIKE '%' || {sql_literal(f.school_name)} || '%'")
        if f.subject_category:
            filters.append(f"ar.subject_category = {sql_literal(f.subject_category)}")
        if f.major_name:
            filters.append(f"ar.major_name ILIKE '%' || {sql_literal(f.major_name)} || '%'")
        if f.special_program:
            filters.append(f"ar.admission_program ILIKE '%' || {sql_literal(f.special_program)} || '%'")
        if f.batch:
            filters.append(f"ar.batch ILIKE '%' || {sql_literal(f.batch)} || '%'")
        joins = ""
        if f.city or f.ownership:
            joins = "LEFT JOIN school s ON s.name = ar.school_name"
        if f.city:
            filters.append(f"s.city ILIKE '%' || {sql_literal(f.city)} || '%'")
        if f.ownership:
            filters.append(f"s.ownership = {sql_literal(f.ownership)}")
        if f.tuition_max is not None:
            filters.append(f"ar.tuition <= {int(f.tuition_max)}")

        select_parts = [
            "ar.school_name",
            "ar.major_name",
            "ar.batch",
            "ar.subject_category",
            "ar.admission_program",
            "ar.min_score",
            "ar.min_rank",
            "ar.enrollment_plan_count",
            "ar.tuition",
        ]
        if frame.candidate.rank is not None:
            rank = int(frame.candidate.rank)
            if not f.school_name:
                filters.append(f"ar.min_rank >= {rank}")
            select_parts.extend(
                [
                    f"{rank} AS candidate_rank",
                    f"(ar.min_rank - {rank}) AS rank_gap",
                    "CASE "
                    f"WHEN ar.min_rank - {rank} < -2000 THEN '冲' "
                    f"WHEN ar.min_rank - {rank} > 2000 THEN '保' "
                    "ELSE '稳' END AS confidence_band",
                    "'基于单年位次的参考评估，非概率模型结果' AS confidence_note",
                ]
            )
            order_by = f"ABS(ar.min_rank - {rank}) ASC NULLS LAST"
        else:
            score = int(frame.candidate.score or 0)
            if not f.school_name:
                filters.append(f"ar.min_score <= {score}")
            select_parts.extend(
                [
                    f"{score} AS candidate_score",
                    f"({score} - ar.min_score) AS score_gap",
                    "CASE "
                    f"WHEN {score} - ar.min_score < -10 THEN '冲' "
                    f"WHEN {score} - ar.min_score > 10 THEN '保' "
                    "ELSE '稳' END AS confidence_band",
                    "'基于单年分数差的参考评估，非概率模型结果；优先建议使用位次评估' AS confidence_note",
                ]
            )
            order_by = f"ABS({score} - ar.min_score) ASC NULLS LAST"

        select_clause = ",\n  ".join(select_parts)
        where_clause = " AND ".join(filters)
        sql = f"""
SELECT
  {select_clause}
FROM staging.admission_records ar
{joins}
WHERE {where_clause}
ORDER BY {order_by}
LIMIT {int(frame.output.limit)}
"""
        return QueryPlan(
            sql=sql,
            template_name=(
                "semantic_admission_feasibility"
                if f.school_name
                else "semantic_admission_search"
            ),
            data_sources=("staging.admission_records",) + (("school",) if joins else ()),
        )
