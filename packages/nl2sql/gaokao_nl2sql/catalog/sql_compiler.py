"""从 SemanticFrame 编译确定性 SQL。"""

from __future__ import annotations

from dataclasses import dataclass

from gaokao_nl2sql.catalog.planner import QueryPlan
from gaokao_nl2sql.catalog.semantic import SemanticFrame

RUSH_RANK_WINDOW = 5_000
SECURE_RANK_WINDOW = 8_000
SCORE_WINDOW = 20


def sql_literal(value: str) -> str:
    """生成 SQL 字符串字面量；所有外部文本必须转义单引号。"""

    return "'" + value.replace("'", "''") + "'"


def signed_sql_int(value: int) -> str:
    return f"+ {value}" if value >= 0 else f"- {abs(value)}"


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
        data_sources = ["staging.admission_records"]
        if f.city or f.ownership or f.school_province:
            joins = "LEFT JOIN school s ON s.name = ar.school_name"
            data_sources.append("school")
        if f.school_province:
            joins += "\nLEFT JOIN province p ON p.id = s.province_id"
            filters.append(f"p.name ILIKE '%' || {sql_literal(f.school_province)} || '%'")
            data_sources.append("province")
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
        if f.city or f.ownership:
            select_parts.extend(["s.city", "s.ownership"])
        if f.school_province:
            select_parts.append("p.name AS province_name")
        if frame.candidate.rank is not None:
            rank = int(frame.candidate.rank)
            if not f.school_name:
                filters.append(
                    "ar.min_rank BETWEEN "
                    f"GREATEST(1, {rank} - {RUSH_RANK_WINDOW}) "
                    f"AND {rank} + {SECURE_RANK_WINDOW}"
                )
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
            cte = ""
            if not f.school_name and f.subject_category:
                candidate_rank_expr = "cp.candidate_rank"
                adjustment = int(frame.candidate.rank_adjustment or 0)
                filters.append("cp.candidate_rank IS NOT NULL")
                filters.append(
                    "ar.min_rank BETWEEN "
                    f"GREATEST(1, {candidate_rank_expr} - {RUSH_RANK_WINDOW}) "
                    f"AND {candidate_rank_expr} + {SECURE_RANK_WINDOW}"
                )
                select_parts.extend(
                    [
                        "cp.candidate_score",
                        "cp.candidate_rank",
                        f"({score} - ar.min_score) AS score_gap",
                        f"(ar.min_rank - {candidate_rank_expr}) AS rank_gap",
                        "CASE "
                        f"WHEN ar.min_rank - {candidate_rank_expr} < -2000 THEN '冲' "
                        f"WHEN ar.min_rank - {candidate_rank_expr} > 2000 THEN '保' "
                        "ELSE '稳' END AS confidence_band",
                        "'基于同年一分一段换算位次后的单年位次参考评估，非概率模型结果' AS confidence_note",
                    ]
                )
                order_by = f"ABS(ar.min_rank - {candidate_rank_expr}) ASC NULLS LAST"
                cte = f"""WITH candidate_profile AS (
  SELECT
    {score} AS candidate_score,
    CASE
      WHEN MIN(ss.cumulative_count) IS NULL THEN NULL
      ELSE GREATEST(1, MIN(ss.cumulative_count) {signed_sql_int(adjustment)})::int
    END AS candidate_rank
  FROM staging.score_segments ss
  WHERE ss.exam_province = {sql_literal(frame.exam_province or '贵州')}
    AND ss.plan_year = {int(frame.year or 2025)}
    AND ss.subject_category = {sql_literal(f.subject_category)}
    AND ss.admission_track = '普通类'
    AND ss.score_type = '高考总分'
    AND ss.score = {score}
)"""
                data_sources.append("staging.score_segments")
            else:
                if not f.school_name:
                    filters.append(
                        f"ar.min_score BETWEEN {max(0, score - SCORE_WINDOW)} "
                        f"AND {score + SCORE_WINDOW}"
                    )
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
        cte = locals().get("cte", "")
        from_join = (
            "FROM staging.admission_records ar\nCROSS JOIN candidate_profile cp"
            if cte
            else "FROM staging.admission_records ar"
        )
        sql = f"""
{cte}
SELECT
  {select_clause}
{from_join}
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
            data_sources=tuple(dict.fromkeys(data_sources)),
        )
