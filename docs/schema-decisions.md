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

## 为什么 admission_record 保留 source_school_name？

school_id 表示标准院校身份，source_school_name 表示来源文件中的展示名称。两者不能合并。
例如同一标准院校可能在来源中同时出现“四川大学”和“四川大学（艺术类）”。它们可以映射到
同一个 school_id，但投档事实不能因为学校相同就合并，否则查询“普通类考生能否报考四川大学”
时可能误用不适用的招生记录。

因此 source_school_name 随事实记录保存，并进入唯一索引，用于保留来源招生条目的边界。

## 为什么拆分 admission_track、admission_program 和 source_enrollment_type？

admission_track 表示考生资格和投档规则的大赛道，如普通类、艺术类、体育类或高职分类考试。
它是推荐和查询时最先过滤的资格条件。

admission_program 表示同一赛道下的专项或政策项目，如国家专项、地方专项、民族班、预科、
定向和中外合作办学。普通统考记录可以为空。

source_enrollment_type 原样保存来源文件中的招考类型，避免清洗规则变化后失去回溯依据。
现有 enrollment_type 暂作为兼容字段保留，后续可在字典表完善后收敛为标准展示值。

这三个字段解决不同问题，不应只用一个“招生类型”字段承载全部含义。

## 为什么 filing_count 不等于 admitted_count？

投档表中的“投档人数”表示进入投档环节的人数，不等于最终实际录取人数。实际录取可能受退档、
专业调剂、体检、资格审查等因素影响。

因此 filing_count 单独保存投档人数，admitted_count 仅用于明确来源提供实际录取人数时写入。
不能把投档人数直接导入 admitted_count。

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

## 为什么 RAG 文档与结构化数据分开？

录取记录适合按年份、分数、位次和代码精确查询；政策与招生章程主要是非结构化文本，
适合全文检索和向量检索。将两者分开可以避免结构化事实被文档切分策略或向量模型影响，
也便于 SQL 与 RAG 分别演进。

两类数据通过省份、年份、院校和来源信息在应用层关联，不在 v0.1 中建立脆弱的强外键。

## 为什么 v0.1 暂不加入字典表？

batch、subject_category、admission_track、admission_program、enrollment_type、
school_type、school.education_level 和地域分组字段在多省扩展时一定需要规范化。
但 v0.1 的首要任务是打通贵州数据采集、清洗、查询和评测链路，过早引入完整字典体系会增加
ETL 映射成本。

下一版应优先补充 dict_batch、dict_subject_category、dict_admission_track、
dict_admission_program、dict_enrollment_type 和 dict_region。其中 dict_region
用于表达院校所在地、城市群、区域偏好和意向就读地区，不应把这些查询偏好直接塞进
admission_record。

## 为什么当前 embedding 固定为 2560 维？

当前 RAG 索引默认使用 Qwen/Qwen3-Embedding-4B，因此 `rag_chunk.embedding` 采用
`HALFVEC(2560)`，并建立余弦距离 HNSW 索引。固定维度可以在写入时校验向量长度，也是
pgvector 建立向量索引所需的明确类型信息。

这里使用 `HALFVEC` 而不是普通 `VECTOR`，是因为 pgvector 的 HNSW 索引对普通 `VECTOR`
存在 2000 维上限；Qwen3-Embedding-4B 输出 2560 维，必须使用 half precision 才能在当前
pgvector 版本上建立 HNSW 索引。

向量维度属于模型和索引版本，不属于文档本身。更换模型时应通过 migration 新增向量列，
或重建现有向量列与索引；不应把 README 中的模型描述作为数据库契约，也不应直接修改已经
应用到环境中的历史 migration。

## 为什么采用 rag_document / rag_chunk 而不是 document-level policy_document？

招生章程和高校政策常见 PDF 长度较长，且混合正文、图片、表格和跨页表格。document-level
向量会把过多主题压到一个向量里，检索精度不足，也难以给出精确页码引用。

当前设计把文档拆成 chunk：

- `rag_document` 只保存文档级元数据。
- `rag_chunk` 保存正文、页码、标题路径、表格标题、引用和向量。
- 命中后根据 `section_id` 或邻接 chunk 扩展上下文，保证不跨文档、不跨学校误拼。

这样可以支持招生章程、地方政策、一分一段说明、院校问答等不同文档类型统一入库。
