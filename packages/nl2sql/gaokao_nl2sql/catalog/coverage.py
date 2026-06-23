"""DataCoverageRegistry：字段覆盖率与数据缺口标注。"""

from __future__ import annotations

from dataclasses import dataclass, field

from gaokao_nl2sql.catalog.classifier import QueryCategory


@dataclass(frozen=True)
class CoverageWarning:
    """数据字段覆盖缺口。"""

    field: str
    label: str
    coverage_ratio: float
    message: str


_SELECTION_REQUIREMENTS_WARNING = CoverageWarning(
    field="selection_requirements",
    label="选科要求",
    coverage_ratio=0.0,
    message="当前选科要求字段暂无数据，返回 0 行不代表该专业没有选科要求。",
)
_ADMITTED_COUNT_WARNING = CoverageWarning(
    field="admitted_count",
    label="实际录取人数",
    coverage_ratio=0.0,
    message="当前实际录取人数字段暂无数据，投档人数不能等同于实际录取人数。",
)
_AVERAGE_SCORE_WARNING = CoverageWarning(
    field="average_score",
    label="录取均分",
    coverage_ratio=0.0,
    message="当前数据不包含录取均分。",
)
_PROJECT_985_211_WARNING = CoverageWarning(
    field="project_985_211",
    label="985/211",
    coverage_ratio=0.0,
    message="当前院校主数据仅包含双一流标记，不包含单独的 985/211 字段。",
)


@dataclass(frozen=True)
class DataCoverageRegistry:
    """当前字段覆盖情况的确定性登记表。"""

    warnings_by_field: dict[str, CoverageWarning] = field(
        default_factory=lambda: {
            "selection_requirements": _SELECTION_REQUIREMENTS_WARNING,
            "admitted_count": _ADMITTED_COUNT_WARNING,
            "average_score": _AVERAGE_SCORE_WARNING,
            "project_985_211": _PROJECT_985_211_WARNING,
        }
    )

    def warnings_for(
        self,
        *,
        category: QueryCategory,
        question: str,
    ) -> tuple[CoverageWarning, ...]:
        warnings: list[CoverageWarning] = []
        if category is QueryCategory.SELECTION_REQ or any(
            token in question for token in ("选科要求", "科目要求", "选哪些科目")
        ):
            warnings.append(self.warnings_by_field["selection_requirements"])
        if any(token in question for token in ("实际录取人数", "录取人数", "admitted_count")):
            warnings.append(self.warnings_by_field["admitted_count"])
        if any(token in question for token in ("录取均分", "平均分")):
            warnings.append(self.warnings_by_field["average_score"])
        if any(token in question for token in ("985", "211")):
            warnings.append(self.warnings_by_field["project_985_211"])
        return tuple(dict.fromkeys(warnings))
