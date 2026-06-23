# ETL 输出契约

本文定义私有数据清洗工具向开源项目交付数据时应遵守的边界。

## 仓库职责

- 开源仓库 Gaokao/：保存 schema、文档、清洗后的公开数据和导入契约。
- 私有仓库 gaokao-data_processed-private/：保存 PDF/Excel 解析、清洗规则、字段映射和批处理脚本。

私有 ETL 可以读取开源仓库中的 schema 和文档，但私有实现代码不进入开源仓库。

## 推荐输出目录

    data/processed/
      guizhou/
        2025/
        2026/
      sichuan/

## 数据口径

结构化招生数据应优先对齐：

- docs/schema.md
- docs/schema-decisions.md
- packages/schema/001_core_tables.sql

当前核心事实表模型为“考生考试省份 × 全国院校 × 年份 × 批次 × 专业”。
school.province_id 表示院校所在地，admission_record.exam_province_id 表示考试/招生省份。

## 建议文件命名

    admission_records.csv
    schools.csv
    majors.csv
    score_segments.csv
    source_files.csv

当来源数据只能清洗出部分表时，只输出当前已可靠生成的文件，不为空字段伪造数据。

## 基础字段要求

admission_records.csv 应尽量包含以下字段：

| 字段 | 说明 |
| --- | --- |
| exam_province | 考试/招生省份，例如贵州 |
| plan_year | 招生计划年份 |
| school_code_in_exam_province | 考试省份招生目录中的院校代码 |
| source_school_name | 来源文件中的院校名称 |
| school_name | 标准化或待匹配的院校名称 |
| major_code_in_exam_province | 考试省份招生目录中的专业代码，可为空 |
| major_name | 专业或招生方向名称，可为空 |
| batch | 批次 |
| subject_category | 科类或选科口径 |
| admission_track | 招生大赛道，如普通类、艺术类、体育类 |
| admission_program | 专项或政策项目，如国家专项、民族班、预科、定向，可为空 |
| source_enrollment_type | 来源文件中的原始招考类型 |
| enrollment_type | 兼容字段或标准展示用招生类型 |
| selection_requirements | 选科要求 |
| enrollment_plan_count | 计划人数 |
| filing_count | 投档人数，不等同于实际录取人数 |
| min_score | 最低分 |
| min_rank | 最低位次 |
| tuition | 学费 |
| duration | 学制 |
| source_file_id | 来源文件标识 |
| source_page | 来源页码 |

字段缺失时应留空，不应把未知值写成 0 或“无”。

source_school_name 必须保留来源展示名称。例如“四川大学（艺术类）”可以映射到标准院校
“四川大学”，但投档记录仍应保留原始来源名称，避免不同招生口径被错误聚合。

score_segments.csv 用于承接一分一段或双上线综合成绩分数段统计。字段如下：

| 字段 | 说明 |
| --- | --- |
| exam_province | 考试/招生省份，例如贵州 |
| plan_year | 年份 |
| batch | 批次或适用范围，例如本科双上线；普通类一分一段可为空 |
| subject_category | 科类或选科口径，例如历史类、物理类；艺术/体育综合成绩可为空 |
| admission_track | 招生大赛道，例如普通类、艺术类、体育类 |
| segment_name | 分数段子类，例如普通类、美术与设计类、音乐类-音乐表演声乐 |
| score_type | 分数口径，例如高考总分、综合成绩 |
| score | 可排序的数值分数 |
| score_label | 来源表中的原始分数展示，例如 668及以上 |
| segment_count | 本段人数或各段人数 |
| cumulative_count | 累计人数 |
| cumulative_ratio | 来源表中的累计比例百分数值，例如 0.037 表示 0.037% |
| source_file_id | 来源文件标识 |
| source_page | 来源页码 |
| source_table_index | 来源页内表格序号 |
| source_row_index | 来源表格行号 |
| source_column_index | 来源表格列号 |

分数段数据只进入 staging.score_segments。它不是院校或专业招生事实，不应写入
admission_record。


## 质量要求

- 保留 source_file_id 和 source_page，便于回溯。
- 同一批输出应记录省份、年份、数据类型和生成时间。
- 数值字段在写出前应完成类型校验。
- 对无法稳定解析的记录，应输出到私有仓库的异常报告，不直接进入公开结果。
