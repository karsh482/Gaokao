-- OpenGaokao staging 数据模型，用于承接公共 processed CSV。
-- staging 层只保存可回溯的来源字段，不生成 school_id 或 major_id。

CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.source_files (
    source_file_id VARCHAR(128) PRIMARY KEY,
    source_file_name TEXT NOT NULL,
    source_sha256 CHAR(64) NOT NULL,
    source_page_count INTEGER NOT NULL,
    dataset_type VARCHAR(64) NOT NULL,
    exam_province VARCHAR(32) NOT NULL,
    plan_year SMALLINT NOT NULL,
    batch VARCHAR(64),
    subject_category VARCHAR(64),
    admission_track VARCHAR(32) NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT staging_source_files_sha256_format CHECK (
        source_sha256 ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT staging_source_files_page_count_positive CHECK (
        source_page_count > 0
    ),
    CONSTRAINT staging_source_files_year_range CHECK (
        plan_year BETWEEN 1977 AND 2100
    )
);

CREATE TABLE IF NOT EXISTS staging.admission_records (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_province VARCHAR(32) NOT NULL,
    plan_year SMALLINT NOT NULL,
    school_code_in_exam_province VARCHAR(20),
    source_school_name VARCHAR(128) NOT NULL,
    school_name VARCHAR(128) NOT NULL,
    major_code_in_exam_province VARCHAR(20),
    major_name VARCHAR(128),
    batch VARCHAR(64) NOT NULL,
    subject_category VARCHAR(64) NOT NULL,
    admission_track VARCHAR(32) NOT NULL,
    admission_program VARCHAR(64),
    source_enrollment_type VARCHAR(64) NOT NULL,
    enrollment_type VARCHAR(64) NOT NULL,
    selection_requirements VARCHAR(255),
    enrollment_plan_count INTEGER,
    filing_count INTEGER,
    admitted_count INTEGER,
    min_score NUMERIC(6, 2),
    min_rank INTEGER,
    tuition NUMERIC(12, 2),
    duration VARCHAR(32),
    source_file_id VARCHAR(128) NOT NULL REFERENCES staging.source_files (
        source_file_id
    ),
    source_page INTEGER NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT staging_admission_records_year_range CHECK (
        plan_year BETWEEN 1977 AND 2100
    ),
    CONSTRAINT staging_admission_records_source_school_name_not_blank CHECK (
        btrim(source_school_name) <> ''
    ),
    CONSTRAINT staging_admission_records_school_name_not_blank CHECK (
        btrim(school_name) <> ''
    ),
    CONSTRAINT staging_admission_records_admission_track_not_blank CHECK (
        btrim(admission_track) <> ''
    ),
    CONSTRAINT staging_admission_records_source_enrollment_type_not_blank CHECK (
        btrim(source_enrollment_type) <> ''
    ),
    CONSTRAINT staging_admission_records_enrollment_type_not_blank CHECK (
        btrim(enrollment_type) <> ''
    ),
    CONSTRAINT staging_admission_records_enrollment_plan_count_nonnegative CHECK (
        enrollment_plan_count IS NULL OR enrollment_plan_count >= 0
    ),
    CONSTRAINT staging_admission_records_filing_count_nonnegative CHECK (
        filing_count IS NULL OR filing_count >= 0
    ),
    CONSTRAINT staging_admission_records_admitted_count_nonnegative CHECK (
        admitted_count IS NULL OR admitted_count >= 0
    ),
    CONSTRAINT staging_admission_records_min_rank_positive CHECK (
        min_rank IS NULL OR min_rank > 0
    ),
    CONSTRAINT staging_admission_records_tuition_nonnegative CHECK (
        tuition IS NULL OR tuition >= 0
    ),
    CONSTRAINT staging_admission_records_source_page_positive CHECK (
        source_page > 0
    ),
    CONSTRAINT staging_admission_records_filing_score_consistency CHECK (
        filing_count IS NULL
        OR filing_count > 0
        OR (filing_count = 0 AND min_score IS NULL AND min_rank IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS staging.score_segments (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_province VARCHAR(32) NOT NULL,
    plan_year SMALLINT NOT NULL,
    batch VARCHAR(64),
    subject_category VARCHAR(64),
    admission_track VARCHAR(32) NOT NULL,
    segment_name VARCHAR(128) NOT NULL,
    score_type VARCHAR(64) NOT NULL,
    score NUMERIC(6, 2) NOT NULL,
    score_label VARCHAR(64) NOT NULL,
    segment_count INTEGER NOT NULL,
    cumulative_count INTEGER NOT NULL,
    cumulative_ratio NUMERIC(8, 3) NOT NULL,
    source_file_id VARCHAR(128) NOT NULL REFERENCES staging.source_files (
        source_file_id
    ),
    source_page INTEGER NOT NULL,
    source_table_index INTEGER NOT NULL,
    source_row_index INTEGER NOT NULL,
    source_column_index INTEGER NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT staging_score_segments_year_range CHECK (
        plan_year BETWEEN 1977 AND 2100
    ),
    CONSTRAINT staging_score_segments_admission_track_not_blank CHECK (
        btrim(admission_track) <> ''
    ),
    CONSTRAINT staging_score_segments_segment_name_not_blank CHECK (
        btrim(segment_name) <> ''
    ),
    CONSTRAINT staging_score_segments_score_type_not_blank CHECK (
        btrim(score_type) <> ''
    ),
    CONSTRAINT staging_score_segments_score_label_not_blank CHECK (
        btrim(score_label) <> ''
    ),
    CONSTRAINT staging_score_segments_score_nonnegative CHECK (
        score >= 0
    ),
    CONSTRAINT staging_score_segments_segment_count_nonnegative CHECK (
        segment_count >= 0
    ),
    CONSTRAINT staging_score_segments_cumulative_count_nonnegative CHECK (
        cumulative_count >= 0
    ),
    CONSTRAINT staging_score_segments_cumulative_ratio_range CHECK (
        cumulative_ratio BETWEEN 0 AND 100
    ),
    CONSTRAINT staging_score_segments_source_page_positive CHECK (
        source_page > 0
    ),
    CONSTRAINT staging_score_segments_source_position_positive CHECK (
        source_table_index > 0
        AND source_row_index > 0
        AND source_column_index > 0
    )
);

CREATE INDEX IF NOT EXISTS idx_staging_admission_records_source_file
    ON staging.admission_records (source_file_id);

CREATE INDEX IF NOT EXISTS idx_staging_admission_records_exam_year
    ON staging.admission_records (exam_province, plan_year);

CREATE INDEX IF NOT EXISTS idx_staging_admission_records_source_page
    ON staging.admission_records (source_file_id, source_page);

CREATE INDEX IF NOT EXISTS idx_staging_admission_records_exam_codes
    ON staging.admission_records (
        exam_province,
        plan_year,
        school_code_in_exam_province,
        major_code_in_exam_province
    );

CREATE INDEX IF NOT EXISTS idx_staging_score_segments_source_file
    ON staging.score_segments (source_file_id);

CREATE INDEX IF NOT EXISTS idx_staging_score_segments_dimension
    ON staging.score_segments (
        exam_province,
        plan_year,
        admission_track,
        subject_category,
        segment_name,
        score DESC
    );
