"""SemanticFrame 到受控 SQL 的编译测试。"""

from __future__ import annotations

from gaokao_nl2sql.catalog.semantic import frame_from_mapping
from gaokao_nl2sql.catalog.sql_compiler import SqlCompiler


def test_sql_compiler_builds_open_admission_search() -> None:
    frame = frame_from_mapping(
        {
            "route": "sql",
            "task": "admission_search",
            "exam_province": "贵州",
            "year": 2025,
            "candidate": {"rank": 9500},
            "filters": {"subject_category": "物理类"},
            "output": {"target": "schools", "limit": 10},
        }
    )

    plan = SqlCompiler().compile(frame)

    assert plan is not None
    assert plan.template_name == "semantic_admission_search"
    assert "ar.exam_province = '贵州'" in plan.sql
    assert "ar.plan_year = 2025" in plan.sql
    assert "ar.subject_category = '物理类'" in plan.sql
    assert "ar.min_rank >= 9500" in plan.sql
    assert "ar.school_name ILIKE" not in plan.sql
    assert "9500 AS candidate_rank" in plan.sql
    assert "ORDER BY ABS(ar.min_rank - 9500)" in plan.sql
    assert "LIMIT 10" in plan.sql


def test_sql_compiler_builds_school_feasibility_without_open_rank_filter() -> None:
    frame = frame_from_mapping(
        {
            "route": "sql",
            "task": "admission_feasibility",
            "exam_province": "贵州",
            "year": 2025,
            "candidate": {"rank": 10000},
            "filters": {
                "school_name": "贵州大学",
                "major_name": "法学",
                "subject_category": "物理类",
            },
            "output": {"target": "records", "limit": 20},
        }
    )

    plan = SqlCompiler().compile(frame)

    assert plan is not None
    assert plan.template_name == "semantic_admission_feasibility"
    assert "ar.school_name ILIKE '%' || '贵州大学' || '%'" in plan.sql
    assert "ar.major_name ILIKE '%' || '法学' || '%'" in plan.sql
    assert "ar.min_rank >= 10000" not in plan.sql
    assert "LIMIT 20" in plan.sql


def test_sql_compiler_ignores_non_sql_or_missing_candidate_metric() -> None:
    rag_frame = frame_from_mapping({"route": "rag", "task": "admission_search"})
    no_metric_frame = frame_from_mapping({"route": "sql", "task": "admission_search"})

    compiler = SqlCompiler()

    assert compiler.compile(rag_frame) is None
    assert compiler.compile(no_metric_frame) is None
