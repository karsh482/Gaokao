"""Chunk 级 RAG 检索编排。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from gaokao_rag.answering import AnswerGenerator
from gaokao_rag.embeddings import EmbeddingProvider
from gaokao_rag.errors import PolicyRagError
from gaokao_rag.models import RagCitation, RagQueryResult, RagResultItem, RagSearchHit
from gaokao_rag.repository import RagChunkRepository


_EMPTY_NOTE = "暂无可检索 RAG chunk。"
_NO_ANSWER_NOTE = "当前返回 RAG chunk 检索候选与引用，未生成最终政策解释。"


def _keywords(question: str) -> tuple[str, ...]:
    words = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_]{2,}", question)
    return tuple(dict.fromkeys(words))


def _snippet(content: str, question: str, max_chars: int = 320) -> str:
    content = content.strip()
    if len(content) <= max_chars:
        return content
    start = 0
    for keyword in _keywords(question):
        index = content.find(keyword)
        if index >= 0:
            start = max(0, index - 60)
            break
    end = min(len(content), start + max_chars)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(content) else ""
    return f"{prefix}{content[start:end].strip()}{suffix}"


@dataclass(slots=True)
class RagPipeline:
    """RAG chunk 检索流水线。"""

    embedding_provider: EmbeddingProvider
    repository: RagChunkRepository
    answer_generator: AnswerGenerator | None = None
    default_top_k: int = 5
    max_top_k: int = 20

    def query(
        self,
        question: str,
        *,
        school: str | None = None,
        year: int | None = None,
        category: str | None = None,
        province: str | None = None,
        plan_year: int | None = None,
        document_type: str | None = None,
        top_k: int | None = None,
    ) -> RagQueryResult:
        """执行向量检索并返回候选 chunk 与引用。

        `plan_year` / `document_type` 是旧政策接口参数，分别映射到
        `year` / `category`，用于平滑替换旧 document-level RAG。
        """

        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("RAG 检索问题不能为空。")

        resolved_top_k = self._resolve_top_k(top_k)
        resolved_year = year if year is not None else plan_year
        resolved_category = category or document_type
        embedding = self.embedding_provider.embed(normalized_question)
        hits = self.repository.search(
            embedding,
            top_k=resolved_top_k,
            school=school,
            year=resolved_year,
            category=resolved_category,
            province=province,
        )

        items = tuple(
            RagResultItem(
                id=hit.id,
                document_uid=hit.document_uid,
                global_chunk_id=hit.global_chunk_id,
                local_chunk_id=hit.local_chunk_id,
                title=hit.title,
                category=hit.category,
                content_type=hit.content_type,
                chunk_role=hit.chunk_role,
                source_url=hit.source_url,
                snippet=_snippet(hit.content, normalized_question),
                similarity=hit.similarity,
                source=hit.source,
                school_name=hit.school_name,
                province=hit.province,
                document_year=hit.document_year,
                page_number=hit.page_number,
                page_side=hit.page_side,
                heading_path=hit.heading_path,
                table_title=hit.table_title,
                context_text=hit.context_text,
                context_chunk_ids=hit.context_chunk_ids,
            )
            for hit in hits
        )
        answer, answer_note = self._answer(normalized_question, tuple(hits))
        citations = self._citations(hits)
        notes = self._notes(
            items,
            school=school,
            year=resolved_year,
            category=resolved_category,
            province=province,
            answer_note=answer_note,
        )
        return RagQueryResult(
            question=normalized_question,
            answer=answer,
            results=items,
            citations=citations,
            notes=notes,
        )

    def _resolve_top_k(self, top_k: int | None) -> int:
        value = self.default_top_k if top_k is None else top_k
        if value <= 0:
            raise ValueError("top_k 必须大于 0。")
        return min(value, self.max_top_k)

    def _answer(
        self,
        question: str,
        hits: tuple[RagSearchHit, ...],
    ) -> tuple[str | None, str]:
        if self.answer_generator is None:
            return None, _NO_ANSWER_NOTE
        if not hits:
            return None, _EMPTY_NOTE
        try:
            answer = self.answer_generator.generate(question, hits)
        except PolicyRagError as exc:
            return None, f"RAG 答案生成失败，已返回检索候选：{exc}"
        if not answer.strip():
            return None, "RAG 答案生成结果为空，已返回检索候选。"
        return answer.strip(), "已基于 RAG chunk 生成答案。"

    @staticmethod
    def _citations(hits: list[RagSearchHit]) -> tuple[RagCitation, ...]:
        citations: list[RagCitation] = []
        seen: set[tuple[str | None, int | None, str | None]] = set()
        for hit in hits:
            key = (hit.global_chunk_id, hit.page_number, hit.page_side)
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                RagCitation(
                    title=hit.title,
                    category=hit.category,
                    source_url=hit.source_url,
                    source=hit.source,
                    school_name=hit.school_name,
                    province=hit.province,
                    document_year=hit.document_year,
                    page_number=hit.page_number,
                    page_side=hit.page_side,
                    heading_path=hit.heading_path,
                    table_title=hit.table_title,
                    global_chunk_id=hit.global_chunk_id,
                    local_chunk_id=hit.local_chunk_id,
                )
            )
        return tuple(citations)

    @staticmethod
    def _notes(
        items: tuple[RagResultItem, ...],
        *,
        school: str | None,
        year: int | None,
        category: str | None,
        province: str | None,
        answer_note: str,
    ) -> tuple[str, ...]:
        notes: list[str] = []
        scope_parts = []
        if school:
            scope_parts.append(f"学校={school}")
        if province:
            scope_parts.append(f"省份={province}")
        if year:
            scope_parts.append(f"年份={year}")
        if category:
            scope_parts.append(f"类别={category}")
        if scope_parts:
            notes.append("RAG 检索范围：" + "，".join(scope_parts) + "。")
        if not items:
            notes.append(_EMPTY_NOTE)
        else:
            notes.append(answer_note)
        return tuple(notes)


# 兼容旧导入名。旧 PolicyRagPipeline 现在指向 chunk 级 RAG 流水线。
PolicyRagPipeline = RagPipeline
