CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS project_visual_indices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id VARCHAR(255) NOT NULL,
    image_url TEXT NOT NULL,
    tags TEXT[] NOT NULL,
    detailed_description TEXT NOT NULL,
    embedding_vector vector(1536),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS project_visual_indices_vector_idx
    ON project_visual_indices USING hnsw (embedding_vector vector_cosine_ops);
CREATE INDEX IF NOT EXISTS project_visual_indices_project_id_idx
    ON project_visual_indices (project_id);

CREATE TABLE IF NOT EXISTS project_audit_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id VARCHAR(255) NOT NULL,
    scope_text TEXT NOT NULL,
    report_json JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS project_audit_reports_project_id_idx
    ON project_audit_reports (project_id);

CREATE TABLE IF NOT EXISTS project_index_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    total_images INT NOT NULL DEFAULT 0,
    processed_images INT NOT NULL DEFAULT 0,
    succeeded_images INT NOT NULL DEFAULT 0,
    failed_images INT NOT NULL DEFAULT 0,
    error_log JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS project_index_jobs_project_id_idx
    ON project_index_jobs (project_id);
