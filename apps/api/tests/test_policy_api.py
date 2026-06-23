"""RAG chunk 检索 API 测试。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from gaokao_rag import (
    LocalSentenceTransformerEmbeddingProvider,
    OpenAICompatibleAnswerGenerator,
    OpenAICompatibleEmbeddingProvider,
    PolicyRagError,
    RagCitation,
    RagQueryResult,
    RagResultItem,
)
from gaokao_nl2sql import (
    IntentExtractor,
    OpenAICompatibleModel,
    OpenAICompatibleSqlAnswerSynthesizer,
    SemanticFrameExtractor,
)

from app.config import Settings
from app.dependencies import (
    _build_answer_generator,
    _build_embedding_provider,
    _build_intent_extractor,
    _build_semantic_extractor,
    _build_sql_answer_synthesizer,
)
from app.models import PolicyQueryRequest
from app.routers.policy import policy_query


class FakePolicyRagPipeline:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error
        self.calls = []

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
    ):
        self.calls.append(
            {
                "question": question,
                "school": school,
                "year": year,
                "category": category,
                "province": province,
                "plan_year": plan_year,
                "document_type": document_type,
                "top_k": top_k,
            }
        )
        if self._error:
            raise self._error
        return self._result


def test_policy_query_happy_path():
    result = RagQueryResult(
        question="北京大学基础医学有哪些二级学科研究方向？",
        answer="基础医学包含人体解剖与组织胚胎学等二级学科。",
        results=(
            RagResultItem(
                id=1,
                document_uid="doc-1",
                global_chunk_id="doc-1:chunk-1",
                local_chunk_id="chunk-1",
                title="北京大学2026年本科招生章程",
                category="university_admission_chapter",
                content_type="table",
                chunk_role="table",
                snippet="| 二级学科 | 研究方向 |",
                similarity=0.92,
                source_url="https://example.test/pku.pdf",
                source="北京大学",
                school_name="北京大学",
                province="全国",
                document_year=2026,
                page_number=85,
                page_side="右页",
                heading_path=("基础医学院", "二级学科"),
                table_title="二级学科 / 研究方向",
                context_text="[chunk-1]\n| 二级学科 | 研究方向 |",
                context_chunk_ids=("chunk-1",),
            ),
        ),
        citations=(
            RagCitation(
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
                global_chunk_id="doc-1:chunk-1",
                local_chunk_id="chunk-1",
            ),
        ),
        notes=("当前返回 RAG chunk 检索候选与引用，未生成最终政策解释。",),
    )
    pipeline = FakePolicyRagPipeline(result=result)

    response = policy_query(
        PolicyQueryRequest(
            question="北京大学基础医学有哪些二级学科研究方向？",
            school="北京大学",
            year=2026,
            category="university_admission_chapter",
            top_k=3,
        ),
        pipeline=pipeline,
    )

    assert pipeline.calls[0]["school"] == "北京大学"
    assert pipeline.calls[0]["year"] == 2026
    assert response.result_count == 1
    assert response.answer == "基础医学包含人体解剖与组织胚胎学等二级学科。"
    assert response.results[0].global_chunk_id == "doc-1:chunk-1"
    assert response.results[0].heading_path == ["基础医学院", "二级学科"]
    assert response.results[0].context_text is None
    assert response.results[0].context_chunk_ids == ["chunk-1"]
    assert response.citations[0].source_url == "https://example.test/pku.pdf"
    assert response.citations[0].page_number == 85
    assert "未生成最终政策解释" in response.notes[0]


def test_policy_query_can_include_context_for_debugging():
    result = RagQueryResult(
        question="北京大学基础医学有哪些二级学科研究方向？",
        answer=None,
        results=(
            RagResultItem(
                id=1,
                document_uid="doc-1",
                global_chunk_id="doc-1:chunk-1",
                local_chunk_id="chunk-1",
                title="北京大学2026年本科招生章程",
                category="university_admission_chapter",
                content_type="table",
                chunk_role="table",
                snippet="| 二级学科 | 研究方向 |",
                similarity=0.92,
                context_text="[chunk-1]\n| 二级学科 | 研究方向 |",
                context_chunk_ids=("chunk-1",),
            ),
        ),
        citations=(),
        notes=("当前返回 RAG chunk 检索候选与引用，未生成最终政策解释。",),
    )

    response = policy_query(
        PolicyQueryRequest(
            question="北京大学基础医学有哪些二级学科研究方向？",
            include_context=True,
        ),
        pipeline=FakePolicyRagPipeline(result=result),
    )

    assert response.results[0].context_text == "[chunk-1]\n| 二级学科 | 研究方向 |"


def test_policy_query_keeps_legacy_request_fields():
    result = RagQueryResult(
        question="投档规则是什么",
        answer=None,
        results=(),
        citations=(),
        notes=("暂无可检索 RAG chunk。",),
    )
    pipeline = FakePolicyRagPipeline(result=result)

    response = policy_query(
        PolicyQueryRequest(
            question="投档规则是什么",
            province="全国",
            plan_year=2026,
            document_type="university_admission_chapter",
        ),
        pipeline=pipeline,
    )

    assert pipeline.calls[0]["province"] == "全国"
    assert pipeline.calls[0]["plan_year"] == 2026
    assert pipeline.calls[0]["document_type"] == "university_admission_chapter"
    assert response.result_count == 0
    assert response.results == []


def test_build_answer_generator_disabled_by_default():
    generator = _build_answer_generator(Settings(rag_answer_enabled=False))

    assert generator is None


def test_build_answer_generator_requires_llm_api_key():
    generator = _build_answer_generator(
        Settings(
            rag_answer_enabled=True,
            llm_api_key="",
        )
    )

    assert generator is None


def test_build_answer_generator_uses_llm_settings():
    generator = _build_answer_generator(
        Settings(
            rag_answer_enabled=True,
            llm_base_url="https://example.test",
            llm_api_key="secret",
            llm_model="test-chat",
            llm_temperature=0.2,
            llm_timeout=12.5,
            rag_answer_max_context_chars=3456,
        )
    )

    assert isinstance(generator, OpenAICompatibleAnswerGenerator)
    assert generator.base_url == "https://example.test"
    assert generator.api_key == "secret"
    assert generator.model == "test-chat"
    assert generator.temperature == 0.2
    assert generator.timeout == 12.5
    assert generator.max_context_chars == 3456


def test_build_intent_extractor_requires_key_and_enabled_flag():
    model = OpenAICompatibleModel(
        base_url="https://example.test",
        api_key="secret",
        model="test-chat",
    )

    assert _build_intent_extractor(Settings(llm_api_key=""), model) is None
    assert (
        _build_intent_extractor(
            Settings(llm_api_key="secret", llm_intent_enabled=False),
            model,
        )
        is None
    )

    extractor = _build_intent_extractor(Settings(llm_api_key="secret"), model)

    assert isinstance(extractor, IntentExtractor)


def test_build_semantic_extractor_reuses_intent_flag_and_key() -> None:
    model = OpenAICompatibleModel(
        base_url="https://example.test",
        api_key="secret",
        model="test-chat",
    )

    assert _build_semantic_extractor(Settings(llm_api_key=""), model) is None
    assert (
        _build_semantic_extractor(
            Settings(llm_api_key="secret", llm_intent_enabled=False),
            model,
        )
        is None
    )

    extractor = _build_semantic_extractor(Settings(llm_api_key="secret"), model)

    assert isinstance(extractor, SemanticFrameExtractor)


def test_build_sql_answer_synthesizer_requires_key_and_enabled_flag() -> None:
    model = OpenAICompatibleModel(
        base_url="https://example.test",
        api_key="secret",
        model="test-chat",
    )

    assert _build_sql_answer_synthesizer(Settings(sql_answer_enabled=False), model) is None
    assert (
        _build_sql_answer_synthesizer(
            Settings(sql_answer_enabled=True, llm_api_key=""),
            model,
        )
        is None
    )

    synthesizer = _build_sql_answer_synthesizer(
        Settings(
            sql_answer_enabled=True,
            llm_api_key="secret",
            sql_answer_max_rows=7,
            sql_answer_max_chars=3456,
        ),
        model,
    )

    assert isinstance(synthesizer, OpenAICompatibleSqlAnswerSynthesizer)
    assert synthesizer.max_rows == 7
    assert synthesizer.max_chars == 3456


def test_build_sql_answer_synthesizer_enabled_by_default_with_key() -> None:
    model = OpenAICompatibleModel(
        base_url="https://example.test",
        api_key="secret",
        model="test-chat",
    )

    synthesizer = _build_sql_answer_synthesizer(Settings(llm_api_key="secret"), model)

    assert isinstance(synthesizer, OpenAICompatibleSqlAnswerSynthesizer)


def test_policy_query_rag_error_returns_500():
    with pytest.raises(HTTPException) as exc_info:
        policy_query(
            PolicyQueryRequest(question="投档规则是什么"),
            pipeline=FakePolicyRagPipeline(error=PolicyRagError("db failed")),
        )

    assert exc_info.value.status_code == 500
    assert "政策检索失败" in exc_info.value.detail


def test_policy_query_invalid_top_k_returns_422():
    with pytest.raises(ValueError):
        PolicyQueryRequest(question="投档规则是什么", top_k=0)


def test_build_embedding_provider_defaults_to_local():
    provider = _build_embedding_provider(
        Settings(
            embedding_provider="local",
            embedding_model="fake-model",
            embedding_dimension=2,
            embedding_device="auto",
            embedding_torch_dtype="auto",
            embedding_normalize=True,
        )
    )

    assert isinstance(provider, LocalSentenceTransformerEmbeddingProvider)
    assert provider.model == "fake-model"
    assert provider.dimension == 2
    assert provider.device is None
    assert provider.torch_dtype == "auto"
    assert provider.normalize is True


def test_build_embedding_provider_supports_openai_compatible_api():
    provider = _build_embedding_provider(
        Settings(
            embedding_provider="openai",
            embedding_base_url="https://example.test/v1",
            embedding_api_key="secret",
            embedding_model="fake-model",
            embedding_dimension=2,
            embedding_encoding_format="float",
            embedding_max_retries=1,
        )
    )

    assert isinstance(provider, OpenAICompatibleEmbeddingProvider)
    assert provider.base_url == "https://example.test/v1"
    assert provider.api_key == "secret"
    assert provider.model == "fake-model"
    assert provider.dimension == 2
    assert provider.encoding_format == "float"
