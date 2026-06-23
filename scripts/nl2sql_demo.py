#!/usr/bin/env python3
"""NL2SQL 烟雾测试：验证 LLM（DeepSeek V4）连接、SQL 生成与（可选）执行。

用法：
    # 仅生成 SQL（只需要 LLM Key，不需要数据库）
    python scripts/nl2sql_demo.py "贵州2025历史类，位次一万能上哪些学校？"

    # 生成并执行（需要可连接的数据库）
    python scripts/nl2sql_demo.py "..." --execute

配置从仓库根目录 .env 读取：
    GAOKAO_LLM_BASE_URL   默认 https://api.deepseek.com
    GAOKAO_LLM_API_KEY    DeepSeek API Key（必填）
    GAOKAO_LLM_MODEL      默认 deepseek-v4-flash
    GAOKAO_DATABASE_URL   --execute 时使用
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from gaokao_nl2sql import (
    Nl2SqlError,
    OpenAICompatibleModel,
    PostgresExecutor,
    SqlGenerator,
    validate_select_sql,
)

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-flash"


def load_dotenv(path: Path) -> None:
    """把仓库根 .env 加载进 os.environ（.env 的值优先于已有空环境变量）。"""

    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        # .env 中的非空值优先；只有当 .env 也为空时才保留已有环境变量。
        if value or key not in os.environ:
            os.environ[key] = value


def main() -> int:
    parser = argparse.ArgumentParser(description="NL2SQL 烟雾测试")
    parser.add_argument("question", help="自然语言问题")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="生成后在数据库上执行（需要 GAOKAO_DATABASE_URL）。",
    )
    args = parser.parse_args()

    # 从仓库根 .env 读取配置（scripts -> 仓库根）。
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")

    api_key = os.environ.get("GAOKAO_LLM_API_KEY", "")
    if not api_key:
        print("错误：未设置 GAOKAO_LLM_API_KEY。", file=sys.stderr)
        return 2

    model = OpenAICompatibleModel(
        base_url=os.environ.get("GAOKAO_LLM_BASE_URL", DEFAULT_BASE_URL),
        api_key=api_key,
        model=os.environ.get("GAOKAO_LLM_MODEL", DEFAULT_MODEL),
    )
    generator = SqlGenerator(model=model)

    try:
        raw_sql = generator.generate(args.question)
        safe_sql = validate_select_sql(raw_sql)
    except Nl2SqlError as exc:
        print(f"生成/校验失败：{exc}", file=sys.stderr)
        return 1

    print("== 生成的安全 SQL ==")
    print(safe_sql)

    if not args.execute:
        return 0

    dsn = os.environ.get("GAOKAO_DATABASE_URL")
    if not dsn:
        print("错误：--execute 需要 GAOKAO_DATABASE_URL。", file=sys.stderr)
        return 2

    try:
        rows = PostgresExecutor(dsn=dsn).run(safe_sql)
    except Nl2SqlError as exc:
        print(f"执行失败：{exc}", file=sys.stderr)
        return 1

    print(f"\n== 结果（{len(rows)} 行，最多展示前 20 行）==")
    for row in rows[:20]:
        print(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
