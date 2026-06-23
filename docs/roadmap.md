# 路线图

本文记录 Gaokao RAG Lab 的阶段目标与当前进度。愿景与技术架构见 [README](../README.md)。

## 当前进度总览

| 层 | 模块 | 状态 |
| --- | --- | --- |
| 数据基础设施 | 核心 schema（`packages/schema/001_core_tables.sql`） | ✅ 完成 |
| 数据基础设施 | staging schema（`002_staging_tables.sql`） | ✅ 完成 |
| 数据基础设施 | Docker 部署与自动导入种子脚本 | ✅ 完成 |
| 数据基础设施 | 贵州 2025 投档数据（24643 条）、分数段（10574 条） | ✅ 已入库 |
| 数据基础设施 | 院校 / 省份主数据（2919 所 / 31 省） | ✅ 已入库 |
| 数据基础设施 | 私有 ETL 工具链（PDF 解析、清洗、导出） | ✅ 可用 |
| 数据基础设施 | 招生专业目录解析、四川数据、major 主数据 | ⏳ 待办 |
| AI 应用 | NL2SQL（自然语言查询） | 🚧 进行中 |
| AI 应用 | FastAPI 后端 | 🚧 进行中 |
| AI 应用 | RAG / 政策与招生章程 chunk 检索 | 🚧 进行中 |
| AI 应用 | Semantic Router / Agent 编排 | ⏳ 未开始 |
| AI 应用 | Next.js 前端 | ⏳ 未开始 |
| AI 应用 | 评测 benchmark | ⏳ 未开始 |

> 数据“可查询”的来源目前是 staging 层（`staging.admission_records`、`staging.score_segments`）
> 与主数据表（`province`、`school`）。核心 `admission_record` 表在完成 school_id / major_id
> 映射前仍为空，NL2SQL 当前以 staging 层为主要查询面。

## 阶段 0：项目管理与现状对齐

- [x] 填写本路线图
- [x] README 增加“当前进度”章节
- [x] 私有 ETL 仓库补充 pytest 开发依赖
- [x] 增加最小 CI（测试 + processed CSV 契约校验）

## 阶段 1：让数据可查询——最小 NL2SQL + API 闭环

- [x] `packages/nl2sql`：自然语言 → 只读 SQL
  - [x] Schema Linking：向 LLM 提供可查询表结构上下文
  - [x] SQL 安全护栏：仅允许单条 SELECT，强制 LIMIT，拒绝写操作
  - [x] 只读执行器（READ ONLY 事务 + statement_timeout）
  - [x] 单元测试覆盖护栏与流程（mock LLM / DB，26 项）
- [x] `apps/api`：FastAPI 服务
  - [x] `/health` 健康检查
  - [x] `/query` 自然语言查询接口
  - [x] 可选 API Key 鉴权
  - [x] API 测试（依赖覆盖，3 项）
- [ ] 端到端跑通贵州 2025 真实数据 demo（需本地起 Docker 数据库 + 配置 LLM API Key）

## 阶段 2：扩充数据覆盖

- [ ] 招生专业目录 / 招生计划公共 CSV 契约
- [ ] 招生计划 staging 表
- [ ] 双栏 PDF 目录解析器（物理类 / 历史类 / 2026 高职）
- [ ] 四川省数据接入
- [ ] major 主数据补齐

## 阶段 3：RAG 与政策 / 招生章程检索

- [x] 政策 / 章程文档采集入 `rag_document` / `rag_chunk`
- [x] `packages/rag`：Qwen3-Embedding-4B 向量检索（2560 维）
- [x] HNSW 语义检索
- [x] `/policy/query` 返回 chunk 候选、上下文和引用
- [ ] Hybrid RAG（向量 + 关键词）

## 阶段 4：Agent 编排与前端

- [ ] Semantic Router（SQL / RAG / Analytics 路由）
- [ ] LangGraph 编排多 Agent + 答案合成
- [ ] `apps/web`：Next.js 问答界面
- [ ] `packages/evals`：benchmark 与幻觉检测

## 阶段 5：高级研究方向

- [ ] 志愿推荐引擎
- [ ] 录取概率模型
- [ ] GraphRAG
