# 核心数据模型

数据库采用 PostgreSQL 15+，政策文档向量字段依赖 pgvector。初始化脚本位于
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
province 1 ── N policy_document
```

`policy_document.province_id` 允许为空，用于保存国家级政策。

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

按考试省份、院校、专业、计划年份、批次、科类和招生类型记录招生录取事实。
v0.1 中 `exam_province_id` 应指向贵州；`school_id` 可以指向全国任意院校。

- `exam_province_id` 表示考试/招生省份，不是院校所在地。
- `exam_province_id` 同时也是招生计划与投档录取数据的发布省份。
- `major_id` 为空时表示院校级投档或录取数据。
- `school_code_in_exam_province` 和 `major_code_in_exam_province` 保存贵州等考试省份
  招生目录中的填报代码，不与教育主管部门标准代码混用。
- `enrollment_plan_count` 表示招生计划人数，`admitted_count` 表示实际录取人数。
- `min_rank` 为最低分对应位次，是跨年度分析的主要指标。
- `source_file_id` 和 `source_page` 用于追踪原始文件及页码。
- 唯一索引包含省编代码，防止不同招生条目被错误合并。

## policy_document

保存招生政策、招生章程等文档的原文与检索元数据。

- `content_hash` 使用小写 SHA-256，用于内容去重。
- 当前默认 `embedding` 维度为 1024，对应 BGE-M3。
- 如更换嵌入模型，应通过 migration 新增向量列或重建向量列及其索引，
  不直接修改已部署的基础建表脚本。
- HNSW 索引使用余弦距离，支持政策文档语义检索。

关键设计取舍参见 [`schema-decisions.md`](schema-decisions.md)。

## 下一版字典表规划

v0.1 为保持导入链路简单，`batch`、`subject_category`、`enrollment_type`、`school_type`
等字段暂以文本保存。多省扩展后，应优先补充以下字典表，避免各省口径和展示名称混杂：

| 字典表 | 规范字段 |
| --- | --- |
| `dict_batch` | 批次，如本科批、专科批、特殊类型批 |
| `dict_subject_category` | 科类或选科口径，如物理类、历史类、文史、理工 |
| `dict_enrollment_type` | 招生类型，如普通类、国家专项、地方专项、中外合作 |
| `dict_region` | 院校所在地、城市群、意向就读地区等地域筛选维度 |

后续如需规范院校类型和办学层次，可将 `school_type`、`school.education_level`
迁移到字典表或维表；不建议在事实表中直接堆叠地域偏好字段。
