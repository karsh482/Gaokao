#!/usr/bin/env python3
"""Query Catalog 真实环境 E2E 验证脚本。

优先验证：
1. 真实数据库可达；
2. Query Catalog 模板查询可执行；
3. 范围外请求可短路；
4. 若配置了 LLM，再验证回退路径。

用法：
    python scripts/query_catalog_e2e.py

环境变量：
    GAOKAO_DATABASE_URL   真实 PostgreSQL 连接串（必填）
    GAOKAO_LLM_BASE_URL   可选，配置后可验证回退路径
    GAOKAO_LLM_API_KEY    可选，配置后可验证回退路径
    GAOKAO_LLM_MODEL      可选
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gaokao_nl2sql import (
    CatalogPipeline,
    IntentExtractor,
    Nl2SqlPipeline,
    Nl2SqlError,
    OpenAICompatibleModel,
    PostgresExecutor,
    SqlGenerator,
)


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and (value or key not in os.environ):
            os.environ[key] = value


@dataclass(frozen=True)
class Case:
    name: str
    question: str
    expected_template: str | None
    expected_available: bool
    expect_short_circuit: bool = False
    expected_coverage_fields: tuple[str, ...] = ()


def _build_pipeline() -> CatalogPipeline:
    dsn = os.environ.get("GAOKAO_DATABASE_URL")
    if not dsn:
        raise SystemExit("缺少 GAOKAO_DATABASE_URL。")
    executor = PostgresExecutor(dsn=dsn)

    api_key = os.environ.get("GAOKAO_LLM_API_KEY", "")
    if api_key:
        model = OpenAICompatibleModel(
            base_url=os.environ.get("GAOKAO_LLM_BASE_URL", "https://api.deepseek.com"),
            api_key=api_key,
            model=os.environ.get("GAOKAO_LLM_MODEL", "deepseek-v4-flash"),
        )
        generator = SqlGenerator(model=model)
        intent_extractor = IntentExtractor(model=model)
    else:
        # 没有 LLM Key 时，用一个不会被模板命中的占位生成器。
        class _FallbackModel:
            def complete(self, system_prompt: str, user_prompt: str) -> str:
                return "SELECT 1"

        generator = SqlGenerator(model=_FallbackModel())
        intent_extractor = None

    return CatalogPipeline(
        nl2sql_pipeline=Nl2SqlPipeline(generator=generator, executor=executor),
        intent_extractor=intent_extractor,
    )


def _run_case(pipeline: CatalogPipeline, case: Case) -> int:
    result = pipeline.run(case.question)
    ok = True
    if result.availability.available != case.expected_available:
        print(f"[FAIL] {case.name}: availability={result.availability.available}")
        ok = False
    if result.template_name != case.expected_template:
        print(f"[FAIL] {case.name}: template_name={result.template_name}")
        ok = False
    if case.expect_short_circuit:
        if result.sql is not None or result.row_count != 0:
            print(f"[FAIL] {case.name}: expected short circuit")
            ok = False
    coverage_fields = tuple(w.field for w in result.coverage_warnings)
    for field in case.expected_coverage_fields:
        if field not in coverage_fields:
            print(f"[FAIL] {case.name}: missing coverage warning {field}")
            ok = False
    print(
        f"[{ 'OK' if ok else 'FAIL' }] {case.name}: "
        f"rows={result.row_count}, template={result.template_name}, "
        f"available={result.availability.available}, coverage={coverage_fields}"
    )
    return 0 if ok else 1


def main() -> int:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    pipeline = _build_pipeline()
    try:
        pipeline.nl2sql_pipeline.executor.run("SELECT 1")
    except Nl2SqlError as exc:
        print(f"数据库连接不可用：{exc}", file=sys.stderr)
        print(
            "请确认已执行 docker compose up -d gaokao-postgres，"
            "且 GAOKAO_DATABASE_URL 指向可访问数据库。",
            file=sys.stderr,
        )
        return 2

    cases = [
        Case(
            name="school_detail",
            question="查询贵州大学投档线和基本信息",
            expected_template="school_detail",
            expected_available=True,
        ),
        Case(
            name="rank_filter",
            question="物理类 位次 10000 能上哪些学校",
            expected_template="admission_search_lookup",
            expected_available=True,
        ),
        Case(
            name="region_lookup",
            question="成都有哪些大学",
            expected_template="region_school_lookup",
            expected_available=True,
        ),
        Case(
            name="special_program",
            question="国家专项有哪些院校",
            expected_template="special_program_lookup",
            expected_available=True,
        ),
        Case(
            name="selection_requirement",
            question="计算机专业选科要求是什么",
            expected_template="selection_requirement_lookup",
            expected_available=True,
            expected_coverage_fields=("selection_requirements",),
        ),
        Case(
            name="multi_filter",
            question="物理类 位次 30000 公办 学费 8000 以下的计算机专业有哪些学校",
            expected_template="multi_filter_lookup",
            expected_available=True,
        ),
        Case(
            name="out_of_scope",
            question="四川省 2025 年有哪些学校",
            expected_template=None,
            expected_available=False,
            expect_short_circuit=True,
        ),
        Case(
            name="trend",
            question="近几年贵州大学投档线趋势如何",
            expected_template=None,
            expected_available=False,
            expect_short_circuit=True,
        ),
    ]

    failures = 0
    for case in cases:
        failures += _run_case(pipeline, case)

    if failures:
        return 1
    print("E2E 校验通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
