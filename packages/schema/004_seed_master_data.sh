#!/usr/bin/env bash
set -euo pipefail

master_dir="/data/processed/master"
provinces_csv="${master_dir}/provinces.csv"
schools_csv="${master_dir}/schools.csv"

if [ ! -f "${provinces_csv}" ] || [ ! -f "${schools_csv}" ]; then
    echo "Skipping master data import: provinces.csv or schools.csv is missing."
    exit 0
fi

echo "Importing master data from ${master_dir}..."

psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" <<SQL
CREATE TEMP TABLE tmp_provinces (
    code VARCHAR(6),
    name VARCHAR(32),
    abbreviation VARCHAR(8)
);

CREATE TEMP TABLE tmp_schools (
    school_code VARCHAR(20),
    name VARCHAR(128),
    province VARCHAR(32),
    city VARCHAR(64),
    school_type VARCHAR(32),
    education_level VARCHAR(32),
    ownership VARCHAR(32),
    is_double_first_class TEXT,
    website TEXT,
    source_file_id VARCHAR(128)
);

\copy tmp_provinces (code, name, abbreviation) FROM '${provinces_csv}' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\copy tmp_schools (school_code, name, province, city, school_type, education_level, ownership, is_double_first_class, website, source_file_id) FROM '${schools_csv}' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

INSERT INTO province (code, name, abbreviation)
SELECT code, name, abbreviation
FROM tmp_provinces
ON CONFLICT (code) DO UPDATE
SET
    name = EXCLUDED.name,
    abbreviation = EXCLUDED.abbreviation,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO school (
    school_code,
    name,
    province_id,
    city,
    school_type,
    education_level,
    ownership,
    is_double_first_class,
    website
)
SELECT
    schools.school_code,
    schools.name,
    provinces.id,
    NULLIF(schools.city, ''),
    NULLIF(schools.school_type, ''),
    NULLIF(schools.education_level, ''),
    NULLIF(schools.ownership, ''),
    CASE
        WHEN lower(NULLIF(schools.is_double_first_class, '')) IN ('true', 't', '1', 'yes', 'y')
            THEN TRUE
        ELSE FALSE
    END,
    NULLIF(schools.website, '')
FROM tmp_schools AS schools
JOIN province AS provinces
    ON provinces.name = schools.province
ON CONFLICT (school_code) DO UPDATE
SET
    name = EXCLUDED.name,
    province_id = EXCLUDED.province_id,
    city = EXCLUDED.city,
    school_type = EXCLUDED.school_type,
    education_level = EXCLUDED.education_level,
    ownership = EXCLUDED.ownership,
    is_double_first_class = EXCLUDED.is_double_first_class,
    website = EXCLUDED.website,
    updated_at = CURRENT_TIMESTAMP;
SQL

echo "Master data import complete."
