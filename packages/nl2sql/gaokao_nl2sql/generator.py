"""SQL 生成器：自然语言 + schema 上下文 -> SQL 文本。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from gaokao_nl2sql.errors import SqlGenerationError
from gaokao_nl2sql.llm import ChatModel
from gaokao_nl2sql.schema_context import build_schema_context

_SQL_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_sql(text: str) -> str:
    """从模型回复中提取 SQL，兼容是否带代码围栏。"""

    if not text or not text.strip():
        raise SqlGenerationError("模型回复为空。")

    fenced = _SQL_FENCE.search(text)
    candidate = fenced.group(1) if fenced else text
    return candidate.strip()


@dataclass(slots=True)
class SqlGenerator:
    """把问题交给 LLM 生成 SQL。"""

    model: ChatModel
    schema_context: str = ""

    def __post_init__(self) -> None:
        if not self.schema_context:
            self.schema_context = build_schema_context()

    def generate(self, question: str) -> str:
        if not question or not question.strip():
            raise SqlGenerationError("问题为空。")

        user_prompt = (
            f"问题：{question.strip()}\n\n"
            "请只输出一条 PostgreSQL 只读 SELECT 语句。"
        )
        reply = self.model.complete(self.schema_context, user_prompt)
        return extract_sql(reply)
