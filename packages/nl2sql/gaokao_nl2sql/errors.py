"""NL2SQL 相关异常。"""

from __future__ import annotations


class Nl2SqlError(Exception):
    """NL2SQL 流程的基类异常。"""


class SqlGenerationError(Nl2SqlError):
    """LLM 未能生成可用 SQL。"""


class UnsafeSqlError(Nl2SqlError):
    """生成的 SQL 未通过安全护栏。"""


class SqlExecutionError(Nl2SqlError):
    """SQL 执行阶段出错。"""
