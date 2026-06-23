"""LLM 客户端：调用 OpenAI 兼容的 /chat/completions 接口。

通过 base_url 可对接 OpenAI、Azure、本地 vLLM、Ollama 等兼容服务。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from gaokao_nl2sql.errors import SqlGenerationError


class ChatModel(Protocol):
    """最小聊天补全接口，便于在测试中替换为 mock。"""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """返回模型对给定提示的文本回复。"""
        ...


@dataclass(slots=True)
class OpenAICompatibleModel:
    """OpenAI 兼容聊天补全客户端。"""

    base_url: str
    api_key: str
    model: str
    temperature: float = 0.0
    timeout: float = 30.0

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        try:
            response = httpx.post(
                url, headers=headers, json=payload, timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise SqlGenerationError(f"LLM 调用失败: {exc}") from exc
