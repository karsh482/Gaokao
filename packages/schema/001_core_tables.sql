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
    source_school_name VARCHAR(128) NOT NULL,
    school_code_in_exam_province VARCHAR(20),
    major_code_in_exam_province VARCHAR(20),
    batch VARCHAR(64) NOT NULL,
    subject_category VARCHAR(64) NOT NULL,
    admission_track VARCHAR(32) NOT NULL DEFAULT '普通类',
    admission_program VARCHAR(64),
    source_enrollment_type VARCHAR(64) NOT NULL,
    enrollment_type VARCHAR(64) NOT NULL DEFAULT '普通类',
    selection_requirements VARCHAR(255),
    enrollment_plan_count INTEGER,
    filing_count INTEGER,
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
    CONSTRAINT admission_record_source_school_name_not_blank CHECK (
        btrim(source_school_name) <> ''
    ),
    CONSTRAINT admission_record_admission_track_not_blank CHECK (
        btrim(admission_track) <> ''
    ),
    CONSTRAINT admission_record_source_enrollment_type_not_blank CHECK (
        btrim(source_enrollment_type) <> ''
    ),
    CONSTRAINT admission_record_enrollment_plan_count_nonnegative CHECK (
        enrollment_plan_count IS NULL OR enrollment_plan_count >= 0
    ),
    CONSTRAINT admission_record_filing_count_nonnegative CHECK (
        filing_count IS NULL OR filing_count >= 0
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
    ),
    CONSTRAINT admission_record_filing_score_consistency CHECK (
        filing_count IS NULL
        OR filing_count > 0
        OR (filing_count = 0 AND min_score IS NULL AND min_rank IS NULL)
    )
);

-- 考试省份编制的代码用于区分同一标准院校或专业在招生目录中的不同条目。
CREATE UNIQUE INDEX uq_admission_record_dimension
    ON admission_record (
        exam_province_id,
        school_id,
        COALESCE(major_id, 0),
        plan_year,
        source_school_name,
        COALESCE(school_code_in_exam_province, ''),
        COALESCE(major_code_in_exam_province, ''),
        batch,
        subject_category,
        admission_track,
        COALESCE(admission_program, ''),
        source_enrollment_type,
        enrollment_type
    );

CREATE INDEX idx_admission_record_school_year
    ON admission_record (school_id, plan_year DESC);
CREATE INDEX idx_admission_record_exam_province_year
    ON admission_record (exam_province_id, plan_year DESC);
CREATE INDEX idx_admission_record_eligibility
    ON admission_record (
        exam_province_id,
        plan_year DESC,
        admission_track,
        batch,
        subject_category,
        admission_program
    );
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

CREATE TABLE rag_document (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_uid VARCHAR(255) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    category VARCHAR(64) NOT NULL,
    source VARCHAR(128),
    school_name VARCHAR(128),
    province VARCHAR(64),
    document_year SMALLINT,
    source_url TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT rag_document_title_not_blank CHECK (btrim(title) <> ''),
    CONSTRAINT rag_document_category_not_blank CHECK (btrim(category) <> ''),
    CONSTRAINT rag_document_year_range CHECK (
        document_year IS NULL OR document_year BETWEEN 1977 AND 2100
    )
);

CREATE INDEX idx_rag_document_school_year
    ON rag_document (school_name, document_year DESC);
CREATE INDEX idx_rag_document_category
    ON rag_document (category);
CREATE INDEX idx_rag_document_province
    ON rag_document (province);
CREATE INDEX idx_rag_document_metadata_gin
    ON rag_document USING gin (metadata);

CREATE TABLE rag_chunk (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES rag_document (id) ON DELETE CASCADE,
    global_chunk_id VARCHAR(512) NOT NULL UNIQUE,
    local_chunk_id VARCHAR(160) NOT NULL,
    chunk_index INTEGER NOT NULL,
    content_type VARCHAR(32) NOT NULL,
    chunk_role VARCHAR(32) NOT NULL,
    content TEXT NOT NULL,
    page_number INTEGER,
    page_side VARCHAR(16),
    heading_path JSONB NOT NULL DEFAULT '[]'::jsonb,
    table_title TEXT,
    context_expandable BOOLEAN NOT NULL DEFAULT TRUE,
    previous_chunk_id VARCHAR(160),
    next_chunk_id VARCHAR(160),
    section_id VARCHAR(512),
    local_section_id VARCHAR(255),
    retrieval_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    citation JSONB NOT NULL DEFAULT '{}'::jsonb,
    chunk_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding_provider VARCHAR(64) NOT NULL,
    embedding_model VARCHAR(128) NOT NULL,
    embedding_text_version VARCHAR(32) NOT NULL,
    embedding_dim SMALLINT NOT NULL,
    embedding HALFVEC(2560) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT rag_chunk_index_positive CHECK (chunk_index > 0),
    CONSTRAINT rag_chunk_content_not_blank CHECK (btrim(content) <> ''),
    CONSTRAINT rag_chunk_embedding_dim CHECK (embedding_dim = 2560),
    CONSTRAINT rag_chunk_page_number_positive CHECK (
        page_number IS NULL OR page_number > 0
    )
);

CREATE UNIQUE INDEX uq_rag_chunk_document_local
    ON rag_chunk (document_id, local_chunk_id);
CREATE INDEX idx_rag_chunk_document_index
    ON rag_chunk (document_id, chunk_index);
CREATE INDEX idx_rag_chunk_content_type
    ON rag_chunk (content_type);
CREATE INDEX idx_rag_chunk_role
    ON rag_chunk (chunk_role);
CREATE INDEX idx_rag_chunk_section
    ON rag_chunk (section_id)
    WHERE section_id IS NOT NULL;
CREATE INDEX idx_rag_chunk_heading_path_gin
    ON rag_chunk USING gin (heading_path);
CREATE INDEX idx_rag_chunk_metadata_gin
    ON rag_chunk USING gin (chunk_metadata);
CREATE INDEX idx_rag_chunk_embedding_hnsw
    ON rag_chunk
    USING hnsw (embedding halfvec_cosine_ops);
