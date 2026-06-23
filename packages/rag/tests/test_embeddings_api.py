"""ModelScope / OpenAI-compatible embedding integration smoke test.

默认不访问外部服务。需要手动设置：

GAOKAO_EMBEDDING_API_KEY=...
GAOKAO_RUN_EMBEDDING_INTEGRATION=1
"""

from __future__ import annotations

import os

import pytest


@pytest.mark.skipif(
    os.getenv("GAOKAO_RUN_EMBEDDING_INTEGRATION") != "1",
    reason="external embedding integration test is opt-in",
)
def test_modelscope_embedding_api_smoke() -> None:
    api_key = os.getenv("GAOKAO_EMBEDDING_API_KEY", "").strip()
    if not api_key:
        pytest.skip("GAOKAO_EMBEDDING_API_KEY is not configured")

    openai = pytest.importorskip("openai")
    client = openai.OpenAI(
        base_url=os.getenv(
            "GAOKAO_EMBEDDING_BASE_URL",
            "https://api-inference.modelscope.cn/v1",
        ),
        api_key=api_key,
    )

    response = client.embeddings.create(
        model=os.getenv("GAOKAO_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-4B"),
        input="你好",
        encoding_format="float",
    )

    assert response.data
    assert response.data[0].embedding
