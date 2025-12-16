# RCA-RAG Code Intelligence — Project Skeleton & Blueprint

> Goal: Hệ thống SaaS nội bộ, air‑gapped, phân tích diff/PR của Java (chủ đạo) + Python + PHP; tự động tag owner, đề xuất fix, RCA, ước lượng tác động & thời gian fix; lưu 90 ngày raw diff; RAG cấp chức năng “Hỏi dự án”.

---

## 0) Kiến trúc tổng thể (event-driven)
```
[GitHub Webhooks]
   -> [Gateway] (/webhooks)
   -> [Queue Router] ---Kafka/Redis---> [Ingestion Worker]
                                    \-> [Analysis Worker]
                                     \-> [Indexer/Chunker]
                                      \-> [Notifier]
                                      \-> [Policy Engine]

[Postgres (OLTP)]  <---->  [RAG API (FastAPI)]  <----> [pgvector]
       ^                                           ^
       |                                           |
   [Object Storage (S3-compatible) for raw diffs & artifacts]

[Google Chat bot]  [Jira]
```

- **Throughput target**: ~100 commits/ngày, ~20 PR/ngày ⇒ Kafka **khuyến nghị** (partition theo `repo`) nhưng hỗ trợ Redis/RabbitMQ cho start nhỏ.
- **Air‑gapped**: tất cả model inference OSS/On‑prem cho code; có thể hybrid cho natural language (qua gateway và redaction).

---

## 1) Repo mono dự án (Python/FastAPI)
```
rca-rag/
├─ apps/
│  ├─ gateway/                  # FastAPI: webhooks, REST API (auth, query)
│  ├─ ingestion/                # nhận events, enrich, lưu raw
│  ├─ analysis/                 # AST/call-graph, rules, risk, TTF features
│  ├─ indexer/                  # chunker, embedding, upsert pgvector
│  ├─ rag/                      # retrieval + generation, citations bắt buộc
│  ├─ notifier/                 # Google Chat/Jira notifications
│  ├─ policy/                   # guardrails, routing, escalation
│  └─ shared/                   # domain models, db, mq, utils, config
├─ deployments/
│  ├─ docker-compose.dev.yml
│  ├─ docker/
│  │  ├─ Dockerfile.api
│  │  ├─ Dockerfile.worker
│  │  └─ Dockerfile.embeddings
│  ├─ k8s/ (optional later)
├─ infra/
│  ├─ migrations/               # alembic
│  ├─ sql/
│  │  ├─ 001_init.sql
│  │  └─ 002_pgvector.sql
├─ configs/
│  ├─ app.example.env
│  ├─ ruff.toml
│  ├─ mypy.ini
│  └─ logging.yaml
├─ Jenkinsfile
├─ pyproject.toml
├─ README.md
└─ docs/
   ├─ api_contracts.md
   ├─ architecture_rules.md
   └─ runbooks/
```

---

## 2) Postgres schema (OLTP + audit)
```sql
-- core entities
CREATE TABLE repos (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  monorepo BOOLEAN DEFAULT TRUE,
  service_map JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE commits (
  id BIGSERIAL PRIMARY KEY,
  repo_id BIGINT REFERENCES repos(id),
  sha CHAR(40) NOT NULL,
  author TEXT,
  authored_at TIMESTAMPTZ,
  added_loc INT DEFAULT 0,
  removed_loc INT DEFAULT 0,
  files_changed INT DEFAULT 0
);

CREATE TABLE pull_requests (
  id BIGSERIAL PRIMARY KEY,
  repo_id BIGINT REFERENCES repos(id),
  number INT NOT NULL,
  title TEXT,
  author TEXT,
  created_at TIMESTAMPTZ,
  merged_at TIMESTAMPTZ,
  state TEXT,
  base_branch TEXT,
  head_sha CHAR(40)
);

CREATE TABLE diffs (
  id BIGSERIAL PRIMARY KEY,
  repo_id BIGINT REFERENCES repos(id),
  pr_id BIGINT REFERENCES pull_requests(id),
  commit_id BIGINT REFERENCES commits(id),
  path TEXT,
  lang TEXT,
  added_loc INT,
  removed_loc INT,
  hunk_count INT,
  object_uri TEXT,           -- link S3 nội bộ: raw patch
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE findings (
  id BIGSERIAL PRIMARY KEY,
  repo_id BIGINT REFERENCES repos(id),
  pr_id BIGINT REFERENCES pull_requests(id),
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

CREATE TABLE test_artifacts (
  id BIGSERIAL PRIMARY KEY,
  pr_id BIGINT REFERENCES pull_requests(id),
  commit_id BIGINT REFERENCES commits(id),
  framework TEXT,            -- junit/xunit
  passed INT, failed INT, skipped INT,
  coverage_line NUMERIC,     -- %
  coverage_branch NUMERIC,
  object_uri TEXT
);

CREATE TABLE notifications (
  id BIGSERIAL PRIMARY KEY,
  pr_id BIGINT REFERENCES pull_requests(id),
  channel TEXT,              -- google_chat/jira
  payload JSONB,
  delivered BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- audit trail
CREATE TABLE audits (
  id BIGSERIAL PRIMARY KEY,
  actor TEXT,
  action TEXT,
  entity TEXT,
  entity_id BIGINT,
  metadata JSONB,
  at TIMESTAMPTZ DEFAULT now()
);
```

### pgvector
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE rag_chunks (
  id BIGSERIAL PRIMARY KEY,
  repo_id BIGINT REFERENCES repos(id),
  source_type TEXT,          -- function|pr|issue|adr|runbook
  source_id TEXT,
  path TEXT,
  lang TEXT,
  commit_sha CHAR(40),
  content TEXT,
  ast_signature TEXT,        -- hàm/lớp
  metadata JSONB,
  embedding vector(1536)     -- dimension tuỳ model
);

CREATE INDEX ON rag_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

---

## 3) Vector hoá & chunking
- **Java/Python/PHP function-level**: dùng parser (tree-sitter hoặc javalang/ast) → trích `function/method/class` + docstring + comments lân cận.
- **PR-level**: mỗi file diff tạo chunk riêng (thêm context trước/sau hunk, tests liên quan).
- **Issue/Thread**: lấy tóm tắt + quyết định kỹ thuật.
- **ADR/Runbooks**: giữ nguyên đoạn ngắn (<=2k tokens), gán `packages`, `module`.
- **Metadata**: `repo, path, commit, author, risk_score, tests, imports, call_graph_neighbors`.

---

## 4) Ownership inference (không có CODEOWNERS)
**Thuật toán hợp thành (owner score 0–1):**
```
owner_score = w1*recent_commit_share + w2*lines_authored_share +
              w3*reviewer_history + w4*module_affinity + w5*service_map_hint
```
- `recent_commit_share`: tỉ lệ commits 30–90 ngày gần nhất ở path.
- `lines_authored_share`: theo git blame, decay theo thời gian.
- `reviewer_history`: ai hay review/merge path này.
- `module_affinity`: từ call-graph/module map.
- `service_map_hint`: nếu service_map cấu hình, tăng mạnh.
- **Output**: top‑k candidates + confidence; dùng làm **routing** Google Chat.

---

## 5) Rules kiến trúc (Clean Architecture)
> Ánh xạ sang loader rule engine (regex path + AST import graph)
```yaml
- id: domain_no_dep_infra
  type: forbid_imports
  from: ["app.domain"]
  to:   ["app.infra", "app.adapters", "app.external"]

- id: usecase_no_call_web
  type: forbid_imports
  from: ["app.usecases"]
  to:   ["app.api", "app.http", "app.ui"]

- id: billing_not_import_marketing
  type: forbid_imports
  from: ["app.billing"]
  to:   ["app.marketing"]

- id: db_gateway_only
  type: allow_only
  target: ["app.infra.db"]
  callers: ["app.infra.repositories", "app.migrations"]

- id: no_cycles
  type: graph_check
  check: no_cycles

- id: public_api_fixed
  type: enforce_public
  packages: ["app.domain", "app.usecases"]
```

**Áp dụng cho Java/Python/PHP**: chuẩn hoá `module path` theo thư mục (ví dụ `app/domain/**`). Với Java monorepo: group theo Gradle module (`:billing`, `:marketing`).

---

## 6) Phân tích tĩnh & bí mật
- **AST/Call‑graph**: Java (JavaParser/jdt), Python (ast), PHP (php-parser). Kết hợp tree‑sitter thống nhất.
- **Secret scan**: regex + entropy + allowlist; chặn gửi ra ngoài; auto‑redaction khi tạo mẫu PR comment.
- **Dependency risk**: tạo BOM đơn giản từ `pom.xml`/`requirements.txt`/`composer.json` + cảnh báo CVE nội bộ.

---

## 7) RCA pipeline (tự động khi build fail / sự cố)
```
CI thất bại -> Webhook checks -> Pull logs + test artifacts ->
Map stack traces -> (file, function, commit range) ->
Truy hồi từ RAG (chunks liên quan + PR tương tự) ->
Sinh báo cáo RCA (root cause, blast radius, đề xuất fix, citations) ->
Gửi Google Chat + đính kèm link dashboard.
```
**Citational guarantees**: mọi gợi ý phải kèm citation (file:path:line hoặc PR# + commit).

---

## 8) Ước lượng TTF (time‑to‑fix)
**Features**: size diff, hunk complexity (cyclomatic delta), import churn, test debt (coverage path), reviewer load, history latency, flakiness, day‑of‑week.
- **Model**: baseline XGBoost nội bộ; fallback heuristic (P50/P90 theo bucket size/lang/module).
- **Output**: `TTF_range`: P50/P90 + độ tin cậy.

---

## 9) API bề mặt (FastAPI)
```
POST /webhooks/github        # nhận: push, pull_request, check_run, review
GET  /repos/:id/health       # metrics, hotspots, drift, debt
GET  /pr/:id/findings        # list findings + citations
POST /rag/query              # {question, repo, branch?, files?}
POST /rca/generate           # theo commit/PR/build-id
POST /admin/service-map      # cập nhật ownership map
```

**Auth**: JWT nội bộ; mTLS tuỳ chọn; RBAC (viewer/reviewer/admin).

---

## 10) Notifier (Google Chat & Jira)
- **Google Chat**: gửi message rich card (sections: summary, owners, suggestions, TTF). Thread theo PR.
- **Jira**: tuỳ chọn tạo Issue cho findings severity ≥ High với labels: `rca-rag`, `auto`.

---

## 11) Retention & redaction
- Raw diff & artifacts: **90 ngày** trong S3 nội bộ (bucket versioning + SSE).
- Sau 90 ngày: chỉ giữ **metadata** (LOC, tác giả, hash rút gọn).
- Redaction: secrets/PII bị mask trước khi lưu vào vector store; raw diff trong S3 áp dụng KMS + scoped IAM.

---

## 12) Docker Compose (dev)
```yaml
version: "3.9"
services:
  api:
    build: { context: ., dockerfile: deployments/docker/Dockerfile.api }
    env_file: [configs/app.example.env]
    ports: ["8080:8080"]
    depends_on: [db, vector, mq]
  worker:
    build: { context: ., dockerfile: deployments/docker/Dockerfile.worker }
    env_file: [configs/app.example.env]
    depends_on: [db, vector, mq]
  db:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: postgres
    volumes: ["pgdata:/var/lib/postgresql/data"]
  vector:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_PASSWORD: postgres
  mq:
    image: bitnami/kafka:latest   # hoặc redis/rabbitmq theo flag
  s3:
    image: minio/minio
    command: server /data
    environment:
      MINIO_ROOT_USER: minio
      MINIO_ROOT_PASSWORD: minio123
    ports: ["9000:9000", "9001:9001"]
volumes:
  pgdata:
```

---

## 13) pyproject.toml (trích)
```toml
[project]
name = "rca-rag"
version = "0.1.0"
dependencies = [
  "fastapi", "uvicorn[standard]", "pydantic", "sqlalchemy[asyncio]~=2.0",
  "alembic", "psycopg[binary]", "pgvector", "boto3", "tenacity",
  "httpx", "python-jose[cryptography]", "passlib[bcrypt]",
  "loguru", "opentelemetry-sdk", "prometheus-client",
  "tree-sitter", "javalang", "lxml", "beautifulsoup4",
  "scikit-learn", "xgboost", "orjson",
]
[tool.ruff]
line-length = 100
[tool.mypy]
strict = true
```

---

## 14) Jenkinsfile (CI nội bộ)
```groovy
pipeline {
  agent any
  options { timestamps() }
  stages {
    stage('Setup') {
      steps { sh 'python -m pip install -U uv && uv pip install -r requirements.txt' }
    }
    stage('Lint & Type') {
      steps { sh 'ruff check . && mypy .' }
    }
    stage('Unit Tests') {
      steps { sh 'pytest -q --junitxml=reports/junit.xml --cov=apps --cov-report=xml' }
      post { always { junit 'reports/junit.xml' } }
    }
    stage('Build Images') {
      steps { sh 'docker build -f deployments/docker/Dockerfile.api -t rca-rag/api:$(git rev-parse --short HEAD) .' }
    }
    stage('Deploy Dev') {
      when { branch 'main' }
      steps { sh 'docker compose -f deployments/docker-compose.dev.yml up -d --build' }
    }
  }
}
```

---

## 15) Webhook & luồng dữ liệu
- **/webhooks/github**: nhận `push`, `pull_request`, `pull_request_review`, `check_run`.
- Chuẩn hoá event → enqueue `{repo, pr, commits, artifacts_uri}`.
- Ingestion lưu: commits, PR, diffs (raw vào S3, record vào Postgres).
- Analysis chạy: AST/lint/rules/secret/dep risk + ownership inference + TTF features.
- Indexer: tạo chunks & embedding vào `rag_chunks` (pgvector).
- Notifier: tạo message Google Chat (+ links dashboard), citations đến file/PR/commit.

---

## 16) RAG contract (citations bắt buộc)
**Input**: `{question, repo, branch?, scope_files?, error_trace?}`
**Retrieval**: hybrid (BM25 + vector) trên `rag_chunks`.
**Generation**: model on‑prem cho code; mọi câu trả lời **phải** kèm `citations: [{path, commit, lines}]`.

---

## 17) PR Comment template (Google Chat)
```
*RCA-RAG Bot*
PR #{number} — {title}
• Risk: {risk_score}/10 | Coverage: {cov}% | TTF(P50/P90): {p50}/{p90}h
• Suspected owners: {owner1} ({c1}%), {owner2} ({c2}%)
• Rules violated: {rule_ids}
• Suggested fix (patch): ```diff\n...\n```
• Citations: {file:path:lines}, PR#{ref}, commit {sha}
```

---

## 18) Bảo mật & kiểm toán
- mTLS nội bộ, JWT audience theo service.
- Secret quản lý qua Vault/Secret Manager; không ghi raw secret trong logs/artifacts.
- Audit trail đầy đủ cho mọi gợi ý/sửa/ai xem gì (bảng `audits`).

---

## 19) Roadmap thực thi (sẵn để bắt đầu)
**Week 1**: Gateway + Ingestion + Postgres + S3 + Webhook end‑to‑end (push/PR) → lưu diffs.
**Week 2**: Analysis (AST Java/Python/PHP cơ bản, rules, secret scan) + ownership v1 + Notifier GChat.
**Week 3**: Indexer + RAG API + citations + RCA báo cáo tự động khi check fail.
**Week 4–5**: TTF model baseline + dashboard health + dependency risk + tuning rules.

---

## 20) Next steps (việc cần bạn xác nhận/điền nhỏ)
1) **Google Chat space & webhook URL** (dev) để mình cấu hình Notifier.
2) **Jenkins job name + credentials id** (để publish junit/coverage lên webhook).
3) **Service map** ban đầu (JSON tối giản): `module → team/owner`.
4) **Danh sách 1–2 monorepo pilot** + access GitHub App (private).

---

## 21) Phụ lục: mẫu service map (JSON)
```json
{
  "modules": {
    ":billing": { "team": "payments", "slack": "gchat://spaces/AAA" },
    ":marketing": { "team": "growth",  "slack": "gchat://spaces/BBB" }
  },
  "paths": {
    "apps/billing/**": ":billing",
    "apps/marketing/**": ":marketing"
  }
}
```

## 22) Phụ lục: API hợp đồng GitHub App → Gateway
```http
POST /webhooks/github
X-Hub-Signature-256: sha256=...
X-GitHub-Event: pull_request | push | check_run | pull_request_review

{ "installation": {"id": ...}, "repository": {...}, "pull_request": {...}, ... }
```

---

**Sẵn sàng sinh code skeleton (FastAPI, models, migrations, worker stubs) theo blueprint này.**



---

# Detailed Execution Plan (Phases, Subtasks, Inputs/Outputs, Services, Deadlines)

**Timezone:** Asia/Ho_Chi_Minh  
**Assumed kick‑off:** **Wed, Nov 12, 2025**  
**Target MVP:** **Wed, Dec 24, 2025**  

## Phase 0 — Project Setup & Access (Nov 12–14, 2025)
**Goal:** Có đủ quyền tích hợp & môi trường dev chạy end‑to‑end tối thiểu.

| Subtask | Inputs | Output | Services/Areas | Acceptance Criteria | Deadline |
|---|---|---|---|---|---|
| 0.1 Tạo Google Chat webhook (dev) | Space đã chọn | Webhook URL | Notifier | Ping test nhận được trong thread | Nov 12 |
| 0.2 Cài GitHub App (private) | Org/repo pilot | Webhook deliveries đến /webhooks/github | Gateway/Ingestion | Event `ping` nhận & log | Nov 12 |
| 0.3 Jenkins credentials & job wiring | Jenkins creds id, job | JUnit/Coverage gửi được tới gateway | Gateway | Nhận & lưu 1 artifact mẫu | Nov 13 |
| 0.4 Provision DB/pgvector/S3/minio | Infra access | Postgres + pgvector + MinIO sẵn sàng | Infra | Migration 001/002 chạy OK | Nov 13 |
| 0.5 Service map khởi tạo | JSON tối thiểu | Bản `service_map` load vào DB | Policy/Ownership | API `/admin/service-map` 200 OK | Nov 14 |

## Phase 1 — Webhooks → Storage (Nov 17–Nov 28, 2025)
**Goal:** Lưu được commits/PR/diffs + artifacts; notifier gửi tóm tắt PR.

| Subtask | Inputs | Output | Services/Areas | Acceptance Criteria | Deadline |
|---|---|---|---|---|---|
| 1.1 Chuẩn hóa payload GitHub | `push`, `pull_request`, `review`, `check_run` | Event model thống nhất | Gateway/Ingestion | Unit test 90% cho mapper | Nov 18 |
| 1.2 Lưu PR/commit/diff metadata | Events từ 1.1 | Rows ở `pull_requests`, `commits`, `diffs` | Ingestion/DB | 1 PR thật có đủ records | Nov 19 |
| 1.3 Lưu raw patch + artifacts | patch, junit, coverage | Files trong S3 + record `object_uri` | Ingestion/S3 | Kiểm tra tải về được | Nov 20 |
| 1.4 Notifier Google Chat v1 | PR metadata | Card tóm tắt PR | Notifier | Nhận message khi PR mở | Nov 21 |
| 1.5 Retention job (90 ngày) | Policy | Job xóa raw > 90d, giữ metadata | Worker/Infra | Dry‑run log chính xác | Nov 25 |
| 1.6 Observability cơ bản | logging.yaml, metrics | /metrics xuất Prometheus | All | 5 metrics cốt lõi hiển thị | Nov 26 |
| 1.7 Hardening air‑gapped | Net policies | Chặn outbound ngoài allowlist | Infra/Sec | Nmap kiểm chứng | Nov 28 |

## Phase 2 — Phân tích & Ownership v1 + RAG Index (Dec 1–Dec 12, 2025)
**Goal:** Tạo findings từ rules + secret/dependency; suy đoán owner; index RAG function/PR/issue/ADR.

| Subtask | Inputs | Output | Services/Areas | Acceptance Criteria | Deadline |
|---|---|---|---|---|---|
| 2.1 AST parsers (Java/Python/PHP) | Diffs, source | API trích function/class + imports | Analysis | 50 file mẫu parse OK | Dec 3 |
| 2.2 Rule engine (forbid/allow/cycles/public) | Rule YAML | Findings + citations | Analysis/Policy | Vi phạm giả lập bị bắt đúng | Dec 4 |
| 2.3 Secret scan & dep risk | Source/BOM | Findings severity + details | Analysis | Tìm thấy secret giả, CVE mẫu | Dec 5 |
| 2.4 Ownership inference v1 | Git blame, history, map | Top‑k owners + confidence | Analysis/Policy | Precision ≥60% trên pilot | Dec 6 |
| 2.5 Indexer/Chunker | Source, PR, issues, ADR | Rows `rag_chunks` + embedding | Indexer/RAG | 10k chunks nạp < 30m | Dec 9 |
| 2.6 RAG query API v1 | Question + scope | Answer + citations (file:lines) | RAG | 5 câu hỏi mẫu trả lời đúng | Dec 10 |
| 2.7 Notifier v2 (findings) | Findings, owners | Chat card: rules, patch gợi ý | Notifier | Thêm patch stub vào card | Dec 12 |

## Phase 3 — RCA tự động & TTF Baseline + Hardening (Dec 15–Dec 24, 2025)
**Goal:** Tạo báo cáo RCA khi build fail; dự đoán TTF; polish & launch.

| Subtask | Inputs | Output | Services/Areas | Acceptance Criteria | Deadline |
|---|---|---|---|---|---|
| 3.1 Log/trace mapper | JUnit, stack traces | Map → file/function/commit | Analysis | 80% match trên sample | Dec 16 |
| 3.2 RCA generator | Diffs + traces + RAG | Báo cáo RCA (root cause, blast radius, fix) + citations | RAG/Analysis | 3 case demo pass review | Dec 18 |
| 3.3 TTF model baseline | PR history, features | P50/P90 + confidence | Analysis/ML | MAE trong ngưỡng ±25% | Dec 19 |
| 3.4 Policy & guardrails | Hallucination/citation | Chặn trả lời thiếu citation | Policy/RAG | 0 trả lời thiếu citation | Dec 20 |
| 3.5 Security/Audit polish | Audit logs, mTLS | Báo cáo kiểm tra bảo mật | Infra/Sec | Checklist pass | Dec 23 |
| 3.6 Go‑Live MVP | All above | Tag v0.1.0 + runbooks | All | Demo cho 2 monorepo pilot | Dec 24 |

---

## Cross‑cutting Backlog (song song theo phase)
- Docs: API contracts, rule packs, runbooks (docs/).  
- Dashboards: repo health, hotspots, ownership precision, TTF distribution.  
- Cost guardrails & rate limiting.  
- Performance: batch upserts, ivfflat tuning.

---

## RACI (vai trò)
- **PO/PM**: ưu tiên & chốt scope.  
- **Lead Eng**: kiến trúc, code review, bảo mật.  
- **Backend**: Gateway/Ingestion/Analysis/Indexer/RAG.  
- **ML Eng**: TTF features/model.  
- **DevOps/Sec**: DB, S3, CI, mTLS, audit.  
- **QA**: test case, acceptance.

---

## Deliverables theo phase
- **P0**: Infra up, webhooks wired, service_map importable.  
- **P1**: Data landing zone (DB + S3), notifier v1.  
- **P2**: Findings + Ownership v1 + RAG indexing/query v1.  
- **P3**: RCA auto, TTF baseline, Go‑Live v0.1.0.

---

## Acceptance Gates
- **Gate 1 (P1→P2)**: 20 PR/ngày ingest ổn định 7 ngày; không drop events; latency < 30s.  
- **Gate 2 (P2→P3)**: Ownership precision ≥60%; RAG trả lời đúng ≥70% trên bộ câu hỏi chuẩn; secret scan false‑positive ≤10%.  
- **Gate 3 (Go‑Live)**: RCA cho build fail hoạt động; TTF dự đoán MAE ≤25%; audit/air‑gap pass.

---

## Risk & Mitigation
- **Parser đa ngôn ngữ**: fallback tree‑sitter khi javalang/php-parser lỗi.  
- **Thiếu ownership**: tăng trọng số service_map và reviewer history; semi‑auto gán owner.  
- **Hiệu năng index**: batch size, COPY vào Postgres, ivfflat lists tuning.  
- **Air‑gapped model**: dùng OSS cho code; natural text qua gateway có redaction khi cần.  
- **Noise từ tests flaky**: whitelist flake, rerun signal trong Jenkins.

---

## Checklist “Definition of Done” (MVP)
- API `/webhooks/github`, `/rag/query`, `/pr/:id/findings`, `/rca/generate` hoạt động.  
- Google Chat nhận card có **owners**, **findings**, **patch gợi ý**, **citations**.  
- RAG trả về câu trả lời **có citation** đến file/PR/commit.  
- Retention 90 ngày chạy theo lịch.  
- Audit log đầy đủ theo truy cập & gợi ý.

