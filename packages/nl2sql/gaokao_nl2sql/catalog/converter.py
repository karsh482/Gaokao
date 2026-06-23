"""ScoreRankConverter：基于一分一段数据的位次↔分数换算（纯函数逻辑）。

分数段按累计人数（含本段及以上）单调：分数越高，累计位次越小。
换算结果标明 score_type 与 subject_category；超出覆盖范围时置 out_of_range，
不返回虚构换算值。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class ScoreSegment:
    """一分一段中的一个分数点。

    cumulative_count 表示分数 >= score 的累计人数（含本段）。
    """

    score: float
    cumulative_count: int
    score_type: str
    subject_category: str | None = None


@dataclass(frozen=True)
class ConversionResult:
    """换算结果，附带口径标注。"""

    score_type: str
    subject_category: str | None
    cumulative_rank: int | None  # 分数→位次
    score_or_range: tuple[float, float] | None  # 位次→分数区间
    out_of_range: bool


def _sorted_segments(
    segments: Sequence[ScoreSegment],
) -> list[ScoreSegment]:
    """按分数升序返回分数段副本。"""
    return sorted(segments, key=lambda s: s.score)


def _scope(segments: Sequence[ScoreSegment]) -> tuple[str, str | None]:
    """从分数段取统一的 score_type 与 subject_category 口径。"""
    first = segments[0]
    return first.score_type, first.subject_category


@dataclass(frozen=True)
class ScoreRankConverter:
    """位次↔分数换算器。"""

    def score_to_rank(
        self, segments: Sequence[ScoreSegment], score: float
    ) -> ConversionResult:
        """分数 → 累计位次。

        返回分数所属段的 cumulative_count；分数超出 [min, max] 时 out_of_range。
        """
        if not segments:
            raise ValueError("segments 不能为空")
        ordered = _sorted_segments(segments)
        score_type, subject_category = _scope(ordered)
        min_score = ordered[0].score
        max_score = ordered[-1].score

        if score < min_score or score > max_score:
            return ConversionResult(
                score_type=score_type,
                subject_category=subject_category,
                cumulative_rank=None,
                score_or_range=None,
                out_of_range=True,
            )

        # 所属段：分数 <= score 的最高分段（分数越高，位次越小）。
        segment = ordered[0]
        for seg in ordered:
            if seg.score <= score:
                segment = seg
            else:
                break
        return ConversionResult(
            score_type=score_type,
            subject_category=subject_category,
            cumulative_rank=segment.cumulative_count,
            score_or_range=None,
            out_of_range=False,
        )

    def rank_to_score(
        self, segments: Sequence[ScoreSegment], rank: int
    ) -> ConversionResult:
        """位次 → 分数区间。

        找到累计区间包含该位次的分段，返回其分数区间 [s_i, s_{i+1}]；
        位次超出 [1, 最大累计人数] 时 out_of_range。
        """
        if not segments:
            raise ValueError("segments 不能为空")
        ordered = _sorted_segments(segments)
        score_type, subject_category = _scope(ordered)
        # 累计人数最大值出现在最低分段。
        max_cumulative = max(seg.cumulative_count for seg in ordered)

        if rank < 1 or rank > max_cumulative:
            return ConversionResult(
                score_type=score_type,
                subject_category=subject_category,
                cumulative_rank=None,
                score_or_range=None,
                out_of_range=True,
            )

        # 从高分段向低分段找：第一个 cumulative_count >= rank 的段即所属段。
        # 高分段累计人数更小；当某段累计人数首次 >= rank，该位次落在此段。
        descending = list(reversed(ordered))  # 分数从高到低
        chosen_index = len(descending) - 1
        for idx, seg in enumerate(descending):
            if seg.cumulative_count >= rank:
                chosen_index = idx
                break

        chosen = descending[chosen_index]
        # 分数区间上界为更高一段的分数（若存在），否则为本段分数。
        if chosen_index > 0:
            high = descending[chosen_index - 1].score
        else:
            high = chosen.score
        low = chosen.score
        return ConversionResult(
            score_type=score_type,
            subject_category=subject_category,
            cumulative_rank=None,
            score_or_range=(low, high),
            out_of_range=False,
        )
