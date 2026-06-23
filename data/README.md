# 数据目录

data/ 保存项目数据资产，不承载长期业务逻辑。

## 目录约定

- raw/：保留可公开的原始来源文件，按省份和年份组织。
- processed/master/：保存可直接导入核心表的公开主数据，例如省份和院校库。
- processed/<province>/<year>/：保存按省份和年份组织的招生事实 staging CSV。

当前结构：

```text
data/
  raw/
    guizhou/
      2025/
      2026/
    sichuan/
  processed/
    master/
      provinces.csv
      schools.csv
      source_files.csv
    guizhou/
      2025/
        admission_records.csv
        source_files.csv
      2026/
    sichuan/
```

## 导入规则

Docker 首次初始化数据库时会自动导入：

1. `processed/master/` 中的 `provinces.csv` 和 `schools.csv` 到核心表
   `province`、`school`。
2. `processed/<province>/<year>/` 中同时存在 `source_files.csv` 和
   `admission_records.csv` 的招生事实数据到 staging 表。

`raw/` 和 `processed/` 均不保存清洗代码。私有清洗实现不进入开源仓库。
