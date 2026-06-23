"""只读 SQL 执行器。

通过 READ ONLY 事务 + statement_timeout 提供纵深防御，
并强烈建议连接使用只读数据库角色。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from gaokao_nl2sql.errors import SqlExecutionError


class QueryExecutor(Protocol):
    """执行只读 SQL 并返回行的接口，便于测试替换。"""

    def run(self, sql: str) -> list[dict[str, Any]]:
        ...


@dataclass(slots=True)
class PostgresExecutor:
    """基于 psycopg 的只读执行器。"""

    dsn: str
    statement_timeout_ms: int = 10_000
    max_rows: int = 1000
    # 延迟导入 psycopg，避免未安装 db 额外依赖时导入失败。
    _connect: Any = field(default=None, repr=False)

    def run(self, sql: str) -> list[dict[str, Any]]:
        connect = self._connect or self._default_connect()
        try:
            with connect(self.dsn) as conn:
                conn.read_only = True
                with conn.cursor() as cur:
                    cur.execute(
                        f"SET statement_timeout = {int(self.statement_timeout_ms)}"
                    )
                    cur.execute(sql)
                    columns = [desc[0] for desc in cur.description or []]
                    rows = cur.fetchmany(self.max_rows)
            return [dict(zip(columns, row)) for row in rows]
        except Exception as exc:  # noqa: BLE001 - 统一包装执行异常
            raise SqlExecutionError(f"SQL 执行失败: {exc}") from exc

    @staticmethod
    def _default_connect() -> Any:
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - 取决于环境
            raise SqlExecutionError(
                "需要安装可选依赖 psycopg（pip install 'gaokao-nl2sql[db]'）。"
            ) from exc
        return psycopg.connect
