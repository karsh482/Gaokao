# Requirements Document

## Introduction

本文档定义 Gaokao RAG Lab 的 **Query Catalog（查询目录）**。Query Catalog 的目标是先回答“用户会问什么”，建立一份覆盖典型用户问题的查询类别清单，作为后续数据底座扩充与 NL2SQL 能力建设的需求基础。

本文档**只定义查询的业务需求与验收标准**，不包含 SQL 语句、表结构（DDL）、代码或具体技术实现细节。每个查询类别都标注其【数据可用性】，以区分当前可直接实现的查询与需要后续数据扩充或后续模型支撑的查询。

**当前数据范围（务必体现在验收标准中）：**

- 考试/招生省份：仅贵州（exam_province = '贵州'）。
- 招生年份：仅 2025（plan_year = 2025）。
- 批次/科类：本科批普通类（历史类/物理类），外加艺术类、体育类的综合成绩分数段。
- 已有指标：投档线（min_score）、最低位次（min_rank）、计划数（enrollment_plan_count）、投档数（filing_count）、专项类型（admission_program）、选科要求（selection_requirements）、学费（tuition）、学制（duration）、一分一段/综合成绩分数段（score_segments）、院校主数据（school，含所在省、城市、院校类型、办学层次、办学性质、双一流标记）。
- 重要口径限制：只有“投档线”与“位次”，**没有“录取均分”**；实际录取人数（admitted_count）当前为空；只有“双一流”标记，**没有单独的 985/211 字段**。

**当前不支持（需在查询中明确标注并诚实反馈）：**

- 跨年度/趋势查询（当前仅单年 2025）。
- 四川等贵州以外的省份（本阶段不接入，但查询模式应与省份/年份解耦，做成可参数化）。
- 录取均分、985/211 等当前数据缺失的指标。

**设计原则：** 所有查询应可按 `exam_province`（考试/招生省份）与 `plan_year`（招生年份）参数化，即使当前实际仅有贵州 2025 一组数据。对超出当前数据范围的查询，系统必须明确告知“数据暂不可用”，禁止虚构。

## Glossary

- **Query_Catalog（查询目录）**：本文档定义的、用户可能提出的查询类别集合。
- **System（系统）**：Gaokao RAG Lab 的查询服务，接收用户自然语言问题并基于已入库数据返回结果。
- **投档线 / Min_Score（最低投档分）**：某院校某专业在某科类批次下被投档考生的最低分数，是当前判断录取难度的主要分数指标。
- **位次 / Min_Rank（最低位次）**：最低投档分在全省同科类考生中所处的排名，是跨院校、跨科类比较录取难度的首选指标。
- **录取均分**：被录取考生的平均分。当前数据**不包含**此指标。
- **一分一段 / Score_Segment（分数段）**：全省按分数（或综合成绩）统计的人数与累计人数（cumulative_count）及累计比例（cumulative_ratio），用于分数与位次相互换算。
- **双一流 / Double_First_Class**：院校主数据中的 `is_double_first_class` 标记，表示该校是否为双一流建设高校。当前数据**不含**单独的 985/211 字段。
- **专项计划 / Admission_Program（专项/特殊招生）**：国家专项、地方专项、民族班、预科、中外合作办学等特殊招生项目；普通统考记录该字段为空。
- **赛道 / Admission_Track（招生大赛道）**：招生大类，如普通类、艺术类、体育类，用于判断考生资格是否适用某条记录。
- **科类 / Subject_Category**：考生选科口径，如历史类、物理类。
- **办学性质 / Ownership**：院校的办学属性，如公办、民办。
- **办学层次 / Education_Level**：院校的培养层次，如本科、专科。
- **院校所在地 / School_Province**：院校所在省份（`school.province_id`），用于地域筛选；**不等于**考试/招生省份。
- **考试/招生省份 / Exam_Province**：招生计划与投档录取数据的发布省份（当前为贵州）；**不等于**院校所在地。
- **招生年份 / Plan_Year**：招生计划年份（当前为 2025）。
- **招生计划目录数据**：本阶段计划补充的招生专业目录数据，用于支撑部分专业/计划维度的查询。
- **数据可用性标注**：每个查询类别的实现状态，取值为：可直接实现 / 需招生计划目录数据 / 需多年数据 / 属 RAG 后续。
- **冲稳保 / 录取概率评估**：基于考生分数或位次估计某院校录取把握度的能力，部分依赖后续模型。

## Requirements

### Requirement 1: 学校查询

【数据可用性：可直接实现】

**User Story:** 作为考生或家长，我想查询某所院校的投档线、专业列表、基本信息和所在地，以便快速了解一所目标院校的整体情况。

#### Acceptance Criteria

1. WHEN 用户提供一个院校名称，THE System SHALL 返回该院校在指定 exam_province 与 plan_year 下的投档记录，包含投档线（min_score）、最低位次（min_rank）与所涉专业列表。
2. WHEN 用户查询某院校的基本信息，THE System SHALL 返回该院校的所在省份、城市、院校类型、办学层次、办学性质与双一流标记。
3. WHEN 用户未指定 exam_province 或 plan_year，THE System SHALL 使用当前默认范围（贵州、2025）并在结果中标明所用的 exam_province 与 plan_year。
4. IF 用户查询的院校在当前数据范围内不存在投档记录，THEN THE System SHALL 返回“该院校在指定省份与年份下暂无数据”的明确提示，而非虚构结果。

### Requirement 2: 专业查询

【数据可用性：部分需招生计划目录数据】

**User Story:** 作为考生，我想查询某个专业在哪些院校开设、以及某校某专业的分数、计划与学费，以便围绕目标专业选择院校。

#### Acceptance Criteria

1. WHEN 用户提供一个专业名称，THE System SHALL 返回在指定 exam_province 与 plan_year 下开设该专业的院校列表及对应投档线（min_score）与最低位次（min_rank）。
2. WHEN 用户查询某校某专业的招生明细，THE System SHALL 返回该专业的投档线、最低位次、计划人数（enrollment_plan_count）、学费（tuition）与学制（duration）（在数据可得范围内）。
3. WHERE 某专业维度的计划信息依赖尚未入库的招生计划目录数据，THE System SHALL 返回“该专业计划信息需招生计划目录数据，暂不可用”的明确标注。
4. IF 指定专业在当前数据范围内无记录，THEN THE System SHALL 返回“暂无该专业数据”的明确提示。

### Requirement 3: 分数/位次筛选查询

【数据可用性：可直接实现】

**User Story:** 作为考生，我想知道某个分数或位次能上哪些院校或专业，以便定位与自身成绩匹配的院校范围。

#### Acceptance Criteria

1. WHEN 用户提供一个分数或位次，THE System SHALL 返回在指定 exam_province、plan_year 与 subject_category 下投档线或最低位次不高于该输入的院校与专业列表。
2. THE System SHALL 优先使用最低位次（min_rank）进行匹配，并在结果中同时展示投档线（min_score）与最低位次。
3. WHEN 用户提供分数但未提供科类，THE System SHALL 提示需要 subject_category 以保证位次口径一致，或在结果中标明所采用的科类。
4. IF 输入分数或位次超出当前分数段数据覆盖范围，THEN THE System SHALL 返回“该分数/位次超出现有数据范围”的明确提示。

### Requirement 4: 对比查询

【数据可用性：可直接实现】

**User Story:** 作为考生或顾问，我想对比两所或多所院校、或两个专业之间的投档线、位次与计划数，以便在候选项之间做出取舍。

#### Acceptance Criteria

1. WHEN 用户提供两个或多个院校或专业，THE System SHALL 在统一的 exam_province、plan_year 与 subject_category 口径下并列返回各自的投档线（min_score）、最低位次（min_rank）与计划人数（enrollment_plan_count）。
2. THE System SHALL 在对比结果中明确标注用于对比的科类与批次口径。
3. IF 被对比的某一项在当前数据范围内缺失记录，THEN THE System SHALL 在结果中标注该项“暂无数据”，并继续返回其余可对比项。
4. THE System SHALL 仅在用户显式发起对比请求时生成对比结果，不主动持续维护对比结果。

### Requirement 5: 趋势查询

【数据可用性：需多年数据，当前不可实现】

**User Story:** 作为顾问，我想查看院校录取线的跨年度变化以及涨幅最快的院校，以便判断院校录取难度的走势。

#### Acceptance Criteria

1. WHEN 用户请求跨年度的录取线或位次变化，THE System SHALL 返回“跨年度趋势查询需多年数据，当前仅有单一年份，暂不可用”的明确提示。
2. IF 用户请求“涨幅最快/最慢”等跨年度排名，THEN THE System SHALL 返回数据暂不可用的提示，而非基于单年数据虚构趋势。
3. WHERE 已入库两个及以上 plan_year 的数据，THE System SHALL 启用并支持按 exam_province 与多个 plan_year 参数化执行趋势对比。
4. IF 当前仅有单一 plan_year 的数据，THEN THE System SHALL 禁用趋势比较功能并返回“趋势分析不可用（需两个及以上年份的数据）”的明确提示。

### Requirement 6: 统计/排名查询

【数据可用性：可直接实现】

**User Story:** 作为顾问，我想查询平均投档线、最高或最低 N 所院校、计划总数等聚合结果，以便从整体层面把握招生情况。

#### Acceptance Criteria

1. WHEN 用户请求某范围内的平均投档线或平均位次，THE System SHALL 在指定 exam_province、plan_year 与 subject_category 口径下返回聚合结果。
2. WHEN 用户请求投档线最高或最低的 N 所院校或专业，THE System SHALL 返回按投档线或位次排序的前 N 条结果。
3. WHEN 用户请求计划总数等求和类聚合，THE System SHALL 基于 enrollment_plan_count 返回汇总值并标明统计范围。
4. IF 用户请求基于录取均分或实际录取人数（admitted_count）的统计，THEN THE System SHALL 返回“该指标当前无数据”的明确提示。

### Requirement 7: 位次↔分数换算查询

【数据可用性：可直接实现】

**User Story:** 作为考生，我想基于一分一段表把分数换算成位次、或把位次换算成分数，以便理解自己的成绩在全省的相对位置。

#### Acceptance Criteria

1. WHEN 用户提供一个分数，THE System SHALL 基于指定 exam_province、plan_year 与 subject_category 的分数段数据返回对应的累计位次（cumulative_count）。
2. WHEN 用户提供一个位次，THE System SHALL 基于分数段数据返回对应的分数或分数区间。
3. THE System SHALL 在换算结果中标明所采用的分数口径（score_type，如高考总分或综合成绩）与科类。
4. IF 输入分数或位次超出分数段数据覆盖范围，THEN THE System SHALL 返回“超出现有一分一段数据范围”的明确提示。

### Requirement 8: 招生计划查询

【数据可用性：需招生计划目录数据（本阶段计划补充）】

**User Story:** 作为考生，我想查询某校某专业的招生计划人数、学费与学制，以便了解具体的招生规模与就读成本。

#### Acceptance Criteria

1. WHEN 用户查询某校某专业的招生计划，THE System SHALL 返回该专业在指定 exam_province 与 plan_year 下的计划人数（enrollment_plan_count）、学费（tuition）与学制（duration）（在数据可得范围内）。
2. WHERE 所请求的计划维度依赖尚未入库的招生计划目录数据，THE System SHALL 返回“该招生计划信息需招生专业目录数据，暂不可用”的明确标注。
3. IF 指定院校或专业在当前数据范围内无计划记录，THEN THE System SHALL 返回“暂无招生计划数据”的明确提示。

### Requirement 9: 选科要求查询

【数据可用性：可直接实现】

**User Story:** 作为考生，我想知道报考某专业需要选哪些科目，以便核对自己的选科组合是否符合报考资格。

#### Acceptance Criteria

1. WHEN 用户查询某校某专业的选科要求，THE System SHALL 基于 selection_requirements 返回该专业在指定 exam_province 与 plan_year 下的选科要求。
2. WHEN 用户提供自身选科组合并询问可报专业，THE System SHALL 返回选科要求与该组合相符的专业列表。
3. IF 某专业在当前数据中无选科要求记录，THEN THE System SHALL 返回“该专业暂无选科要求数据”的明确提示。

### Requirement 10: 专项/特殊招生查询

【数据可用性：可直接实现】

**User Story:** 作为考生，我想查询国家专项、地方专项、民族班、预科、中外合作办学等特殊招生项目，以便判断自己是否适用相应的招生政策。

#### Acceptance Criteria

1. WHEN 用户查询某类专项或特殊招生项目，THE System SHALL 基于 admission_program 返回指定 exam_province 与 plan_year 下属于该项目的院校与专业及其投档线、位次。
2. WHEN 用户查询某院校的所有特殊招生项目，THE System SHALL 返回该院校在当前数据范围内涉及的全部 admission_program 类型。
3. IF 指定专项类型在当前数据范围内无记录，THEN THE System SHALL 返回“暂无该专项招生数据”的明确提示。

### Requirement 11: 多条件组合筛选

【数据可用性：可直接实现】

**User Story:** 作为考生，我想用科类、分数、目标专业、办学性质、学费上限等条件组合筛选院校与专业，以便一次性缩小到符合多项偏好的选择范围。

#### Acceptance Criteria

1. WHEN 用户提供多个筛选条件（如 subject_category、分数或位次、专业、ownership、学费上限），THE System SHALL 返回在指定 exam_province 与 plan_year 下同时满足全部条件的院校与专业列表。
2. THE System SHALL 在结果中标明所应用的全部筛选条件。
3. IF 组合条件下无任何匹配记录，THEN THE System SHALL 返回“无符合全部条件的结果”的明确提示。
4. IF 某个筛选条件引用了当前无数据的指标（如录取均分），THEN THE System SHALL 继续基于其余可用条件执行查询，并明确说明哪些条件因数据缺失而被忽略；只要存在被忽略的条件，THE System SHALL 始终返回“该筛选指标当前无数据、已被忽略”的明确提示，不得在无提示的情况下静默忽略条件。

### Requirement 12: 地域查询

【数据可用性：可直接实现】

**User Story:** 作为考生，我想按院校所在省或城市筛选院校（如“成都有哪些院校”“省内双一流”），以便围绕意向就读地区选择院校。

#### Acceptance Criteria

1. WHEN 用户按城市或省份查询院校，THE System SHALL 基于 school 的所在省份（province_id）与城市（city）返回符合条件的院校列表。
2. WHEN 用户查询某地域内的双一流院校，THE System SHALL 结合 is_double_first_class 标记返回该地域内的双一流院校。
3. THE System SHALL 在地域查询中明确区分“院校所在地”与“考试/招生省份”，不将二者混用。
4. IF 指定地域在院校主数据中无匹配院校，THEN THE System SHALL 返回“该地域暂无匹配院校”的明确提示。

### Requirement 13: 可行性/录取概率（冲稳保）

【数据可用性：部分需后续模型，标注为后续增强】

**User Story:** 作为考生，我想基于自己的分数或位次评估某院校的录取把握（冲/稳/保），以便制定志愿填报策略。

#### Acceptance Criteria

1. WHEN 用户提供分数或位次并指定院校，THE System SHALL 基于该院校的历史投档线与最低位次给出可解释的把握度参考（如基于位次差的比较结果）。
2. WHERE 精确的录取概率依赖尚未建立的概率模型，THE System SHALL 标注当前结果为“基于单年位次的参考评估，非概率模型结果”。
3. IF 用户请求基于多年数据或录取概率模型的精确概率，THEN THE System SHALL 返回“概率模型为后续增强能力，当前暂不可用”的明确提示。

### Requirement 14: 解释/政策类查询

【数据可用性：属 RAG 后续（阶段 3），本阶段范围外】

**User Story:** 作为考生或家长，我想查询名词解释与志愿填报规则等政策性问题，以便理解招生录取的相关概念与规则。

#### Acceptance Criteria

1. WHEN 用户提出名词解释或政策规则类问题，THE System SHALL 返回“政策与解释类查询由后续 RAG/政策文档检索能力支持，当前阶段不在范围内”的明确提示。
2. THE System SHALL 将该类查询与结构化数据查询区分开，不使用结构化招生数据虚构政策性答复。

### Requirement 15: 数据范围外查询的诚实反馈（非功能需求）

【适用于全部查询类别】

**User Story:** 作为用户，我希望系统在缺少数据时如实告知，而不是编造答案，以便我能信任系统返回的每一条结果。

#### Acceptance Criteria

1. IF 用户查询涉及当前无数据的省份（exam_province 非贵州），THEN THE System SHALL 返回“该省份数据暂不可用”的明确提示，而非虚构结果。
2. IF 用户查询同时涉及受支持省份（贵州）与不受支持省份，THEN THE System SHALL 拒绝整个查询并返回“查询包含暂不可用省份，无法执行”的明确提示，而非仅返回受支持省份的部分结果。
3. IF 用户查询涉及当前无数据的年份（plan_year 非 2025），THEN THE System SHALL 返回“该年份数据暂不可用”的明确提示。
4. IF 用户查询涉及当前缺失的指标（如录取均分、跨年度趋势、985/211 标记、实际录取人数），THEN THE System SHALL 返回“该指标数据暂不可用”的明确提示。
5. IF 用户查询同时涉及不受支持省份与当前缺失的指标，THEN THE System SHALL 优先按“跨/混合省份查询”处理，拒绝整条查询并返回“查询包含暂不可用省份，无法执行”的明确提示。
6. THE System SHALL 在所有查询类别中支持按 exam_province 与 plan_year 参数化，即使当前实际数据仅覆盖贵州与 2025。
7. WHILE 处于当前数据范围之外的请求，THE System SHALL 禁止生成未经数据支撑的具体数值或结论。
