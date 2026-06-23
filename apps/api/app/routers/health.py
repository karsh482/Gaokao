"""健康检查。"""

from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.models import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    database = "ok"
    try:
        import psycopg

        with psycopg.connect(settings.database_url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
    except Exception as exc:  # noqa: BLE001 - 健康检查不应抛出
        database = f"error: {exc}"

    status = "ok" if database == "ok" else "degraded"
    return HealthResponse(status=status, database=database)
