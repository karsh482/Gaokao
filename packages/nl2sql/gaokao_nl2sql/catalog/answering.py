"""SQL 查询结果答案生成。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from gaokao_nl2sql.errors import SqlGenerationError
from gaokao_nl2sql.llm import ChatModel


class SqlAnswerSynthesizer(Protocol):
    """基于已执行 SQL 结果生成答案的最小接口。"""

    def synthesize(
        self,
        *,
        question: str,
        sql: str,
        rows: list[dict[str, Any]],
        summary: str,
        notes: tuple[str, ...],
    ) -> str:
        """只能基于 rows/summary/notes 生成最终回答。"""
        ...


@dataclass(frozen=True, slots=True)
class OpenAICompatibleSqlAnswerSynthesizer:
    """OpenAI 兼容 SQL 结果答案生成器。"""

    model: ChatModel
    max_rows: int = 20
    max_chars: int = 12_000

    def synthesize(
        self,
        *,
        question: str,
        sql: str,
        rows: list[dict[str, Any]],
        summary: str,
        notes: tuple[str, ...],
    ) -> str:
        if not rows:
            return summary
        user_prompt = self._user_prompt(
            question=question,
            sql=sql,
            rows=rows,
            summary=summary,
            notes=notes,
        )
        try:
            return self.model.complete(_SYSTEM_PROMPT, user_prompt).strip()
        except SqlGenerationError:
            return summary

    def _user_prompt(
        self,
        *,
        question: str,
        sql: str,
        rows: list[dict[str, Any]],
        summary: str,
        notes: tuple[str, ...],
    ) -> str:
        rows_json = json.dumps(
            rows[: self.max_rows],
            ensure_ascii=False,
            default=str,
        )
        if len(rows_json) > self.max_chars:
            rows_json = rows_json[: self.max_chars].rstrip() + "...[rows 已截断]"
        return (
            f"用户问题：{question}\n\n"
            f"已执行 SQL：\n{sql}\n\n"
            f"程序摘要：{summary}\n\n"
            f"口径说明：{json.dumps(list(notes), ensure_ascii=False)}\n\n"
            f"查询结果 rows（最多 {self.max_rows} 条）：\n{rows_json}\n\n"
            "请基于这些 rows 回答用户。"
        )


_SYSTEM_PROMPT = """你是高考志愿结构化数据问答助手。

安全规则：
1. 只能基于给定 rows、程序摘要和口径说明回答，不得编造 rows 中没有的信息。
2. 不得修改、补写或推测 SQL。
3. 对录取评估只能表述为“基于历史单年投档/录取数据的参考”，不得承诺录取。
4. rows 为空时说明暂无匹配数据，不要编造学校或专业。
5. 回答要简洁，先给结论，再列出关键参考记录。
6. 涉及位次/分数时必须说明年份、省份、科类口径。"""
