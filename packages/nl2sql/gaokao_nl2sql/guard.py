"""SQL 安全护栏：保证 LLM 生成的语句是单条只读 SELECT。

这是 NL2SQL 链路的安全关键组件。除本模块的静态校验外，执行层还应：
- 使用只读数据库角色；
- 在 READ ONLY 事务中执行；
- 设置 statement_timeout。
形成纵深防御，不要仅依赖文本校验。
"""

from __future__ import annotations

import re

from gaokao_nl2sql.errors import UnsafeSqlError

# 禁止出现的写/DDL/权限/系统关键字（按独立单词匹配）。
_FORBIDDEN_KEYWORDS = (
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "truncate",
    "grant",
    "revoke",
    "copy",
    "merge",
    "call",
    "do",
    "vacuum",
    "analyze",
    "reindex",
    "cluster",
    "comment",
    "set",
    "reset",
    "begin",
    "commit",
    "rollback",
    "savepoint",
    "listen",
    "notify",
    "lock",
    "prepare",
    "execute",
    "deallocate",
    "explain",
    "into",  # 防止 SELECT ... INTO 建表
)

_DEFAULT_LIMIT = 200
_MAX_LIMIT = 1000

_LINE_COMMENT = re.compile(r"--[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_LIMIT_PATTERN = re.compile(r"\blimit\s+(\d+)\b", re.IGNORECASE)


def _strip_comments(sql: str) -> str:
    sql = _BLOCK_COMMENT.sub(" ", sql)
    sql = _LINE_COMMENT.sub(" ", sql)
    return sql


def _strip_string_literals(sql: str) -> str:
    """移除单引号字符串字面量，避免把字面量里的词误判为关键字。"""

    return re.sub(r"'(?:''|[^'])*'", "''", sql)


def _normalize(sql: str) -> str:
    cleaned = _strip_comments(sql).strip()
    # 去掉结尾的单个分号；保留中间分号以便检测多语句。
    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].rstrip()
    return cleaned


def validate_select_sql(
    sql: str,
    *,
    default_limit: int = _DEFAULT_LIMIT,
    max_limit: int = _MAX_LIMIT,
) -> str:
    """校验并规范化只读 SELECT 语句，返回安全可执行的 SQL。

    校验失败时抛出 ``UnsafeSqlError``。
    """

    if not sql or not sql.strip():
        raise UnsafeSqlError("SQL 为空。")

    normalized = _normalize(sql)
    if not normalized:
        raise UnsafeSqlError("SQL 去除注释后为空。")

    # 多语句检测：去字符串后不应再出现分号。
    without_strings = _strip_string_literals(normalized)
    if ";" in without_strings:
        raise UnsafeSqlError("只允许单条语句，检测到多条语句。")

    lowered = without_strings.lower()

    # 必须以 select 或 with 开头。
    if not re.match(r"^\s*(select|with)\b", lowered):
        raise UnsafeSqlError("只允许 SELECT 或 WITH 查询。")

    # 禁止关键字（按单词边界）。
    for keyword in _FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", lowered):
            raise UnsafeSqlError(f"检测到禁止的关键字: {keyword}")

    return _enforce_limit(
        normalized,
        lowered,
        default_limit=default_limit,
        max_limit=max_limit,
    )


def _enforce_limit(
    normalized: str,
    lowered: str,
    *,
    default_limit: int,
    max_limit: int,
) -> str:
    """确保语句带 LIMIT，且不超过上限。"""

    match = _LIMIT_PATTERN.search(lowered)
    if match is None:
        return f"{normalized} LIMIT {default_limit}"

    requested = int(match.group(1))
    if requested > max_limit:
        # 用上限替换原 LIMIT 数值（基于 normalized，大小写不敏感）。
        return _LIMIT_PATTERN.sub(f"LIMIT {max_limit}", normalized, count=1)
    return normalized
