-- 将旧 document-level policy_document 替换为 chunk-level RAG 表。
-- 新库会通过 001_core_tables.sql 直接创建这些表；本文件用于已有开发库增量升级。

CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS policy_document CASCADE;

CREATE TABLE IF NOT EXISTS rag_document (
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

CREATE INDEX IF NOT EXISTS idx_rag_document_school_year
    ON rag_document (school_name, document_year DESC);
CREATE INDEX IF NOT EXISTS idx_rag_document_category
    ON rag_document (category);
CREATE INDEX IF NOT EXISTS idx_rag_document_province
    ON rag_document (province);
CREATE INDEX IF NOT EXISTS idx_rag_document_metadata_gin
    ON rag_document USING gin (metadata);

CREATE TABLE IF NOT EXISTS rag_chunk (
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

CREATE UNIQUE INDEX IF NOT EXISTS uq_rag_chunk_document_local
    ON rag_chunk (document_id, local_chunk_id);
CREATE INDEX IF NOT EXISTS idx_rag_chunk_document_index
    ON rag_chunk (document_id, chunk_index);
CREATE INDEX IF NOT EXISTS idx_rag_chunk_content_type
    ON rag_chunk (content_type);
CREATE INDEX IF NOT EXISTS idx_rag_chunk_role
    ON rag_chunk (chunk_role);
CREATE INDEX IF NOT EXISTS idx_rag_chunk_section
    ON rag_chunk (section_id)
    WHERE section_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_rag_chunk_heading_path_gin
    ON rag_chunk USING gin (heading_path);
CREATE INDEX IF NOT EXISTS idx_rag_chunk_metadata_gin
    ON rag_chunk USING gin (chunk_metadata);
CREATE INDEX IF NOT EXISTS idx_rag_chunk_embedding_hnsw
    ON rag_chunk
    USING hnsw (embedding halfvec_cosine_ops);
