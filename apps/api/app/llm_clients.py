"""LLM adapters used by the API service."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from gaokao_nl2sql.errors import SqlGenerationError
from gaokao_rag.errors import PolicyRagError
from gaokao_rag.models import RagSearchHit


@dataclass(slots=True)
class AIGPURentLLMTextModel:
    """Adapt ai-gpurent-cli LLM_TEXT_CHAT tasks to the local ChatModel protocol."""

    base_url: str
    api_key: str = field(repr=False)
    provider: str = "deepseek"
    task_timeout_sec: int = 300
    poll_timeout: float = 300.0
    poll_interval: float = 1.0
    http_timeout: float = 15.0
    http_client: httpx.Client | None = field(default=None, repr=False)

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key.strip():
            raise SqlGenerationError("缺少 ai-gpurent API Key。")

        task = self._create_task(system_prompt=system_prompt, user_prompt=user_prompt)
        task_id = str(task.get("task_id") or "").strip()
        if not task_id:
            raise SqlGenerationError("ai-gpurent 未返回 task_id。")
        return self._wait_for_text(task_id)

    def _create_task(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload = {
            "kind": "LLM_TEXT_CHAT",
            "timeout_sec": self.task_timeout_sec,
            "payload": {
                "provider": self.provider.strip() or "deepseek",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0,
            },
        }
        return self._json_request("POST", "/tasks", json=payload)

    def _wait_for_text(self, task_id: str) -> str:
        deadline = time.monotonic() + max(self.poll_timeout, 1)
        while True:
            task = self._json_request("GET", f"/tasks/{task_id}")
            status = str(task.get("status") or "").strip().upper()
            if status == "SUCCEEDED":
                return self._extract_text(task)
            if status == "FAILED":
                failure = task.get("failure") or task.get("message") or "未知错误"
                raise SqlGenerationError(f"ai-gpurent LLM 任务失败: {failure}")
            if time.monotonic() >= deadline:
                raise SqlGenerationError(f"等待 ai-gpurent LLM 任务超时: {task_id}")
            time.sleep(max(self.poll_interval, 0.1))

    def _extract_text(self, task: dict[str, Any]) -> str:
        message = str(task.get("message") or "").strip()
        if message:
            return message

        artifact_urls = task.get("artifact_urls")
        if isinstance(artifact_urls, list) and artifact_urls:
            data = self._json_request("GET", str(artifact_urls[0]), absolute_url=True)
            return self._text_from_artifact(data)

        artifact_ids = task.get("artifact_ids")
        if isinstance(artifact_ids, list) and artifact_ids:
            data = self._json_request("GET", f"/artifacts/{artifact_ids[0]}")
            return self._text_from_artifact(data)

        raise SqlGenerationError("ai-gpurent LLM 任务成功但未返回文本。")

    @staticmethod
    def _text_from_artifact(data: dict[str, Any]) -> str:
        text = str(data.get("text") or "").strip()
        if text:
            return text
        try:
            return str(data["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise SqlGenerationError("ai-gpurent LLM artifact 中没有可用文本。") from exc

    def _json_request(
        self,
        method: str,
        path_or_url: str,
        *,
        json: Any | None = None,
        absolute_url: bool = False,
    ) -> dict[str, Any]:
        url = (
            path_or_url
            if absolute_url or path_or_url.startswith(("http://", "https://"))
            else f"{self.base_url.rstrip('/')}/{path_or_url.lstrip('/')}"
        )
        headers = {}
        if not absolute_url:
            headers["X-API-Key"] = self.api_key.strip()
        try:
            response = self._request(method, url, headers=headers, json=json)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise SqlGenerationError(f"ai-gpurent 调用失败: {exc}") from exc
        if not isinstance(data, dict):
            raise SqlGenerationError("ai-gpurent 返回了非对象 JSON。")
        return data

    def _request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        json: Any | None,
    ) -> httpx.Response:
        if self.http_client is not None:
            return self.http_client.request(method, url, headers=headers, json=json)
        return httpx.request(
            method,
            url,
            headers=headers,
            json=json,
            timeout=self.http_timeout,
        )


@dataclass(frozen=True, slots=True)
class ChatModelRagAnswerGenerator:
    """RAG answer generator backed by any ChatModel-like object."""

    model: Any
    max_context_chars: int = 12_000
    max_hits: int = 3

    def generate(self, question: str, hits: tuple[RagSearchHit, ...]) -> str:
        if not hits:
            return "未检索到可用于回答该问题的政策或招生章程片段。"
        try:
            return self.model.complete(
                _RAG_SYSTEM_PROMPT,
                self._user_prompt(question, hits),
            ).strip()
        except Exception as exc:
            raise PolicyRagError(f"RAG 答案生成失败: {exc}") from exc

    def _user_prompt(self, question: str, hits: tuple[RagSearchHit, ...]) -> str:
        context = _format_hits(
            hits,
            max_chars=self.max_context_chars,
            max_hits=self.max_hits,
        )
        return (
            f"用户问题：{question}\n\n"
            "检索上下文：\n"
            f"{context}\n\n"
            "请基于检索上下文回答用户问题。"
        )


def _format_hits(
    hits: tuple[RagSearchHit, ...],
    *,
    max_chars: int,
    max_hits: int,
) -> str:
    parts: list[str] = []
    used = 0
    seen_context_keys: set[tuple[str, ...]] = set()
    for index, hit in enumerate(hits, start=1):
        if len(parts) >= max_hits:
            break
        context_key = hit.context_chunk_ids or (hit.local_chunk_id,)
        if context_key in seen_context_keys:
            continue
        seen_context_keys.add(context_key)
        source = _source_label(hit)
        content = (hit.context_text or hit.content).strip()
        block = f"[{index}] {source}\n{content}"
        if used + len(block) > max_chars:
            remaining = max_chars - used
            if remaining <= 200:
                break
            block = block[:remaining].rstrip() + "\n...[上下文已截断]"
        parts.append(block)
        used += len(block)
    return "\n\n".join(parts)


def _source_label(hit: RagSearchHit) -> str:
    parts = [
        hit.title,
        hit.school_name,
        str(hit.document_year) if hit.document_year else None,
    ]
    if hit.page_number:
        page = f"第 {hit.page_number} 页"
        if hit.page_side:
            page += f" {hit.page_side}"
        parts.append(page)
    if hit.heading_path:
        parts.append(" / ".join(hit.heading_path))
    if hit.table_title:
        parts.append(hit.table_title)
    parts.append(f"chunk={hit.local_chunk_id}")
    return " | ".join(str(part) for part in parts if part)


_RAG_SYSTEM_PROMPT = """你是高考志愿政策与高校招生章程问答助手。
只能基于给定检索上下文回答，不要编造上下文没有的信息。
如果上下文不足，请明确说明“根据当前检索片段无法确认”。
回答要求：
1. 先直接回答结论；
2. 对表格类内容优先整理为条目；
3. 关键事实后标注引用编号，例如 [1]；
4. 不输出与问题无关的长篇背景。"""
