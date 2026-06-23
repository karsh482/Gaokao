FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pytest.ini ./
COPY packages/nl2sql ./packages/nl2sql
COPY packages/rag ./packages/rag
COPY apps/api ./apps/api

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir \
        -e "packages/nl2sql[db]" \
        -e "packages/rag[db]" \
        -e "apps/api"

COPY scripts ./scripts

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "apps/api"]
