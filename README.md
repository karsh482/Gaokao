# Gaokao RAG Lab

中国高考领域开源 AI 数据基础设施实验项目。项目目标是把公开招生数据、录取数据、政策文档检索和自然语言查询能力整理成一套可本地复现的开发环境，方便继续构建：

- 高考招生数据查询服务
- 中文 NL2SQL / Query Catalog
- 政策、章程、招生简章 RAG 检索
- 志愿推荐、教育 Copilot 和 Agent 工作流

## 当前可用能力

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| Docker 一键环境 | 可用 | 一键启动 PostgreSQL + pgvector、FastAPI、Web 查询台 |
| 公开结构化样例数据 | 可用 | 内置贵州 2025 投档线 / 一分一段 staging CSV，以及省份、院校主数据 |
| `/query` 结构化查询 | 可用，持续迭代 | 支持按省份、年份、学校、专业、分数、位次等条件查询 |
| `/policy/query` RAG 接口 | 可用，需导入数据 | 表结构、导入脚本、检索接口已具备；开源仓库暂不内置 RAG 知识库 JSONL |
| Agent / 评测 | 规划中 | 详见 [docs/roadmap.md](docs/roadmap.md) |

> 默认一键启动后，结构化招生数据查询可以直接使用。RAG 政策检索需要先按 [docs/rag-import.md](docs/rag-import.md) 导入自己的 `rag_index.jsonl` / `chunks.jsonl`。

## 技术栈

- Web：Vite + React + TypeScript
- API：FastAPI
- 数据库：PostgreSQL + pgvector
- 检索：chunk-level RAG + HNSW 向量索引
- NL2SQL：Query Catalog + 只读 SQL 安全校验
- 部署：Docker Compose

## 一键拉取并启动

前置条件：

- Git
- Docker Desktop 或 Docker Engine
- 首次启动需要能拉取 Docker 镜像，并安装镜像构建过程中的 npm / pip 依赖

从零开始：

```bash
git clone https://github.com/karsh482/Gaokao.git
cd Gaokao
cp .env.example .env
docker compose up -d --build
```

启动后访问：

- Web 查询台：<http://localhost:5173>
- API 健康检查：<http://localhost:8000/health>
- API 文档：<http://localhost:8000/docs>
- PostgreSQL：`localhost:15432`

查看容器状态：

```bash
docker compose ps
```

查看运行日志：

```bash
docker compose logs -f
```

如果想在前台直接看构建和运行日志，也可以使用：

```bash
docker compose up --build
```

## 验证项目是否跑通

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

结构化查询示例：

```bash
curl -X POST "http://127.0.0.1:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"question":"贵州物理类 位次10000 能不能上贵州大学？","exam_province":"贵州","plan_year":2025}'
```

查看数据库样例数据行数：

```bash
docker compose exec -T gaokao-postgres psql -U gaokao -d gaokao -c "
SELECT
  (SELECT count(*) FROM staging.source_files) AS source_file_count,
  (SELECT count(*) FROM staging.admission_records) AS admission_record_count,
  (SELECT count(*) FROM staging.score_segments) AS score_segment_count;
"
```

当前贵州 2025 staging 数据预期结果：

```text
source_file_count = 16
admission_record_count = 24643
score_segment_count = 10574
```

## 环境变量

复制 `.env.example` 后即可本地运行：

```bash
cp .env.example .env
```

常用配置：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `GAOKAO_WEB_HOST_PORT` | `5173` | Web 查询台宿主机端口 |
| `GAOKAO_API_HOST_PORT` | `8000` | FastAPI 宿主机端口 |
| `GAOKAO_POSTGRES_HOST_PORT` | `15432` | PostgreSQL 宿主机端口 |
| `GAOKAO_LLM_API_KEY` | 空 | 可选。配置后可启用 LLM 意图抽取和答案生成 |
| `GAOKAO_API_KEY` | 空 | 可选。配置后 API 请求需要 `X-API-Key` 请求头 |
| `GAOKAO_EMBEDDING_API_KEY` | 空 | 可选。RAG 查询使用 OpenAI 兼容 Embedding API 时需要 |

未设置 `GAOKAO_API_KEY` 时接口默认无鉴权，只建议本地开发使用。

## 数据范围

开源仓库当前包含：

- `data/processed/master/`：省份、院校等公开主数据
- `data/processed/guizhou/2025/`：贵州 2025 投档线、来源文件、一分一段 staging CSV
- `packages/schema/`：核心表、staging 表、RAG 表结构和 Docker 初始化脚本

开源仓库当前不包含：

- 私有 ETL 清洗代码
- `/data/未清洗数据`
- RAG 知识库产物，例如 `rag_index.jsonl`、`chunks.jsonl`
- 本地模型缓存

Docker 首次创建数据库 volume 时，会自动建表并导入 `data/processed/` 下的公开样例数据。后续如果修改 schema 或 CSV，已有 volume 不会自动重新初始化，需要按下一节重建数据库。

## 重建或清理本地环境

停止容器但保留数据库 volume：

```bash
docker compose down
```

删除容器并重建本地开发数据库：

```bash
docker compose down -v
docker compose up -d --build
```

`docker compose down -v` 会删除本项目的 PostgreSQL volume，数据库中的本地数据会被清空。适合修改 schema、CSV 后重新初始化。

如果还想删除本项目构建出的本地镜像：

```bash
docker compose down -v --rmi local --remove-orphans
```

## RAG 知识库导入

本仓库已经提供 RAG 表结构、导入脚本和 `/policy/query` 接口，但没有随仓库发布完整政策 / 招生章程知识库数据。

导入脚本在本机 Python 环境执行。首次使用前先安装 RAG 包及数据库依赖：

```bash
python -m pip install -e "packages/rag[db]"
```

导入外部 RAG 索引的基本流程：

```bash
export GAOKAO_DATABASE_URL="postgresql://gaokao:gaokao_dev_password@localhost:15432/gaokao"

PYTHONPATH=packages/rag python3 scripts/import_rag_index.py \
  "/path/to/rag_index.jsonl" \
  --chunks-jsonl "/path/to/chunks.jsonl"
```

导入后可调用：

```bash
curl -X POST "http://127.0.0.1:8000/policy/query" \
  -H "Content-Type: application/json" \
  -d '{"question":"北京大学基础医学有哪些二级学科研究方向？","school":"北京大学","year":2026,"category":"university_admission_chapter","top_k":5}'
```

完整说明见 [docs/rag-import.md](docs/rag-import.md)。

## 本地开发

只启动数据库：

```bash
docker compose up -d gaokao-postgres
```

安装 Python 包：

```bash
python -m pip install -e "packages/nl2sql[db,dev]"
python -m pip install -e "packages/rag[db,dev]"
python -m pip install -e "apps/api[dev]"
```

启动 API：

```bash
uvicorn app.main:app --reload --app-dir apps/api
```

启动 Web：

```bash
cd apps/web
npm install
npm run dev
```

运行测试：

```bash
pytest packages/nl2sql packages/rag apps/api -q
```

## 项目结构

```text
apps/
  api/                 FastAPI 服务
  web/                 Vite + React 查询台
data/
  processed/           可公开发布的结构化样例数据
docs/                  数据导入、schema、RAG 和路线图文档
packages/
  nl2sql/              Query Catalog、NL2SQL、SQL 安全校验
  rag/                 RAG chunk 模型、导入、检索
  schema/              PostgreSQL 初始化脚本
scripts/
  import_rag_index.py  RAG JSONL 导入脚本
  query_catalog_e2e.py Query Catalog 真实库验证脚本
```

## 常见问题

### 端口被占用

修改 `.env` 中的端口：

```text
GAOKAO_WEB_HOST_PORT=5173
GAOKAO_API_HOST_PORT=8000
GAOKAO_POSTGRES_HOST_PORT=15432
```

修改后重新启动：

```bash
docker compose up -d --build
```

### 修改 CSV 或 schema 后数据没变化

PostgreSQL 官方镜像只会在数据目录为空时执行初始化脚本。需要重建 volume：

```bash
docker compose down -v
docker compose up -d --build
```

### `/policy/query` 没有检索结果

一键启动不会自动导入 RAG 知识库。请先导入 `rag_index.jsonl`，再查询 `/policy/query`。

### 没有配置 LLM API Key 能不能用

可以使用结构化查询的确定性模板和 SQL 查询能力；自然语言答案生成、部分 LLM 意图抽取和 RAG 答案生成会自动跳过。需要这些能力时，在 `.env` 中配置 `GAOKAO_LLM_API_KEY`。

## 更多文档

- [docs/staging-import.md](docs/staging-import.md)：结构化 CSV 导入与校验
- [docs/rag-import.md](docs/rag-import.md)：RAG 索引导入与验证
- [docs/schema.md](docs/schema.md)：核心数据模型
- [docs/schema-decisions.md](docs/schema-decisions.md)：schema 设计取舍
- [docs/roadmap.md](docs/roadmap.md)：路线图
- [apps/api/README.md](apps/api/README.md)：API 开发说明

## License

Apache License 2.0. See [LICENSE](LICENSE).
