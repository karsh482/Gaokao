"""提供给 LLM 的 schema linking 上下文。

只暴露当前确有数据的查询面：
- staging.admission_records  贵州 2025 普通类本科批投档事实（约 24643 行）
- staging.score_segments     贵州 2025 一分一段 / 综合成绩分数段（约 10574 行）
- staging.program_catalog_records  贵州 2026 招生专业目录 / 招生计划
- province                   省份主数据（31 行）
- school                     全国院校主数据（约 2919 行）

核心 admission_record 表在完成 school_id / major_id 映射前为空，因此不纳入查询面。
"""

from __future__ import annotations

# 允许 NL2SQL 访问的表白名单（schema-qualified）。
ALLOWED_TABLES: frozenset[str] = frozenset(
    {
        "staging.admission_records",
        "staging.score_segments",
        "staging.program_catalog_records",
        "province",
        "school",
        "public.province",
        "public.school",
    }
)

SCHEMA_CONTEXT = """\
你是高考招生数据的 SQL 分析助手。只能基于以下 PostgreSQL 表生成只读查询。

== staging.admission_records （投档事实，贵州 2025 普通类本科批）==
含义：一行表示某院校某专业在某科类批次下的投档情况。
关键列：
- exam_province TEXT        考试/招生省份，当前只有 '贵州'
- plan_year SMALLINT        招生年份，当前只有 2025
- source_school_name TEXT   来源文件中的院校展示名，如 '四川大学（艺术类）'
- school_name TEXT          标准化/待匹配院校名，可与 source_school_name 相同
- school_code_in_exam_province TEXT  贵州招生目录中的院校代码
- major_name TEXT           专业名，可能为空
- major_code_in_exam_province TEXT   贵州招生目录中的专业代码，可能为空
- batch TEXT                批次，如 '本科批'
- subject_category TEXT     科类/选科，如 '历史类'、'物理类'
- admission_track TEXT      招生大赛道，如 '普通类'
- admission_program TEXT    专项/政策项目，如 '国家专项'、'民族班'，普通统考为空
- selection_requirements TEXT  选科要求
- enrollment_plan_count INT 招生计划人数
- filing_count INT          投档人数（注意：不等于实际录取人数）
- admitted_count INT        实际录取人数（投档表中通常为空）
- min_score NUMERIC         最低投档分
- min_rank INT              最低分对应位次（跨年度分析的主要指标）
- tuition NUMERIC           学费
- duration TEXT             学制
- source_file_id TEXT, source_page INT  溯源信息

== staging.score_segments （分数段统计 / 一分一段）==
含义：一行表示某分数（段）的人数与累计人数。
关键列：
- exam_province TEXT        当前只有 '贵州'
- plan_year SMALLINT        当前只有 2025
- batch TEXT               批次或适用范围，可能为空
- subject_category TEXT    科类，可能为空
- admission_track TEXT     招生大赛道，如 '普通类'、'体育类'、'艺术类'
- segment_name TEXT        分数段子类
- score_type TEXT          分数口径，如 '高考总分'、'综合成绩'
- score NUMERIC            可排序的数值分数
- score_label TEXT         原始分数展示，如 '668及以上'
- segment_count INT        本段人数
- cumulative_count INT     累计人数（含本段及以上）
- cumulative_ratio NUMERIC 累计百分比数值，如 0.037 表示 0.037%

== staging.program_catalog_records （招生专业目录 / 招生计划，贵州 2026）==
含义：一行表示 2026 招生专业目录中某院校某专业的计划信息，不是投档/录取结果。
关键列：
- exam_province TEXT        考试/招生省份，当前只有 '贵州'
- plan_year SMALLINT        招生年份，当前只有 2026
- dataset_type TEXT         当前为 'program_catalog'
- subject_category TEXT     科类/选科，如 '历史类'、'物理类'
- admission_track TEXT      招生大赛道，如 '普通类'、'艺术类'、'体育类'
- education_level TEXT      层次，如 '本科'、'高职（专科）'
- batch TEXT                批次，如 '本科批'
- enrollment_type TEXT      招生类型/项目，如 '民族班'、'国家专项计划'
- school_code_in_exam_province TEXT  贵州招生目录中的院校代码
- school_name TEXT          院校名
- school_location TEXT      院校所在地原文
- school_plan_count INT     该院校在当前目录上下文的小计计划数
- major_code_in_exam_province TEXT   贵州招生目录中的专业代码
- major_name TEXT           专业名
- selection_requirements TEXT  再选科目要求
- enrollment_plan_count INT 专业招生计划人数
- language TEXT             外语语种要求
- duration TEXT             学制
- tuition TEXT              原始学费展示，可能为免费、待定或数值
- remarks TEXT              备注
- source_file_id TEXT, source_file_name TEXT, source_page INT  溯源信息

== province （省份主数据）==
- id SMALLINT 主键
- code VARCHAR 六位行政区划代码
- name VARCHAR 省份全称，如 '北京市'
- abbreviation VARCHAR 简称，如 '京'

== school （全国院校主数据）==
- id BIGINT 主键
- school_code VARCHAR 院校代码
- name VARCHAR 院校名称
- province_id SMALLINT  院校所在地，外键 -> province.id（注意：不是招生省份）
- city VARCHAR
- school_type VARCHAR
- education_level VARCHAR 办学层次，如 '本科'
- ownership VARCHAR 办学性质，如 '公办'
- is_double_first_class BOOLEAN 是否双一流

重要口径提醒：
- exam_province / staging 中的省份是“考试/招生省份”，school.province_id 是“院校所在地”，不要混用。
- filing_count（投档人数）不能当作录取人数。
- staging.program_catalog_records 只能回答 2026 招生计划、专业目录、选科、学费、学制、备注；没有 min_score/min_rank，不能用于录取难度结论。
- 2025 投档/录取事实与 2026 招生计划目录不能混用成同一个结论。
- 跨院校比较录取难度时优先用 min_rank（位次），其次 min_score。
- 院校名匹配优先用 staging.admission_records.school_name；连 school 主表时按名称关联。

生成规则：
- 只能生成单条 SELECT 语句（可用 WITH/CTE）。
- 禁止任何写操作（INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE 等）。
- 默认按相关性或分数/位次排序，并加合理的 LIMIT。
- 只输出 SQL，不要输出解释。
"""


def build_schema_context() -> str:
    """返回 schema linking 上下文文本。"""

    return SCHEMA_CONTEXT
