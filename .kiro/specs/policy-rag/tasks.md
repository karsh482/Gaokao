# Implementation Plan

## Tasks

- [x] 1. 创建 Policy RAG 规格文档
  - 新增 `requirements.md`、`design.md`、`tasks.md`
  - 明确本阶段只做检索候选与引用返回，不做答案合成
  - _Requirements: 4.4, 5.3_

- [x] 2. 搭建 `packages/rag` 包
  - 新增 `gaokao-rag` Python 包
  - 定义错误类型、数据模型、公开导出
  - _Requirements: 2.4_

- [x] 3. 实现本地政策文档加载器
  - 支持 Markdown / TXT / HTML
  - 规范化正文并生成 SHA-256 `content_hash`
  - 空正文拒绝
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 4. 实现嵌入模型抽象与 OpenAI 兼容客户端
  - 定义 `EmbeddingProvider`
  - 实现 `/embeddings` 调用
  - 增加显式超时、有限重试、退避、抖动和维度校验
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 5. 实现 policy_document 仓储
  - 实现按 `content_hash` 去重写入
  - 实现 pgvector top_k 检索
  - 支持省份和文档类型过滤
  - _Requirements: 1.4, 3.1, 3.2, 3.3_

- [x] 6. 实现 PolicyRagPipeline
  - 串联问题向量生成、检索、片段生成、引用生成
  - 空结果返回明确提示
  - _Requirements: 3.4, 4.1, 4.2, 4.3, 5.1_

- [x] 7. 接入 FastAPI
  - 新增 `/policy/query`
  - 增加请求 / 响应模型
  - 复用 API Key 鉴权
  - _Requirements: 4.1, 4.2, 4.3_

- [x] 8. 补充测试
  - RAG 包单元测试：loader、embedding、repository、pipeline
  - API 测试：成功、空结果、错误映射
  - _Requirements: 所有_

- [x] 9. 运行测试并修复
  - 运行 `packages/rag` 测试
  - 运行 `apps/api` 测试
  - 根据失败修复
  - _Requirements: 所有_
