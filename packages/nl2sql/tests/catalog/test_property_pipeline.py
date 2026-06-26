# Feature: query-catalog, Property 3: 被拒请求绝不虚构数据
"""CatalogPipeline 属性测试：闸门拒绝时不调用 LLM、不执行 SQL。"""

from __future__ import annotations

from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from gaokao_nl2sql.catalog.pipeline import CatalogPipeline
from gaokao_nl2sql.generator import SqlGenerator
from gaokao_nl2sql.pipeline import Nl2SqlPipeline


class RecordingModel:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        return "SELECT 1"


class RecordingExecutor:
    def __init__(self) -> None:
        self.calls = 0
        self.sql: str | None = None

    def run(self, sql: str) -> list[dict[str, Any]]:
        self.calls += 1
        self.sql = sql
        return [{"ok": 1}]


@settings(max_examples=100)
@given(
    question=st.sampled_from(
        [
            "四川省 2025 年有哪些学校",
            "近几年贵州大学投档线趋势",
            "平行志愿是什么意思",
            "按录取均分给大学排名",
            "录取概率是多少",
        ]
    )
)
def test_rejected_request_never_calls_llm_or_executor(question: str) -> None:
    model = RecordingModel()
    executor = RecordingExecutor()
    pipeline = CatalogPipeline(
        nl2sql_pipeline=Nl2SqlPipeline(
            generator=SqlGenerator(model=model),
            executor=executor,
        )
    )

    result = pipeline.run(question)

    assert result.availability.available is False
    assert result.sql is None
    assert result.rows == []
    assert result.row_count == 0
    assert result.citations == ()
    assert result.availability.message
    assert model.calls == 0
    assert executor.calls == 0


def test_template_hit_never_calls_llm_but_executes_sql() -> None:
    model = RecordingModel()
    executor = RecordingExecutor()
    pipeline = CatalogPipeline(
        nl2sql_pipeline=Nl2SqlPipeline(
            generator=SqlGenerator(model=model),
            executor=executor,
        )
    )

    result = pipeline.run("物理类 位次 10000 能上哪些学校")

    assert result.availability.available is True
    assert result.template_name == "admission_search_lookup"
    assert result.sql is not None
    assert "min_rank BETWEEN GREATEST(1, 10000 - 5000) AND 10000 + 8000" in result.sql
    assert model.calls == 0
    assert executor.calls == 1


def test_template_miss_falls_back_to_llm_pipeline() -> None:
    model = RecordingModel()
    executor = RecordingExecutor()
    pipeline = CatalogPipeline(
        nl2sql_pipeline=Nl2SqlPipeline(
            generator=SqlGenerator(model=model),
            executor=executor,
        )
    )

    result = pipeline.run("请给我一个宽泛的招生数据概览")

    assert result.availability.available is True
    assert result.template_name is None
    assert model.calls == 1
    assert executor.calls == 1


def test_probability_without_intent_extractor_is_still_rejected() -> None:
    model = RecordingModel()
    executor = RecordingExecutor()
    pipeline = CatalogPipeline(
        nl2sql_pipeline=Nl2SqlPipeline(
            generator=SqlGenerator(model=model),
            executor=executor,
        )
    )

    result = pipeline.run("贵州大学录取概率是多少")

    assert result.availability.available is False
    assert result.sql is None
    assert model.calls == 0
    assert executor.calls == 0
