"""Gaokao RAG package."""

from gaokao_rag.answering import AnswerGenerator, OpenAICompatibleAnswerGenerator
from gaokao_rag.embeddings import (
    EmbeddingProvider,
    LocalSentenceTransformerEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
)
from gaokao_rag.errors import (
    DocumentLoadError,
    EmbeddingError,
    PolicyRagError,
    PolicyRepositoryError,
)
from gaokao_rag.loader import DocumentLoader, RagIndexLoader, content_hash
from gaokao_rag.models import (
    RagChunkInput,
    RagCitation,
    RagQueryResult,
    RagResultItem,
    RagSearchHit,
    PolicyCitation,
    PolicyDocumentInput,
    PolicyRagResult,
    PolicyResultItem,
    PolicySearchHit,
)
from gaokao_rag.pipeline import PolicyRagPipeline, RagPipeline
from gaokao_rag.repository import (
    PgVectorRagChunkRepository,
    PgVectorPolicyDocumentRepository,
    RagChunkRepository,
    PolicyDocumentRepository,
    chunk_from_rag_index_record,
    vector_literal,
)

__all__ = [
    "AnswerGenerator",
    "DocumentLoadError",
    "DocumentLoader",
    "EmbeddingError",
    "EmbeddingProvider",
    "LocalSentenceTransformerEmbeddingProvider",
    "OpenAICompatibleEmbeddingProvider",
    "OpenAICompatibleAnswerGenerator",
    "PgVectorRagChunkRepository",
    "PgVectorPolicyDocumentRepository",
    "PolicyCitation",
    "PolicyDocumentInput",
    "PolicyDocumentRepository",
    "PolicyRagError",
    "PolicyRagPipeline",
    "PolicyRagResult",
    "PolicyRepositoryError",
    "PolicyResultItem",
    "PolicySearchHit",
    "RagChunkInput",
    "RagChunkRepository",
    "RagCitation",
    "RagIndexLoader",
    "RagPipeline",
    "RagQueryResult",
    "RagResultItem",
    "RagSearchHit",
    "chunk_from_rag_index_record",
    "content_hash",
    "vector_literal",
]
