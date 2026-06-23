"""DataCoverageRegistry 单元测试。"""

from __future__ import annotations

from gaokao_nl2sql.catalog.classifier import QueryCategory
from gaokao_nl2sql.catalog.coverage import DataCoverageRegistry


def test_selection_requirement_coverage_warning() -> None:
    warnings = DataCoverageRegistry().warnings_for(
        category=QueryCategory.SELECTION_REQ,
        question="计算机专业选科要求是什么",
    )

    assert len(warnings) == 1
    assert warnings[0].field == "selection_requirements"
    assert warnings[0].coverage_ratio == 0.0
    assert "字段暂无数据" in warnings[0].message


def test_metric_coverage_warnings_from_question() -> None:
    warnings = DataCoverageRegistry().warnings_for(
        category=QueryCategory.MULTI_FILTER,
        question="985 院校按录取均分和实际录取人数筛选",
    )

    fields = {warning.field for warning in warnings}
    assert fields == {"project_985_211", "average_score", "admitted_count"}
