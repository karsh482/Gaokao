"""FastAPI 应用入口。"""

from __future__ import annotations

from fastapi import FastAPI

from app.config import get_settings
from app.routers import health, policy, query


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Gaokao NL2SQL API",
        version="0.1.0",
        description="对高考招生公开数据的自然语言查询服务。",
    )
    app.include_router(health.router)
    app.include_router(query.router)
    app.include_router(policy.router)

    if not settings.api_key:
        import warnings

        warnings.warn(
            "GAOKAO_API_KEY 未设置，/query 接口当前无鉴权，仅建议用于本地开发。",
            stacklevel=2,
        )

    return app


app = create_app()
