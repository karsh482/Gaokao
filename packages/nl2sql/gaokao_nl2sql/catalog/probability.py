"""录取把握度参考（冲稳保）：基于单年位次差的可解释参考评估。

这不是概率模型。给定院校最低录取位次与考生位次，按位次差给出冲/稳/保参考档位；
考生位次相对更优（数值更小）时把握度参考单调不降。所有结果都带有
"基于单年位次的参考评估，非概率模型结果" 的明确标注，避免被误读为录取概率。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

NON_PROBABILITY_NOTE = "基于单年位次的参考评估，非概率模型结果"


class ConfidenceBand(Enum):
    """把握度参考档位（数值越大表示把握越高）。"""

    RUSH = "冲"  # 考生位次明显劣于院校位次
    STABLE = "稳"  # 考生位次与院校位次接近
    SECURE = "保"  # 考生位次明显优于院校位次

    @property
    def level(self) -> int:
        return {"冲": 0, "稳": 1, "保": 2}[self.value]


@dataclass(frozen=True)
class ConfidenceReference:
    """把握度参考结果。

    score 为连续的单调把握度参考值（越大越有把握）；band 为离散档位。
    """

    band: ConfidenceBand
    score: float
    note: str = NON_PROBABILITY_NOTE


@dataclass(frozen=True)
class AdmissionConfidence:
    """基于位次差的把握度参考函数。

    rush_threshold / secure_threshold 以位次差（school_min_rank - candidate_rank）
    为口径划分档位：差值越大表示考生位次相对越优、把握越高。
    """

    rush_threshold: int = -2000  # 差值低于此 -> 冲
    secure_threshold: int = 2000  # 差值高于此 -> 保

    def evaluate(
        self, school_min_rank: int, candidate_rank: int
    ) -> ConfidenceReference:
        """给定院校最低录取位次与考生位次，返回把握度参考。

        位次差 = school_min_rank - candidate_rank。考生位次更小（更优）时差值更大，
        把握度参考值随之单调不降。
        """
        diff = school_min_rank - candidate_rank
        if diff < self.rush_threshold:
            band = ConfidenceBand.RUSH
        elif diff > self.secure_threshold:
            band = ConfidenceBand.SECURE
        else:
            band = ConfidenceBand.STABLE
        return ConfidenceReference(band=band, score=float(diff))
