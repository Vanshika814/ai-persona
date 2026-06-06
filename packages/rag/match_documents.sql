-- ============================================================
-- RAG Pipeline – match_documents RPC function
-- ============================================================
-- Run this in the Supabase SQL Editor AFTER setup.sql.
-- It creates the RPC function used by retriever.py for
-- cosine-similarity search against the documents table.
-- ============================================================

CREATE OR REPLACE FUNCTION match_documents(
    query_embedding vector(768),
    match_threshold float,
    match_count int
)
RETURNS TABLE (
    id text,
    text text,
    source text,
    metadata jsonb,
    similarity float
)
LANGUAGE sql STABLE
AS $$
    SELECT id, text, source, metadata,
           1 - (embedding <=> query_embedding) AS similarity
    FROM documents
    WHERE 1 - (embedding <=> query_embedding) > match_threshold
    ORDER BY similarity DESC
    LIMIT match_count;
$$;
