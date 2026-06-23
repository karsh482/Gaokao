"""轻量 QueryPlanner：为高频结构化查询生成确定性 SQL 模板。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from gaokao_nl2sql.catalog.classifier import ClassifiedQuery, QueryCategory
from gaokao_nl2sql.catalog.intent import AdmissionIntent
from gaokao_nl2sql.catalog.scope import QueryScope


@dataclass(frozen=True)
class QueryPlan:
    """确定性模板查询计划。"""

    sql: str
    template_name: str
    data_sources: tuple[str, ...]


_SCHOOL_PATTERN = re.compile(r"([\u4e00-\u9fa5A-Za-z0-9（）()·]{2,30}(?:大学|学院|学校))")
_MAJOR_PATTERN = re.compile(r"([\u4e00-\u9fa5A-Za-z0-9]{2,30}(?:专业|类))")
_RANK_PATTERN = re.compile(r"(?:位次|排名|排位)?\s*([0-9一二三四五六七八九十百千万,，]+)\s*(?:名|位)")
_SCORE_PATTERN = re.compile(r"([0-9]{3})\s*分")
_CITY_PATTERN = re.compile(r"([\u4e00-\u9fa5]{2,8})(?:有哪些大学|有哪些院校|有哪些学校)")
_TUITION_PATTERN = re.compile(r"(?:学费|费用)[^0-9一二三四五六七八九十百千万]{0,6}([0-9一二三四五六七八九十百千万,，]+)")
_SPECIAL_PROGRAMS = ("国家专项", "地方专项", "高校专项", "民族班", "预科", "中外合作")
_CITY_HINTS = ("成都", "贵阳", "昆明", "重庆", "北京", "上海", "广州", "深圳", "武汉", "长沙", "南京", "杭州", "西安")
_FEASIBILITY_KEYWORDS = ("能不能上", "能上", "可以上", "够得上", "有没有机会", "希望大吗")


def _sql_literal(value: str) -> str:
    """生成 SQL 字符串字面量；模板值均来自用户文本，必须转义单引号。"""
    return "'" + value.replace("'", "''") + "'"


def _parse_chinese_number(text: str) -> int | None:
    normalized = text.replace(",", "").replace("，", "").strip()
    if normalized.isdigit():
        return int(normalized)
    if normalized == "一万":
        return 10_000
    match = re.fullmatch(r"([一二三四五六七八九])万", normalized)
    if match:
        return ("一二三四五六七八九".index(match.group(1)) + 1) * 10_000
    return None


def _extract_school(question: str) -> str | None:
    match = _SCHOOL_PATTERN.search(question)
    if match is None:
        return None
    school = match.group(1)
    if any(token in school for token in ("哪些", "什么", "哪所", "哪几所")):
        return None
    for prefix in ("请帮我查询", "请帮我查", "帮我查询", "帮我查", "查询", "查看", "了解", "请问"):
        if school.startswith(prefix):
            return school.removeprefix(prefix)
    return school


def _extract_target_school(question: str) -> str | None:
    """抽取“能不能上 X 大学”中的目标院校，避免把意图词并入学校名。"""

    for keyword in _FEASIBILITY_KEYWORDS:
        if keyword not in question:
            continue
        suffix = question.split(keyword, 1)[1]
        match = _SCHOOL_PATTERN.search(suffix)
        if match is None:
            continue
        school = match.group(1)
        if any(token in school for token in ("哪些", "什么", "哪所", "哪几所")):
            continue
        return school
    return _extract_school(question)


def _extract_major(question: str) -> str | None:
    match = _MAJOR_PATTERN.search(question)
    if match is None:
        return None
    major = match.group(1)
    if major.endswith("专业"):
        major = major[:-2]
    return major


def _extract_rank(question: str) -> int | None:
    match = _RANK_PATTERN.search(question)
    if match is not None:
        return _parse_chinese_number(match.group(1))
    match = re.search(r"(?:位次|排名|排位)\s*([0-9一二三四五六七八九十百千万,，]+)", question)
    if match is not None:
        return _parse_chinese_number(match.group(1))
    return None


def _extract_score(question: str) -> int | None:
    match = _SCORE_PATTERN.search(question)
    if match is None:
        return None
    return int(match.group(1))


def _extract_tuition_limit(question: str) -> int | None:
    if not any(token in question for token in ("学费", "费用")):
        return None
    match = _TUITION_PATTERN.search(question)
    if match is None:
        return None
    return _parse_chinese_number(match.group(1))


def _extract_ownership(question: str) -> str | None:
    if "公办" in question:
        return "公办"
    if "民办" in question:
        return "民办"
    return None


def _extract_city(question: str) -> str | None:
    match = _CITY_PATTERN.search(question)
    if match is not None:
        return match.group(1)
    for city in _CITY_HINTS:
        if city in question:
            return city
    return None


def _extract_major_keyword(
    question: str,
    *,
    allow_generic_major: bool = True,
) -> str | None:
    if "计算机" in question:
        return "计算机"
    if "临床医学" in question:
        return "临床医学"
    if "医学" in question:
        return "医学"
    if "法学" in question:
        return "法学"
    if "会计" in question:
        return "会计"
    if not allow_generic_major:
        return None
    major = _extract_major(question)
    if major is None:
        return None
    if major in {"物理类", "历史类"}:
        return None
    return major


def _extract_special_program(question: str) -> str | None:
    for program in _SPECIAL_PROGRAMS:
        if program in question:
            return program
    if "专项" in question:
        return "专项"
    return None


@dataclass(frozen=True)
class QueryPlanner:
    """对高置信度结构化问题生成 SQL 模板；无法确定时返回 None。"""

    def plan(
        self,
        *,
        question: str,
        scope: QueryScope,
        query: ClassifiedQuery,
        intent: AdmissionIntent | None = None,
    ) -> QueryPlan | None:
        admission_plan = self._admission_plan(question, scope, intent)
        if admission_plan is not None:
            return admission_plan
        if query.category is QueryCategory.MULTI_FILTER and not query.requested_metrics:
            plan = self._multi_filter_plan(question, scope)
            if plan is not None:
                return plan
        if (
            query.category is QueryCategory.SCORE_RANK_FILTER
            or _extract_rank(question) is not None
            or _extract_score(question) is not None
        ):
            return self._score_rank_filter_plan(question, scope)
        if query.category is QueryCategory.SPECIAL_PROGRAM or _extract_special_program(question) is not None:
            return self._special_program_plan(question, scope)
        if query.category is QueryCategory.REGION or _extract_city(question) is not None:
            return self._region_plan(question, scope)
        if query.category is QueryCategory.SELECTION_REQ:
            return self._selection_requirement_plan(question, scope)
        if query.requested_metrics and query.category is QueryCategory.MULTI_FILTER:
            return None
        if query.category is QueryCategory.SCHOOL or _extract_school(question) is not None:
            return self._school_plan(question, scope)
        if query.category is QueryCategory.MAJOR:
            return self._major_plan(question, scope)
        return None

    def _admission_plan(
        self,
        question: str,
        scope: QueryScope,
        intent: AdmissionIntent | None = None,
    ) -> QueryPlan | None:
        structured = intent if intent and intent.is_actionable else None
        school = structured.school_name if structured else _extract_target_school(question)
        rank = structured.candidate_rank if structured else _extract_rank(question)
        score = structured.candidate_score if structured else _extract_score(question)
        if rank is None and score is None:
            return None
        if structured is None and not any(
            keyword in question for keyword in _FEASIBILITY_KEYWORDS
        ):
            return None

        filters = [
            f"ar.exam_province = {_sql_literal(scope.exam_province)}",
            f"ar.plan_year = {int(scope.plan_year)}",
        ]
        if school is not None:
            filters.append(f"ar.school_name ILIKE '%' || {_sql_literal(school)} || '%'")
        subject_category = (
            structured.subject_category
            if structured
            else "物理类"
            if "物理类" in question
            else "历史类"
            if "历史类" in question
            else None
        )
        major = (
            structured.major_name
            if structured
            else _extract_major_keyword(question, allow_generic_major=False)
        )
        if subject_category is not None:
            filters.append(f"ar.subject_category = {_sql_literal(subject_category)}")
        if major is not None:
            filters.append(f"ar.major_name ILIKE '%' || {_sql_literal(major)} || '%'")

        select_parts = [
            "ar.school_name",
            "ar.major_name",
            "ar.batch",
            "ar.subject_category",
            "ar.min_score",
            "ar.min_rank",
            "ar.enrollment_plan_count",
        ]
        order_by = "ar.min_rank ASC NULLS LAST"
        if rank is not None:
            if school is None:
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
        elif score is not None:
            if school is None:
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
WHERE {where_clause}
ORDER BY {order_by}
"""
        return QueryPlan(
            sql=sql,
            template_name=(
                "admission_feasibility_lookup"
                if school is not None
                else "admission_search_lookup"
            ),
            data_sources=("staging.admission_records",),
        )

    def _multi_filter_plan(self, question: str, scope: QueryScope) -> QueryPlan | None:
        filters = [
            f"ar.exam_province = {_sql_literal(scope.exam_province)}",
            f"ar.plan_year = {int(scope.plan_year)}",
        ]
        rank = _extract_rank(question)
        score = _extract_score(question)
        subject_category = "物理类" if "物理类" in question else "历史类" if "历史类" in question else None
        ownership = _extract_ownership(question)
        tuition_limit = _extract_tuition_limit(question)
        major = _extract_major_keyword(question)
        city = _extract_city(question)

        dimensions = 0
        preference_dimensions = 0
        if rank is not None:
            filters.append(f"ar.min_rank >= 1 AND ar.min_rank <= {rank}")
            dimensions += 1
        elif score is not None:
            filters.append(f"ar.min_score <= {score}")
            dimensions += 1
        if subject_category is not None:
            filters.append(f"ar.subject_category = {_sql_literal(subject_category)}")
            dimensions += 1
        if ownership is not None:
            filters.append(f"s.ownership = {_sql_literal(ownership)}")
            dimensions += 1
            preference_dimensions += 1
        if tuition_limit is not None:
            filters.append(f"ar.tuition <= {tuition_limit}")
            dimensions += 1
            preference_dimensions += 1
        if major is not None:
            filters.append(f"ar.major_name ILIKE '%' || {_sql_literal(major)} || '%'")
            dimensions += 1
            preference_dimensions += 1
        if city is not None:
            filters.append(f"s.city ILIKE '%' || {_sql_literal(city)} || '%'")
            dimensions += 1
            preference_dimensions += 1

        if dimensions < 2 or preference_dimensions == 0:
            return None

        sql = f"""
SELECT
  ar.school_name,
  ar.major_name,
  ar.batch,
  ar.subject_category,
  ar.min_score,
  ar.min_rank,
  ar.enrollment_plan_count,
  ar.tuition,
  s.city,
  s.ownership,
  s.school_type,
  s.education_level
FROM staging.admission_records ar
LEFT JOIN school s ON s.name = ar.school_name
WHERE {" AND ".join(filters)}
ORDER BY ar.min_rank ASC NULLS LAST
"""
        return QueryPlan(
            sql=sql,
            template_name="multi_filter_lookup",
            data_sources=("staging.admission_records", "school"),
        )

    def _school_plan(self, question: str, scope: QueryScope) -> QueryPlan | None:
        school = _extract_school(question)
        if school is None:
            return None
        sql = f"""
SELECT
  ar.school_name,
  ar.major_name,
  ar.batch,
  ar.subject_category,
  ar.admission_program,
  ar.selection_requirements,
  ar.enrollment_plan_count,
  ar.filing_count,
  ar.min_score,
  ar.min_rank,
  ar.tuition,
  ar.duration,
  s.city,
  s.school_type,
  s.education_level,
  s.ownership,
  s.is_double_first_class
FROM staging.admission_records ar
LEFT JOIN school s ON s.name = ar.school_name
WHERE ar.exam_province = {_sql_literal(scope.exam_province)}
  AND ar.plan_year = {int(scope.plan_year)}
  AND ar.school_name ILIKE '%' || {_sql_literal(school)} || '%'
ORDER BY ar.subject_category, ar.min_rank ASC NULLS LAST
"""
        return QueryPlan(sql=sql, template_name="school_detail", data_sources=("staging.admission_records", "school"))

    def _major_plan(self, question: str, scope: QueryScope) -> QueryPlan | None:
        major = _extract_major(question)
        if major is None:
            return None
        sql = f"""
SELECT
  ar.school_name,
  ar.major_name,
  ar.batch,
  ar.subject_category,
  ar.min_score,
  ar.min_rank,
  ar.enrollment_plan_count,
  ar.tuition,
  ar.duration
FROM staging.admission_records ar
WHERE ar.exam_province = {_sql_literal(scope.exam_province)}
  AND ar.plan_year = {int(scope.plan_year)}
  AND ar.major_name ILIKE '%' || {_sql_literal(major)} || '%'
ORDER BY ar.min_rank ASC NULLS LAST
"""
        return QueryPlan(sql=sql, template_name="major_lookup", data_sources=("staging.admission_records",))

    def _score_rank_filter_plan(self, question: str, scope: QueryScope) -> QueryPlan | None:
        rank = _extract_rank(question)
        score = _extract_score(question)
        if rank is None and score is None:
            return None
        predicate = f"ar.min_rank >= 1 AND ar.min_rank <= {rank}" if rank is not None else f"ar.min_score <= {score}"
        sql = f"""
SELECT
  ar.school_name,
  ar.major_name,
  ar.batch,
  ar.subject_category,
  ar.min_score,
  ar.min_rank,
  ar.enrollment_plan_count
FROM staging.admission_records ar
WHERE ar.exam_province = {_sql_literal(scope.exam_province)}
  AND ar.plan_year = {int(scope.plan_year)}
  AND {predicate}
ORDER BY ar.min_rank ASC NULLS LAST
"""
        return QueryPlan(sql=sql, template_name="score_rank_filter", data_sources=("staging.admission_records",))

    def _region_plan(self, question: str, scope: QueryScope) -> QueryPlan | None:
        city = _extract_city(question)
        if city is None:
            return None
        sql = f"""
SELECT
  s.name AS school_name,
  s.city,
  s.school_type,
  s.education_level,
  s.ownership,
  s.is_double_first_class,
  p.name AS province_name
FROM school s
LEFT JOIN province p ON p.id = s.province_id
WHERE s.city ILIKE '%' || {_sql_literal(city)} || '%'
ORDER BY s.name ASC
"""
        return QueryPlan(sql=sql, template_name="region_school_lookup", data_sources=("school", "province"))

    def _special_program_plan(self, question: str, scope: QueryScope) -> QueryPlan | None:
        program = _extract_special_program(question)
        if program is None:
            return None
        sql = f"""
SELECT
  ar.school_name,
  ar.major_name,
  ar.subject_category,
  ar.admission_program,
  ar.min_score,
  ar.min_rank,
  ar.enrollment_plan_count
FROM staging.admission_records ar
WHERE ar.exam_province = {_sql_literal(scope.exam_province)}
  AND ar.plan_year = {int(scope.plan_year)}
  AND ar.admission_program ILIKE '%' || {_sql_literal(program)} || '%'
ORDER BY ar.min_rank ASC NULLS LAST
"""
        return QueryPlan(sql=sql, template_name="special_program_lookup", data_sources=("staging.admission_records",))

    def _selection_requirement_plan(self, question: str, scope: QueryScope) -> QueryPlan | None:
        major = _extract_major(question)
        school = _extract_school(question)
        if major is None and school is None:
            return None
        filters = [
            f"ar.exam_province = {_sql_literal(scope.exam_province)}",
            f"ar.plan_year = {int(scope.plan_year)}",
            "ar.selection_requirements IS NOT NULL",
        ]
        if major is not None:
            filters.append(f"ar.major_name ILIKE '%' || {_sql_literal(major)} || '%'")
        if school is not None:
            filters.append(f"ar.school_name ILIKE '%' || {_sql_literal(school)} || '%'")
        sql = f"""
SELECT
  ar.school_name,
  ar.major_name,
  ar.subject_category,
  ar.selection_requirements,
  ar.min_score,
  ar.min_rank
FROM staging.admission_records ar
WHERE {" AND ".join(filters)}
ORDER BY ar.school_name ASC, ar.major_name ASC
"""
        return QueryPlan(sql=sql, template_name="selection_requirement_lookup", data_sources=("staging.admission_records",))
