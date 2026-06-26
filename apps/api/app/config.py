"""服务配置，从环境变量 / .env 读取。"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="GAOKAO_",
        extra="ignore",
    )

    # 数据库连接串（建议使用只读角色）。
    database_url: str = "postgresql://gaokao:gaokao_dev_password@localhost:15432/gaokao"

    # LLM（OpenAI 兼容）配置。默认 DeepSeek V4 Flash。
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_model: str = "deepseek-v4-flash"
    llm_temperature: float = 0.0
    llm_timeout: float = 60.0
    llm_intent_enabled: bool = True

    # ai-gpurent-cli LLM_TEXT_CHAT 代理配置。API Key 可由 Web 请求头传入。
    ai_gpurent_base_url: str = "http://127.0.0.1:8080"
    ai_gpurent_api_key: str = ""
    ai_gpurent_provider: str = "deepseek"
    ai_gpurent_task_timeout_sec: int = 300
    ai_gpurent_poll_timeout: float = 300.0
    ai_gpurent_poll_interval: float = 1.0
    ai_gpurent_http_timeout: float = 15.0

    # SQL 查询答案生成。默认开启；未配置 LLM Key 时会自动跳过。
    sql_answer_enabled: bool = True
    sql_answer_max_rows: int = 20
    sql_answer_max_chars: int = 12_000

    # RAG 答案生成。默认关闭，只返回检索候选；开启后复用 LLM 配置。
    rag_answer_enabled: bool = False
    rag_answer_max_context_chars: int = 12_000
    rag_answer_max_hits: int = 3

    # Embedding 配置。默认使用本地 sentence-transformers，与 rag_index.jsonl 入库向量保持一致。
    embedding_provider: str = "local"
    embedding_base_url: str = "https://api-inference.modelscope.cn/v1"
    embedding_api_key: str = ""
    embedding_model: str = "Qwen/Qwen3-Embedding-4B"
    embedding_dimension: int = 2560
    embedding_encoding_format: str | None = "float"
    embedding_max_retries: int = 3
    embedding_device: str | None = None
    embedding_torch_dtype: str | None = "auto"
    embedding_max_seq_length: int | None = None
    embedding_cache_folder: str | None = "models"
    embedding_normalize: bool = True
    embedding_query_instruction_enabled: bool = True

    # 可选 API Key 鉴权；为空时不鉴权（仅建议用于本地开发）。
    api_key: str = ""

    # 查询限制。
    default_limit: int = 200
    max_limit: int = 1000
    policy_default_top_k: int = 5
    policy_max_top_k: int = 20
    statement_timeout_ms: int = 10_000


@lru_cache
def get_settings() -> Settings:
    return Settings()
