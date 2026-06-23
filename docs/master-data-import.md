# 主数据导入说明

本文说明如何把 `data/processed/master/` 中的公开主数据导入 PostgreSQL 核心表。

## 输入文件

当前主数据文件来自教育部普通高等学校名单：

```text
data/processed/master/provinces.csv
data/processed/master/schools.csv
data/processed/master/source_files.csv
```

`provinces.csv` 写入核心表 `province`。

`schools.csv` 写入核心表 `school`，其中：

| CSV 字段 | 目标字段 |
| --- | --- |
| school_code | school.school_code |
| name | school.name |
| province | 通过 province.name 映射到 school.province_id |
| city | school.city |
| school_type | school.school_type |
| education_level | school.education_level |
| ownership | school.ownership |
| is_double_first_class | school.is_double_first_class |
| website | school.website |

`source_file_id` 只用于公开数据溯源，当前不写入核心 `school` 表。

## Docker 初始化

首次创建 `gaokao-postgres-data` 数据卷时，Docker 会按顺序执行：

```text
001_core_tables.sql
002_staging_tables.sql
003_seed_master_data.sh
004_seed_staging_data.sh
```

因此新库会先导入 `province` 和 `school` 主数据，再导入
`data/processed/*/*/` 下的招生事实 staging 数据。

PostgreSQL 官方镜像只在数据目录为空时执行初始化脚本。已经存在 volume 时，修改 CSV 或脚本不会自动重跑。

## 校验 SQL

主数据行数：

```sql
SELECT count(*) AS province_count FROM province;
SELECT count(*) AS school_count FROM school;
```

当前预期：

```text
province_count = 31
school_count = 2919
```

检查学校省份关联：

```sql
SELECT provinces.name AS province, count(*) AS school_count
FROM school AS schools
JOIN province AS provinces
    ON provinces.id = schools.province_id
GROUP BY provinces.name
ORDER BY provinces.name;
```

## 与招生事实的关系

`school.school_code` 使用教育部学校标识码，不使用贵州招生目录中的
`school_code_in_exam_province`。

从 staging 写入核心 `admission_record` 前，仍需建立学校映射：

```text
staging.school_code_in_exam_province + staging.school_name
    -> school.id
```

不能直接把省编院校代码写入 `school.school_code`。
