# Staging 数据导入说明

本文说明如何把 `data/processed/guizhou/2025/` 中的公共 CSV 导入 PostgreSQL staging
表。staging 层只承接 CSV 原始业务字段，不生成 `school_id`、`major_id`，也不写入核心
`admission_record` 表。

## 输入文件

导入文件按“省份 / 年份”组织。每个数据集目录需要包含两个文件：

```text
data/processed/<province>/<year>/source_files.csv
data/processed/<province>/<year>/admission_records.csv
data/processed/<province>/<year>/score_segments.csv  # 可选
```

示例：

```text
data/processed/guizhou/2025/source_files.csv
data/processed/guizhou/2025/admission_records.csv
data/processed/guizhou/2025/score_segments.csv
data/processed/sichuan/2025/source_files.csv
data/processed/sichuan/2025/admission_records.csv
```

Docker 首次初始化时会扫描 `data/processed/*/*/`。只有同时存在 `source_files.csv` 和
`admission_records.csv` 的目录才会自动导入；缺少任一文件的目录会被跳过。
如果同目录存在 `score_segments.csv`，会在投档数据后自动导入 `staging.score_segments`。

当前 `guizhou/2025` 的 `admission_records.csv` 应包含 24643 条业务记录，
`score_segments.csv` 应包含贵州 2025 普通类、艺术类、体育类分数段统计记录，
`source_files.csv` 应包含投档表和分数段统计表的来源文件记录。

## 本地 Docker 数据库

项目提供独立 PostgreSQL 容器，不应复用本机其他应用的数据库容器。首次使用时复制环境变量
示例文件：

```bash
cp .env.example .env
```

如本机端口冲突，修改 `.env` 中的 `GAOKAO_POSTGRES_HOST_PORT`。容器内 PostgreSQL 仍使用
标准端口 5432，宿主机端口由该变量控制。

默认镜像使用 `pgvector/pgvector:pg16`，因为核心建表脚本需要 `vector` 扩展。不要直接换成
普通 `postgres` 镜像，除非已经确认镜像内安装了 pgvector。

如果只需要启动数据库：

```bash
docker compose up -d gaokao-postgres
```

如果希望同时启动数据库、API 和 Web 查询台，请使用根目录 README 中的一键启动命令：

```bash
docker compose up --build
```

首次创建 `gaokao-postgres-data` 数据卷时，Docker 会自动执行：

```text
packages/schema/001_core_tables.sql
packages/schema/002_staging_tables.sql
packages/schema/004_seed_master_data.sh
packages/schema/003_seed_staging_data.sh
```

因此新用户默认执行 `docker compose up --build` 即可拉起完整应用；如果只调试数据库，
执行 `docker compose up -d gaokao-postgres` 即可完成核心表建表、staging 表建表、
`data/processed/master/` 主数据导入和 `data/processed/*/*/`
下完整招生事实数据集的自动导入。数据库容器内实际执行顺序由 `docker-compose.yml`
挂载到 `/docker-entrypoint-initdb.d/` 的文件名决定：主数据先导入，staging 数据后导入。

默认本地连接串：

```text
postgresql://gaokao:gaokao_dev_password@localhost:15432/gaokao
```

如果修改了 `.env` 中的数据库名、用户、密码或宿主机端口，需要同步调整 `DATABASE_URL`。

## 手动建表

本节仅用于已经存在数据库、未使用 Docker 首次初始化机制，或需要手动排查导入问题的场景。
正常新环境优先使用上一节的 `docker compose up -d gaokao-postgres`。

先执行核心表，再执行 staging 表：

```bash
psql "$DATABASE_URL" -f packages/schema/001_core_tables.sql
psql "$DATABASE_URL" -f packages/schema/002_staging_tables.sql
```

如果数据库已经初始化过核心表，只需要执行：

```bash
psql "$DATABASE_URL" -f packages/schema/002_staging_tables.sql
```

## 手动导入 CSV

本节仅用于已经存在数据库、未使用 Docker 首次初始化机制，或需要手动重跑单个 staging 数据集
的场景。正常新环境会由 `packages/schema/003_seed_staging_data.sh` 自动扫描并导入。

导入前如需重跑同一批 staging 数据，可以清空 staging 表。该操作会删除 staging 表中的
临时导入数据，不影响核心业务表：

```sql
TRUNCATE TABLE staging.admission_records, staging.source_files RESTART IDENTITY;
```

使用 `\copy` 从本地 CSV 导入。需要先导入 `source_files.csv`，再导入
`admission_records.csv`，因为后者通过 `source_file_id` 引用前者。

```bash
psql "$DATABASE_URL" -c "\copy staging.source_files (
    source_file_id,
    source_file_name,
    source_sha256,
    source_page_count,
    dataset_type,
    exam_province,
    plan_year,
    batch,
    subject_category,
    admission_track
) FROM 'data/processed/guizhou/2025/source_files.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')"

psql "$DATABASE_URL" -c "\copy staging.admission_records (
    exam_province,
    plan_year,
    school_code_in_exam_province,
    source_school_name,
    school_name,
    major_code_in_exam_province,
    major_name,
    batch,
    subject_category,
    admission_track,
    admission_program,
    source_enrollment_type,
    enrollment_type,
    selection_requirements,
    enrollment_plan_count,
    filing_count,
    admitted_count,
    min_score,
    min_rank,
    tuition,
    duration,
    source_file_id,
    source_page
) FROM 'data/processed/guizhou/2025/admission_records.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')"
```

以上命令应在 `Gaokao/` 目录下执行。Windows PowerShell、WSL 和 Linux 的引号规则可能不同；
如果命令行转义不稳定，可以进入 `psql` 交互环境后直接执行 `\copy`。

## 重建本地 Docker 数据库

PostgreSQL 官方镜像只会在数据目录为空时执行 `/docker-entrypoint-initdb.d/` 下的初始化脚本。
如果已经启动过数据库，后续修改 schema 或 CSV 后不会自动重跑初始化。

需要完全重建本地开发数据库时，先确认不需要保留当前 volume 中的数据，再执行：

```bash
docker compose down -v
docker compose up -d gaokao-postgres
```

`docker compose down -v` 会删除本项目的 `gaokao-postgres-data` volume，属于开发环境重置操作。

## 导入后校验

基础行数：

```sql
SELECT count(*) AS source_file_count
FROM staging.source_files;

SELECT count(*) AS admission_record_count
FROM staging.admission_records;

SELECT count(*) AS score_segment_count
FROM staging.score_segments;
```

当前贵州 2025 staging 数据的预期结果：

```text
source_file_count = 16
admission_record_count = 24643
score_segment_count = 10574
```

关键字段完整性：

```sql
SELECT
    count(*) FILTER (WHERE source_file_id IS NULL OR btrim(source_file_id) = '')
        AS missing_source_file_id,
    count(*) FILTER (WHERE source_page IS NULL)
        AS missing_source_page,
    count(*) FILTER (
        WHERE source_school_name IS NULL OR btrim(source_school_name) = ''
    ) AS missing_source_school_name,
    count(*) FILTER (
        WHERE source_enrollment_type IS NULL OR btrim(source_enrollment_type) = ''
    ) AS missing_source_enrollment_type
FROM staging.admission_records;
```

预期四个结果均为 0。

投档人数和录取人数语义：

```sql
SELECT
    count(*) FILTER (WHERE filing_count < 0) AS negative_filing_count,
    count(*) FILTER (WHERE admitted_count IS NOT NULL) AS nonblank_admitted_count
FROM staging.admission_records;
```

预期两个结果均为 0。投档表中的 `filing_count` 不能导入为 `admitted_count`。

招生项目拆分分布：

```sql
SELECT COALESCE(admission_program, '空') AS admission_program, count(*) AS count
FROM staging.admission_records
GROUP BY COALESCE(admission_program, '空')
ORDER BY admission_program;
```

当前预期分布：

```text
中外合作办学: 310
国家专项: 1473
地方专项: 144
定向: 38
少数民族语言类: 5
民族班: 315
空: 22088
预科: 270
```

来源文件关联：

```sql
SELECT count(*) AS orphan_record_count
FROM staging.admission_records records
LEFT JOIN staging.source_files files
    ON files.source_file_id = records.source_file_id
WHERE files.source_file_id IS NULL;
```

预期 `orphan_record_count = 0`。

分数段来源文件关联：

```sql
SELECT count(*) AS orphan_score_segment_count
FROM staging.score_segments segments
LEFT JOIN staging.source_files files
    ON files.source_file_id = segments.source_file_id
WHERE files.source_file_id IS NULL;
```

预期 `orphan_score_segment_count = 0`。

## 后续进入核心表的前置条件

从 staging 写入核心 `admission_record` 前，必须先完成：

- `province` 基础数据中存在“贵州”。
- `school` 主数据已建立，并明确 `school.province_id` 表示院校所在地。
- staging 中的 `school_name` / `school_code_in_exam_province` 已映射到正式 `school_id`。
- 如需专业粒度入核心表，`major_name` / `major_code_in_exam_province` 已映射到正式
  `major_id`；不能可靠映射时允许核心表 `major_id` 为空。
- 保留 `source_school_name`、省编院校代码、省编专业代码、`admission_track`、
  `admission_program` 和 `source_enrollment_type`，避免不同招生口径被错误合并。

未满足以上条件时，不应把 staging 数据直接写入核心 `admission_record`。
