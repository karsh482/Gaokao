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
_QUESTION_PREFIX_PATTERN = re.compile(
    r"^(?:请问|请|帮我|麻烦|能不能|可以)?(?:查一下|查下|查询一下|查询|查|看一下|看下|看看|看|了解一下|了解)?"
    r"(?:今年|本年|明年|去年)?"
)
_MAJOR_PATTERN = re.compile(r"([\u4e00-\u9fa5A-Za-z0-9]{2,30}(?:专业|类))")
_DEPARTMENT_PATTERN = re.compile(r"([\u4e00-\u9fa5A-Za-z0-9]{1,30})系")
_EXPLICIT_RANK_PATTERN = re.compile(r"(?:位次|排名|排位)\s*([0-9一二三四五六七八九十百千万,，]+)\s*(?:名|位)?")
_BARE_RANK_PATTERN = re.compile(r"([0-9一二三四五六七八九十百千万,，]+)\s*(?:名|位)")
_SCORE_PATTERN = re.compile(r"([0-9]{3})\s*分")
_LEADING_TIME_PATTERN = re.compile(
    r"^[\s，,、：:的]*(?:(?:20\d{2})年?|今年|本年|明年|去年)[\s，,、：:的]*"
)
_CITY_QUERY_PATTERN = re.compile(r"([\u4e00-\u9fa5]{2,8})(?:有哪些大学|有哪些院校|有哪些学校)")
_CITY_TARGET_PATTERN = re.compile(
    r"(?:填报|报考|在|去|考虑)([\u4e00-\u9fa5]{2,8})(?:的哪些学校|的哪些院校|的哪些大学)"
)
_TUITION_PATTERN = re.compile(r"(?:学费|费用)[^0-9一二三四五六七八九十百千万]{0,6}([0-9一二三四五六七八九十百千万,，]+)")
_SPECIAL_PROGRAMS = ("国家专项", "地方专项", "高校专项", "民族班", "预科", "中外合作")
_CITY_HINTS = ("成都", "贵阳", "昆明", "重庆", "北京", "上海", "广州", "深圳", "武汉", "长沙", "南京", "杭州", "西安")
_PROVINCE_HINTS = (
    "四川",
    "云南",
    "重庆",
    "北京",
    "上海",
    "广东",
    "广西",
    "湖南",
    "湖北",
    "河南",
    "河北",
    "山东",
    "山西",
    "陕西",
    "江苏",
    "浙江",
    "安徽",
    "福建",
    "江西",
    "辽宁",
    "吉林",
    "黑龙江",
    "内蒙古",
    "宁夏",
    "青海",
    "甘肃",
    "新疆",
    "西藏",
    "海南",
    "天津",
)
_FEASIBILITY_KEYWORDS = ("能不能上", "能上", "可以上", "够得上", "有没有机会", "希望大吗")
_OPEN_RECOMMENDATION_KEYWORDS = (
    *_FEASIBILITY_KEYWORDS,
    "能报",
    "可以报",
    "可报",
    "可以填报",
    "填报",
    "推荐",
    "冲稳保",
    "冲一下",
    "冲",
    "哪些学校",
    "哪些大学",
    "哪些院校",
)
_PROGRAM_CATALOG_KEYWORDS = (
    "招生计划",
    "计划人数",
    "招多少",
    "招几人",
    "招几个人",
    "招几个",
    "招几名",
    "计划招生",
    "招生名额",
    "招生人数",
    "招收人数",
    "计划招聘人数",
    "招聘人数",
    "专业目录",
    "有哪些专业",
    "开设哪些专业",
    "学费",
    "选科要求",
    "科目要求",
    "学制",
)
_PROGRAM_LIST_KEYWORDS = (
    "有哪些专业",
    "专业有哪些",
    "招收哪些专业",
    "招哪些专业",
    "开设哪些专业",
    "开设什么专业",
    "招什么专业",
)
_PLAN_CHANGE_KEYWORDS = (
    "是否有变化",
    "有没有变化",
    "有变化吗",
    "变化",
    "变了吗",
    "对比",
    "比较",
    "比去年",
    "比2025",
    "比 2025",
    "增加",
    "减少",
    "多招",
    "少招",
)
_MAJOR_AFTER_SCHOOL_STOP_WORDS = (
    "专业",
    "今年",
    "本年",
    "明年",
    "去年",
    "2026",
    "2025",
    "招",
    "招生",
    "计划",
    "人数",
    "多少",
    "几个",
    "几人",
    "几名",
    "有没有",
    "是否",
    "变化",
    "对比",
    "比较",
    "比",
    "和",
    "与",
    "物理类",
    "历史类",
    "本科批",
    "本科",
    "专科",
    "高职",
    *_SPECIAL_PROGRAMS,
)
_RUSH_RANK_WINDOW = 5_000
_SECURE_RANK_WINDOW = 8_000
_SCORE_WINDOW = 20


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


def _signed_sql_int(value: int) -> str:
    return f"+ {value}" if value >= 0 else f"- {abs(value)}"


def _extract_school(question: str) -> str | None:
    match = _SCHOOL_PATTERN.search(question)
    if match is None:
        return None
    school = match.group(1)
    if any(token in school for token in ("哪些", "什么", "哪所", "哪几所")):
        return None
    school = _QUESTION_PREFIX_PATTERN.sub("", school)
    school = re.sub(r"^20\d{2}年?", "", school)
    school = re.sub(r"^(?:今年|本年|明年|去年)", "", school)
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


def _extract_department_major(question: str) -> str | None:
    school = _extract_school(question)
    target = question
    if school is not None and school in question:
        target = question.split(school, 1)[1]
    target = re.sub(r"^(?:今年|本年|明年|去年|的)", "", target)
    match = _DEPARTMENT_PATTERN.search(target)
    if match is None:
        return None
    major = match.group(1).strip()
    major = re.sub(r"^(?:今年|本年|明年|去年|的)", "", major)
    if not major or any(token in major for token in ("哪些", "什么", "院", "大学", "学院", "学校")):
        return None
    return major


def _extract_major_after_school(question: str) -> str | None:
    school = _extract_school(question)
    if school is None or school not in question:
        return None
    target = question.split(school, 1)[1]
    target = _LEADING_TIME_PATTERN.sub("", target)
    target = target.strip(" ，,、：:的")
    if not target:
        return None

    stop_positions = [
        index
        for keyword in _MAJOR_AFTER_SCHOOL_STOP_WORDS
        if (index := target.find(keyword)) >= 0
    ]
    if stop_positions:
        target = target[: min(stop_positions)]
    target = target.strip(" ，,、：:的")
    if not target:
        return None
    if len(target) > 30:
        return None
    if any(token in target for token in ("大学", "学院", "学校", "哪些", "什么", "多少")):
        return None
    if not re.search(r"[\u4e00-\u9fa5A-Za-z]", target):
        return None
    return target


def _extract_rank(question: str) -> int | None:
    match = _EXPLICIT_RANK_PATTERN.search(question)
    if match is not None:
        return _parse_chinese_number(match.group(1))
    for match in _BARE_RANK_PATTERN.finditer(question):
        prefix = question[max(0, match.start() - 8) : match.start()]
        if any(token in prefix for token in ("高", "低", "提升", "下降", "上升", "下滑", "靠前", "靠后", "前进", "后退")):
            continue
        return _parse_chinese_number(match.group(1))
    return None


def _extract_score(question: str) -> int | None:
    match = _SCORE_PATTERN.search(question)
    if match is None:
        return None
    return int(match.group(1))


def _extract_rank_adjustment(question: str) -> int | None:
    """抽取“排名/位次比去年高/低 N 名”的相对位次变化。

    返回值用于加到同分一分一段累计位次上：排名更靠前为负数，排名更靠后为正数。
    """

    if not any(token in question for token in ("位次", "排名", "排位")):
        return None
    pattern = re.compile(
        r"(?:位次|排名|排位).{0,12}"
        r"(高|提升|上升|提前|靠前|前进|进步|好了|低|下降|下滑|退步|靠后|后退)"
        r"(?:了)?\s*([0-9一二三四五六七八九十百千万,，]+)\s*(?:名|位)?"
    )
    match = pattern.search(question)
    if match is None:
        return None
    value = _parse_chinese_number(match.group(2))
    if value is None:
        return None
    direction = match.group(1)
    if direction in {"高", "提升", "上升", "提前", "靠前", "前进", "进步", "好了"}:
        return -value
    return value


def _is_open_recommendation_question(question: str) -> bool:
    if "以下" in question or "以内" in question or "不超过" in question:
        return False
    return any(keyword in question for keyword in _OPEN_RECOMMENDATION_KEYWORDS)


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
    target_match = _CITY_TARGET_PATTERN.search(question)
    if target_match is not None:
        city = target_match.group(1)
        return None if city in _PROVINCE_HINTS else city
    query_match = _CITY_QUERY_PATTERN.search(question)
    if query_match is not None:
        return query_match.group(1)
    for city in _CITY_HINTS:
        if city in question:
            return city
    return None


def _extract_school_province(question: str) -> str | None:
    for province in _PROVINCE_HINTS:
        if province not in question:
            continue
        if re.search(rf"{re.escape(province)}(?:大学|学院|学校)", question):
            continue
        if re.search(
            rf"{re.escape(province)}(?:省)?(?:的|内|省内|地区|院校|高校|学校|大学)",
            question,
        ):
            return province
        if "填报" in question or "报考" in question:
            return province
    return None


def _extract_major_keyword(
    question: str,
    *,
    allow_generic_major: bool = True,
) -> str | None:
    if _is_school_program_list_question(question):
        return None
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
    department_major = _extract_department_major(question)
    if department_major is not None:
        return department_major
    if not allow_generic_major:
        return _extract_major_after_school(question)
    major = _extract_major(question)
    if major is None:
        return _extract_major_after_school(question)
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


def _is_school_program_list_question(question: str) -> bool:
    return _extract_school(question) is not None and any(
        keyword in question for keyword in _PROGRAM_LIST_KEYWORDS
    )


def _is_program_catalog_question(question: str, scope: QueryScope, query: ClassifiedQuery) -> bool:
    if scope.plan_year == 2026 and any(keyword in question for keyword in _PROGRAM_CATALOG_KEYWORDS):
        return True
    return query.category in {QueryCategory.ENROLLMENT_PLAN, QueryCategory.SELECTION_REQ} and scope.plan_year == 2026


def _is_plan_change_question(question: str, query: ClassifiedQuery) -> bool:
    if query.category is not QueryCategory.ENROLLMENT_PLAN:
        return False
    has_change_signal = any(keyword in question for keyword in _PLAN_CHANGE_KEYWORDS)
    if not has_change_signal:
        return False
    has_plan_signal = any(keyword in question for keyword in _PROGRAM_CATALOG_KEYWORDS) or (
        "专业" in question and any(keyword in question for keyword in ("招", "招生"))
    )
    return has_plan_signal and _extract_school(question) is not None


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
        plan_change = self._program_plan_change_plan(question, scope, query)
        if plan_change is not None:
            return plan_change
        program_catalog_plan = self._program_catalog_plan(question, scope, query)
        if program_catalog_plan is not None:
            return program_catalog_plan
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

    def _program_catalog_plan(
        self,
        question: str,
        scope: QueryScope,
        query: ClassifiedQuery,
    ) -> QueryPlan | None:
        if not _is_program_catalog_question(question, scope, query):
            return None

        filters = [
            f"pc.exam_province = {_sql_literal(scope.exam_province)}",
            f"pc.plan_year = {int(scope.plan_year)}",
        ]
        school = _extract_school(question)
        major = _extract_major_keyword(question)
        subject_category = "物理类" if "物理类" in question else "历史类" if "历史类" in question else None
        special_program = _extract_special_program(question)

        if school is not None:
            filters.append(f"pc.school_name ILIKE '%' || {_sql_literal(school)} || '%'")
        if major is not None:
            filters.append(f"pc.major_name ILIKE '%' || {_sql_literal(major)} || '%'")
        if subject_category is not None:
            filters.append(f"pc.subject_category = {_sql_literal(subject_category)}")
        if special_program is not None:
            filters.append(
                "("
                f"pc.enrollment_type ILIKE '%' || {_sql_literal(special_program)} || '%' "
                "OR "
                f"pc.major_name ILIKE '%' || {_sql_literal(special_program)} || '%' "
                "OR "
                f"pc.remarks ILIKE '%' || {_sql_literal(special_program)} || '%'"
                ")"
            )
        if "本科批" in question or "本科" in question:
            filters.append("pc.education_level = '本科'")
        if "专科" in question or "高职" in question:
            filters.append("pc.education_level = '高职（专科）'")

        sql = f"""
SELECT
  pc.school_name,
  pc.major_name,
  pc.batch,
  pc.subject_category,
  pc.admission_track,
  pc.enrollment_type,
  pc.selection_requirements,
  pc.enrollment_plan_count,
  pc.language,
  pc.duration,
  pc.tuition,
  pc.remarks,
  pc.school_location,
  pc.source_file_name,
  pc.source_page,
  COUNT(*) OVER () AS matched_record_count,
  SUM(pc.enrollment_plan_count) OVER () AS matched_enrollment_plan_count
FROM staging.program_catalog_records pc
WHERE {" AND ".join(filters)}
ORDER BY pc.school_name ASC, pc.major_name ASC, pc.source_page ASC
"""
        return QueryPlan(
            sql=sql,
            template_name="program_catalog_lookup",
            data_sources=("staging.program_catalog_records",),
        )

    def _program_plan_change_plan(
        self,
        question: str,
        scope: QueryScope,
        query: ClassifiedQuery,
    ) -> QueryPlan | None:
        if not _is_plan_change_question(question, query):
            return None

        school = _extract_school(question)
        if school is None:
            return None
        major = _extract_major_keyword(question)
        subject_category = "物理类" if "物理类" in question else "历史类" if "历史类" in question else None
        special_program = _extract_special_program(question)

        filters_2025 = [
            f"exam_province = {_sql_literal(scope.exam_province)}",
            "plan_year = 2025",
            f"school_name ILIKE '%' || {_sql_literal(school)} || '%'",
        ]
        filters_2026 = [
            f"exam_province = {_sql_literal(scope.exam_province)}",
            "plan_year = 2026",
            f"school_name ILIKE '%' || {_sql_literal(school)} || '%'",
        ]
        if major is not None:
            filters_2025.append(f"major_name ILIKE '%' || {_sql_literal(major)} || '%'")
            filters_2026.append(f"major_name ILIKE '%' || {_sql_literal(major)} || '%'")
        if subject_category is not None:
            filters_2025.append(f"subject_category = {_sql_literal(subject_category)}")
            filters_2026.append(f"subject_category = {_sql_literal(subject_category)}")
        if special_program is not None:
            special = _sql_literal(special_program)
            filters_2025.append(
                "("
                f"enrollment_type ILIKE '%' || {special} || '%' "
                "OR "
                f"admission_program ILIKE '%' || {special} || '%'"
                ")"
            )
            filters_2026.append(
                "("
                f"enrollment_type ILIKE '%' || {special} || '%' "
                "OR "
                f"major_name ILIKE '%' || {special} || '%' "
                "OR "
                f"remarks ILIKE '%' || {special} || '%'"
                ")"
            )
        if "本科" in question:
            filters_2026.append("education_level = '本科'")
        if "专科" in question or "高职" in question:
            filters_2026.append("education_level = '高职（专科）'")

        sql = f"""
WITH y2025 AS (
  SELECT
    school_name,
    TRIM(regexp_replace(major_name, '[（(].*?[）)]', '', 'g')) AS major_name,
    subject_category,
    SUM(enrollment_plan_count) AS plan_count_2025,
    COUNT(*) AS record_count_2025
  FROM staging.admission_records
  WHERE {" AND ".join(filters_2025)}
  GROUP BY school_name, TRIM(regexp_replace(major_name, '[（(].*?[）)]', '', 'g')), subject_category
),
y2026 AS (
  SELECT
    school_name,
    TRIM(regexp_replace(major_name, '[（(].*?[）)]', '', 'g')) AS major_name,
    subject_category,
    SUM(enrollment_plan_count) AS plan_count_2026,
    COUNT(*) AS record_count_2026
  FROM staging.program_catalog_records
  WHERE {" AND ".join(filters_2026)}
  GROUP BY school_name, TRIM(regexp_replace(major_name, '[（(].*?[）)]', '', 'g')), subject_category
)
SELECT
  COALESCE(y2026.school_name, y2025.school_name) AS school_name,
  COALESCE(y2026.major_name, y2025.major_name) AS major_name,
  COALESCE(y2026.subject_category, y2025.subject_category) AS subject_category,
  y2025.plan_count_2025,
  y2026.plan_count_2026,
  (COALESCE(y2026.plan_count_2026, 0) - COALESCE(y2025.plan_count_2025, 0)) AS plan_count_change,
  CASE
    WHEN y2025.plan_count_2025 IS NULL THEN '2026新增'
    WHEN y2026.plan_count_2026 IS NULL THEN '2026未见'
    WHEN y2026.plan_count_2026 > y2025.plan_count_2025 THEN '增加'
    WHEN y2026.plan_count_2026 < y2025.plan_count_2025 THEN '减少'
    ELSE '持平'
  END AS change_type,
  y2025.record_count_2025,
  y2026.record_count_2026,
  '按院校、专业主名称、科类聚合匹配；专业名括号内专项/民族班等说明已合并，批次和招生类型未强制一致' AS comparison_note
FROM y2025
FULL JOIN y2026 USING (school_name, major_name, subject_category)
ORDER BY
  ABS(COALESCE(y2026.plan_count_2026, 0) - COALESCE(y2025.plan_count_2025, 0)) DESC,
  school_name ASC,
  major_name ASC,
  subject_category ASC
"""
        return QueryPlan(
            sql=sql,
            template_name="program_plan_change_lookup",
            data_sources=(
                "staging.admission_records",
                "staging.program_catalog_records",
            ),
        )

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
        if structured is None and not _is_open_recommendation_question(question):
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
        city = _extract_city(question)
        school_province = _extract_school_province(question)
        joins = ""
        data_sources = ["staging.admission_records"]
        if city is not None or school_province is not None:
            joins = "LEFT JOIN school s ON s.name = ar.school_name"
            data_sources.append("school")
        if city is not None:
            filters.append(f"s.city ILIKE '%' || {_sql_literal(city)} || '%'")
        if school_province is not None:
            joins += """
LEFT JOIN province p ON p.id = s.province_id"""
            filters.append(f"p.name ILIKE '%' || {_sql_literal(school_province)} || '%'")
            data_sources.append("province")
        data_sources = list(dict.fromkeys(data_sources))

        select_parts = [
            "ar.school_name",
            "ar.major_name",
            "ar.batch",
            "ar.subject_category",
            "ar.min_score",
            "ar.min_rank",
            "ar.enrollment_plan_count",
        ]
        if city is not None:
            select_parts.append("s.city")
        if school_province is not None:
            select_parts.append("p.name AS province_name")
        order_by = "ar.min_rank ASC NULLS LAST"
        if rank is not None:
            if school is None:
                filters.append(
                    "ar.min_rank BETWEEN "
                    f"GREATEST(1, {rank} - {_RUSH_RANK_WINDOW}) "
                    f"AND {rank} + {_SECURE_RANK_WINDOW}"
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
        elif score is not None:
            if school is None and subject_category is not None:
                adjustment = _extract_rank_adjustment(question) or 0
                candidate_rank_expr = "cp.candidate_rank"
                filters.append("cp.candidate_rank IS NOT NULL")
                filters.append(
                    "ar.min_rank BETWEEN "
                    f"GREATEST(1, {candidate_rank_expr} - {_RUSH_RANK_WINDOW}) "
                    f"AND {candidate_rank_expr} + {_SECURE_RANK_WINDOW}"
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
                score_rank_adjustment = _signed_sql_int(adjustment)
                cte = f"""WITH candidate_profile AS (
  SELECT
    {score} AS candidate_score,
    CASE
      WHEN MIN(ss.cumulative_count) IS NULL THEN NULL
      ELSE GREATEST(1, MIN(ss.cumulative_count) {score_rank_adjustment})::int
    END AS candidate_rank
  FROM staging.score_segments ss
  WHERE ss.exam_province = {_sql_literal(scope.exam_province)}
    AND ss.plan_year = {int(scope.plan_year)}
    AND ss.subject_category = {_sql_literal(subject_category)}
    AND ss.admission_track = '普通类'
    AND ss.score_type = '高考总分'
    AND ss.score = {score}
)"""
                data_sources.append("staging.score_segments")
            else:
                if school is None:
                    filters.append(
                        f"ar.min_score BETWEEN {max(0, score - _SCORE_WINDOW)} "
                        f"AND {score + _SCORE_WINDOW}"
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
"""
        return QueryPlan(
            sql=sql,
            template_name=(
                "admission_feasibility_lookup"
                if school is not None
                else "admission_search_lookup"
            ),
            data_sources=tuple(data_sources),
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
        school_province = _extract_school_province(question)

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
        if school_province is not None:
            filters.append(f"p.name ILIKE '%' || {_sql_literal(school_province)} || '%'")
            dimensions += 1
            preference_dimensions += 1

        if dimensions < 2 or preference_dimensions == 0:
            return None

        province_join = "\nLEFT JOIN province p ON p.id = s.province_id" if school_province is not None else ""
        province_select = ",\n  p.name AS province_name" if school_province is not None else ""
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
  s.education_level{province_select}
FROM staging.admission_records ar
LEFT JOIN school s ON s.name = ar.school_name
{province_join}
WHERE {" AND ".join(filters)}
ORDER BY ar.min_rank ASC NULLS LAST
"""
        return QueryPlan(
            sql=sql,
            template_name="multi_filter_lookup",
            data_sources=(
                "staging.admission_records",
                "school",
            )
            + (("province",) if school_province is not None else ()),
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
        filters = [
            f"ar.exam_province = {_sql_literal(scope.exam_province)}",
            f"ar.plan_year = {int(scope.plan_year)}",
            f"ar.min_rank >= 1 AND ar.min_rank <= {rank}" if rank is not None else f"ar.min_score <= {score}",
        ]
        subject_category = "物理类" if "物理类" in question else "历史类" if "历史类" in question else None
        if subject_category is not None:
            filters.append(f"ar.subject_category = {_sql_literal(subject_category)}")
        city = _extract_city(question)
        school_province = _extract_school_province(question)
        joins = ""
        select_extra = ""
        data_sources = ["staging.admission_records"]
        if city is not None or school_province is not None:
            joins = "LEFT JOIN school s ON s.name = ar.school_name"
            data_sources.append("school")
        if city is not None:
            filters.append(f"s.city ILIKE '%' || {_sql_literal(city)} || '%'")
            select_extra += ",\n  s.city"
        if school_province is not None:
            joins += """
LEFT JOIN province p ON p.id = s.province_id"""
            filters.append(f"p.name ILIKE '%' || {_sql_literal(school_province)} || '%'")
            if city is None:
                select_extra += ",\n  s.city"
            select_extra += ",\n  p.name AS province_name"
            data_sources.append("province")
        data_sources = list(dict.fromkeys(data_sources))
        sql = f"""
SELECT
  ar.school_name,
  ar.major_name,
  ar.batch,
  ar.subject_category,
  ar.min_score,
  ar.min_rank,
  ar.enrollment_plan_count{select_extra}
FROM staging.admission_records ar
{joins}
WHERE {" AND ".join(filters)}
ORDER BY ar.min_rank ASC NULLS LAST
"""
        return QueryPlan(sql=sql, template_name="score_rank_filter", data_sources=tuple(data_sources))

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
        filters = [
            f"ar.exam_province = {_sql_literal(scope.exam_province)}",
            f"ar.plan_year = {int(scope.plan_year)}",
            f"ar.admission_program ILIKE '%' || {_sql_literal(program)} || '%'",
        ]
        school = _extract_school(question)
        major = _extract_major_keyword(question)
        subject_category = "物理类" if "物理类" in question else "历史类" if "历史类" in question else None
        if school is not None:
            filters.append(f"ar.school_name ILIKE '%' || {_sql_literal(school)} || '%'")
        if major is not None:
            filters.append(f"ar.major_name ILIKE '%' || {_sql_literal(major)} || '%'")
        if subject_category is not None:
            filters.append(f"ar.subject_category = {_sql_literal(subject_category)}")
        if "本科批" in question:
            filters.append("ar.batch = '本科批'")
        sql = f"""
SELECT
  ar.school_name,
  ar.major_name,
  ar.batch,
  ar.subject_category,
  ar.admission_program,
  ar.min_score,
  ar.min_rank,
  ar.enrollment_plan_count
FROM staging.admission_records ar
WHERE {" AND ".join(filters)}
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
