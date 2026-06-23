# Requirements Document

## Introduction

本文档定义 Gaokao RAG Lab 的 **Policy RAG（政策 / 招生章程检索）** MVP。该阶段目标是承接 Query Catalog 中已识别但尚未支持的政策解释类问题，用可追溯的政策文档检索结果替代结构化数据查询。

本阶段只实现“文档入库、向量检索、引用返回”的最小闭环，不做最终答案合成、复杂 rerank、Agent 编排或 GraphRAG。

## Glossary

- **Policy_Document（政策文档）**：保存在 `policy_document` 表中的招生政策、招生章程、规则说明等非结构化文本。
- **Embedding（向量）**：用于语义检索的文本向量，当前数据库列固定为 1024 维，对应 BGE-M3。
- **Hybrid Retrieval（混合检索）**：以向量检索为主，结合省份、文档类型、年份等确定性过滤条件。
- **Citation（引用）**：返回给用户的来源信息，至少包含文档标题、来源 URL、文档类型和发布时间。

## Requirements

### Requirement 1: 政策文档导入

**User Story:** 作为开发者，我想把本地政策 / 招生章程文档导入数据库，以便后续可以检索这些文本。

#### Acceptance Criteria

1. WHEN 输入本地 Markdown、TXT 或 HTML 文件，THE System SHALL 读取并规范化文本内容。
2. WHEN 导入文档，THE System SHALL 基于正文生成小写 SHA-256 `content_hash`，用于去重。
3. WHEN 文档正文为空，THE System SHALL 拒绝导入并给出明确错误。
4. WHEN 文档重复导入，THE System SHALL 通过 `content_hash` 避免重复插入。

### Requirement 2: 嵌入向量生成

**User Story:** 作为系统，我需要把问题和政策文档转换为向量，以便进行语义检索。

#### Acceptance Criteria

1. WHEN 调用嵌入模型，THE System SHALL 使用显式超时、有限重试、退避和抖动。
2. WHEN 嵌入服务返回异常，THE System SHALL 抛出明确错误，不静默失败。
3. WHEN 配置了向量维度，THE System SHALL 校验返回向量长度。
4. WHEN 运行单元测试，THE System SHALL 支持 fake embedding provider，不依赖外部网络。

### Requirement 3: pgvector 语义检索

**User Story:** 作为用户，我想输入政策类问题并检索相关文档，以便找到有来源支撑的政策依据。

#### Acceptance Criteria

1. WHEN 用户提交问题，THE System SHALL 生成问题向量并通过 `policy_document.embedding` 执行相似度检索。
2. WHEN 指定 `top_k`，THE System SHALL 最多返回对应数量的候选文档。
3. WHEN 指定省份或文档类型，THE System SHALL 使用确定性过滤条件缩小检索范围。
4. WHEN 没有匹配文档，THE System SHALL 返回空结果和“暂无可检索政策文档”的明确提示。

### Requirement 4: API 政策检索接口

**User Story:** 作为前端或调用方，我想通过 API 查询政策文档检索结果，以便展示可追溯的来源。

#### Acceptance Criteria

1. WHEN 调用政策检索接口，THE System SHALL 返回问题、结果数量、候选片段和引用列表。
2. EACH returned candidate SHALL 包含标题、文档类型、来源 URL、相似度和文本片段。
3. EACH returned citation SHALL 包含标题、来源 URL、文档类型、省份和发布时间。
4. THE System SHALL 不在本阶段生成无来源的自然语言结论。

### Requirement 5: 诚实反馈与边界

**User Story:** 作为用户，我希望系统在缺少政策文档时如实告知，而不是编造政策解释。

#### Acceptance Criteria

1. IF 数据库中没有相关政策文档，THEN THE System SHALL 返回空结果和明确提示。
2. IF 检索服务或数据库失败，THEN THE System SHALL 返回错误，不伪造结果。
3. THE System SHALL 保留 Query Catalog 当前的结构化查询安全边界，不让政策类问题进入 NL2SQL 虚构答案。
