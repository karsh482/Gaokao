
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

## 招募

欢迎有意向一起研究相关项目内容的：

- AI工程师
- 数据工程师
- 前端工程师
- 教育行业从业者
- 高考志愿顾问

