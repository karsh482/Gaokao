"""EmbeddingProvider 单元测试。"""

from __future__ import annotations

import httpx
import pytest

from gaokao_rag import (
    EmbeddingError,
    LocalSentenceTransformerEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://example.test/embeddings")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("failed", request=request, response=response)

    def json(self):
        return self._payload


class FakeSentenceTransformerModel:
    def __init__(self, vector):
        self.vector = vector
        self.calls = []
        self.max_seq_length = None

    def encode(self, texts, *, batch_size, normalize_embeddings, show_progress_bar):
        self.calls.append(
            {
                "texts": texts,
                "batch_size": batch_size,
                "normalize_embeddings": normalize_embeddings,
                "show_progress_bar": show_progress_bar,
            }
        )
        return [self.vector for _ in texts]


def test_openai_compatible_embedding_provider_returns_vector():
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append((url, headers, json, timeout))
        return FakeResponse({"data": [{"embedding": [0.1, 0.2]}]})

    provider = OpenAICompatibleEmbeddingProvider(
        base_url="https://example.test",
        api_key="secret",
        model="bge-m3",
        dimension=2,
        _post=fake_post,
    )

    assert provider.embed("政策问题") == [0.1, 0.2]
    assert calls[0][0] == "https://example.test/embeddings"
    assert calls[0][2]["model"] == "bge-m3"
    assert calls[0][2]["encoding_format"] == "float"


def test_local_sentence_transformer_provider_builds_instruction_and_normalizes(tmp_path):
    fake_model = FakeSentenceTransformerModel([3.0, 4.0])
    factory_calls = []
    cache_folder = tmp_path / "models"

    def fake_factory(*args, **kwargs):
        factory_calls.append((args, kwargs))
        return fake_model

    provider = LocalSentenceTransformerEmbeddingProvider(
        model="fake-model",
        dimension=2,
        device="cuda",
        torch_dtype=None,
        max_seq_length=512,
        cache_folder=str(cache_folder),
        _model_factory=fake_factory,
    )

    vector = provider.embed(" 北京大学基础医学有哪些二级学科研究方向？ ")

    assert vector == pytest.approx([0.6, 0.8])
    assert factory_calls[0][0] == ("fake-model",)
    assert factory_calls[0][1]["device"] == "cuda"
    assert factory_calls[0][1]["cache_folder"] == str(cache_folder.resolve())
    assert factory_calls[0][1]["model_kwargs"] is None
    assert fake_model.max_seq_length == 512
    encoded_text = fake_model.calls[0]["texts"][0]
    assert encoded_text.startswith("Instruct: ")
    assert "Query: 北京大学基础医学有哪些二级学科研究方向？" in encoded_text
    assert fake_model.calls[0]["normalize_embeddings"] is True


def test_local_sentence_transformer_provider_can_disable_query_instruction():
    fake_model = FakeSentenceTransformerModel([1.0, 0.0])

    provider = LocalSentenceTransformerEmbeddingProvider(
        model="fake-model",
        dimension=2,
        torch_dtype=None,
        query_instruction_enabled=False,
        _model_factory=lambda *args, **kwargs: fake_model,
    )

    assert provider.embed("政策问题") == [1.0, 0.0]
    assert fake_model.calls[0]["texts"] == ["政策问题"]


def test_local_sentence_transformer_provider_rejects_bad_dimension():
    provider = LocalSentenceTransformerEmbeddingProvider(
        model="fake-model",
        dimension=3,
        torch_dtype=None,
        _model_factory=lambda *args, **kwargs: FakeSentenceTransformerModel([1.0, 0.0]),
    )

    with pytest.raises(EmbeddingError):
        provider.embed("政策问题")


def test_local_sentence_transformer_provider_rejects_blank_text():
    provider = LocalSentenceTransformerEmbeddingProvider(
        model="fake-model",
        _model_factory=lambda *args, **kwargs: FakeSentenceTransformerModel([1.0, 0.0]),
    )

    with pytest.raises(EmbeddingError):
        provider.embed(" ")


def test_openai_compatible_embedding_provider_can_omit_encoding_format():
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append((url, headers, json, timeout))
        return FakeResponse({"data": [{"embedding": [0.1, 0.2]}]})

    provider = OpenAICompatibleEmbeddingProvider(
        base_url="https://example.test",
        api_key="secret",
        model="bge-m3",
        dimension=2,
        encoding_format=None,
        _post=fake_post,
    )

    assert provider.embed("政策问题") == [0.1, 0.2]
    assert "encoding_format" not in calls[0][2]


def test_openai_compatible_embedding_provider_rejects_bad_dimension():
    provider = OpenAICompatibleEmbeddingProvider(
        base_url="https://example.test",
        api_key="secret",
        model="bge-m3",
        dimension=3,
        _post=lambda **kwargs: FakeResponse({"data": [{"embedding": [0.1, 0.2]}]}),
    )

    with pytest.raises(EmbeddingError):
        provider.embed("政策问题")


def test_openai_compatible_embedding_provider_does_not_retry_400():
    calls = 0

    def fake_post(url, headers, json, timeout):
        nonlocal calls
        calls += 1
        return FakeResponse({}, status_code=400)

    provider = OpenAICompatibleEmbeddingProvider(
        base_url="https://example.test",
        api_key="secret",
        model="bge-m3",
        dimension=2,
        max_retries=3,
        _post=fake_post,
    )

    with pytest.raises(EmbeddingError):
        provider.embed("政策问题")
    assert calls == 1


def test_openai_compatible_embedding_provider_rejects_blank_text():
    provider = OpenAICompatibleEmbeddingProvider(
        base_url="https://example.test",
        api_key="secret",
        model="bge-m3",
    )

    with pytest.raises(EmbeddingError):
        provider.embed(" ")
