# Design Document

## Overview

Policy RAG MVP 在现有 `policy_document` 表上实现最小闭环：

```text
Local Policy Files
    ↓
DocumentLoader
    ↓
EmbeddingProvider
    ↓
PolicyDocumentRepository
    ↓
PolicyRetriever / PolicyRagPipeline
    ↓
FastAPI /policy/query
```

本阶段只返回检索候选和引用，不生成最终答案。这样可以先验证数据、向量列、pgvector 检索和 API 契约，再进入答案合成与 Semantic Router。

## Components

### DocumentLoader

职责：

- 读取本地 Markdown、TXT、HTML 文件。
- 清洗 HTML 标签与多余空白。
- 生成 `content_hash`。
- 输出 `PolicyDocumentInput`。

不负责：

- 网络爬取。
- PDF 解析。
- 文档切分。

### EmbeddingProvider

职责：

- 定义 `embed(text) -> list[float]` 抽象。
- 提供 OpenAI 兼容 `/embeddings` 客户端。
- 显式超时、有限重试、指数退避和抖动。
- 校验可选向量维度。

测试中使用 fake provider，不访问外部网络。

### PolicyDocumentRepository

职责：

- 写入 `policy_document`，通过 `content_hash` 去重。
- 使用 `embedding <=> query_embedding` 执行 pgvector 余弦距离检索。
- 支持省份和文档类型过滤。

数据库表沿用 `packages/schema/001_core_tables.sql` 中的 `policy_document`。

### PolicyRagPipeline

职责：

- 校验问题非空。
- 调用 embedding provider 生成问题向量。
- 调用 repository 检索。
- 生成片段、引用和提示。

不负责：

- LLM 答案合成。
- rerank。
- Agent 路由。

### API

新增 `POST /policy/query`：

- 请求：`question`、`province`、`plan_year`、`document_type`、`top_k`。
- 响应：`question`、`result_count`、`results`、`citations`、`notes`。

沿用现有 `X-API-Key` 鉴权依赖。

## Data Flow

1. 用户调用 `/policy/query`。
2. API 依赖装配 `PolicyRagPipeline`。
3. Pipeline 生成问题向量。
4. Repository 查询 `policy_document`。
5. Pipeline 返回候选片段和 citations。
6. API 序列化响应。

## Error Handling

- 空问题由 Pydantic 拒绝。
- 嵌入服务异常包装为 `EmbeddingError`。
- 数据库异常包装为 `PolicyRepositoryError`。
- API 将 RAG 运行错误映射为 500。

## Out of Scope

- 政策文档自动采集。
- PDF / DOCX 解析。
- 文档 chunk 表结构。
- rerank。
- 自然语言答案合成。
- Semantic Router 与 Query Catalog 的统一入口路由。
