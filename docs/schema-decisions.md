# Schema 设计决策

本文记录 v0.1 核心数据模型的业务边界与设计取舍。字段清单和实体关系参见
[`schema.md`](schema.md)。

核心事实表模型固定为“考生考试省份 × 全国院校 × 年份 × 批次 × 专业”。
地域概念统一拆分为“考生考试省份”“院校所在地”“意向就读地区”，避免使用含义不稳定的表达。

## 为什么 school.province_id 表示院校所在地？

`school` 保存院校自身相对稳定的主数据，省份是院校地址和主管关系的一部分。
同一院校可在多个省份招生，但不应因此复制多份院校记录。

招生发生地不存入 `school`，而由 `admission_record.exam_province_id` 表达。

## 为什么 admission_record 使用 exam_province_id？

高考招生计划、批次、科类、选科要求、投档分数和位次均以考生所在省份为口径。
同一院校和专业在不同省份可能使用不同代码，也可能具有完全不同的招生规则和分数线。

v0.1 的服务对象是贵州考生，因此 `exam_province_id` 当前应指向贵州；该字段保留为显式口径，
避免把贵州招生目录和院校所在地混淆。查询全国高校时，应通过 `school.province_id` 判断
院校所在地，通过 `admission_record.exam_province_id` 判断该记录是否属于贵州招生口径。

`school.province_id` 仅用于院校地域筛选，不代表数据发布省份；`exam_province_id` 才是
招生计划与投档录取数据的发布省份。

## 为什么同时保留标准代码和省编代码？

`school.school_code` 与 `major.major_code` 用于标准化主数据；
`admission_record.school_code_in_exam_province` 与
`admission_record.major_code_in_exam_province` 保存贵州等考试省份招生目录中的实际填报代码。

两类代码不能相互替代。省编代码可能按省份、年份或招生类型变化，同一标准专业也可能
拆分为多个招生方向或试验班。录取记录的唯一索引因此包含省编代码。

## 为什么 major 不限于本科专业？

招生数据会同时出现本科、专科、专业类、专业方向和试验班。`major` 使用
`education_level`、`major_category`、`major_class` 和 `source_year` 表达这些差异，
避免把表结构绑定到单一的本科专业目录。

`source_year` 用于保留目录版本。专业代码或分类调整时，新版本应新增记录，不覆盖历史记录。
`major_code` 允许为空，以兼容来源目录中没有明确标准代码的试验班或招生方向。

## 为什么 major_id 允许为空？

部分公开数据只提供院校投档线，没有专业粒度；部分原始文件的专业名称或代码也暂时无法
可靠映射到标准专业目录。此时仍需保留院校级事实，因此 `major_id` 允许为空。

省编专业代码和原始来源信息可以先随录取记录保存，待映射规则完善后再补充 `major_id`。

## 为什么政策文档与结构化数据分开？

录取记录适合按年份、分数、位次和代码精确查询；政策与招生章程主要是非结构化文本，
适合全文检索和向量检索。将两者分开可以避免结构化事实被文档切分策略或向量模型影响，
也便于 SQL 与 RAG 分别演进。

两类数据通过省份、年份、院校和来源信息在应用层关联，不在 v0.1 中建立脆弱的强外键。

## 为什么 v0.1 暂不加入字典表？

`batch`、`subject_category`、`enrollment_type`、`school_type`、`school.education_level`
和地域分组字段在多省扩展时一定需要规范化。但 v0.1 的首要任务是打通贵州数据采集、清洗、
查询和评测链路，过早引入完整字典体系会增加 ETL 映射成本。

下一版应优先补充 `dict_batch`、`dict_subject_category`、`dict_enrollment_type` 和
`dict_region`。其中 `dict_region` 用于表达院校所在地、城市群、区域偏好和意向就读地区，
不应把这些查询偏好直接塞进 `admission_record`。

## 为什么当前 embedding 固定为 1024 维？

v0.1 默认使用 BGE-M3，因此向量列采用 1024 维，并建立余弦距离 HNSW 索引。固定维度可以
在写入时校验向量长度，也是 pgvector 建立向量索引所需的明确类型信息。

向量维度属于模型和索引版本，不属于政策文档本身。更换模型时应通过 migration 新增向量列，
或重建现有向量列与索引；不应把 README 中的模型描述作为数据库契约，也不应直接修改已经
应用到环境中的历史 migration。
