# 核心数据模型

数据库采用 PostgreSQL 15+，RAG chunk 向量字段依赖 pgvector。初始化脚本位于
`packages/schema/001_core_tables.sql`。

v0.1 的服务对象是贵州考生：录取事实和招生计划以贵州考试省份为口径，院校范围覆盖全国。
全国高校所在地通过 `school.province_id` 表达，不应与贵州招生口径混用。

本项目采用“考生考试省份 × 全国院校 × 年份 × 批次 × 专业”的事实表模型。
概念上统一拆分为“考生考试省份”“院校所在地”“意向就读地区”，不使用含义不稳定的地域口径。

## 实体关系

```text
province 1 ── N school            # 院校所在地
province 1 ── N admission_record  # 考试/招生省份，v0.1 为贵州
school   1 ── N admission_record
major    1 ── N admission_record
rag_document 1 ── N rag_chunk
```

`admission_record.major_id` 允许为空，用于保存只精确到院校层级的录取记录。

## province

省级行政区基础信息。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | `smallint` | 主键 |
| `code` | `varchar(6)` | 六位行政区划代码 |
| `name` | `varchar(32)` | 省份全称 |
| `abbreviation` | `varchar(8)` | 省份简称 |

## school

院校基础信息，通过 `province_id` 关联院校所在地。

主要字段包括院校代码、名称、城市、院校类型、办学层次、办学性质和双一流标识。
`school.province_id` 仅表示院校所在地，用于院校地域筛选，不代表招生计划或投档录取数据的发布省份。

## major

跨培养层次的专业目录信息，可同时保存本科、专科、专业类和试验班。

| 字段 | 说明 |
| --- | --- |
| `education_level` | 培养层次，如本科、专科或其他招生层次 |
| `major_category` | 学科门类或专业大类 |
| `major_class` | 专业类或招生专业组 |
| `major_name` | 专业或试验班名称 |
| `major_code` | 对应来源目录中的专业代码，未明确时可为空 |
| `source_year` | 专业目录来源年份，用于处理目录版本变化 |

专业目录按培养层次、专业代码、专业名称和来源年份唯一，不假设专业代码跨年度永久不变。

## admission_record

按考试省份、院校、专业、计划年份、批次、科类和招生口径记录招生录取事实。
v0.1 中 exam_province_id 应指向贵州；school_id 可以指向全国任意院校。

- exam_province_id 表示考试/招生省份，不是院校所在地。
- exam_province_id 同时也是招生计划与投档录取数据的发布省份。
- major_id 为空时表示院校级投档或录取数据。
- source_school_name 保存来源文件中的院校名称，例如“四川大学（艺术类）”；它不替代
  school.name，也不参与院校主数据去重。
- admission_track 表示招生大赛道，如普通类、艺术类、体育类、高职分类考试等，用于判断
  考生资格是否适用该记录。
- admission_program 表示专项、民族班、预科、定向、中外合作办学等特殊项目；普通统考记录
  可为空。
- source_enrollment_type 保存来源文件的原始招考类型，便于回溯和修正规则。
- enrollment_type 保留为当前兼容字段，后续可随字典表演进为标准化展示字段。
- school_code_in_exam_province 和 major_code_in_exam_province 保存贵州等考试省份
  招生目录中的填报代码，不与教育主管部门标准代码混用。
- enrollment_plan_count 表示招生计划人数，filing_count 表示投档人数，
  admitted_count 表示实际录取人数。投档人数不能直接当作实际录取人数。
- min_rank 为最低分对应位次，是跨年度分析的主要指标。
- source_file_id 和 source_page 用于追踪原始文件及页码。
- 唯一索引包含来源院校名称、省编代码、招生赛道、特殊项目和原始招考类型，防止同一标准院校
  下不同招生口径被错误合并。

## rag_document / rag_chunk

保存招生政策、招生章程、院校政策等非结构化文档的 chunk 级检索数据。

- `rag_document` 保存文档级元数据：标题、类别、来源、学校、适用省份、年份和来源 URL。
- `rag_chunk` 保存可检索片段：正文、页码、左右页、标题路径、表格标题、上下文关系和引用信息。
- 当前默认 `embedding` 类型为 `HALFVEC(2560)`，对应 Qwen/Qwen3-Embedding-4B。
  使用 `HALFVEC` 是因为 pgvector 的 HNSW 索引对普通 `VECTOR` 维度有限制，2560 维需使用 half precision。
- `global_chunk_id` 是跨文档唯一 ID，`local_chunk_id` 是文档内 chunk ID。
- `heading_path` 保存完整祖先标题路径，用于提高 embedding 与检索过滤的语义精度。
- `section_id`、`previous_chunk_id`、`next_chunk_id` 用于命中后扩展同文档同章节上下文，不跨文档拼接。
- 如更换嵌入模型，应通过 migration 新增向量列或重建向量列及其索引，
  不直接修改已部署的基础建表脚本。
- HNSW 索引使用余弦距离，支持 RAG chunk 语义检索。

关键设计取舍参见 [`schema-decisions.md`](schema-decisions.md)。

## 下一版字典表规划

v0.1 为保持导入链路简单，batch、subject_category、admission_track、admission_program、
enrollment_type、school_type 等字段暂以文本保存。多省扩展后，应优先补充以下字典表，
避免各省口径和展示名称混杂：

| 字典表 | 规范字段 |
| --- | --- |
| dict_batch | 批次，如本科批、专科批、特殊类型批 |
| dict_subject_category | 科类或选科口径，如物理类、历史类、文史、理工 |
| dict_admission_track | 招生大赛道，如普通类、艺术类、体育类、高职分类考试 |
| dict_admission_program | 特殊项目，如国家专项、地方专项、民族班、预科、定向、中外合作 |
| dict_enrollment_type | 来源招考类型或展示用招生类型 |
| dict_region | 院校所在地、城市群、意向就读地区等地域筛选维度 |

后续如需规范院校类型和办学层次，可将 school_type、school.education_level
迁移到字典表或维表；不建议在事实表中直接堆叠地域偏好字段。
