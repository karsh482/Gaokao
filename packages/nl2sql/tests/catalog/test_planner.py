"""QueryPlanner 单元测试：高频查询模板 SQL。"""

from __future__ import annotations

from gaokao_nl2sql.catalog.classifier import QueryClassifier, QueryCategory
from gaokao_nl2sql.catalog.planner import QueryPlanner
from gaokao_nl2sql.catalog.scope import QueryScope


def _plan(question: str):
    classifier = QueryClassifier()
    return QueryPlanner().plan(
        question=question,
        scope=QueryScope("贵州", 2025, False, False),
        query=classifier.classify(question),
    )


def _plan_2026(question: str):
    classifier = QueryClassifier()
    return QueryPlanner().plan(
        question=question,
        scope=QueryScope("贵州", 2026, False, False),
        query=classifier.classify(question),
    )


def test_school_query_template_joins_school_master_data() -> None:
    plan = _plan("查询贵州大学投档线和基本信息")

    assert plan is not None
    assert plan.template_name == "school_detail"
    assert "FROM staging.admission_records ar" in plan.sql
    assert "LEFT JOIN school s" in plan.sql
    assert "ar.exam_province = '贵州'" in plan.sql
    assert "ar.plan_year = 2025" in plan.sql


def test_admission_search_template_orders_by_rank_gap() -> None:
    plan = _plan("物理类 位次 10000 能上哪些学校")

    assert plan is not None
    assert plan.template_name == "admission_search_lookup"
    assert "ar.min_rank BETWEEN GREATEST(1, 10000 - 5000) AND 10000 + 8000" in plan.sql
    assert "ORDER BY ABS(ar.min_rank - 10000)" in plan.sql


def test_admission_feasibility_template_uses_rank_gap() -> None:
    plan = _plan("贵州物理类 位次 10000 能不能上贵州大学")

    assert plan is not None
    assert plan.template_name == "admission_feasibility_lookup"
    assert "ar.school_name ILIKE" in plan.sql
    assert "'贵州大学'" in plan.sql
    assert "能不能上贵州大学" not in plan.sql
    assert "ar.subject_category = '物理类'" in plan.sql
    assert "ar.major_name ILIKE" not in plan.sql
    assert "10000 AS candidate_rank" in plan.sql
    assert "(ar.min_rank - 10000) AS rank_gap" in plan.sql
    assert "confidence_band" in plan.sql
    assert "非概率模型结果" in plan.sql


def test_admission_search_template_supports_open_school_query() -> None:
    plan = _plan("贵州物理类 9500名，能上哪些大学？")

    assert plan is not None
    assert plan.template_name == "admission_search_lookup"
    assert "ar.school_name ILIKE" not in plan.sql
    assert "ar.subject_category = '物理类'" in plan.sql
    assert "ar.min_rank BETWEEN GREATEST(1, 9500 - 5000) AND 9500 + 8000" in plan.sql
    assert "9500 AS candidate_rank" in plan.sql
    assert "ORDER BY ABS(ar.min_rank - 9500)" in plan.sql


def test_admission_search_template_converts_score_to_rank_for_rush_stable_secure() -> None:
    plan = _plan("物理类 580分排名比去年高了1000名，可以冲哪些学校")

    assert plan is not None
    assert plan.template_name == "admission_search_lookup"
    assert "WITH candidate_profile AS" in plan.sql
    assert "FROM staging.score_segments ss" in plan.sql
    assert "ss.subject_category = '物理类'" in plan.sql
    assert "ss.score = 580" in plan.sql
    assert "MIN(ss.cumulative_count) - 1000" in plan.sql
    assert "CROSS JOIN candidate_profile cp" in plan.sql
    assert "cp.candidate_rank IS NOT NULL" in plan.sql
    assert "ar.min_rank BETWEEN GREATEST(1, cp.candidate_rank - 5000) AND cp.candidate_rank + 8000" in plan.sql
    assert "cp.candidate_rank" in plan.sql
    assert "confidence_band" in plan.sql


def test_admission_feasibility_template_supports_major_filter() -> None:
    plan = _plan("贵州历史类 位次 10000 能不能上贵州大学法学专业")

    assert plan is not None
    assert plan.template_name == "admission_feasibility_lookup"
    assert "ar.major_name ILIKE" in plan.sql
    assert "法学" in plan.sql


def test_admission_feasibility_template_supports_score_gap() -> None:
    plan = _plan("物理类 580分能不能上贵州大学")

    assert plan is not None
    assert plan.template_name == "admission_feasibility_lookup"
    assert "580 AS candidate_score" in plan.sql
    assert "(580 - ar.min_score) AS score_gap" in plan.sql
    assert "优先建议使用位次评估" in plan.sql


def test_score_filter_template_supports_school_province_filter() -> None:
    plan = _plan("物理类 580分可以填报四川的哪些学校")

    assert plan is not None
    assert plan.template_name == "admission_search_lookup"
    assert "LEFT JOIN school s ON s.name = ar.school_name" in plan.sql
    assert "LEFT JOIN province p ON p.id = s.province_id" in plan.sql
    assert "p.name ILIKE '%' || '四川' || '%'" in plan.sql
    assert "ar.subject_category = '物理类'" in plan.sql
    assert "cp.candidate_rank" in plan.sql
    assert "staging.score_segments" in plan.sql
    assert "p.name AS province_name" in plan.sql


def test_score_filter_template_supports_city_filter() -> None:
    plan = _plan("物理类 580分可以填报成都的哪些学校")

    assert plan is not None
    assert plan.template_name == "admission_search_lookup"
    assert "LEFT JOIN school s ON s.name = ar.school_name" in plan.sql
    assert "s.city ILIKE '%' || '成都' || '%'" in plan.sql
    assert "ar.subject_category = '物理类'" in plan.sql
    assert "cp.candidate_rank" in plan.sql
    assert "staging.score_segments" in plan.sql
    assert "s.city" in plan.sql


def test_region_template_uses_school_and_province_only() -> None:
    plan = _plan("成都有哪些大学")

    assert plan is not None
    assert plan.template_name == "region_school_lookup"
    assert "FROM school s" in plan.sql
    assert "LEFT JOIN province p" in plan.sql
    assert "staging.admission_records" not in plan.sql


def test_multi_filter_template_combines_rank_ownership_tuition_and_major() -> None:
    plan = _plan("物理类 位次 30000 公办 学费 8000 以下的计算机专业有哪些学校")

    assert plan is not None
    assert plan.template_name == "multi_filter_lookup"
    assert "LEFT JOIN school s" in plan.sql
    assert "ar.subject_category = '物理类'" in plan.sql
    assert "ar.min_rank <= 30000" in plan.sql
    assert "s.ownership = '公办'" in plan.sql
    assert "ar.tuition <= 8000" in plan.sql
    assert "ar.major_name ILIKE" in plan.sql
    assert "ORDER BY ar.min_rank ASC" in plan.sql


def test_multi_filter_template_supports_city_filter() -> None:
    plan = _plan("物理类 位次 50000 成都 公办大学有哪些")

    assert plan is not None
    assert plan.template_name == "multi_filter_lookup"
    assert "s.city ILIKE" in plan.sql
    assert "s.ownership = '公办'" in plan.sql


def test_special_program_template_combines_school_major_subject_and_batch() -> None:
    plan = _plan("北京语言大学 计算机类(民族班) 本科批 物理类 这个专业招多少人")

    assert plan is not None
    assert plan.template_name == "special_program_lookup"
    assert "ar.admission_program ILIKE" in plan.sql
    assert "'民族班'" in plan.sql
    assert "ar.school_name ILIKE" in plan.sql
    assert "'北京语言大学'" in plan.sql
    assert "ar.major_name ILIKE" in plan.sql
    assert "'计算机'" in plan.sql
    assert "ar.subject_category = '物理类'" in plan.sql
    assert "ar.batch = '本科批'" in plan.sql
    assert "ar.enrollment_plan_count" in plan.sql


def test_program_catalog_template_uses_2026_plan_catalog_table() -> None:
    plan = _plan_2026("北京语言大学 计算机类(民族班) 本科批 物理类 这个专业招多少人")

    assert plan is not None
    assert plan.template_name == "program_catalog_lookup"
    assert "FROM staging.program_catalog_records pc" in plan.sql
    assert "pc.plan_year = 2026" in plan.sql
    assert "pc.school_name ILIKE" in plan.sql
    assert "'北京语言大学'" in plan.sql
    assert "pc.major_name ILIKE" in plan.sql
    assert "'计算机'" in plan.sql
    assert "pc.subject_category = '物理类'" in plan.sql
    assert "pc.education_level = '本科'" in plan.sql
    assert "pc.enrollment_plan_count" in plan.sql
    assert plan.data_sources == ("staging.program_catalog_records",)


def test_program_catalog_template_strips_year_prefix_from_school_name() -> None:
    plan = _plan_2026("2026年北京语言大学计算机类物理类招多少人")

    assert plan is not None
    assert "'北京语言大学'" in plan.sql
    assert "'2026年北京语言大学'" not in plan.sql


def test_program_catalog_template_strips_colloquial_prefix_from_school_name() -> None:
    plan = _plan_2026("帮我查下今年贵州大学计算机系一共招多少人")

    assert plan is not None
    assert plan.template_name == "program_catalog_lookup"
    assert "'贵州大学'" in plan.sql
    assert "'下今年贵州大学'" not in plan.sql
    assert "pc.major_name ILIKE" in plan.sql
    assert "'计算机'" in plan.sql


def test_program_catalog_template_extracts_department_as_major_keyword() -> None:
    plan = _plan_2026("帮我看今年贵州大学数学系招几个")

    assert plan is not None
    assert plan.template_name == "program_catalog_lookup"
    assert "'贵州大学'" in plan.sql
    assert "pc.major_name ILIKE" in plan.sql
    assert "'数学'" in plan.sql


def test_program_catalog_template_supports_school_program_list_question() -> None:
    plan = _plan_2026("2026年贵州大学招收哪些专业")

    assert plan is not None
    assert plan.template_name == "program_catalog_lookup"
    assert "FROM staging.program_catalog_records pc" in plan.sql
    assert "pc.plan_year = 2026" in plan.sql
    assert "pc.school_name ILIKE" in plan.sql
    assert "'贵州大学'" in plan.sql
    assert "pc.major_name ILIKE" not in plan.sql
    assert "COUNT(*) OVER () AS matched_record_count" in plan.sql
    assert "SUM(pc.enrollment_plan_count) OVER () AS matched_enrollment_plan_count" in plan.sql


def test_program_plan_change_template_compares_2025_and_2026_by_major_subject() -> None:
    plan = _plan_2026("贵州大学2026年法学专业招生人数是否有变化")

    assert plan is not None
    assert plan.template_name == "program_plan_change_lookup"
    assert "FROM staging.admission_records" in plan.sql
    assert "FROM staging.program_catalog_records" in plan.sql
    assert "plan_year = 2025" in plan.sql
    assert "plan_year = 2026" in plan.sql
    assert "school_name ILIKE '%' || '贵州大学' || '%'" in plan.sql
    assert "major_name ILIKE '%' || '法学' || '%'" in plan.sql
    assert "FULL JOIN y2026 USING (school_name, major_name, subject_category)" in plan.sql
    assert "plan_count_change" in plan.sql
    assert plan.data_sources == (
        "staging.admission_records",
        "staging.program_catalog_records",
    )


def test_program_plan_change_template_supports_subject_filter() -> None:
    plan = _plan_2026("贵州大学法学专业物理类2026比2025招生人数有变化吗")

    assert plan is not None
    assert plan.template_name == "program_plan_change_lookup"
    assert "subject_category = '物理类'" in plan.sql


def test_major_school_list_question_keeps_admission_major_filter() -> None:
    plan = _plan("物理类 位次 30000 公办 学费 8000 以下的计算机专业有哪些学校")

    assert plan is not None
    assert plan.template_name == "multi_filter_lookup"
    assert "ar.major_name ILIKE" in plan.sql
    assert "'计算机'" in plan.sql


def test_selection_requirement_template_requires_school_or_major() -> None:
    plan = _plan("计算机专业选科要求是什么")

    assert plan is not None
    assert plan.template_name == "selection_requirement_lookup"
    assert "selection_requirements IS NOT NULL" in plan.sql


def test_generic_query_has_no_template() -> None:
    classifier = QueryClassifier()
    query = classifier.classify("你好")
    plan = QueryPlanner().plan(
        question="你好",
        scope=QueryScope("贵州", 2025, False, False),
        query=query,
    )

    assert query.category is QueryCategory.GENERIC
    assert plan is None
