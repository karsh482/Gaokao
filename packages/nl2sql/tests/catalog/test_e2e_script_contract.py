"""E2E 脚本契约测试：不连接真实数据库，仅验证脚本可导入和用例结构。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def test_query_catalog_e2e_script_cases_are_loadable() -> None:
    script = Path(__file__).resolve().parents[4] / "scripts" / "query_catalog_e2e.py"
    spec = importlib.util.spec_from_file_location("query_catalog_e2e", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["query_catalog_e2e"] = module
    spec.loader.exec_module(module)

    case = module.Case(
        name="rank_filter",
        question="物理类 位次 10000 能上哪些学校",
        expected_template="admission_search_lookup",
        expected_available=True,
    )
    assert case.expected_template == "admission_search_lookup"
