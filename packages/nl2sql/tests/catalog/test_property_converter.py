# Feature: query-catalog, Property 5: 位次↔分数换算的往返、边界与口径标注
"""ScoreRankConverter 属性测试。"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from gaokao_nl2sql.catalog.converter import ScoreRankConverter, ScoreSegment


@st.composite
def _segments(draw):
    scores = draw(
        st.lists(
            st.integers(min_value=300, max_value=750),
            min_size=3,
            max_size=20,
            unique=True,
        ).map(sorted)
    )
    counts = draw(
        st.lists(
            st.integers(min_value=1, max_value=500_000),
            min_size=len(scores),
            max_size=len(scores),
            unique=True,
        ).map(sorted)
    )
    return [
        ScoreSegment(
            score=float(score),
            cumulative_count=count,
            score_type="高考总分",
            subject_category="物理类",
        )
        for score, count in zip(scores, reversed(counts))
    ]


@settings(max_examples=100)
@given(segments=_segments())
def test_score_to_rank_and_rank_round_trip(segments: list[ScoreSegment]) -> None:
    converter = ScoreRankConverter()
    segment = segments[len(segments) // 2]

    rank_result = converter.score_to_rank(segments, segment.score)
    assert rank_result.cumulative_rank == segment.cumulative_count
    assert rank_result.out_of_range is False
    assert rank_result.score_type == "高考总分"
    assert rank_result.subject_category == "物理类"

    score_result = converter.rank_to_score(segments, segment.cumulative_count)
    assert score_result.score_or_range is not None
    low, high = score_result.score_or_range
    assert low <= segment.score <= high
    assert score_result.out_of_range is False
    assert score_result.score_type == "高考总分"
    assert score_result.subject_category == "物理类"


@settings(max_examples=100)
@given(segments=_segments())
def test_converter_out_of_range_does_not_fabricate(segments: list[ScoreSegment]) -> None:
    converter = ScoreRankConverter()
    min_score = min(s.score for s in segments)
    max_rank = max(s.cumulative_count for s in segments)

    score_result = converter.score_to_rank(segments, min_score - 1)
    assert score_result.out_of_range is True
    assert score_result.cumulative_rank is None
    assert score_result.score_or_range is None

    rank_result = converter.rank_to_score(segments, max_rank + 1)
    assert rank_result.out_of_range is True
    assert rank_result.cumulative_rank is None
    assert rank_result.score_or_range is None
