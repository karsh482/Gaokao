from __future__ import annotations

import json

import httpx

from app.llm_clients import AIGPURentLLMTextModel


def test_ai_gpurent_llm_text_model_creates_task_and_returns_message() -> None:
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        assert request.headers["X-API-Key"] == "gpurent-key"
        if request.method == "POST" and request.url.path == "/tasks":
            body = json.loads(request.content)
            assert body["kind"] == "LLM_TEXT_CHAT"
            assert body["timeout_sec"] == 120
            assert body["payload"]["provider"] == "deepseek"
            assert body["payload"]["temperature"] == 0
            assert body["payload"]["messages"] == [
                {"role": "system", "content": "system prompt"},
                {"role": "user", "content": "user prompt"},
            ]
            return httpx.Response(200, json={"task_id": "task-1"})
        if request.method == "GET" and request.url.path == "/tasks/task-1":
            return httpx.Response(
                200,
                json={
                    "task_id": "task-1",
                    "status": "SUCCEEDED",
                    "message": "模型回复",
                },
            )
        return httpx.Response(404, json={"error": "not found"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    model = AIGPURentLLMTextModel(
        base_url="http://gpurent.local",
        api_key="gpurent-key",
        task_timeout_sec=120,
        poll_interval=0.001,
        http_client=client,
    )

    assert model.complete("system prompt", "user prompt") == "模型回复"
    assert calls == [("POST", "/tasks"), ("GET", "/tasks/task-1")]


def test_ai_gpurent_llm_text_model_reads_output_artifact_when_message_empty() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/tasks":
            return httpx.Response(200, json={"task_id": "task-1"})
        if request.method == "GET" and request.url.path == "/tasks/task-1":
            return httpx.Response(
                200,
                json={
                    "task_id": "task-1",
                    "status": "SUCCEEDED",
                    "artifact_ids": ["art-1"],
                },
            )
        if request.method == "GET" and request.url.path == "/artifacts/art-1":
            return httpx.Response(200, json={"text": "artifact 回复"})
        return httpx.Response(404, json={"error": "not found"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    model = AIGPURentLLMTextModel(
        base_url="http://gpurent.local",
        api_key="gpurent-key",
        poll_interval=0.001,
        http_client=client,
    )

    assert model.complete("system prompt", "user prompt") == "artifact 回复"
