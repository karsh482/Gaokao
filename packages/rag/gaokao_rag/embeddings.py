"""嵌入向量接口、本地模型与 OpenAI 兼容客户端。"""

from __future__ import annotations

import logging
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

import httpx

from gaokao_rag.errors import EmbeddingError

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-4B"
DEFAULT_EMBEDDING_CACHE_FOLDER = "models"
DEFAULT_QUERY_INSTRUCTION = (
    "Given a Chinese Gaokao admissions question, retrieve relevant passages "
    "from university admission policies, enrollment plans, score tables, "
    "score segment tables, and application guidance."
)
SUPPORTED_TORCH_DTYPES = frozenset(("auto", "float16", "bfloat16", "float32"))


class EmbeddingProvider(Protocol):
    """最小嵌入接口，便于测试替换。"""

    def embed(self, text: str) -> list[float]:
        """返回输入文本的向量。"""
        ...


@dataclass(slots=True)
class LocalSentenceTransformerEmbeddingProvider:
    """基于 sentence-transformers 的本地查询 embedding。"""

    model: str = DEFAULT_EMBEDDING_MODEL
    dimension: int | None = 2560
    device: str | None = None
    torch_dtype: str | None = "auto"
    max_seq_length: int | None = None
    cache_folder: str | None = DEFAULT_EMBEDDING_CACHE_FOLDER
    normalize: bool = True
    query_instruction_enabled: bool = True
    query_instruction: str = DEFAULT_QUERY_INSTRUCTION
    trust_remote_code: bool = True
    _model_factory: Callable[..., Any] | None = field(default=None, repr=False)
    _model: Any = field(default=None, init=False, repr=False)

    def embed(self, text: str) -> list[float]:
        stripped = text.strip()
        if not stripped:
            raise EmbeddingError("待向量化文本不能为空。")

        query_text = self._build_query_text(stripped)
        try:
            vectors = self._load_model().encode(
                [query_text],
                batch_size=1,
                normalize_embeddings=self.normalize,
                show_progress_bar=False,
            )
        except RuntimeError as exc:
            raise EmbeddingError(f"本地嵌入模型调用失败: {exc}") from exc

        try:
            vector = vectors[0]
        except (IndexError, TypeError) as exc:
            raise EmbeddingError(f"本地嵌入模型返回格式无效: {exc}") from exc
        return self._prepare_vector(vector)

    def _build_query_text(self, query: str) -> str:
        if not self.query_instruction_enabled:
            return query
        return f"Instruct: {self.query_instruction}\nQuery: {query}"

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        if self.torch_dtype is not None and self.torch_dtype not in SUPPORTED_TORCH_DTYPES:
            supported = "、".join(sorted(SUPPORTED_TORCH_DTYPES))
            raise EmbeddingError(f"torch_dtype 必须是 {supported} 之一。")
        if self.max_seq_length is not None and self.max_seq_length <= 0:
            raise EmbeddingError("max_seq_length 必须大于 0。")

        factory = self._model_factory or _load_sentence_transformer_factory()
        try:
            self._model = factory(
                self.model,
                device=self.device,
                cache_folder=self._resolved_cache_folder(),
                trust_remote_code=self.trust_remote_code,
                model_kwargs=_build_model_kwargs(self.torch_dtype),
            )
        except Exception as exc:
            raise EmbeddingError(f"本地嵌入模型加载失败: {exc}") from exc
        if self.max_seq_length is not None:
            self._model.max_seq_length = self.max_seq_length
        return self._model

    def _prepare_vector(self, vector: Any) -> list[float]:
        values = vector.tolist() if hasattr(vector, "tolist") else vector
        try:
            prepared = [float(value) for value in values]
        except TypeError as exc:
            raise EmbeddingError(f"本地嵌入向量格式无效: {exc}") from exc
        if self.dimension is not None:
            prepared = prepared[: self.dimension]
            if len(prepared) != self.dimension:
                raise EmbeddingError(
                    f"嵌入向量维度不匹配: expected={self.dimension}, actual={len(prepared)}"
                )
        if self.normalize:
            prepared = _normalize_vector(prepared)
        return prepared

    def _resolved_cache_folder(self) -> str | None:
        if self.cache_folder is None:
            return None
        stripped = self.cache_folder.strip()
        if stripped.lower() in ("", "none", "null"):
            return None
        return str(Path(stripped).expanduser().resolve())


@dataclass(slots=True)
class OpenAICompatibleEmbeddingProvider:
    """OpenAI 兼容 /embeddings 客户端。"""

    base_url: str
    api_key: str
    model: str
    dimension: int | None = 2560
    encoding_format: str | None = "float"
    timeout: httpx.Timeout = field(
        default_factory=lambda: httpx.Timeout(
            connect=5.0,
            read=30.0,
            write=10.0,
            pool=5.0,
        )
    )
    max_retries: int = 3
    backoff_base_seconds: float = 0.5
    backoff_max_seconds: float = 5.0
    _post: Any = field(default=None, repr=False)

    def embed(self, text: str) -> list[float]:
        if not text.strip():
            raise EmbeddingError("待向量化文本不能为空。")

        payload = {
            "model": self.model,
            "input": text,
        }
        if self.encoding_format:
            payload["encoding_format"] = self.encoding_format
        url = f"{self.base_url.rstrip('/')}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last_error: Exception | None = None
        attempts = max(1, self.max_retries + 1)
        for attempt in range(attempts):
            try:
                response = (self._post or httpx.post)(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()
                embedding = data["data"][0]["embedding"]
                vector = [float(value) for value in embedding]
                self._validate_dimension(vector)
                return vector
            except httpx.HTTPStatusError as exc:
                last_error = exc
                status_code = exc.response.status_code
                if status_code < 500 or attempt == attempts - 1:
                    break
                self._sleep_before_retry(attempt, exc)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                if attempt == attempts - 1:
                    break
                self._sleep_before_retry(attempt, exc)
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise EmbeddingError(f"嵌入服务返回格式无效: {exc}") from exc

        raise EmbeddingError(f"嵌入服务调用失败: {last_error}") from last_error

    def _validate_dimension(self, vector: list[float]) -> None:
        if self.dimension is not None and len(vector) != self.dimension:
            raise EmbeddingError(
                f"嵌入向量维度不匹配: expected={self.dimension}, actual={len(vector)}"
            )

    def _sleep_before_retry(self, attempt: int, exc: Exception) -> None:
        delay = min(
            self.backoff_max_seconds,
            self.backoff_base_seconds * (2**attempt),
        )
        delay += random.uniform(0, self.backoff_base_seconds)
        logger.warning(
            "嵌入服务调用失败，将重试: target=%s, error=%s, attempt=%s",
            self.base_url.rstrip("/"),
            type(exc).__name__,
            attempt + 1,
        )
        time.sleep(delay)


def _load_sentence_transformer_factory() -> Any:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise EmbeddingError(
            "缺少本地 embedding 依赖 sentence-transformers。"
            "请先执行: python -m pip install -e \"packages/rag[local]\""
        ) from exc
    return SentenceTransformer


def _build_model_kwargs(torch_dtype: str | None) -> dict[str, Any] | None:
    if torch_dtype is None:
        return None
    if torch_dtype == "auto":
        return {"torch_dtype": "auto"}

    try:
        import torch
    except ImportError as exc:
        raise EmbeddingError("设置 torch_dtype 需要安装 PyTorch。") from exc

    dtype_map = {
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
        "float32": torch.float32,
    }
    return {"torch_dtype": dtype_map[torch_dtype]}


def _normalize_vector(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]
