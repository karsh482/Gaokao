"""Chunk 级 RAG 数据模型。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RagChunkInput:
    """待入库的 RAG chunk。"""

    document_uid: str
    global_chunk_id: str
    local_chunk_id: str
    chunk_index: int
    content_type: str
    chunk_role: str
    content: str
    embedding: list[float]
    embedding_provider: str
    embedding_model: str
    embedding_text_version: str
    embedding_dim: int
    title: str
    category: str
    source: str | None = None
    school_name: str | None = None
    province: str | None = None
    document_year: int | None = None
    source_url: str | None = None
    page_number: int | None = None
    page_side: str | None = None
    heading_path: tuple[str, ...] = ()
    table_title: str | None = None
    context_expandable: bool = True
    previous_chunk_id: str | None = None
    next_chunk_id: str | None = None
    section_id: str | None = None
    local_section_id: str | None = None
    retrieval_metadata: dict[str, Any] | None = None
    citation: dict[str, Any] | None = None
    chunk_metadata: dict[str, Any] | None = None
    document_metadata: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class RagSearchHit:
    """RAG 检索命中项。"""

    id: int
    document_uid: str
    global_chunk_id: str
    local_chunk_id: str
    chunk_index: int
    content_type: str
    chunk_role: str
    content: str
    similarity: float
    title: str
    category: str
    source_url: str | None = None
    source: str | None = None
    school_name: str | None = None
    province: str | None = None
    document_year: int | None = None
    page_number: int | None = None
    page_side: str | None = None
    heading_path: tuple[str, ...] = ()
    table_title: str | None = None
    citation: dict[str, Any] | None = None
    context_text: str | None = None
    context_chunk_ids: tuple[str, ...] = ()
    context_citations: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class RagResultItem:
    """API 可展示的 RAG 检索候选。"""

    id: int
    document_uid: str
    global_chunk_id: str
    local_chunk_id: str
    title: str
    category: str
    content_type: str
    chunk_role: str
    snippet: str
    similarity: float
    source_url: str | None = None
    source: str | None = None
    school_name: str | None = None
    province: str | None = None
    document_year: int | None = None
    page_number: int | None = None
    page_side: str | None = None
    heading_path: tuple[str, ...] = ()
    table_title: str | None = None
    context_text: str | None = None
    context_chunk_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RagCitation:
    """RAG 来源引用。"""

    title: str
    category: str
    source_url: str | None = None
    source: str | None = None
    school_name: str | None = None
    province: str | None = None
    document_year: int | None = None
    page_number: int | None = None
    page_side: str | None = None
    heading_path: tuple[str, ...] = ()
    table_title: str | None = None
    global_chunk_id: str | None = None
    local_chunk_id: str | None = None


@dataclass(frozen=True, slots=True)
class RagQueryResult:
    """RAG 检索结果。"""

    question: str
    answer: str | None
    results: tuple[RagResultItem, ...]
    citations: tuple[RagCitation, ...]
    notes: tuple[str, ...]

    @property
    def result_count(self) -> int:
        return len(self.results)


# 兼容旧导入名。当前项目已改为 chunk 级 RAG，这些别名只保持测试和外部导入不崩。
PolicySearchHit = RagSearchHit
PolicyResultItem = RagResultItem
PolicyCitation = RagCitation
PolicyRagResult = RagQueryResult
PolicyDocumentInput = RagChunkInput
