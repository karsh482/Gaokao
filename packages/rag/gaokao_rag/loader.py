"""RAG 索引文件加载器。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from gaokao_rag.errors import DocumentLoadError
from gaokao_rag.models import RagChunkInput
from gaokao_rag.repository import chunk_from_rag_index_record


def content_hash(content: str) -> str:
    """返回正文的小写 SHA-256。"""

    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RagIndexLoader:
    """读取私有清洗流程产出的 rag_index.jsonl。"""

    def iter_file(self, path: str | Path) -> Iterator[RagChunkInput]:
        file_path = Path(path).expanduser()
        if file_path.suffix.lower() != ".jsonl":
            raise DocumentLoadError(f"不支持的 RAG 索引格式: {file_path.suffix or '(无后缀)'}")
        try:
            with file_path.open(encoding="utf-8") as file:
                for line_number, line in enumerate(file, start=1):
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        record = json.loads(stripped)
                        yield chunk_from_rag_index_record(record)
                    except Exception as exc:  # noqa: BLE001 - 补充文件行号后统一抛出
                        raise DocumentLoadError(
                            f"{file_path}:{line_number} RAG 索引记录无效: {exc}"
                        ) from exc
        except OSError as exc:
            raise DocumentLoadError(f"读取 RAG 索引失败: {file_path}") from exc

    def load_file(self, path: str | Path) -> list[RagChunkInput]:
        """一次性加载全部 chunk，适用于小型样例或测试。"""

        return list(self.iter_file(path))


# 兼容旧导入名。旧 DocumentLoader 已替换为 rag_index.jsonl 加载器。
DocumentLoader = RagIndexLoader
