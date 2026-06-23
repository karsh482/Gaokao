"""RagPipeline 单元测试。"""

from __future__ import annotations

import pytest

from gaokao_rag import PolicyRagError, RagPipeline, RagSearchHit
from gaokao_rag.answering import _format_hits


class FakeEmbeddingProvider:
    def __init__(self):
        self.calls = []

    def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return [0.1, 0.2]


class FakeRepository:
    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def upsert_chunk(self, chunk):
        return 1

    def search(
        self,
        query_embedding,
        *,
        top_k,
        school=None,
        year=None,
        category=None,
        province=None,
    ):
        self.calls.append(
            {
                "query_embedding": query_embedding,
                "top_k": top_k,
                "school": school,
                "year": year,
                "category": category,
                "province": province,
            }
        )
        return self.hits


class FakeAnswerGenerator:
    def __init__(self, answer="这是生成答案。", error=None):
        self.answer = answer
        self.error = error
        self.calls = []

    def generate(self, question, hits):
        self.calls.append({"question": question, "hits": hits})
        if self.error:
            raise self.error
        return self.answer


def _hit() -> RagSearchHit:
    return RagSearchHit(
        id=7,
        document_uid="2026-北京大学-章程-university_admission_chapter-abc",
        global_chunk_id="2026-北京大学-章程-university_admission_chapter-abc:document-p0085-right-01254",
        local_chunk_id="document-p0085-right-01254",
        chunk_index=1254,
        content_type="table",
        chunk_role="table",
        content="<table><tr><td>二级学科</td><td>研究方向</td></tr></table>",
        similarity=0.91,
        title="北京大学2026年本科招生章程",
        category="university_admission_chapter",
        source_url="https://example.test/pku.pdf",
        source="北京大学",
        school_name="北京大学",
        province="全国",
        document_year=2026,
        page_number=85,
        page_side="右页",
        heading_path=("基础医学院", "二级学科"),
        table_title="二级学科 / 研究方向",
        context_text="[document-p0085-right-01254]\n<table>...</table>",
        context_chunk_ids=("document-p0085-right-01254",),
    )


def test_rag_pipeline_returns_results_and_citations():
    embedding = FakeEmbeddingProvider()
    repository = FakeRepository([_hit()])
    pipeline = RagPipeline(
        embedding_provider=embedding,
        repository=repository,
        default_top_k=5,
        max_top_k=10,
    )

    result = pipeline.query(
        "北京大学基础医学有哪些二级学科研究方向？",
        school="北京大学",
        year=2026,
        category="university_admission_chapter",
        top_k=3,
    )

    assert embedding.calls == ["北京大学基础医学有哪些二级学科研究方向？"]
    assert repository.calls[0]["top_k"] == 3
    assert repository.calls[0]["school"] == "北京大学"
    assert repository.calls[0]["year"] == 2026
    assert result.result_count == 1
    assert result.answer is None
    assert result.results[0].global_chunk_id.endswith("document-p0085-right-01254")
    assert result.results[0].heading_path == ("基础医学院", "二级学科")
    assert result.results[0].context_chunk_ids == ("document-p0085-right-01254",)
    assert result.citations[0].source_url == "https://example.test/pku.pdf"
    assert result.citations[0].page_number == 85
    assert "未生成最终政策解释" in result.notes[-1]


def test_rag_pipeline_generates_answer_when_generator_is_configured():
    answer_generator = FakeAnswerGenerator(answer="基础医学包含人体解剖与组织胚胎学等方向。")
    pipeline = RagPipeline(
        embedding_provider=FakeEmbeddingProvider(),
        repository=FakeRepository([_hit()]),
        answer_generator=answer_generator,
    )

    result = pipeline.query("北京大学基础医学有哪些二级学科研究方向？")

    assert result.answer == "基础医学包含人体解剖与组织胚胎学等方向。"
    assert answer_generator.calls[0]["question"] == "北京大学基础医学有哪些二级学科研究方向？"
    assert answer_generator.calls[0]["hits"][0].local_chunk_id == "document-p0085-right-01254"
    assert "已基于 RAG chunk 生成答案" in result.notes[-1]


def test_rag_pipeline_keeps_candidates_when_answer_generation_fails():
    pipeline = RagPipeline(
        embedding_provider=FakeEmbeddingProvider(),
        repository=FakeRepository([_hit()]),
        answer_generator=FakeAnswerGenerator(error=PolicyRagError("llm failed")),
    )

    result = pipeline.query("北京大学基础医学有哪些二级学科研究方向？")

    assert result.answer is None
    assert result.result_count == 1
    assert "答案生成失败" in result.notes[-1]


def test_answer_context_deduplicates_context_groups_and_limits_hits():
    first = _hit()
    duplicate = RagSearchHit(
        id=8,
        document_uid=first.document_uid,
        global_chunk_id=first.global_chunk_id + "-dup",
        local_chunk_id="document-p0085-right-01255",
        chunk_index=1255,
        content_type=first.content_type,
        chunk_role=first.chunk_role,
        content="重复上下文",
        similarity=0.9,
        title=first.title,
        category=first.category,
        context_text=first.context_text,
        context_chunk_ids=first.context_chunk_ids,
    )
    other = RagSearchHit(
        id=9,
        document_uid=first.document_uid,
        global_chunk_id=first.global_chunk_id + "-other",
        local_chunk_id="document-p0086-left-01256",
        chunk_index=1256,
        content_type="table",
        chunk_role="table",
        content="其他上下文",
        similarity=0.88,
        title=first.title,
        category=first.category,
        context_chunk_ids=("document-p0086-left-01256",),
    )

    context = _format_hits((first, duplicate, other), max_chars=10_000, max_hits=2)

    assert "document-p0085-right-01254" in context
    assert "document-p0085-right-01255" not in context
    assert "document-p0086-left-01256" in context


def test_rag_pipeline_keeps_legacy_filters_compatible():
    repository = FakeRepository([])
    pipeline = RagPipeline(
        embedding_provider=FakeEmbeddingProvider(),
        repository=repository,
    )

    pipeline.query(
        "招生章程",
        province="全国",
        plan_year=2026,
        document_type="university_admission_chapter",
    )

    assert repository.calls[0]["year"] == 2026
    assert repository.calls[0]["category"] == "university_admission_chapter"
    assert repository.calls[0]["province"] == "全国"


def test_rag_pipeline_returns_empty_note():
    result = RagPipeline(
        embedding_provider=FakeEmbeddingProvider(),
        repository=FakeRepository([]),
    ).query("投档规则是什么", school="北京大学")

    assert result.result_count == 0
    assert result.results == ()
    assert result.citations == ()
    assert "暂无可检索 RAG chunk" in result.notes[-1]


def test_rag_pipeline_clamps_top_k():
    repository = FakeRepository([])
    pipeline = RagPipeline(
        embedding_provider=FakeEmbeddingProvider(),
        repository=repository,
        default_top_k=5,
        max_top_k=8,
    )

    pipeline.query("投档规则是什么", top_k=20)

    assert repository.calls[0]["top_k"] == 8


def test_rag_pipeline_rejects_invalid_top_k():
    pipeline = RagPipeline(
        embedding_provider=FakeEmbeddingProvider(),
        repository=FakeRepository([]),
    )

    with pytest.raises(ValueError):
        pipeline.query("投档规则是什么", top_k=0)
