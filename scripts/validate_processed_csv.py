#!/usr/bin/env python3
"""校验 data/processed 下的公共 CSV 是否符合 docs/etl-output-contract.md 的列契约。

只依赖标准库，可在 CI 或本地运行：

    python scripts/validate_processed_csv.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_ROOT = REPO_ROOT / "data" / "processed"

# 各数据集文件应包含的最小列集合（顺序无关，允许多余列由具体校验另行处理）。
ADMISSION_COLUMNS = {
    "exam_province",
    "plan_year",
    "school_code_in_exam_province",
    "source_school_name",
    "school_name",
    "major_code_in_exam_province",
    "major_name",
    "batch",
    "subject_category",
    "admission_track",
    "admission_program",
    "source_enrollment_type",
    "enrollment_type",
    "selection_requirements",
    "enrollment_plan_count",
    "filing_count",
    "admitted_count",
    "min_score",
    "min_rank",
    "tuition",
    "duration",
    "source_file_id",
    "source_page",
}

SCORE_SEGMENT_COLUMNS = {
    "exam_province",
    "plan_year",
    "batch",
    "subject_category",
    "admission_track",
    "segment_name",
    "score_type",
    "score",
    "score_label",
    "segment_count",
    "cumulative_count",
    "cumulative_ratio",
    "source_file_id",
    "source_page",
    "source_table_index",
    "source_row_index",
    "source_column_index",
}

PROGRAM_CATALOG_COLUMNS = {
    "record_number",
    "exam_province",
    "plan_year",
    "dataset_type",
    "subject_category",
    "admission_track",
    "education_level",
    "batch",
    "enrollment_type",
    "school_code_in_exam_province",
    "school_name",
    "school_location",
    "school_plan_count",
    "major_code_in_exam_province",
    "major_name",
    "selection_requirements",
    "enrollment_plan_count",
    "language",
    "duration",
    "tuition",
    "remarks",
    "source_file_id",
    "source_file_name",
    "source_page",
    "source_column",
    "source_line_start",
    "source_line_end",
    "extraction_method",
    "confidence",
}

SOURCE_FILES_COLUMNS = {
    "source_file_id",
    "source_file_name",
    "source_sha256",
    "source_page_count",
    "dataset_type",
    "exam_province",
    "plan_year",
    "batch",
    "subject_category",
    "admission_track",
}

# master/ 下的 source_files.csv 是主数据来源清单，列结构不同于省份数据集。
MASTER_SOURCE_FILES_COLUMNS = {
    "source_file_id",
    "source_file_name",
    "source_sha256",
    "dataset_type",
    "as_of_date",
    "row_count",
}

PROVINCES_COLUMNS = {"code", "name", "abbreviation"}

SCHOOLS_COLUMNS = {
    "school_code",
    "name",
    "province",
    "city",
    "school_type",
    "education_level",
    "ownership",
    "is_double_first_class",
    "website",
    "source_file_id",
}

# 文件名 -> 必需列集合。
EXPECTED_COLUMNS = {
    "admission_records.csv": ADMISSION_COLUMNS,
    "score_segments.csv": SCORE_SEGMENT_COLUMNS,
    "program_catalog_records.csv": PROGRAM_CATALOG_COLUMNS,
    "source_files.csv": SOURCE_FILES_COLUMNS,
    "provinces.csv": PROVINCES_COLUMNS,
    "schools.csv": SCHOOLS_COLUMNS,
}


def read_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        return next(reader, [])


def expected_columns_for(path: Path) -> set[str] | None:
    """根据文件名与所在目录决定应校验的列集合。

    source_files.csv 是溯源清单：master/ 下的主数据溯源与省份数据集溯源列结构不同，
    真实业务数据在 admission_records.csv / score_segments.csv /
    program_catalog_records.csv / schools.csv / provinces.csv 中。
    """

    if path.name == "source_files.csv":
        if path.parent.name == "master":
            return MASTER_SOURCE_FILES_COLUMNS
        return SOURCE_FILES_COLUMNS
    return EXPECTED_COLUMNS.get(path.name)


def validate_file(path: Path) -> list[str]:
    """返回该文件的错误信息列表，空列表表示通过。"""

    expected = expected_columns_for(path)
    if expected is None:
        return []

    header = {column.strip() for column in read_header(path)}
    missing = sorted(expected - header)
    if missing:
        return [f"{path}: 缺少必需列 {missing}"]
    return []


def main() -> int:
    if not PROCESSED_ROOT.exists():
        print(f"未找到 processed 目录: {PROCESSED_ROOT}")
        return 1

    errors: list[str] = []
    checked = 0
    for csv_path in sorted(PROCESSED_ROOT.rglob("*.csv")):
        if expected_columns_for(csv_path) is None:
            continue
        checked += 1
        errors.extend(validate_file(csv_path))

    if errors:
        print("CSV 契约校验失败:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"CSV 契约校验通过：检查了 {checked} 个文件。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
