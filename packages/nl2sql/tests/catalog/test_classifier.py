"""QueryClassifier 单元测试：各类别代表性问题。"""

from __future__ import annotations

import pytest

from gaokao_nl2sql.catalog.classifier import (
    ClassifiedQuery,
    QueryCategory,
    QueryClassifier,
)


@pytest.fixture
def classifier() -> QueryClassifier:
    return QueryClassifier()


@pytest.mark.parametrize(
    "question, expected",
    [
        ("贵州大学是什么档次的学校", QueryCategory.SCHOOL),
        ("计算机专业怎么样", QueryCategory.MAJOR),
        ("600 分能上哪些学校", QueryCategory.SCORE_RANK_FILTER),
        ("近几年贵州大学的投档线趋势如何", QueryCategory.TREND),
        ("贵州大学历年涨幅", QueryCategory.TREND),
        ("位次一万对应多少分", QueryCategory.SCORE_RANK_CONVERT),
        ("一分一段表里 500 分排名多少", QueryCategory.SCORE_RANK_CONVERT),
        ("国家专项计划有哪些院校", QueryCategory.SPECIAL_PROGRAM),
        ("这个专业的选科要求是什么", QueryCategory.SELECTION_REQ),
        ("贵州大学的招生计划人数是多少", QueryCategory.ENROLLMENT_PLAN),
        ("我这个位次冲稳保怎么填", QueryCategory.ADMISSION_PROBABILITY),
        ("平行志愿是什么意思", QueryCategory.POLICY_EXPLAIN),
        ("按录取均分给大学排名", QueryCategory.STATS_RANK),
    ],
)
def test_categorize_representative_questions(
    classifier: QueryClassifier, question: str, expected: QueryCategory
) -> None:
    assert classifier.classify(question).category is expected


def test_multi_filter_detected_when_multiple_dimensions(
    classifier: QueryClassifier,
) -> None:
    # 选科 + 地域 两个维度 -> 多条件组合筛选
    result = classifier.classify("物理类考生想报省内的公办大学")
    assert result.category is QueryCategory.MULTI_FILTER


def test_requested_metrics_extracted(classifier: QueryClassifier) -> None:
    result = classifier.classify("按录取均分排名，并且要 985 院校")
    assert "录取均分" in result.requested_metrics
    assert "985" in result.requested_metrics


def test_metric_synonyms_normalized(classifier: QueryClassifier) -> None:
    result = classifier.classify("各校平均分是多少")
    assert result.requested_metrics == frozenset({"录取均分"})


def test_generic_fallback(classifier: QueryClassifier) -> None:
    result = classifier.classify("你好")
    assert result.category is QueryCategory.GENERIC
    assert isinstance(result, ClassifiedQuery)
