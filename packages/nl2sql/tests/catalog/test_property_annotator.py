# Feature: query-catalog, Property 6: 查询响应忠实标注所采用的口径与条件
"""ResultAnnotator 属性测试：口径、部分可用、科类与地域/范围分离。"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from gaokao_nl2sql.catalog.annotator import ResultAnnotator
from gaokao_nl2sql.catalog.classifier import QueryCategory
from gaokao_nl2sql.catalog.gate import GateDecision
from gaokao_nl2sql.catalog.scope import QueryScope


@settings(max_examples=100)
@given(
    province=st.sampled_from(["贵州", "四川", "云南"]),
    year=st.integers(min_value=2020, max_value=2030),
    subject=st.sampled_from(["物理类", "历史类"]),
)
def test_annotation_marks_actual_scope_and_filters(
    province: str,
    year: int,
    subject: str,
) -> None:
    scope = QueryScope(province, year, False, False)
    annotation = ResultAnnotator().annotate(
        scope=scope,
        decision=GateDecision(True, (), ""),
        question=f"{subject} 600 分能上哪些学校",
        category=QueryCategory.SCORE_RANK_FILTER,
        rows=[{"school_name": "测试大学"}],
    )

    assert annotation.exam_province == province
    assert annotation.plan_year == year
    assert annotation.subject_category == subject
    assert annotation.applied_filters["exam_province"] == province
    assert annotation.applied_filters["plan_year"] == year
    assert annotation.applied_filters["subject_category"] == subject


# Feature: query-catalog, Property 7: 部分可用时保留可用项并标注缺失项
@settings(max_examples=100)
@given(
    requested=st.lists(
        st.sampled_from(["A大学", "B大学", "C大学", "D大学"]),
        min_size=1,
        max_size=4,
        unique=True,
    ),
    available=st.lists(
        st.sampled_from(["A大学", "B大学", "C大学", "D大学"]),
        min_size=0,
        max_size=4,
        unique=True,
    ),
)
def test_annotation_preserves_available_items_and_marks_missing(
    requested: list[str],
    available: list[str],
) -> None:
    available_in_request = [item for item in available if item in requested]
    notes = ResultAnnotator().annotate_requested_items(
        requested_items=requested,
        available_items=available_in_request,
    )

    missing = [item for item in requested if item not in available_in_request]
    assert len(available_in_request) + len(notes) == len(requested)
    assert notes == tuple(f"{item}：暂无数据。" for item in missing)


def test_annotation_marks_ignored_missing_metric_condition() -> None:
    annotation = ResultAnnotator().annotate(
        scope=QueryScope("贵州", 2025, False, False),
        decision=GateDecision(
            True,
            (),
            "",
            ignored_metric_conditions=("录取均分", "985"),
        ),
        question="物理类 公办 录取均分筛选 985",
        category=QueryCategory.MULTI_FILTER,
        rows=[{"school_name": "测试大学"}],
    )

    assert "录取均分" in annotation.availability.ignored_metric_conditions
    assert "985" in annotation.availability.ignored_metric_conditions
    assert any("录取均分" in note and "已被忽略" in note for note in annotation.notes)
    assert any("985" in note and "已被忽略" in note for note in annotation.notes)


# Feature: query-catalog, Property 8: 缺少科类时口径被显式处理
@settings(max_examples=100)
@given(score=st.integers(min_value=300, max_value=750))
def test_annotation_handles_missing_subject_category(score: int) -> None:
    annotation = ResultAnnotator().annotate(
        scope=QueryScope("贵州", 2025, False, False),
        decision=GateDecision(True, (), ""),
        question=f"{score} 分能上哪些学校",
        category=QueryCategory.SCORE_RANK_FILTER,
        rows=[{"school_name": "测试大学"}],
    )

    assert annotation.subject_category is None
    assert any("需要 subject_category" in note for note in annotation.notes)


# Feature: query-catalog, Property 9: 院校所在地与考试/招生省份始终分离
@settings(max_examples=100)
@given(
    school_city=st.sampled_from(["成都", "贵阳", "昆明"]),
    exam_province=st.sampled_from(["贵州", "四川"]),
)
def test_region_dimension_and_exam_scope_are_separate(
    school_city: str,
    exam_province: str,
) -> None:
    annotation = ResultAnnotator().annotate(
        scope=QueryScope(exam_province, 2025, False, False),
        decision=GateDecision(True, (), ""),
        question=f"{school_city}有哪些大学",
        category=QueryCategory.REGION,
        rows=[{"city": school_city, "school_name": "测试大学"}],
        applied_filters={"school_city": school_city},
    )

    assert annotation.applied_filters["school_city"] == school_city
    assert annotation.applied_filters["exam_province"] == exam_province
    assert "school_city" in annotation.applied_filters
    assert annotation.applied_filters["school_city"] != annotation.applied_filters["exam_province"]
