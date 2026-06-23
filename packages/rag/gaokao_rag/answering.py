"""RAG 答案生成器。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from gaokao_rag.errors import PolicyRagError
from gaokao_rag.models import RagSearchHit


class AnswerGenerator(Protocol):
    """基于检索命中生成可读答案的最小接口。"""

    def generate(self, question: str, hits: tuple[RagSearchHit, ...]) -> str:
        """根据用户问题与命中 chunk 生成答案。"""
        ...


@dataclass(frozen=True, slots=True)
class OpenAICompatibleAnswerGenerator:
    """OpenAI 兼容聊天补全答案生成器。"""

    base_url: str
    api_key: str
    model: str
    temperature: float = 0.0
    timeout: float = 60.0
    max_context_chars: int = 12_000
    max_hits: int = 3

    def generate(self, question: str, hits: tuple[RagSearchHit, ...]) -> str:
        if not self.api_key.strip():
            raise PolicyRagError("缺少 LLM API Key，无法生成 RAG 答案。")
        if not hits:
            return "未检索到可用于回答该问题的政策或招生章程片段。"

        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": self._user_prompt(question, hits)},
            ],
        }
        try:
            response = httpx.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            return str(data["choices"][0]["message"]["content"]).strip()
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise PolicyRagError(f"RAG 答案生成失败: {exc}") from exc

    def _user_prompt(self, question: str, hits: tuple[RagSearchHit, ...]) -> str:
        context = _format_hits(
            hits,
            max_chars=self.max_context_chars,
            max_hits=self.max_hits,
        )
        return (
            f"用户问题：{question}\n\n"
            "检索上下文：\n"
            f"{context}\n\n"
            "请基于检索上下文回答用户问题。"
        )


def _format_hits(
    hits: tuple[RagSearchHit, ...],
    *,
    max_chars: int,
    max_hits: int,
) -> str:
    parts: list[str] = []
    used = 0
    seen_context_keys: set[tuple[str, ...]] = set()
    for index, hit in enumerate(hits, start=1):
        if len(parts) >= max_hits:
            break
        context_key = hit.context_chunk_ids or (hit.local_chunk_id,)
        if context_key in seen_context_keys:
            continue
        seen_context_keys.add(context_key)
        source = _source_label(hit)
        content = (hit.context_text or hit.content).strip()
        block = f"[{index}] {source}\n{content}"
        if used + len(block) > max_chars:
            remaining = max_chars - used
            if remaining <= 200:
                break
            block = block[:remaining].rstrip() + "\n...[上下文已截断]"
        parts.append(block)
        used += len(block)
    return "\n\n".join(parts)


def _source_label(hit: RagSearchHit) -> str:
    parts = [
        hit.title,
        hit.school_name,
        str(hit.document_year) if hit.document_year else None,
    ]
    if hit.page_number:
        page = f"第 {hit.page_number} 页"
        if hit.page_side:
            page += f" {hit.page_side}"
        parts.append(page)
    if hit.heading_path:
        parts.append(" / ".join(hit.heading_path))
    if hit.table_title:
        parts.append(hit.table_title)
    parts.append(f"chunk={hit.local_chunk_id}")
    return " | ".join(str(part) for part in parts if part)


_SYSTEM_PROMPT = """你是高考志愿政策与高校招生章程问答助手。
只能基于给定检索上下文回答，不要编造上下文没有的信息。
如果上下文不足，请明确说明“根据当前检索片段无法确认”。
回答要求：
1. 先直接回答结论；
2. 对表格类内容优先整理为条目；
3. 关键事实后标注引用编号，例如 [1]；
4. 不输出与问题无关的长篇背景。"""
