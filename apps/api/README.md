# Gaokao NL2SQL API

对高考招生公开数据的自然语言查询服务。把问题转成只读 SQL，在 PostgreSQL 上执行后返回结果。

## 架构

```text
POST /query (自然语言)
   -> packages/nl2sql: SqlGenerator (LLM 生成 SQL)
   -> packages/nl2sql: validate_select_sql (安全护栏：单条 SELECT / 强制 LIMIT / 拒绝写操作)
   -> packages/nl2sql: PostgresExecutor (只读事务 + statement_timeout)
   -> 结构化结果
```

当前查询面为 staging 层与主数据表（`staging.admission_records`、`staging.score_segments`、
`province`、`school`），详见 `packages/nl2sql/gaokao_nl2sql/schema_context.py`。

## 安装

```bash
pip install -e packages/nl2sql[db]
pip install -e packages/rag[db]
pip install -e apps/api[dev]
```

如需本地 `sentence-transformers` Embedding 模型，再安装：

```bash
pip install -e apps/api[local-embedding]
```

## 配置

复制 `apps/api/.env.example` 为 `.env` 并填写：

- `GAOKAO_DATABASE_URL`：数据库连接串，建议使用只读角色。
- `GAOKAO_LLM_BASE_URL` / `GAOKAO_LLM_API_KEY` / `GAOKAO_LLM_MODEL`：OpenAI 兼容 LLM。
  默认使用 DeepSeek V4 Flash：`base_url=https://api.deepseek.com`，
  `model=deepseek-v4-flash`，只需填入 DeepSeek 的 API Key。
- `GAOKAO_RAG_ANSWER_ENABLED`：是否让 `/policy/query` 基于检索 chunk 生成最终答案。
  默认 `false`，只返回候选 chunk；设为 `true` 且配置 LLM API Key 后返回 `answer`。
- `GAOKAO_RAG_ANSWER_MAX_CONTEXT_CHARS` / `GAOKAO_RAG_ANSWER_MAX_HITS`：限制答案生成使用的
  上下文总长度和命中组数，避免把大量重复 chunk 塞进 LLM。
- `GAOKAO_EMBEDDING_PROVIDER` / `GAOKAO_EMBEDDING_MODEL` / `GAOKAO_EMBEDDING_DIMENSION`：
  Embedding 查询向量配置。本地 Python 默认 `local`，使用 `sentence-transformers` 加载
  `Qwen/Qwen3-Embedding-4B`，需与 `rag_chunk.embedding` 的 2560 维向量保持一致。
  Docker Compose 一键环境默认覆盖为 `openai`，避免启动时下载本地大模型。
- `GAOKAO_EMBEDDING_CACHE_FOLDER`：本地 embedding 模型缓存目录，默认 `models`，
  即从项目根目录启动 API 时使用 `D:\Gaokao\Gaokao\models`。
- `GAOKAO_EMBEDDING_BASE_URL` / `GAOKAO_EMBEDDING_API_KEY`：
  仅在 `GAOKAO_EMBEDDING_PROVIDER=openai` 时使用，用于 OpenAI 兼容 Embedding API。
- `GAOKAO_API_KEY`：可选。设置后 `/query` 需要请求头 `X-API-Key`。

## 安全提醒

- 未设置 `GAOKAO_API_KEY` 时 `/query` 无鉴权，仅用于本地开发。生产环境必须设置。
- SQL 护栏是文本层校验，应与只读数据库角色配合形成纵深防御。建议为本服务创建仅有
  `SELECT` 权限的数据库用户，连接串使用该用户。

## 运行

先按 `docs/staging-import.md` 用 Docker 起库并导入数据，然后：

```bash
uvicorn app.main:app --reload --app-dir apps/api
```

- 健康检查：`GET /health`
- 查询：`POST /query`，body `{"question": "贵州2025历史类，位次一万能上哪些学校？"}`
- 录取参考：`POST /query`，body `{"question": "贵州物理类 位次10000 能不能上贵州大学？"}`
- RAG 检索：`POST /policy/query`，body `{"question":"北京大学基础医学有哪些二级学科研究方向？","school":"北京大学","year":2026,"category":"university_admission_chapter","top_k":5}`
- 交互文档：`http://localhost:8000/docs`

## 测试

```bash
pytest apps/api -q
```

## RAG Chunk 检索接口

`POST /policy/query` 用于检索政策 / 招生章程等 RAG chunk。默认返回候选片段、扩展上下文与引用；
当 `GAOKAO_RAG_ANSWER_ENABLED=true` 且配置了 `GAOKAO_LLM_API_KEY` 时，会额外返回基于 chunk 生成的 `answer`。

示例请求：

```bash
curl -X POST "http://127.0.0.1:8000/policy/query" \
  -H "Content-Type: application/json" \
  -d '{"question":"北京大学基础医学有哪些二级学科研究方向？","school":"北京大学","year":2026,"category":"university_admission_chapter","top_k":5,"include_context":false}'
```

响应重点字段：

- `answer`：可选。启用 RAG 答案生成后返回；未启用或生成失败时为 `null`。
- `results`：chunk 候选片段、相似度、页码、标题路径和来源 URL。默认不返回完整
  `context_text`；调试召回上下文时传 `include_context=true`。
- `citations`：标题、来源 URL、学校、年份、页码、标题路径和 chunk ID。
- `notes`：检索范围、答案生成状态或降级提示。

导入已清洗索引：

```bash
export GAOKAO_DATABASE_URL="postgresql://gaokao:gaokao_dev_password@localhost:15432/gaokao"
PYTHONPATH=packages/rag python scripts/import_rag_index.py \
  "/mnt/d/gaokao/未清洗数据/rag知识库/高校政策/2026/北京大学/2026_北京大学本科招生章程/rag_index.jsonl" \
  --chunks-jsonl "/mnt/d/gaokao/未清洗数据/rag知识库/高校政策/2026/北京大学/2026_北京大学本科招生章程/chunks.jsonl"
```

`--chunks-jsonl` 可选，但建议传入；它会补充 `section_id`、`previous_chunk_id`、`next_chunk_id`，
用于命中后扩展同文档同章节上下文。
导入脚本直接读取 `rag_index.jsonl` 中已有向量，不会调用在线 Embedding 服务；在线 Embedding
只在 `GAOKAO_EMBEDDING_PROVIDER=openai` 时用于 `/policy/query` 的问题向量生成。
默认本地模式会在首次 `/policy/query` 时加载本地 embedding 模型。

## 录取参考查询

`POST /query` 已内置确定性模板 `admission_feasibility_lookup`，用于回答“我这个分数/位次能不能上某校/某专业”。
该能力基于历史最低分/最低位次给出 `冲` / `稳` / `保` 参考，不是概率模型。

示例：

```bash
curl -X POST "http://127.0.0.1:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"question":"贵州物理类 位次10000 能不能上贵州大学？","exam_province":"贵州","plan_year":2025}'
```

响应重点字段：

- `summary`：可直接展示给用户的保守结论，包含参考档位、依据和“非概率模型”提示。
- `rows[].confidence_band`：`冲` / `稳` / `保`。
- `rows[].rank_gap`：院校/专业最低位次 - 考生位次；差值越大表示考生位次相对越优。
- `rows[].confidence_note`：口径说明。分数查询会提示优先使用位次评估。

## Query Catalog 真实库 E2E

启动并导入本地 PostgreSQL 后，可运行固定问题集验证 Query Catalog、模板 SQL、来源标注和短路逻辑：

```bash
docker compose up -d gaokao-postgres
export GAOKAO_DATABASE_URL="postgresql://gaokao:gaokao_dev_password@localhost:15432/gaokao"
python scripts/query_catalog_e2e.py
```

该脚本会验证学校查询、位次筛选、地域查询、专项查询、选科要求、范围外请求和趋势类短路。
未配置 `GAOKAO_LLM_API_KEY` 时，只验证模板命中与短路路径；配置 LLM 后可继续扩展验证回退路径。

响应中的 `coverage_warnings` 用于区分“没有匹配结果”和“字段整体暂无数据”。例如当前
`selection_requirements` 覆盖率为 0，选科要求查询返回 0 行时会附带覆盖率缺口说明。

脚本还会验证多条件筛选模板 `multi_filter_lookup`，用于位次/分数叠加公办民办、学费、
专业关键词和城市条件的查询。
