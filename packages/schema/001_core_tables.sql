-- OpenGaokao 核心数据模型，面向 PostgreSQL 15+ 与 pgvector。
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE province (
    id SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code VARCHAR(6) NOT NULL UNIQUE,
    name VARCHAR(32) NOT NULL UNIQUE,
    abbreviation VARCHAR(8) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT province_code_format CHECK (code ~ '^[0-9]{6}$')
);

CREATE TABLE school (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    school_code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL,
    province_id SMALLINT NOT NULL REFERENCES province (id),
    city VARCHAR(64),
    school_type VARCHAR(32),
    education_level VARCHAR(32),
    ownership VARCHAR(32),
    is_double_first_class BOOLEAN NOT NULL DEFAULT FALSE,
    website TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_school_province_id ON school (province_id);
CREATE INDEX idx_school_name ON school (name);

CREATE TABLE major (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    education_level VARCHAR(32) NOT NULL,
    major_category VARCHAR(64),
    major_class VARCHAR(64),
    major_name VARCHAR(128) NOT NULL,
    major_code VARCHAR(20),
    source_year SMALLINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT major_source_year_range CHECK (source_year BETWEEN 1977 AND 2100)
);

CREATE UNIQUE INDEX uq_major_catalog_version
    ON major (
        education_level,
        COALESCE(major_code, ''),
        major_name,
        source_year
    );

CREATE INDEX idx_major_name ON major (major_name);
CREATE INDEX idx_major_catalog
    ON major (education_level, major_category, major_class);

CREATE TABLE admission_record (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_province_id SMALLINT NOT NULL REFERENCES province (id),
    school_id BIGINT NOT NULL REFERENCES school (id),
    major_id BIGINT REFERENCES major (id),
    plan_year SMALLINT NOT NULL,
    school_code_in_exam_province VARCHAR(20),
    major_code_in_exam_province VARCHAR(20),
    batch VARCHAR(64) NOT NULL,
    subject_category VARCHAR(64) NOT NULL,
    enrollment_type VARCHAR(64) NOT NULL DEFAULT '普通类',
    selection_requirements VARCHAR(255),
    enrollment_plan_count INTEGER,
    admitted_count INTEGER,
    min_score NUMERIC(6, 2),
    avg_score NUMERIC(6, 2),
    max_score NUMERIC(6, 2),
    min_rank INTEGER,
    tuition NUMERIC(12, 2),
    duration VARCHAR(32),
    source_file_id VARCHAR(128),
    source_page INTEGER,
    source_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT admission_record_year_range CHECK (
        plan_year BETWEEN 1977 AND 2100
    ),
    CONSTRAINT admission_record_enrollment_plan_count_nonnegative CHECK (
        enrollment_plan_count IS NULL OR enrollment_plan_count >= 0
    ),
    CONSTRAINT admission_record_admitted_count_nonnegative CHECK (
        admitted_count IS NULL OR admitted_count >= 0
    ),
    CONSTRAINT admission_record_min_rank_positive CHECK (
        min_rank IS NULL OR min_rank > 0
    ),
    CONSTRAINT admission_record_tuition_nonnegative CHECK (
        tuition IS NULL OR tuition >= 0
    ),
    CONSTRAINT admission_record_source_page_positive CHECK (
        source_page IS NULL OR source_page > 0
    ),
    CONSTRAINT admission_record_score_order CHECK (
        (min_score IS NULL OR avg_score IS NULL OR min_score <= avg_score)
        AND (avg_score IS NULL OR max_score IS NULL OR avg_score <= max_score)
        AND (min_score IS NULL OR max_score IS NULL OR min_score <= max_score)
    )
);

-- 考试省份编制的代码用于区分同一标准院校或专业在招生目录中的不同条目。
CREATE UNIQUE INDEX uq_admission_record_dimension
    ON admission_record (
        exam_province_id,
        school_id,
        COALESCE(major_id, 0),
        plan_year,
        COALESCE(school_code_in_exam_province, ''),
        COALESCE(major_code_in_exam_province, ''),
        batch,
        subject_category,
        enrollment_type
    );

CREATE INDEX idx_admission_record_school_year
    ON admission_record (school_id, plan_year DESC);
CREATE INDEX idx_admission_record_exam_province_year
    ON admission_record (exam_province_id, plan_year DESC);
CREATE INDEX idx_admission_record_major_id
    ON admission_record (major_id)
    WHERE major_id IS NOT NULL;
CREATE INDEX idx_admission_record_min_rank
    ON admission_record (exam_province_id, plan_year DESC, min_rank)
    WHERE min_rank IS NOT NULL;
CREATE INDEX idx_admission_record_exam_province_codes
    ON admission_record (
        exam_province_id,
        plan_year DESC,
        school_code_in_exam_province,
        major_code_in_exam_province
    );

CREATE TABLE policy_document (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    province_id SMALLINT REFERENCES province (id),
    title VARCHAR(255) NOT NULL,
    document_type VARCHAR(64) NOT NULL,
    issuing_authority VARCHAR(128),
    document_number VARCHAR(64),
    published_at DATE,
    effective_at DATE,
    source_url TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash CHAR(64) NOT NULL UNIQUE,
    embedding VECTOR(1024),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT policy_document_effective_date CHECK (
        published_at IS NULL OR effective_at IS NULL OR effective_at >= published_at
    ),
    CONSTRAINT policy_document_content_not_blank CHECK (btrim(content) <> ''),
    CONSTRAINT policy_document_hash_format CHECK (
        content_hash ~ '^[0-9a-f]{64}$'
    )
);

CREATE INDEX idx_policy_document_province_published_at
    ON policy_document (province_id, published_at DESC);
CREATE INDEX idx_policy_document_type ON policy_document (document_type);
CREATE INDEX idx_policy_document_embedding_hnsw
    ON policy_document
    USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;
