"""SQL 安全护栏测试（安全关键）。"""

from __future__ import annotations

import pytest

from gaokao_nl2sql.errors import UnsafeSqlError
from gaokao_nl2sql.guard import validate_select_sql


def test_simple_select_gets_limit_appended():
    sql = validate_select_sql("SELECT school_name FROM staging.admission_records")
    assert sql.lower().startswith("select")
    assert "limit 200" in sql.lower()


def test_with_cte_is_allowed():
    sql = validate_select_sql(
        "WITH t AS (SELECT 1 AS n) SELECT n FROM t LIMIT 5"
    )
    assert sql.lower().startswith("with")


def test_existing_limit_preserved():
    sql = validate_select_sql("SELECT 1 LIMIT 10")
    assert "limit 10" in sql.lower()


def test_limit_capped_at_max():
    sql = validate_select_sql("SELECT 1 LIMIT 99999", max_limit=1000)
    assert "limit 1000" in sql.lower()
    assert "99999" not in sql


def test_trailing_semicolon_allowed():
    sql = validate_select_sql("SELECT 1;")
    assert ";" not in sql


@pytest.mark.parametrize(
    "statement",
    [
        "DELETE FROM school",
        "UPDATE school SET name = 'x'",
        "INSERT INTO school (name) VALUES ('x')",
        "DROP TABLE school",
        "TRUNCATE school",
        "ALTER TABLE school ADD COLUMN x int",
        "CREATE TABLE t (id int)",
        "GRANT ALL ON school TO public",
        "SELECT * INTO new_table FROM school",
        "SET statement_timeout = 0",
    ],
)
def test_write_and_ddl_rejected(statement):
    with pytest.raises(UnsafeSqlError):
        validate_select_sql(statement)


def test_multiple_statements_rejected():
    with pytest.raises(UnsafeSqlError):
        validate_select_sql("SELECT 1; DROP TABLE school")


def test_stacked_query_via_semicolon_rejected():
    with pytest.raises(UnsafeSqlError):
        validate_select_sql(
            "SELECT * FROM school; SELECT * FROM province LIMIT 1"
        )


def test_empty_rejected():
    with pytest.raises(UnsafeSqlError):
        validate_select_sql("   ")


def test_comment_only_rejected():
    with pytest.raises(UnsafeSqlError):
        validate_select_sql("-- just a comment")


def test_non_select_statement_rejected():
    with pytest.raises(UnsafeSqlError):
        validate_select_sql("EXPLAIN SELECT 1")


def test_keyword_inside_string_literal_is_allowed():
    # 字面量里的 'delete' 不应被误判为写操作。
    sql = validate_select_sql(
        "SELECT school_name FROM school WHERE school_name = 'delete大学' LIMIT 5"
    )
    assert "limit 5" in sql.lower()
