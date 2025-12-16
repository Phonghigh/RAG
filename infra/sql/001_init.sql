-- Core entities
CREATE TABLE IF NOT EXISTS repos (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  monorepo BOOLEAN DEFAULT TRUE,
  service_map JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS commits (
  id BIGSERIAL PRIMARY KEY,
  repo_id BIGINT REFERENCES repos(id) ON DELETE CASCADE,
  sha CHAR(40) NOT NULL,
  author TEXT,
  authored_at TIMESTAMPTZ,
  added_loc INT DEFAULT 0,
  removed_loc INT DEFAULT 0,
  files_changed INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(repo_id, sha)
);

CREATE TABLE IF NOT EXISTS pull_requests (
  id BIGSERIAL PRIMARY KEY,
  repo_id BIGINT REFERENCES repos(id) ON DELETE CASCADE,
  number INT NOT NULL,
  title TEXT,
  author TEXT,
  created_at TIMESTAMPTZ,
  merged_at TIMESTAMPTZ,
  state TEXT,
  base_branch TEXT,
  head_sha CHAR(40),
  created_at_db TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(repo_id, number)
);

CREATE TABLE IF NOT EXISTS diffs (
  id BIGSERIAL PRIMARY KEY,
  repo_id BIGINT REFERENCES repos(id) ON DELETE CASCADE,
  pr_id BIGINT REFERENCES pull_requests(id) ON DELETE CASCADE,
  commit_id BIGINT REFERENCES commits(id) ON DELETE CASCADE,
  path TEXT,
  lang TEXT,
  added_loc INT,
  removed_loc INT,
  hunk_count INT,
  object_uri TEXT,           -- link S3 nội bộ: raw patch
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS findings (
  id BIGSERIAL PRIMARY KEY,
  repo_id BIGINT REFERENCES repos(id) ON DELETE CASCADE,
  pr_id BIGINT REFERENCES pull_requests(id) ON DELETE CASCADE,
  file_path TEXT,
  rule_id TEXT,
  severity TEXT,
  message TEXT,
  details JSONB,
  suggestion JSONB,
  owner_hint TEXT,           -- đề xuất owner
  confidence NUMERIC,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS test_artifacts (
  id BIGSERIAL PRIMARY KEY,
  pr_id BIGINT REFERENCES pull_requests(id) ON DELETE CASCADE,
  commit_id BIGINT REFERENCES commits(id) ON DELETE CASCADE,
  framework TEXT,            -- junit/xunit
  passed INT, failed INT, skipped INT,
  coverage_line NUMERIC,     -- %
  coverage_branch NUMERIC,
  object_uri TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS notifications (
  id BIGSERIAL PRIMARY KEY,
  pr_id BIGINT REFERENCES pull_requests(id) ON DELETE CASCADE,
  channel TEXT,              -- google_chat/jira
  payload JSONB,
  delivered BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Audit trail
CREATE TABLE IF NOT EXISTS audits (
  id BIGSERIAL PRIMARY KEY,
  actor TEXT,
  action TEXT,
  entity TEXT,
  entity_id BIGINT,
  metadata JSONB,
  at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_commits_repo_sha ON commits(repo_id, sha);
CREATE INDEX IF NOT EXISTS idx_commits_authored_at ON commits(authored_at);
CREATE INDEX IF NOT EXISTS idx_prs_repo_number ON pull_requests(repo_id, number);
CREATE INDEX IF NOT EXISTS idx_prs_state ON pull_requests(state);
CREATE INDEX IF NOT EXISTS idx_diffs_repo_pr ON diffs(repo_id, pr_id);
CREATE INDEX IF NOT EXISTS idx_diffs_commit ON diffs(commit_id);
CREATE INDEX IF NOT EXISTS idx_findings_pr ON findings(pr_id);
CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity);
CREATE INDEX IF NOT EXISTS idx_notifications_pr ON notifications(pr_id);
CREATE INDEX IF NOT EXISTS idx_notifications_delivered ON notifications(delivered);
CREATE INDEX IF NOT EXISTS idx_audits_entity ON audits(entity, entity_id);
CREATE INDEX IF NOT EXISTS idx_audits_at ON audits(at);

