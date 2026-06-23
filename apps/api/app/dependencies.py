"""FastAPI 依赖：鉴权与 NL2SQL 流程装配。"""

from __future__ import annotations

from functools import lru_cache

from fastapi import Header, HTTPException, status

from gaokao_rag import (
    LocalSentenceTransformerEmbeddingProvider,
    OpenAICompatibleAnswerGenerator,
    OpenAICompatibleEmbeddingProvider,
    PgVectorRagChunkRepository,
    RagPipeline,
)

from gaokao_nl2sql import (
    CatalogPipeline,
    IntentExtractor,
    Nl2SqlPipeline,
    OpenAICompatibleSqlAnswerSynthesizer,
    OpenAICompatibleModel,
    PostgresExecutor,
    SemanticFrameExtractor,
    SqlGenerator,
)

from app.config import get_settings


@lru_cache
def get_pipeline() -> CatalogPipeline:
    """装配 Query Catalog + NL2SQL 流程（进程内复用）。"""

    settings = get_settings()
    model = OpenAICompatibleModel(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
    )
    executor = PostgresExecutor(
        dsn=settings.database_url,
        statement_timeout_ms=settings.statement_timeout_ms,
        max_rows=settings.max_limit,
    )
    nl2sql_pipeline = Nl2SqlPipeline(
        generator=SqlGenerator(model=model),
        executor=executor,
        default_limit=settings.default_limit,
        max_limit=settings.max_limit,
    )
    return CatalogPipeline(
        nl2sql_pipeline=nl2sql_pipeline,
        semantic_extractor=_build_semantic_extractor(settings, model),
        intent_extractor=_build_intent_extractor(settings, model),
        answer_synthesizer=_build_sql_answer_synthesizer(settings, model),
    )


def _build_semantic_extractor(settings, model):
    if not settings.llm_intent_enabled:
        return None
    if not settings.llm_api_key.strip():
        return None
    return SemanticFrameExtractor(model=model)


def _build_intent_extractor(settings, model):
    if not settings.llm_intent_enabled:
        return None
    if not settings.llm_api_key.strip():
        return None
    return IntentExtractor(model=model)


def _build_sql_answer_synthesizer(settings, model):
    if not settings.sql_answer_enabled:
        return None
    if not settings.llm_api_key.strip():
        return None
    return OpenAICompatibleSqlAnswerSynthesizer(
        model=model,
        max_rows=settings.sql_answer_max_rows,
        max_chars=settings.sql_answer_max_chars,
    )


@lru_cache
def get_policy_rag_pipeline() -> RagPipeline:
    """装配 RAG chunk 检索流程（进程内复用）。"""

    settings = get_settings()
    embedding_provider = _build_embedding_provider(settings)
    repository = PgVectorRagChunkRepository(
        dsn=settings.database_url,
        statement_timeout_ms=settings.statement_timeout_ms,
    )
    return RagPipeline(
        embedding_provider=embedding_provider,
        repository=repository,
        answer_generator=_build_answer_generator(settings),
        default_top_k=settings.policy_default_top_k,
        max_top_k=settings.policy_max_top_k,
    )


def _build_embedding_provider(settings):
    provider = settings.embedding_provider.strip().lower()
    if provider in ("local", "sentence-transformers", "sentence_transformers"):
        return LocalSentenceTransformerEmbeddingProvider(
            model=settings.embedding_model,
            dimension=settings.embedding_dimension,
            device=_optional_device(settings.embedding_device),
            torch_dtype=_optional_text_setting(settings.embedding_torch_dtype),
            max_seq_length=settings.embedding_max_seq_length,
            cache_folder=_optional_text_setting(settings.embedding_cache_folder),
            normalize=settings.embedding_normalize,
            query_instruction_enabled=settings.embedding_query_instruction_enabled,
        )
    if provider in ("openai", "openai-compatible", "openai_compatible", "modelscope"):
        return OpenAICompatibleEmbeddingProvider(
            base_url=settings.embedding_base_url,
            api_key=settings.embedding_api_key,
            model=settings.embedding_model,
            dimension=settings.embedding_dimension,
            encoding_format=settings.embedding_encoding_format,
            max_retries=settings.embedding_max_retries,
        )
    raise ValueError("GAOKAO_EMBEDDING_PROVIDER 仅支持 local 或 openai。")


def _build_answer_generator(settings):
    if not settings.rag_answer_enabled:
        return None
    if not settings.llm_api_key.strip():
        return None
    return OpenAICompatibleAnswerGenerator(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout,
        max_context_chars=settings.rag_answer_max_context_chars,
        max_hits=settings.rag_answer_max_hits,
    )


def _optional_device(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if normalized.lower() in ("", "auto", "none", "null"):
        return None
    return normalized


def _optional_text_setting(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if normalized.lower() in ("", "none", "null"):
        return None
    return normalized


def require_api_key(
    x_api_key: str | None = Header(default=None),
) -> None:
    """当配置了 GAOKAO_API_KEY 时校验请求头 X-API-Key。"""

    settings = get_settings()
    if not settings.api_key:
        # 未配置 API Key：开发模式放行。生产环境应配置 GAOKAO_API_KEY。
        return
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少或无效的 X-API-Key。",
        )
