# Feature: query-catalog, Property 10: 录取把握度参考单调且标注为非概率模型
"""AdmissionConfidence 属性测试。"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from gaokao_nl2sql.catalog.probability import AdmissionConfidence, NON_PROBABILITY_NOTE


@settings(max_examples=100)
@given(
    school_min_rank=st.integers(min_value=1, max_value=300_000),
    better_rank=st.integers(min_value=1, max_value=150_000),
    delta=st.integers(min_value=0, max_value=100_000),
)
def test_admission_confidence_monotonic_and_non_probability_note(
    school_min_rank: int,
    better_rank: int,
    delta: int,
) -> None:
    evaluator = AdmissionConfidence()
    worse_rank = better_rank + delta

    better = evaluator.evaluate(school_min_rank, better_rank)
    worse = evaluator.evaluate(school_min_rank, worse_rank)

    assert better.score >= worse.score
    assert better.band.level >= worse.band.level
    assert better.note == NON_PROBABILITY_NOTE
    assert "非概率模型" in better.note
