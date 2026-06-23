"""CitationBuilder 单元测试：数据来源标注。"""

from __future__ import annotations

from gaokao_nl2sql.catalog.citation import CitationBuilder
from gaokao_nl2sql.catalog.classifier import QueryCategory
from gaokao_nl2sql.catalog.scope import QueryScope


def test_admission_record_citation_uses_returned_fields_and_scope() -> None:
    citations = CitationBuilder().build(
        category=QueryCategory.SCORE_RANK_FILTER,
        scope=QueryScope("贵州", 2025, False, False),
        rows=[{"school_name": "贵州大学", "min_score": 600, "min_rank": 10000}],
    )

    assert len(citations) == 1
    citation = citations[0]
    assert citation.source == "staging.admission_records"
    assert citation.label == "投档录取数据"
    assert citation.exam_province == "贵州"
    assert citation.plan_year == 2025
    assert citation.fields == ("min_rank", "min_score", "school_name")


def test_region_query_cites_school_and_province_sources() -> None:
    citations = CitationBuilder().build(
        category=QueryCategory.REGION,
        scope=QueryScope("贵州", 2025, False, False),
        rows=[{"city": "成都", "school_name": "四川大学", "province_name": "四川省"}],
    )

    assert tuple(c.source for c in citations) == ("school", "province")
    assert citations[0].fields == ("city",)
    assert "院校所在地" in citations[0].note
    assert citations[1].fields == ("province_name",)


def test_score_convert_query_cites_score_segments() -> None:
    citations = CitationBuilder().build(
        category=QueryCategory.SCORE_RANK_CONVERT,
        scope=QueryScope("贵州", 2025, False, False),
        rows=[{"score": 600, "cumulative_count": 10000, "score_type": "高考总分"}],
    )

    assert len(citations) == 1
    assert citations[0].source == "staging.score_segments"
    assert citations[0].fields == ("cumulative_count", "score", "score_type")
    assert "分数段数据" in citations[0].label
