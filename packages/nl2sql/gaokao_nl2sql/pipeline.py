"""NL2SQL 流程编排：生成 -> 安全护栏 -> 只读执行。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gaokao_nl2sql.executor import QueryExecutor
from gaokao_nl2sql.generator import SqlGenerator
from gaokao_nl2sql.guard import validate_select_sql


@dataclass(slots=True)
class Nl2SqlResult:
    """一次 NL2SQL 查询的结果。"""

    question: str
    sql: str
    rows: list[dict[str, Any]]
    row_count: int


@dataclass(slots=True)
class Nl2SqlPipeline:
    """把问题转成只读 SQL 并执行。

    generator 与 executor 均可注入，便于在无 LLM / 无数据库时单测。
    """

    generator: SqlGenerator
    executor: QueryExecutor
    default_limit: int = 200
    max_limit: int = 1000

    def run(self, question: str) -> Nl2SqlResult:
        raw_sql = self.generator.generate(question)
        safe_sql = validate_select_sql(
            raw_sql,
            default_limit=self.default_limit,
            max_limit=self.max_limit,
        )
        rows = self.executor.run(safe_sql)
        return Nl2SqlResult(
            question=question,
            sql=safe_sql,
            rows=rows,
            row_count=len(rows),
        )
