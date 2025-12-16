-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- RAG chunks table for vector storage
CREATE TABLE IF NOT EXISTS rag_chunks (
  id BIGSERIAL PRIMARY KEY,
  repo_id BIGINT REFERENCES repos(id) ON DELETE CASCADE,
  source_type TEXT,          -- function|pr|issue|adr|runbook
  source_id TEXT,
  path TEXT,
  lang TEXT,
  commit_sha CHAR(40),
  content TEXT,
  ast_signature TEXT,        -- hàm/lớp
  metadata JSONB,
  embedding vector(1536),    -- dimension tuỳ model
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Index for vector similarity search
CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding ON rag_chunks 
  USING ivfflat (embedding vector_cosine_ops) 
  WITH (lists = 100);

-- Indexes for filtering
CREATE INDEX IF NOT EXISTS idx_rag_chunks_repo ON rag_chunks(repo_id);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_source ON rag_chunks(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_path ON rag_chunks(path);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_lang ON rag_chunks(lang);

