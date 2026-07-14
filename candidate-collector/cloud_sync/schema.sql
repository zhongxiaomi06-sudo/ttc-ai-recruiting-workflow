-- Cloud sync schema for TTC candidate-collector (MySQL 8.0).
-- Run this SQL against your RDS MySQL instance before syncing data.

CREATE TABLE IF NOT EXISTS cloud_candidates (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    fingerprint VARCHAR(128) NOT NULL UNIQUE,
    name VARCHAR(255),
    platform VARCHAR(128),
    source_url TEXT,
    source_type VARCHAR(128),
    title VARCHAR(255),
    location VARCHAR(255),
    current_company VARCHAR(255),
    current_role VARCHAR(255),
    phone VARCHAR(64),
    email VARCHAR(255),
    undergraduate_school VARCHAR(255),
    expected_salary VARCHAR(128),
    experiences_json JSON,
    education_json JSON,
    keywords_json JSON,
    raw_text LONGTEXT,
    review_status VARCHAR(32) DEFAULT 'pending',
    attachment_path TEXT,
    attachment_sha256 VARCHAR(128),
    collected_at DATETIME,
    parsed_json JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE INDEX idx_cloud_candidates_phone ON cloud_candidates(phone);
CREATE INDEX idx_cloud_candidates_email ON cloud_candidates(email);
CREATE INDEX idx_cloud_candidates_name ON cloud_candidates(name);
CREATE INDEX idx_cloud_candidates_collected_at ON cloud_candidates(collected_at DESC);

CREATE TABLE IF NOT EXISTS memories (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    project_id VARCHAR(128) NOT NULL,
    source VARCHAR(128) NOT NULL,
    content_type VARCHAR(64) NOT NULL,
    content_text LONGTEXT NOT NULL,
    metadata JSON,
    embedding JSON,
    embedding_model VARCHAR(128),
    embedded_at DATETIME,
    source_record_id VARCHAR(255),
    content_hash VARCHAR(32) GENERATED ALWAYS AS (
        MD5(CONCAT(project_id, ':', source, ':', content_text))
    ) STORED,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_source_record (source, source_record_id),
    UNIQUE KEY uk_content_hash (project_id, source, content_hash)
);

CREATE INDEX idx_memories_project ON memories(project_id);
CREATE INDEX idx_memories_source ON memories(source, content_type);
CREATE INDEX idx_memories_created_at ON memories(created_at DESC);
