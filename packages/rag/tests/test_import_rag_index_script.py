"""scripts/import_rag_index.py 单元测试。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_script_module():
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "import_rag_index.py"
    spec = importlib.util.spec_from_file_location("import_rag_index_script", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeRepository:
    def __init__(self):
        self.chunks = []

    def upsert_chunk(self, chunk):
        self.chunks.append(chunk)
        return len(self.chunks)


def _rag_index_record() -> dict:
    return {
        "document_id": "doc-1",
        "global_chunk_id": "doc-1:chunk-1",
        "chunk_id": "chunk-1",
        "chunk_index": 1,
        "content_type": "text",
        "chunk_role": "body",
        "chunk_text": "招生章程正文",
        "embedding": [0.1, 0.2],
        "embedding_provider": "sentence-transformers",
        "embedding_model": "Qwen/Qwen3-Embedding-4B",
        "embedding_text_version": "v1",
        "embedding_dim": 2,
        "metadata": {
            "title": "北京大学2026年本科招生章程",
            "category": "university_admission_chapter",
            "school": "北京大学",
            "year": 2026,
        },
        "retrieval_metadata": {
            "title": "北京大学2026年本科招生章程",
            "category": "university_admission_chapter",
            "school": "北京大学",
            "year": 2026,
        },
    }


def test_import_rag_index_merges_chunks_context(tmp_path):
    module = _load_script_module()
    rag_index = tmp_path / "rag_index.jsonl"
    chunks = tmp_path / "chunks.jsonl"
    rag_index.write_text(
        json.dumps(_rag_index_record(), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    chunks.write_text(
        json.dumps(
            {
                "global_chunk_id": "doc-1:chunk-1",
                "chunk_id": "chunk-1",
                "context_expandable": True,
                "previous_chunk_id": "chunk-0",
                "next_chunk_id": "chunk-2",
                "section_id": "doc-1:section-1",
                "local_section_id": "section-1",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    repository = FakeRepository()

    count = module.import_rag_index(repository, rag_index, chunks_path=chunks)

    assert count == 1
    assert repository.chunks[0].section_id == "doc-1:section-1"
    assert repository.chunks[0].previous_chunk_id == "chunk-0"
    assert repository.chunks[0].next_chunk_id == "chunk-2"
