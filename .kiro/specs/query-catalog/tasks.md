# Implementation Plan

## Overview

本计划把 `design.md` 中的组件与 10 条正确性属性落地为增量编码任务。新增的确定性纯逻辑组件放在 `packages/nl2sql/gaokao_nl2sql/catalog/` 子模块，编排器在既有 `Nl2SqlPipeline` 外再包一层，既有三段式链路与安全护栏保持不变。属性测试统一使用 Hypothesis（与既有 pytest 栈一致），每条属性至少运行 100 次迭代，并通过 mock 的 `ChatModel` / `QueryExecutor` 隔离 LLM 与数据库。

## Tasks

- [x] 1. 搭建 catalog 子模块与测试依赖
  - 在 `packages/nl2sql/gaokao_nl2sql/` 下新增 `catalog/__init__.py` 子包，作为 Query Catalog 纯逻辑组件的容器
  - 在 `packages/nl2sql/pyproject.toml` 的 `[project.optional-dependencies].dev` 增加 `hypothesis>=6,<7`
  - 在 `packages/nl2sql/tests/` 下新增 `catalog/` 测试目录占位，复用既有 `FakeModel` / `FakeExecutor` 模式
  - _Requirements: 15.6_

- [x] 2. 实现 DataScopeRegistry 与 DataScope（数据范围单一事实源）
  - 定义 `DataScope`（frozen dataclass）：`available_provinces`、`available_years`、`unavailable_metrics`、`plan_catalog_loaded`、`policy_rag_enabled`
  - 提供默认登记值：`{"贵州"}`、`{2025}`、`{"录取均分","admitted_count","实际录取人数","985","211"}`、`plan_catalog_loaded=False`、`policy_rag_enabled=False`
  - 提供查询辅助方法（省份是否可用、年份是否可用、指标是否缺失）
  - 编写单元测试断言默认登记值正确
  - _Requirements: 15.1, 15.3, 15.4, 2.3, 8.2, 14.1_

- [x] 3. 实现 ScopeResolver（范围解析与回落标注）
  - 定义 `QueryScope`（frozen dataclass）：`exam_province`、`plan_year`、`used_default_province`、`used_default_year`
  - 实现 `resolve(exam_province, plan_year)`：未提供时回落默认（贵州 / 2025）并置 `used_default_*=True`，已提供时原样采用并置 `used_default_*=False`
  - _Requirements: 1.3, 15.6_

- [x] 3.1 编写属性测试：范围解析忠实回落并标注（全类别参数化）
  - 生成器随机产出 `exam_province`（含 None）、`plan_year`（含 None）与查询类别
  - 断言未提供时回落默认且 `used_default_*` 为真，已提供时原样采用且为假；解析值与类别无关
  - 标注 `# Feature: query-catalog, Property 1`
  - _Properties: Property 1_
  - _Requirements: 1.3, 15.6_

- [x] 4. 实现 QueryClassifier（查询类别识别）
  - 定义 `QueryCategory` 枚举（15 类 + GENERIC）与 `ClassifiedQuery`（`category`、`requested_metrics`）
  - 基于关键词/意图标志位实现分类（趋势/政策/概率/缺失指标等），并抽取问题中引用的指标名
  - 编写单元测试覆盖各类别的代表性问题
  - _Requirements: 5.1, 13.3, 14.1, 6.4_

- [x] 5. 实现 AvailabilityGate（可用性闸门，安全关键）
  - 定义 `UnavailableReason` 枚举与 `GateDecision`（`allowed`、`reasons`、`message`）
  - 按 design 的优先级实现 `evaluate(scope, query, data_scope)`：省份 > 年份 > 趋势 > 政策 > 概率 > 缺失指标主输出 > 计划目录
  - 混合省份（含受支持与不受支持）整体拒绝；缺失指标作为多条件筛选之一时不短路（交由 ResultAnnotator 降级标注）
  - 为每个原因提供明确中文提示文案
  - _Requirements: 5.1, 5.2, 5.4, 6.4, 13.3, 14.1, 15.1, 15.2, 15.3, 15.4, 15.5, 2.3, 8.2_

- [x] 5.1 编写属性测试：闸门对超范围请求给出正确不可用原因（含整体拒绝与优先级）
  - 表驱动随机生成各类超范围成因（非贵州省份、非 2025 年份、趋势类、政策类、精确概率、缺失主输出指标、混合省份）
  - 断言 `allowed=False` 且 `reasons` 准确对应成因；混合省份整体拒绝；省份与缺失指标同时成立时 `reasons` 必含 `PROVINCE_OUT_OF_SCOPE`
  - 标注 `# Feature: query-catalog, Property 2`
  - _Properties: Property 2_
  - _Requirements: 5.1, 5.2, 5.4, 6.4, 13.3, 14.1, 15.1, 15.2, 15.3, 15.4, 15.5_

- [x] 5.2 编写属性测试：依赖招生计划目录的维度降级并显式标注
  - 生成请求计划目录维度的查询，`plan_catalog_loaded=False`
  - 断言响应携带 `PLAN_CATALOG_REQUIRED` 对应明确标注，且不返回未经数据支撑的具体数值
  - 标注 `# Feature: query-catalog, Property 4`
  - _Properties: Property 4_
  - _Requirements: 2.3, 8.2_

- [x] 6. 实现 ScoreRankConverter（位次↔分数换算）
  - 定义 `ScoreSegment`、`ConversionResult`
  - 实现 `score_to_rank` 与 `rank_to_score`：基于按分数单调的分数段，分数→累计位次、位次→分数区间
  - 超出 `[min_score, max_score]` 覆盖范围置 `out_of_range=True`；结果标明 `score_type` 与 `subject_category`
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 3.4_

- [x] 6.1 编写属性测试：位次↔分数换算的往返、边界与口径标注
  - 生成按分数单调的有效分数段序列与覆盖范围内/外的分数、位次
  - 断言 `score_to_rank` 等于所属段 `cumulative_count`；`rank_to_score(score_to_rank(x))` 区间包含原分数；超范围置 `out_of_range=True` 且不虚构；结果含 `score_type`、`subject_category`
  - 标注 `# Feature: query-catalog, Property 5`
  - _Properties: Property 5_
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 3.4_

- [x] 7. 实现 ResultAnnotator（结果标注与部分可用降级）
  - 实现采用口径标注（`exam_province`、`plan_year`、`subject_category`/批次）与所应用筛选条件集合标注
  - 实现部分可用守恒：保留命中/可用项，逐项标注缺失/被忽略项；多条件筛选中被忽略的缺失指标条件必产生明确标注，绝不静默忽略
  - 实现缺科类处理：提供分数未提供 `subject_category` 时给出提示或标明所采用科类
  - 实现院校所在地与考试/招生省份分离：地域维度仅取 `school.province_id`/`city`，范围维度仅取 `exam_province`
  - 实现各类别空结果提示文案
  - _Requirements: 1.3, 2.3, 3.3, 4.2, 4.3, 6.3, 7.3, 11.2, 11.4, 12.3, 1.4, 2.4, 8.3, 9.3, 10.3, 11.3, 12.4_

- [x] 7.1 编写属性测试：查询响应忠实标注所采用的口径与条件
  - 生成通过闸门的查询与输入条件集合
  - 断言标注的 `exam_province`、`plan_year`、`subject_category`/批次及筛选条件集合恒等于实际采用值
  - 标注 `# Feature: query-catalog, Property 6`
  - _Properties: Property 6_
  - _Requirements: 4.2, 11.2_

- [x] 7.2 编写属性测试：部分可用时保留可用项并标注缺失项
  - 生成对比/多条件筛选请求，随机划分可用项与缺失/不可用项
  - 断言保留全部命中项、逐项标注缺失/被忽略项，且“命中项数 + 标注项数 = 请求项总数”；被忽略的缺失指标条件必有明确标注
  - 标注 `# Feature: query-catalog, Property 7`
  - _Properties: Property 7_
  - _Requirements: 4.3, 11.4_

- [x] 7.3 编写属性测试：缺少科类时口径被显式处理
  - 生成提供分数但未提供 `subject_category` 的筛选/换算请求
  - 断言响应要么含“需要 subject_category”提示，要么标明所采用科类（二者必居其一），不静默返回位次结论
  - 标注 `# Feature: query-catalog, Property 8`
  - _Properties: Property 8_
  - _Requirements: 3.3_

- [x] 7.4 编写属性测试：院校所在地与考试/招生省份始终分离
  - 生成同时含地域条件与考试省份范围的请求
  - 断言地域维度仅来源 `school.province_id`/`city`、范围维度仅来源 `exam_province`，二者互不写入
  - 标注 `# Feature: query-catalog, Property 9`
  - _Properties: Property 9_
  - _Requirements: 12.3_

- [x] 8. 实现录取把握度参考（冲稳保，基于位次）
  - 实现基于院校最低位次与考生位次差的可解释把握度参考函数
  - 结果附带“基于单年位次的参考评估，非概率模型结果”标注
  - _Requirements: 13.1, 13.2_

- [x] 8.1 编写属性测试：录取把握度参考单调且标注为非概率模型
  - 生成院校最低位次与考生位次输入
  - 断言考生位次相对更优（数值更小）时把握度参考单调不降；结果含非概率模型标注
  - 标注 `# Feature: query-catalog, Property 10`
  - _Properties: Property 10_
  - _Requirements: 13.1, 13.2_

- [x] 9. 实现 CatalogPipeline（编排器）
  - 串联 `ScopeResolver → QueryClassifier → AvailabilityGate →（短路 unavailable | 进入 Nl2SqlPipeline）→ ResultAnnotator`
  - 闸门拒绝时短路：不调用 LLM、不执行 SQL，返回 `sql=None`、`rows=[]`、`row_count=0` 与明确中文提示
  - 既有 `Nl2SqlPipeline` 与 `validate_select_sql` 护栏保持不变
  - _Requirements: 14.2, 15.7_

- [x] 9.1 编写属性测试：被拒请求绝不虚构数据
  - 通过 mock `ChatModel`（记录调用次数）与 mock `QueryExecutor` 注入 CatalogPipeline
  - 对任意被判定 `allowed=False` 的请求，断言 LLM 调用次数为 0、未执行 SQL、`sql is None`、`rows==[]`、`row_count==0`、`availability.message` 为明确中文提示
  - 标注 `# Feature: query-catalog, Property 3`
  - _Properties: Property 3_
  - _Requirements: 14.2, 15.7_

- [x] 10. 扩展 API 请求/响应模型与路由
  - `QueryRequest` 增加可选 `exam_province`、`plan_year`
  - `QueryResponse` 增加 `exam_province`、`plan_year`、`subject_category`、`availability`（`AvailabilityInfo`）、`notes`，`sql` 改为可空
  - `apps/api/app/dependencies.py` 装配 `CatalogPipeline`；`routers/query.py` 调用编排器并保持既有错误码映射（502/400/500、422）
  - _Requirements: 15.6_

- [x] 11. 编写单元/边界单元测试（渲染与空结果）
  - 学校/专业/专项/地域查询渲染：mock executor 返回固定行，断言响应含要求字段（投档线、位次、专业列表、院校基本信息、选科要求、专项类型等）
  - 空结果提示：mock executor 返回空行，断言各类别“暂无数据”提示文案正确
  - 分数/位次筛选与统计排序：断言过滤阈值、排序方向（位次优先）与聚合范围标注
  - _Requirements: 1.1, 1.2, 1.4, 2.1, 2.2, 2.4, 3.1, 3.2, 6.1, 6.2, 6.3, 8.1, 8.3, 9.1, 9.2, 9.3, 10.1, 10.2, 10.3, 11.1, 11.3, 12.1, 12.2, 12.4_

- [x] 12. 编写 API 集成测试（少量代表性用例）
  - `POST /query`：(a) 贵州 2025 正常查询返回数据；(b) 非贵州省份返回 `availability.available=False` 且 `sql is None`；(c) 趋势类问题短路
  - 验证新增字段与既有错误码映射兼容
  - _Requirements: 15.1, 15.7, 5.1_

- [x] 13. 运行完整测试套件并修复
  - 运行 `packages/nl2sql` 与 `apps/api` 全部测试（属性测试以单次执行模式，非 watch）
  - 确认 10 条属性测试与单元/集成测试全部通过，修复发现的问题
  - _Requirements: 所有_

## Task Dependency Graph

```json
{
  "waves": [
    {
      "wave": 1,
      "tasks": ["1"],
      "description": "搭建 catalog 子模块与测试依赖，无前置依赖"
    },
    {
      "wave": 2,
      "tasks": ["2", "3", "4", "6", "8"],
      "description": "纯逻辑基础组件，仅依赖任务 1，可并行"
    },
    {
      "wave": 3,
      "tasks": ["3.1", "5", "6.1", "8.1"],
      "description": "ScopeResolver 属性测试，以及依赖 2/3/4 的可用性闸门、换算与把握度属性测试"
    },
    {
      "wave": 4,
      "tasks": ["5.1", "5.2", "7"],
      "description": "闸门属性测试，以及依赖 2/5 的结果标注器"
    },
    {
      "wave": 5,
      "tasks": ["7.1", "7.2", "7.3", "7.4", "9"],
      "description": "标注器属性测试，以及依赖 5/6/7/8 的编排器"
    },
    {
      "wave": 6,
      "tasks": ["9.1", "10"],
      "description": "编排器属性测试（被拒不虚构），以及 API 模型与路由扩展"
    },
    {
      "wave": 7,
      "tasks": ["11", "12"],
      "description": "依赖 API 扩展的单元/边界测试与集成测试，可并行"
    },
    {
      "wave": 8,
      "tasks": ["13"],
      "description": "运行完整测试套件并修复"
    }
  ]
}
```

## Notes

- 所有新增组件为确定性纯逻辑，放在 `packages/nl2sql/gaokao_nl2sql/catalog/`，可独立单测，不依赖真实 LLM 与数据库。
- 既有 `Nl2SqlPipeline` 三段式链路与 `validate_select_sql` 安全护栏保持不变；CatalogPipeline 仅在其外层包裹范围解析、可用性闸门与结果标注。
- 属性测试使用 Hypothesis，每条至少 100 次迭代（`@settings(max_examples=100)`），并以单次执行模式运行（不要使用 watch 模式）。
- Property 3 依赖 mock `ChatModel` 记录调用次数，以验证被拒请求 0 次调用 LLM。
- 不在本阶段实现：跨年度趋势、录取均分、985/211、录取概率模型、政策 RAG；这些仅验证“暂不可用”短路。
- 任务 1 完成后，2/3/4/6/8 可并行推进；闸门（5）需等待 2/3/4，编排器（9）需等待 5/6/7/8。
