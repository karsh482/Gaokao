"""RAG 错误类型。"""

from __future__ import annotations


class PolicyRagError(RuntimeError):
    """RAG 基础错误。"""


class DocumentLoadError(PolicyRagError):
    """RAG 索引加载失败。"""


class EmbeddingError(PolicyRagError):
    """嵌入向量生成失败。"""


class PolicyRepositoryError(PolicyRagError):
    """RAG 仓储读写失败。"""
