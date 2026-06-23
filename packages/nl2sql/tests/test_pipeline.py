"""NL2SQL 流程测试，使用 mock LLM 与 mock 执行器（无需真实 LLM / 数据库）。"""

from __future__ import annotations

from typing import Any

import pytest

from gaokao_nl2sql.errors import SqlGenerationError, UnsafeSqlError
from gaokao_nl2sql.generator import SqlGenerator, extract_sql
from gaokao_nl2sql.pipeline import Nl2SqlPipeline


class FakeModel:
    """返回预设回复的假模型。"""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return self.reply


class FakeExecutor:
    """记录收到的 SQL 并返回固定行。"""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.executed_sql: str | None = None

    def run(self, sql: str) -> list[dict[str, Any]]:
        self.executed_sql = sql
        return self.rows


def test_extract_sql_from_fenced_block():
    text = "好的：\n```sql\nSELECT 1\n```"
    assert extract_sql(text) == "SELECT 1"


def test_extract_sql_without_fence():
    assert extract_sql("SELECT 1 LIMIT 5") == "SELECT 1 LIMIT 5"


def test_pipeline_happy_path():
    model = FakeModel("```sql\nSELECT school_name FROM staging.admission_records WHERE min_rank <= 10000\n```")
    executor = FakeExecutor([{"school_name": "四川大学"}])
    pipeline = Nl2SqlPipeline(
        generator=SqlGenerator(model=model),
        executor=executor,
    )

    result = pipeline.run("位次一万能上哪些学校？")

    assert result.row_count == 1
    assert result.rows[0]["school_name"] == "四川大学"
    # 护栏应自动补上 LIMIT。
    assert "limit 200" in executor.executed_sql.lower()
    # schema 上下文应作为 system prompt 传入。
    assert "staging.admission_records" in model.calls[0][0]


def test_pipeline_rejects_unsafe_sql_before_execution():
    model = FakeModel("DROP TABLE school")
    executor = FakeExecutor([])
    pipeline = Nl2SqlPipeline(
        generator=SqlGenerator(model=model),
        executor=executor,
    )

    with pytest.raises(UnsafeSqlError):
        pipeline.run("删除所有学校")

    # 不安全的 SQL 不应到达执行器。
    assert executor.executed_sql is None


def test_pipeline_empty_question_rejected():
    pipeline = Nl2SqlPipeline(
        generator=SqlGenerator(model=FakeModel("SELECT 1")),
        executor=FakeExecutor([]),
    )
    with pytest.raises(SqlGenerationError):
        pipeline.run("   ")
