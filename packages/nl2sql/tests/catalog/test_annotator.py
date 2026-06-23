"""ResultAnnotator 单元与属性相关测试。"""

from __future__ import annotations

from gaokao_nl2sql.catalog.annotator import ResultAnnotator
from gaokao_nl2sql.catalog.classifier import QueryCategory
from gaokao_nl2sql.catalog.gate import GateDecision
from gaokao_nl2sql.catalog.scope import QueryScope


def _scope() -> QueryScope:
    return QueryScope("贵州", 2025, True, True)


def test_annotation_marks_scope_and_filters() -> None:
    annotation = ResultAnnotator().annotate(
        scope=_scope(),
        decision=GateDecision(True, (), ""),
        question="物理类 600 分能上哪些学校",
        category=QueryCategory.SCORE_RANK_FILTER,
        rows=[{"school_name": "贵州大学"}],
    )

    assert annotation.exam_province == "贵州"
    assert annotation.plan_year == 2025
    assert annotation.subject_category == "物理类"
    assert annotation.applied_filters["exam_province"] == "贵州"
    assert annotation.applied_filters["plan_year"] == 2025
    assert annotation.applied_filters["subject_category"] == "物理类"
    assert any("默认值" in note for note in annotation.notes)


def test_annotation_marks_ignored_missing_metrics() -> None:
    annotation = ResultAnnotator().annotate(
        scope=_scope(),
        decision=GateDecision(
            True,
            (),
            "",
            ignored_metric_conditions=("录取均分",),
        ),
        question="物理类 公办 按录取均分筛选",
        category=QueryCategory.MULTI_FILTER,
        rows=[{"school_name": "贵州大学"}],
    )

    assert annotation.availability.available is True
    assert annotation.availability.ignored_metric_conditions == ("录取均分",)
    assert any("已被忽略：录取均分" in note for note in annotation.notes)


def test_annotation_requires_subject_category_for_score_without_subject() -> None:
    annotation = ResultAnnotator().annotate(
        scope=_scope(),
        decision=GateDecision(True, (), ""),
        question="600 分能上哪些学校",
        category=QueryCategory.SCORE_RANK_FILTER,
        rows=[{"school_name": "贵州大学"}],
    )

    assert annotation.subject_category is None
    assert any("需要 subject_category" in note for note in annotation.notes)


def test_annotation_partial_items_marks_missing_items() -> None:
    notes = ResultAnnotator().annotate_requested_items(
        requested_items=["A大学", "B大学", "C大学"],
        available_items=["A大学", "C大学"],
    )

    assert notes == ("B大学：暂无数据。",)
