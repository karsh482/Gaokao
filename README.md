
# Gaokao RAG Lab

## 中国高考领域开源 AI 数据基础设施计划

### 愿景
我们希望构建中国高考领域的开源 AI 基础设施，让开发者能够基于公开数据快速构建：

- RAG 系统
- NL2SQL 系统
- Agent 智能体
- 志愿推荐系统
- 教育领域 Copilot

---

## 当前进度

| 层 | 状态 |
| --- | --- |
| 数据基础设施（schema / Docker / 贵州 2025 数据 / 院校主数据 / ETL 工具链） | ✅ 可用 |
| NL2SQL + FastAPI 查询闭环 | 🚧 进行中 |
| RAG chunk 检索 | 🚧 进行中 |
| Agent / 前端 / 评测 | ⏳ 未开始 |

详细里程碑与待办见 [docs/roadmap.md](docs/roadmap.md)。

---

## 技术架构

```text
User Query
    ↓
Semantic Router
    ↓
┌──────────────┬──────────────┐
│              │              │
SQL Agent    RAG Agent   Analytics Agent
│              │              │
PostgreSQL   pgvector    Metrics
│              │
Admission DB  Policy Docs
└───────┬──────┘
        ↓
Answer Synthesis
```

---

## 核心研究方向

### P1
- 中文 NL2SQL
- Query Router
- Schema Linking

### P2
- Hybrid RAG
- Benchmark Construction
- Hallucination Detection

### P3
- GraphRAG
- Recommendation Engine
- Admission Probability

---

## 第一阶段

省份：

- 贵州
- 四川

数据：

- 院校库
- 专业库
- 一分一段
- 投档线
- 招生章程

---

## 技术栈

- Next.js
- FastAPI
- PostgreSQL
- pgvector
- LlamaIndex
- LangGraph
- Qwen3-Embedding-4B
- Docker

---

## 一键启动

本项目提供 Docker Compose 本地开发环境，默认会启动 PostgreSQL、FastAPI 和 Web 查询台。

前置条件：

- Docker Desktop / Docker Engine
- 首次启动需要能拉取 Docker 镜像和 npm / pip 依赖

启动：

```bash
cp .env.example .env
docker compose up --build
```

启动后访问：

- Web 查询台：<http://localhost:5173>
- API 健康检查：<http://localhost:8000/health>
- API 文档：<http://localhost:8000/docs>
- PostgreSQL：`localhost:15432`

首次创建数据库 volume 时，Compose 会自动建表并导入 `data/processed/` 下的公开样例数据。
当前贵州 2025 staging 数据预期包含：

- `staging.source_files`：16 行
- `staging.admission_records`：24643 行
- `staging.score_segments`：10574 行

如果修改了 schema 或 CSV，需要重建本地开发数据库：

```bash
docker compose down -v
docker compose up --build
```

默认一键环境优先保证录取查询可用；RAG `/policy/query` 默认使用 OpenAI 兼容 Embedding
配置，不会在容器启动时下载本地 embedding 大模型。如需政策检索，请在 `.env` 中配置
`GAOKAO_EMBEDDING_API_KEY`，或按 `docs/rag-import.md` 切换成本地模型模式。

---

## 招募

欢迎有意向一起研究相关项目内容的：

- AI工程师
- 数据工程师
- 前端工程师
- 教育行业从业者
- 高考志愿顾问
