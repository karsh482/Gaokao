#!/usr/bin/env bash
set -euo pipefail

echo "Scanning processed datasets under /data/processed..."

shopt -s nullglob
dataset_dirs=(/data/processed/*/*)

if [ ${#dataset_dirs[@]} -eq 0 ]; then
    echo "No processed dataset directories found."
    exit 0
fi

imported_count=0
skipped_count=0

for dataset_dir in "${dataset_dirs[@]}"; do
    province_slug="$(basename "$(dirname "${dataset_dir}")")"
    year_slug="$(basename "${dataset_dir}")"
    source_files_csv="${dataset_dir}/source_files.csv"
    admission_records_csv="${dataset_dir}/admission_records.csv"
    score_segments_csv="${dataset_dir}/score_segments.csv"

    if [[ ! "${province_slug}" =~ ^[a-z]+$ ]] || [[ ! "${year_slug}" =~ ^[0-9]{4}$ ]]; then
        echo "Skipping ${dataset_dir}: not a province/year admission dataset."
        skipped_count=$((skipped_count + 1))
        continue
    fi

    if [ ! -f "${source_files_csv}" ] || [ ! -f "${admission_records_csv}" ]; then
        echo "Skipping ${dataset_dir}: source_files.csv or admission_records.csv is missing."
        skipped_count=$((skipped_count + 1))
        continue
    fi

    echo "Importing ${dataset_dir}..."

    psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" <<SQL
\copy staging.source_files (source_file_id, source_file_name, source_sha256, source_page_count, dataset_type, exam_province, plan_year, batch, subject_category, admission_track) FROM '${source_files_csv}' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
\copy staging.admission_records (exam_province, plan_year, school_code_in_exam_province, source_school_name, school_name, major_code_in_exam_province, major_name, batch, subject_category, admission_track, admission_program, source_enrollment_type, enrollment_type, selection_requirements, enrollment_plan_count, filing_count, admitted_count, min_score, min_rank, tuition, duration, source_file_id, source_page) FROM '${admission_records_csv}' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
SQL

    if [ -f "${score_segments_csv}" ]; then
        echo "Importing score segments from ${score_segments_csv}..."
        psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" <<SQL
\copy staging.score_segments (exam_province, plan_year, batch, subject_category, admission_track, segment_name, score_type, score, score_label, segment_count, cumulative_count, cumulative_ratio, source_file_id, source_page, source_table_index, source_row_index, source_column_index) FROM '${score_segments_csv}' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
SQL
    fi

    imported_count=$((imported_count + 1))
done

echo "Processed dataset import complete: imported=${imported_count}, skipped=${skipped_count}."
