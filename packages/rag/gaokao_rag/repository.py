"""rag_document / rag_chunk 仓储与 pgvector 检索。"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from gaokao_rag.errors import PolicyRepositoryError
from gaokao_rag.models import RagChunkInput, RagSearchHit


class RagChunkRepository(Protocol):
    """Chunk 级 RAG 仓储接口。"""

    def upsert_chunk(self, chunk: RagChunkInput) -> int:
        """写入 chunk 并返回 chunk ID。"""
        ...

    def search(
        self,
        query_embedding: list[float],
        *,
        top_k: int,
        school: str | None = None,
        year: int | None = None,
        category: str | None = None,
        province: str | None = None,
    ) -> list[RagSearchHit]:
        """按向量相似度检索 RAG chunk。"""
        ...


def vector_literal(vector: list[float]) -> str:
    """转换为 pgvector 字面量，并校验为有限数值。"""

    if not vector:
        raise PolicyRepositoryError("向量不能为空。")
    values: list[str] = []
    for value in vector:
        number = float(value)
        if not math.isfinite(number):
            raise PolicyRepositoryError("向量包含非有限数值。")
        values.append(f"{number:.12g}")
    return "[" + ",".join(values) + "]"


@dataclass(slots=True)
class PgVectorRagChunkRepository:
    """基于 PostgreSQL + pgvector 的 chunk 级 RAG 仓储。"""

    dsn: str
    statement_timeout_ms: int = 10_000
    _connect: Any = field(default=None, repr=False)

    def upsert_chunk(self, chunk: RagChunkInput) -> int:
        self._validate_chunk(chunk)
        try:
            row = self._fetch_one(
                _UPSERT_CHUNK_SQL,
                _chunk_params(chunk),
            )
        except Exception as exc:  # noqa: BLE001 - 统一包装仓储异常
            raise PolicyRepositoryError(f"RAG chunk 写入失败: {exc}") from exc
        return int(row["id"])

    def import_rag_index_jsonl(self, path: Path) -> int:
        """从 rag_index.jsonl 导入全部 chunk，返回导入条数。"""

        count = 0
        source = path.expanduser().resolve()
        with source.open(encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    record = json.loads(stripped)
                    self.upsert_chunk(chunk_from_rag_index_record(record))
                except Exception as exc:  # noqa: BLE001 - 标注行号后统一抛出
                    raise PolicyRepositoryError(
                        f"{source}:{line_number} 导入失败: {exc}"
                    ) from exc
                count += 1
        return count

    def search(
        self,
        query_embedding: list[float],
        *,
        top_k: int,
        school: str | None = None,
        year: int | None = None,
        category: str | None = None,
        province: str | None = None,
    ) -> list[RagSearchHit]:
        if top_k <= 0:
            raise PolicyRepositoryError("top_k 必须大于 0。")
        embedding_literal = vector_literal(query_embedding)
        params = {
            "embedding": embedding_literal,
            "top_k": top_k,
            "school": school,
            "year": year,
            "category": category,
            "province": province,
        }
        try:
            rows = self._fetch_all(_SEARCH_SQL, params)
        except Exception as exc:  # noqa: BLE001 - 统一包装仓储异常
            raise PolicyRepositoryError(f"RAG chunk 检索失败: {exc}") from exc
        return [_row_to_hit(row) for row in rows]

    def _validate_chunk(self, chunk: RagChunkInput) -> None:
        if chunk.embedding_dim != len(chunk.embedding):
            raise PolicyRepositoryError(
                "向量维度不匹配: "
                f"embedding_dim={chunk.embedding_dim}, actual={len(chunk.embedding)}"
            )
        if chunk.embedding_dim != 2560:
            raise PolicyRepositoryError("当前 rag_chunk.embedding 仅支持 2560 维。")
        if not chunk.content.strip():
            raise PolicyRepositoryError("chunk 内容不能为空。")

    def _fetch_one(self, sql: str, params: dict[str, Any]) -> dict[str, Any]:
        rows = self._execute(sql, params, fetch_many=False)
        if not rows:
            raise PolicyRepositoryError("数据库未返回 RAG chunk ID。")
        return rows[0]

    def _fetch_all(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        return self._execute(sql, params, fetch_many=True)

    def _execute(
        self,
        sql: str,
        params: dict[str, Any],
        *,
        fetch_many: bool,
    ) -> list[dict[str, Any]]:
        connect = self._connect or self._default_connect()
        with connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(f"SET statement_timeout = {int(self.statement_timeout_ms)}")
                cur.execute(sql, params)
                columns = [desc[0] for desc in cur.description or []]
                rows = cur.fetchall() if fetch_many else cur.fetchmany(1)
        return [dict(zip(columns, row)) for row in rows]

    @staticmethod
    def _default_connect() -> Any:
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - 取决于环境
            raise PolicyRepositoryError(
                "需要安装可选依赖 psycopg（pip install 'gaokao-rag[db]'）。"
            ) from exc
        return psycopg.connect


def chunk_from_rag_index_record(record: dict[str, Any]) -> RagChunkInput:
    """将私有清洗产物 rag_index.jsonl 记录转换为公开库入库模型。"""

    metadata = record.get("metadata") or {}
    retrieval_metadata = record.get("retrieval_metadata") or {}
    citation = record.get("citation") or {}
    document_uid = str(record.get("document_id") or "")
    if not document_uid:
        raise PolicyRepositoryError("rag_index 记录缺少 document_id。")
    global_chunk_id = str(record.get("global_chunk_id") or record.get("id") or "")
    if not global_chunk_id:
        raise PolicyRepositoryError("rag_index 记录缺少 global_chunk_id。")

    return RagChunkInput(
        document_uid=document_uid,
        global_chunk_id=global_chunk_id,
        local_chunk_id=str(record.get("local_chunk_id") or record.get("chunk_id") or ""),
        chunk_index=int(record.get("chunk_index") or 0),
        content_type=str(record.get("content_type") or ""),
        chunk_role=str(record.get("chunk_role") or ""),
        content=str(record.get("chunk_text") or record.get("text") or ""),
        embedding=[float(value) for value in (record.get("embedding") or [])],
        embedding_provider=str(record.get("embedding_provider") or ""),
        embedding_model=str(record.get("embedding_model") or ""),
        embedding_text_version=str(record.get("embedding_text_version") or ""),
        embedding_dim=int(record.get("embedding_dim") or 0),
        title=str(
            retrieval_metadata.get("title")
            or citation.get("title")
            or metadata.get("title")
            or document_uid
        ),
        category=str(
            retrieval_metadata.get("category")
            or citation.get("category")
            or metadata.get("category")
            or "unknown"
        ),
        source=_optional_str(retrieval_metadata.get("source") or metadata.get("source")),
        school_name=_optional_str(
            retrieval_metadata.get("school")
            or citation.get("school")
            or metadata.get("school")
        ),
        province=_optional_str(retrieval_metadata.get("province") or metadata.get("province")),
        document_year=_optional_int(
            retrieval_metadata.get("year")
            or citation.get("year")
            or metadata.get("year")
        ),
        source_url=_optional_str(citation.get("url") or metadata.get("url")),
        page_number=_optional_int(retrieval_metadata.get("page_number") or metadata.get("page_number")),
        page_side=_optional_str(retrieval_metadata.get("page_side") or metadata.get("page_side")),
        heading_path=tuple(str(item) for item in (retrieval_metadata.get("heading_path") or [])),
        table_title=_optional_str(retrieval_metadata.get("table_title") or metadata.get("table_title")),
        context_expandable=bool(record.get("context_expandable", True)),
        previous_chunk_id=_optional_str(record.get("previous_chunk_id")),
        next_chunk_id=_optional_str(record.get("next_chunk_id")),
        section_id=_optional_str(record.get("section_id")),
        local_section_id=_optional_str(record.get("local_section_id")),
        retrieval_metadata=dict(retrieval_metadata),
        citation=dict(citation),
        chunk_metadata=dict(metadata),
        document_metadata={
            "title": metadata.get("title"),
            "source": metadata.get("source"),
            "school": metadata.get("school"),
            "year": metadata.get("year"),
            "category": metadata.get("category"),
            "province": metadata.get("province"),
            "url": metadata.get("url"),
        },
    )


def _chunk_params(chunk: RagChunkInput) -> dict[str, Any]:
    return {
        "document_uid": chunk.document_uid,
        "title": chunk.title,
        "category": chunk.category,
        "source": chunk.source,
        "school_name": chunk.school_name,
        "province": chunk.province,
        "document_year": chunk.document_year,
        "source_url": chunk.source_url,
        "document_metadata": json.dumps(chunk.document_metadata or {}, ensure_ascii=False),
        "global_chunk_id": chunk.global_chunk_id,
        "local_chunk_id": chunk.local_chunk_id,
        "chunk_index": chunk.chunk_index,
        "content_type": chunk.content_type,
        "chunk_role": chunk.chunk_role,
        "content": chunk.content,
        "page_number": chunk.page_number,
        "page_side": chunk.page_side,
        "heading_path": json.dumps(list(chunk.heading_path), ensure_ascii=False),
        "table_title": chunk.table_title,
        "context_expandable": chunk.context_expandable,
        "previous_chunk_id": chunk.previous_chunk_id,
        "next_chunk_id": chunk.next_chunk_id,
        "section_id": chunk.section_id,
        "local_section_id": chunk.local_section_id,
        "retrieval_metadata": json.dumps(chunk.retrieval_metadata or {}, ensure_ascii=False),
        "citation": json.dumps(chunk.citation or {}, ensure_ascii=False),
        "chunk_metadata": json.dumps(chunk.chunk_metadata or {}, ensure_ascii=False),
        "embedding_provider": chunk.embedding_provider,
        "embedding_model": chunk.embedding_model,
        "embedding_text_version": chunk.embedding_text_version,
        "embedding_dim": chunk.embedding_dim,
        "embedding": vector_literal(chunk.embedding),
    }


def _row_to_hit(row: dict[str, Any]) -> RagSearchHit:
    heading_path = _json_value(row.get("heading_path"), [])
    citation = _json_value(row.get("citation"), {})
    context_rows = _json_value(row.get("context_rows"), [])
    context_chunk_ids = tuple(
        str(item.get("local_chunk_id") or "")
        for item in context_rows
        if item.get("local_chunk_id")
    )
    context_citations = tuple(
        dict(item.get("citation") or {})
        for item in context_rows
        if item.get("citation")
    )
    return RagSearchHit(
        id=int(row["id"]),
        document_uid=str(row["document_uid"]),
        global_chunk_id=str(row["global_chunk_id"]),
        local_chunk_id=str(row["local_chunk_id"]),
        chunk_index=int(row["chunk_index"]),
        content_type=str(row["content_type"]),
        chunk_role=str(row["chunk_role"]),
        content=str(row["content"]),
        similarity=float(row["similarity"]),
        title=str(row["title"]),
        category=str(row["category"]),
        source_url=row.get("source_url"),
        source=row.get("source"),
        school_name=row.get("school_name"),
        province=row.get("province"),
        document_year=row.get("document_year"),
        page_number=row.get("page_number"),
        page_side=row.get("page_side"),
        heading_path=tuple(str(item) for item in heading_path),
        table_title=row.get("table_title"),
        citation=dict(citation),
        context_text=_format_context_text(context_rows),
        context_chunk_ids=context_chunk_ids,
        context_citations=context_citations,
    )


def _json_value(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value


def _format_context_text(context_rows: list[dict[str, Any]]) -> str | None:
    if not context_rows:
        return None
    parts: list[str] = []
    for item in context_rows:
        heading_path = item.get("heading_path") or []
        heading = " / ".join(str(value) for value in heading_path if value)
        page_number = item.get("page_number")
        page_side = item.get("page_side")
        table_title = item.get("table_title")
        meta = []
        if page_number:
            page = f"第 {page_number} 页"
            if page_side:
                page += f" - {page_side}"
            meta.append(page)
        if heading:
            meta.append(heading)
        if table_title:
            meta.append(str(table_title))
        local_chunk_id = str(item.get("local_chunk_id") or "")
        prefix = f"[{local_chunk_id}]"
        if meta:
            prefix += " " + " | ".join(meta)
        parts.append(prefix + "\n" + str(item.get("content") or "").strip())
    return "\n\n".join(parts)


def _optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


_UPSERT_CHUNK_SQL = """
WITH upsert_document AS (
    INSERT INTO rag_document (
        document_uid,
        title,
        category,
        source,
        school_name,
        province,
        document_year,
        source_url,
        metadata
    )
    VALUES (
        %(document_uid)s,
        %(title)s,
        %(category)s,
        %(source)s,
        %(school_name)s,
        %(province)s,
        %(document_year)s,
        %(source_url)s,
        %(document_metadata)s::jsonb
    )
    ON CONFLICT (document_uid) DO UPDATE SET
        title = EXCLUDED.title,
        category = EXCLUDED.category,
        source = EXCLUDED.source,
        school_name = EXCLUDED.school_name,
        province = EXCLUDED.province,
        document_year = EXCLUDED.document_year,
        source_url = EXCLUDED.source_url,
        metadata = EXCLUDED.metadata,
        updated_at = CURRENT_TIMESTAMP
    RETURNING id
)
INSERT INTO rag_chunk (
    document_id,
    global_chunk_id,
    local_chunk_id,
    chunk_index,
    content_type,
    chunk_role,
    content,
    page_number,
    page_side,
    heading_path,
    table_title,
    context_expandable,
    previous_chunk_id,
    next_chunk_id,
    section_id,
    local_section_id,
    retrieval_metadata,
    citation,
    chunk_metadata,
    embedding_provider,
    embedding_model,
    embedding_text_version,
    embedding_dim,
    embedding
)
VALUES (
    (SELECT id FROM upsert_document),
    %(global_chunk_id)s,
    %(local_chunk_id)s,
    %(chunk_index)s,
    %(content_type)s,
    %(chunk_role)s,
    %(content)s,
    %(page_number)s,
    %(page_side)s,
    %(heading_path)s::jsonb,
    %(table_title)s,
    %(context_expandable)s,
    %(previous_chunk_id)s,
    %(next_chunk_id)s,
    %(section_id)s,
    %(local_section_id)s,
    %(retrieval_metadata)s::jsonb,
    %(citation)s::jsonb,
    %(chunk_metadata)s::jsonb,
    %(embedding_provider)s,
    %(embedding_model)s,
    %(embedding_text_version)s,
    %(embedding_dim)s,
    %(embedding)s::halfvec
)
ON CONFLICT (global_chunk_id) DO UPDATE SET
    local_chunk_id = EXCLUDED.local_chunk_id,
    chunk_index = EXCLUDED.chunk_index,
    content_type = EXCLUDED.content_type,
    chunk_role = EXCLUDED.chunk_role,
    content = EXCLUDED.content,
    page_number = EXCLUDED.page_number,
    page_side = EXCLUDED.page_side,
    heading_path = EXCLUDED.heading_path,
    table_title = EXCLUDED.table_title,
    context_expandable = EXCLUDED.context_expandable,
    previous_chunk_id = EXCLUDED.previous_chunk_id,
    next_chunk_id = EXCLUDED.next_chunk_id,
    section_id = EXCLUDED.section_id,
    local_section_id = EXCLUDED.local_section_id,
    retrieval_metadata = EXCLUDED.retrieval_metadata,
    citation = EXCLUDED.citation,
    chunk_metadata = EXCLUDED.chunk_metadata,
    embedding_provider = EXCLUDED.embedding_provider,
    embedding_model = EXCLUDED.embedding_model,
    embedding_text_version = EXCLUDED.embedding_text_version,
    embedding_dim = EXCLUDED.embedding_dim,
    embedding = EXCLUDED.embedding,
    updated_at = CURRENT_TIMESTAMP
RETURNING id
"""


_SEARCH_SQL = """
WITH hits AS (
    SELECT
        c.id,
        c.document_id,
        d.document_uid,
        c.global_chunk_id,
        c.local_chunk_id,
        c.chunk_index,
        c.content_type,
        c.chunk_role,
        c.content,
        c.page_number,
        c.page_side,
        c.heading_path,
        c.table_title,
        c.context_expandable,
        c.section_id,
        c.citation,
        d.title,
        d.category,
        d.source,
        d.school_name,
        d.province,
        d.document_year,
        d.source_url,
        c.embedding <=> %(embedding)s::halfvec AS distance,
        1 - (c.embedding <=> %(embedding)s::halfvec) AS similarity
    FROM rag_chunk c
    JOIN rag_document d ON d.id = c.document_id
    WHERE (%(school)s::text IS NULL OR d.school_name = %(school)s::text)
      AND (%(year)s::int IS NULL OR d.document_year = %(year)s::int)
      AND (%(category)s::text IS NULL OR d.category = %(category)s::text)
      AND (%(province)s::text IS NULL OR d.province = %(province)s::text)
    ORDER BY c.embedding <=> %(embedding)s::halfvec
    LIMIT %(top_k)s
)
SELECT
    h.id,
    h.document_uid,
    h.global_chunk_id,
    h.local_chunk_id,
    h.chunk_index,
    h.content_type,
    h.chunk_role,
    h.content,
    h.page_number,
    h.page_side,
    h.heading_path,
    h.table_title,
    h.citation,
    h.title,
    h.category,
    h.source,
    h.school_name,
    h.province,
    h.document_year,
    h.source_url,
    h.similarity,
    context.context_rows
FROM hits h
LEFT JOIN LATERAL (
    SELECT jsonb_agg(
        jsonb_build_object(
            'global_chunk_id', ctx.global_chunk_id,
            'local_chunk_id', ctx.local_chunk_id,
            'chunk_index', ctx.chunk_index,
            'content', ctx.content,
            'page_number', ctx.page_number,
            'page_side', ctx.page_side,
            'heading_path', ctx.heading_path,
            'table_title', ctx.table_title,
            'citation', ctx.citation
        )
        ORDER BY ctx.chunk_index
    ) AS context_rows
    FROM (
        SELECT ctx.*
        FROM rag_chunk ctx
        WHERE ctx.document_id = h.document_id
          AND ctx.context_expandable = TRUE
          AND (
              (h.section_id IS NOT NULL AND ctx.section_id = h.section_id)
              OR (
                  h.section_id IS NULL
                  AND ctx.chunk_index BETWEEN h.chunk_index - 1 AND h.chunk_index + 1
              )
          )
        ORDER BY
            CASE WHEN ctx.id = h.id THEN 0 ELSE 1 END,
            ABS(ctx.chunk_index - h.chunk_index),
            ctx.chunk_index
        LIMIT 6
    ) ctx
) context ON TRUE
ORDER BY h.distance
"""


# 兼容旧导入名。旧 policy_document 表已下线。
PolicyDocumentRepository = RagChunkRepository
PgVectorPolicyDocumentRepository = PgVectorRagChunkRepository
