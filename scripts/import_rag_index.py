#!/usr/bin/env python3
"""导入 rag_index.jsonl 到 rag_document / rag_chunk。"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from gaokao_rag import PgVectorRagChunkRepository, chunk_from_rag_index_record


_CONTEXT_FIELDS = (
    "context_expandable",
    "previous_chunk_id",
    "next_chunk_id",
    "section_id",
    "local_section_id",
)


def _load_chunk_context(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}

    context: dict[str, dict[str, Any]] = {}
    source = path.expanduser()
    with source.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{source}:{line_number} 不是有效 JSONL。") from exc

            global_chunk_id = str(record.get("global_chunk_id") or "")
            local_chunk_id = str(record.get("local_chunk_id") or record.get("chunk_id") or "")
            values = {
                field: record.get(field)
                for field in _CONTEXT_FIELDS
                if record.get(field) is not None
            }
            if global_chunk_id:
                context[global_chunk_id] = values
            if local_chunk_id:
                context[local_chunk_id] = values
    return context


def _merge_context(record: dict[str, Any], context: dict[str, dict[str, Any]]) -> dict[str, Any]:
    global_chunk_id = str(record.get("global_chunk_id") or record.get("id") or "")
    local_chunk_id = str(record.get("local_chunk_id") or record.get("chunk_id") or "")
    extra = context.get(global_chunk_id) or context.get(local_chunk_id)
    if not extra:
        return record

    merged = dict(record)
    for field, value in extra.items():
        if field not in merged:
            merged[field] = value
    return merged


def import_rag_index(
    repository: PgVectorRagChunkRepository,
    rag_index_path: Path,
    *,
    chunks_path: Path | None = None,
) -> int:
    """导入 rag_index，可选从 chunks.jsonl 补 section/邻接上下文。"""

    context = _load_chunk_context(chunks_path)
    source = rag_index_path.expanduser()
    count = 0
    with source.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = _merge_context(json.loads(stripped), context)
                repository.upsert_chunk(chunk_from_rag_index_record(record))
            except Exception as exc:  # noqa: BLE001 - CLI 输出需要包含文件行号
                raise RuntimeError(f"{source}:{line_number} 导入失败: {exc}") from exc
            count += 1
    return count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rag_index", type=Path, help="rag_index.jsonl 路径")
    parser.add_argument(
        "--chunks-jsonl",
        type=Path,
        default=None,
        help="可选 chunks.jsonl 路径，用于补充 section/previous/next 上下文字段",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("GAOKAO_DATABASE_URL"),
        help="PostgreSQL 连接串；默认读取 GAOKAO_DATABASE_URL",
    )
    parser.add_argument(
        "--statement-timeout-ms",
        type=int,
        default=30_000,
        help="单条 SQL 超时时间，默认 30000ms",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.database_url:
        raise SystemExit("缺少数据库连接串：请传 --database-url 或设置 GAOKAO_DATABASE_URL。")

    repository = PgVectorRagChunkRepository(
        dsn=args.database_url,
        statement_timeout_ms=args.statement_timeout_ms,
    )
    count = import_rag_index(
        repository,
        args.rag_index,
        chunks_path=args.chunks_jsonl,
    )
    print(
        json.dumps(
            {
                "rag_index": str(args.rag_index),
                "chunks_jsonl": str(args.chunks_jsonl) if args.chunks_jsonl else None,
                "imported_count": count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
