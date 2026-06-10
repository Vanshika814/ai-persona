-- RAG Pipeline – Supabase Setup

-- 1. Enable the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create the documents table
CREATE TABLE IF NOT EXISTS documents (
    id         TEXT PRIMARY KEY,
    text       TEXT NOT NULL,
    embedding  vector(768),
    source     TEXT NOT NULL,
    metadata   JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 3. Create HNSW index for fast cosine-similarity search
CREATE INDEX IF NOT EXISTS documents_embedding_idx
ON documents USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
