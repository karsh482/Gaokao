"""RagIndexLoader 单元测试。"""

from __future__ import annotations

import json

import pytest

from gaokao_rag import DocumentLoadError, RagIndexLoader, content_hash


def _record() -> dict:
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


def test_rag_index_loader_reads_jsonl(tmp_path):
    path = tmp_path / "rag_index.jsonl"
    path.write_text(json.dumps(_record(), ensure_ascii=False) + "\n", encoding="utf-8")

    chunks = RagIndexLoader().load_file(path)

    assert len(chunks) == 1
    assert chunks[0].document_uid == "doc-1"
    assert chunks[0].content == "招生章程正文"
    assert chunks[0].school_name == "北京大学"


def test_rag_index_loader_rejects_unsupported_suffix(tmp_path):
    path = tmp_path / "rag_index.json"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(DocumentLoadError):
        RagIndexLoader().load_file(path)


def test_rag_index_loader_reports_bad_jsonl(tmp_path):
    path = tmp_path / "rag_index.jsonl"
    path.write_text("{bad json}", encoding="utf-8")

    with pytest.raises(DocumentLoadError):
        RagIndexLoader().load_file(path)


def test_content_hash_returns_sha256():
    assert content_hash("abc") == (
        "ba7816bf8f01cfea414140de5dae2223"
        "b00361a396177a9cb410ff61f20015ad"
    )
