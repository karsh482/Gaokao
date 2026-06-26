# 清洗结果

本目录保存 ETL 输出的公开标准化数据。

## 目录结构

```text
processed/
  master/
    provinces.csv
    schools.csv
    source_files.csv
  guizhou/
    2025/
      admission_records.csv
      score_segments.csv
      source_files.csv
    2026/
      program_catalog_records.csv
      source_files.csv
  sichuan/
```

## 数据类型

- `master/`：核心主数据。当前包含省份和教育部普通高校名单。
- `<province>/<year>/`：staging 数据。当前包含贵州 2025 普通类本科批历史类、物理类
  投档数据，普通类、艺术类、体育类分数段统计，以及贵州 2026 招生专业目录 / 招生计划。

## 导入顺序

Docker 新库初始化时先导入 `master/` 到核心表，再导入 `<province>/<year>/`
到 staging 表。详见：

- `docs/master-data-import.md`
- `docs/staging-import.md`

输出字段应优先对齐 `docs/schema.md`、`docs/etl-output-contract.md` 和
`packages/schema/001_core_tables.sql`。
