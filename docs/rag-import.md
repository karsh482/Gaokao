# RAG 索引导入与验证

本文说明如何把私有清洗流程产出的 `rag_index.jsonl` 导入开源项目数据库。

## 数据表

RAG 使用 chunk 级表结构：

- `rag_document`：文档级元数据，如标题、学校、年份、类别、来源 URL。
- `rag_chunk`：可检索片段、页码、标题路径、表格标题、上下文关系、引用和向量。

当前向量列为 `HALFVEC(2560)`，对应 `Qwen/Qwen3-Embedding-4B`。使用 `HALFVEC`
是为了支持 2560 维向量的 HNSW 索引。

## 初始化或升级本地库

新建数据库会自动执行 `packages/schema/001_core_tables.sql`。

已有开发库可执行增量脚本：

```bash
docker cp "packages/schema/005_rag_tables.sql" "gaokao-postgres:/tmp/005_rag_tables.sql"
docker compose exec -T gaokao-postgres \
  psql -U gaokao -d gaokao -f /tmp/005_rag_tables.sql
```

该脚本会删除旧的 `policy_document` 表，并创建 `rag_document` / `rag_chunk`。

## 导入索引

```bash
export GAOKAO_DATABASE_URL="postgresql://gaokao:gaokao_dev_password@localhost:15432/gaokao"

PYTHONPATH=packages/rag python3 scripts/import_rag_index.py \
  "/mnt/d/gaokao/未清洗数据/rag知识库/高校政策/2026/北京大学/2026_北京大学本科招生章程/rag_index.jsonl" \
  --chunks-jsonl "/mnt/d/gaokao/未清洗数据/rag知识库/高校政策/2026/北京大学/2026_北京大学本科招生章程/chunks.jsonl"
```

`--chunks-jsonl` 建议传入。它会把 `section_id`、`previous_chunk_id`、`next_chunk_id`
合并到入库记录中，检索命中后可以扩展同文档同章节上下文。

## 验证

查看入库数量：

```bash
docker compose exec -T gaokao-postgres psql -U gaokao -d gaokao -c "
SELECT
  (SELECT count(*) FROM rag_document) AS rag_document_count,
  (SELECT count(*) FROM rag_chunk) AS rag_chunk_count,
  (SELECT count(*) FROM rag_chunk WHERE section_id IS NOT NULL) AS chunks_with_section;
"
```

查看向量索引：

```bash
docker compose exec -T gaokao-postgres psql -U gaokao -d gaokao -c "
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'rag_chunk'
  AND indexname = 'idx_rag_chunk_embedding_hnsw';
"
```

## API 检索

`/policy/query` 会实时生成查询向量，并到 `rag_chunk` 做向量检索。默认使用本地
`sentence-transformers` 加载 `Qwen/Qwen3-Embedding-4B`，需要与入库时 `rag_index.jsonl`
中的 embedding 模型保持一致。

```bash
GAOKAO_EMBEDDING_PROVIDER=local
GAOKAO_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-4B
GAOKAO_EMBEDDING_DIMENSION=2560
GAOKAO_EMBEDDING_DEVICE=auto
GAOKAO_EMBEDDING_TORCH_DTYPE=auto
GAOKAO_EMBEDDING_CACHE_FOLDER=models
GAOKAO_EMBEDDING_NORMALIZE=true
GAOKAO_EMBEDDING_QUERY_INSTRUCTION_ENABLED=true
```

首次查询会加载本地模型，耗时和显存占用会明显高于后续查询。`GAOKAO_EMBEDDING_DEVICE`
留空或设为 `auto` 时由 `sentence-transformers` 自动选择设备；也可以显式设置为 `cuda`
或 `cpu`。`GAOKAO_EMBEDDING_CACHE_FOLDER=models` 会把本地模型缓存固定到项目根目录
`models/` 下，避免默认写入系统盘缓存目录。

如需切回 OpenAI 兼容 Embedding API，可设置：

```bash
GAOKAO_EMBEDDING_PROVIDER=openai
GAOKAO_EMBEDDING_BASE_URL=https://api-inference.modelscope.cn/v1
GAOKAO_EMBEDDING_API_KEY=your-token
GAOKAO_EMBEDDING_ENCODING_FORMAT=float
```

不要把真实 Token 写入仓库，建议只放在本机 `.env` 或部署环境变量中。

`/policy/query` 默认只返回候选 chunk、上下文和引用。需要生成最终自然语言答案时，开启：

```bash
GAOKAO_RAG_ANSWER_ENABLED=true
GAOKAO_LLM_BASE_URL=https://api.deepseek.com
GAOKAO_LLM_API_KEY=your-token
GAOKAO_LLM_MODEL=deepseek-v4-flash
GAOKAO_RAG_ANSWER_MAX_CONTEXT_CHARS=12000
GAOKAO_RAG_ANSWER_MAX_HITS=3
```

答案生成复用检索结果，不改变 `rag_chunk` 入库数据。生成失败时接口仍返回候选 chunk，
并在 `notes` 中说明降级原因。`GAOKAO_RAG_ANSWER_MAX_HITS` 会限制进入 LLM 的去重命中组数，
`GAOKAO_RAG_ANSWER_MAX_CONTEXT_CHARS` 会限制上下文总长度，避免 top-k 扩展上下文过大。

请求示例：

```bash
curl -X POST "http://127.0.0.1:8000/policy/query" \
  -H "Content-Type: application/json" \
  -d '{"question":"北京大学基础医学有哪些二级学科研究方向？","school":"北京大学","year":2026,"category":"university_admission_chapter","top_k":5,"include_context":false}'
```

默认 `include_context=false`，响应中只返回 snippet、引用和 context chunk id。需要人工排查召回上下文时，
可在请求体中设置 `include_context=true`。
