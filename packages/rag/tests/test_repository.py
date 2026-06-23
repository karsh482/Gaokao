"""RagChunkRepository 单元测试。"""

from __future__ import annotations

import pytest

from gaokao_rag import PolicyRepositoryError, chunk_from_rag_index_record, vector_literal


def test_vector_literal_formats_pgvector_value():
    assert vector_literal([0.1, 2, -3.5]) == "[0.1,2,-3.5]"


def test_vector_literal_rejects_empty_vector():
    with pytest.raises(PolicyRepositoryError):
        vector_literal([])


def test_vector_literal_rejects_non_finite_value():
    with pytest.raises(PolicyRepositoryError):
        vector_literal([float("nan")])


def test_chunk_from_rag_index_record_maps_private_index_record():
    record = {
        "document_id": "2026-北京大学-章程-university_admission_chapter-abc",
        "global_chunk_id": "2026-北京大学-章程-university_admission_chapter-abc:document-p0085-right-01254",
        "chunk_id": "document-p0085-right-01254",
        "local_chunk_id": "document-p0085-right-01254",
        "chunk_index": 1254,
        "content_type": "table",
        "chunk_role": "table",
        "chunk_text": "| 二级学科 | 研究方向 |",
        "embedding": [0.1, 0.2],
        "embedding_provider": "sentence-transformers",
        "embedding_model": "Qwen/Qwen3-Embedding-4B",
        "embedding_text_version": "v1",
        "embedding_dim": 2,
        "context_expandable": True,
        "previous_chunk_id": "document-p0085-right-01253",
        "next_chunk_id": "document-p0086-left-01256",
        "section_id": "doc:basic:secondary",
        "local_section_id": "basic:secondary",
        "metadata": {
            "title": "北京大学2026年本科招生章程",
            "source": "北京大学",
            "year": 2026,
            "category": "university_admission_chapter",
            "province": "全国",
            "school": "北京大学",
            "url": "https://example.test/pku.pdf",
            "page_number": 85,
            "page_side": "右页",
            "heading_path": ["基础医学院", "二级学科"],
            "table_title": "二级学科 / 研究方向",
        },
        "retrieval_metadata": {
            "school": "北京大学",
            "year": 2026,
            "category": "university_admission_chapter",
            "province": "全国",
            "source": "北京大学",
            "title": "北京大学2026年本科招生章程",
            "page_number": 85,
            "page_side": "右页",
            "heading_path": ["基础医学院", "二级学科"],
            "table_title": "二级学科 / 研究方向",
        },
        "citation": {
            "title": "北京大学2026年本科招生章程",
            "source": "北京大学",
            "school": "北京大学",
            "year": 2026,
            "category": "university_admission_chapter",
            "url": "https://example.test/pku.pdf",
        },
    }

    chunk = chunk_from_rag_index_record(record)

    assert chunk.document_uid == "2026-北京大学-章程-university_admission_chapter-abc"
    assert chunk.local_chunk_id == "document-p0085-right-01254"
    assert chunk.content == "| 二级学科 | 研究方向 |"
    assert chunk.school_name == "北京大学"
    assert chunk.document_year == 2026
    assert chunk.heading_path == ("基础医学院", "二级学科")
    assert chunk.table_title == "二级学科 / 研究方向"
    assert chunk.section_id == "doc:basic:secondary"
