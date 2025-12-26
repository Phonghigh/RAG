# RCA-RAG Code Intelligence

> Hệ thống SaaS nội bộ, air‑gapped, phân tích diff/PR của Java (chủ đạo) + Python + PHP; tự động tag owner, đề xuất fix, RCA, ước lượng tác động & thời gian fix; lưu 90 ngày raw diff; RAG cấp chức năng "Hỏi dự án".

## Cấu trúc thư mục

```
rca-rag/
├─ apps/
│  ├─ gateway/              # FastAPI app (webhooks, REST API)
│  │  ├─ main.py           # FastAPI app, routers
│  │  ├─ webhook/
│  │  │  └─ github.py      # GitHub webhook handler
│  │  └─ api/              # REST endpoints (health, metrics, admin)
│  ├─ ingestion/           # Ingestion worker
│  │  ├─ worker.py         # Main worker loop
│  │  ├─ processors/       # Event processors
│  │  ├─ storage/          # Storage operations
│  │  └─ retention/       # Retention job worker
│  ├─ notifier/            # Notification service
│  │  ├─ client.py         # Google Chat client
│  │  └─ formatters.py     # Message formatting
│  ├─ shared/              # Shared code
│  │  ├─ config.py         # Pydantic Settings
│  │  ├─ db/               # Database setup, models
│  │  ├─ storage/          # S3/MinIO abstraction
│  │  ├─ mq/               # Message queue abstraction
│  │  └─ utils/            # Utilities
├─ infra/
│  ├─ migrations/          # Alembic migrations
│  └─ sql/                 # Raw SQL scripts
├─ deployments/
│  ├─ docker-compose.dev.yml
│  └─ docker/
│     ├─ Dockerfile.api
│     └─ Dockerfile.worker
├─ configs/
│  ├─ app.example.env      # Environment template
│  ├─ logging.yaml
│  ├─ ruff.toml
│  └─ mypy.ini
├─ tests/                  # Test suite
│  ├─ unit/
│  ├─ integration/
│  └─ fixtures/
├─ pyproject.toml
├─ requirements.txt
└─ README.md
```

## API Endpoints

### Health & Metrics

- `GET /health` - Basic health check
- `GET /health/ready` - Readiness check (Kubernetes)
- `GET /health/live` - Liveness check (Kubernetes)
- `GET /metrics` - Prometheus metrics

### Webhooks

- `POST /webhooks/github` - GitHub webhook endpoint
  - Supports: `push`, `pull_request`, `pull_request_review`, `check_run`
  - Requires: `X-Hub-Signature-256` header for signature verification

### Admin

- `POST /admin/service-map` - Update service map for a repository
  - Body: `{"repo_name": "org/repo", "service_map": {...}}`
- `GET /admin/service-map/{repo_name}` - Get service map for a repository

### RAG Query

- `POST /rag/query` - Query codebase using RAG
  - Body: `{"question": "How does authentication work?", "repo": "org/repo", "top_k": 5, "files": ["app/auth/**"]}`
  - Returns: Answer with citations and relevant code chunks

## Setup Guide

> **New to the project?** See [GETTING_STARTED.md](GETTING_STARTED.md) for a comprehensive step-by-step guide with troubleshooting tips.

### Quick Start

1. **Clone repository and install dependencies:**

```bash
git clone <repo-url>
cd rca-rag
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

2. **Configure environment:**

```bash
cp configs/app.example.env configs/.env
# Edit configs/.env with your settings
```

3. **Start infrastructure:**

```bash
docker-compose -f deployments/docker-compose.dev.yml up -d
```

4. **Run database migrations:**

```bash
alembic -c infra/migrations/alembic.ini upgrade head
```

5. **Start services:**

```bash
# Start API gateway
uvicorn apps.gateway.main:app --host 0.0.0.0 --port 8080

# Start ingestion worker (in separate terminal)
python -m apps.ingestion.worker

# Start analysis worker (in separate terminal)
python -m apps.analysis

# Start indexer worker in message queue mode (in separate terminal, optional)
python -m apps.indexer --mq

# Or manually index a repository
python -m apps.indexer <repo_id>
```

For detailed setup instructions, troubleshooting, and configuration options, see [GETTING_STARTED.md](GETTING_STARTED.md).

### Docker Compose Services

- **api**: FastAPI gateway (port 8080)
- **worker**: Ingestion worker
- **db**: PostgreSQL 16 with pgvector (port 5432)
- **mq**: Redis (port 6379) - configurable to Kafka/RabbitMQ
- **s3**: MinIO (ports 9000, 9001)

## Configuration

### Environment Variables

Key configuration options in `configs/.env`:

- `DATABASE_URL`: PostgreSQL connection string
- `MQ_TYPE`: Message queue type (`redis`, `kafka`, `rabbitmq`)
- `STORAGE_TYPE`: Storage type (`s3`, `minio`)
- `GITHUB_WEBHOOK_SECRET`: GitHub webhook secret for signature verification
- `GOOGLE_CHAT_WEBHOOK_URL`: Google Chat webhook URL
- `RETENTION_DAYS`: Days to retain raw diffs (default: 90)
- `EMBEDDING_MODEL_NAME`: Embedding model for RAG (default: all-MiniLM-L6-v2)
- `RULES_CONFIG_PATH`: Path to rules YAML configuration file
- `CVE_DB_PATH`: Path to CVE database file (optional)
- `INDEXING_ENABLED`: Enable automatic indexing after analysis (default: true)
- `ANALYSIS_TIMEOUT`: Analysis timeout in seconds (default: 300)

See `configs/app.example.env` for all available options.

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=apps --cov-report=html

# Run specific test file
pytest tests/unit/test_event_normalization.py
```

### Linting & Type Checking

```bash
# Lint
ruff check .

# Type check
mypy apps

# Format code
ruff format .
```

### Database Migrations

```bash
# Create new migration
alembic -c infra/migrations/alembic.ini revision --autogenerate -m "description"

# Apply migrations
alembic -c infra/migrations/alembic.ini upgrade head

# Rollback
alembic -c infra/migrations/alembic.ini downgrade -1
```

## Services & Modules

### Gateway

FastAPI application handling:
- GitHub webhook events
- REST API endpoints
- Health checks and metrics
- Admin operations

### Ingestion Worker

Background worker processing:
- GitHub events from message queue
- Storing commits, PRs, diffs in database
- Uploading raw patches and artifacts to S3/MinIO
- Enriching data with metadata

### Analysis Worker

Background worker processing:
- GitHub PR events from message queue
- Fetching diffs from S3/MinIO storage
- Running AST parsing, rule validation, secret scanning
- Dependency risk analysis
- Ownership inference
- Storing findings in database
- Triggering automatic indexing

### Indexer Worker

Background worker for RAG indexing:
- Subscribes to indexing requests from analysis worker
- Chunks code (function-level, file-level, PR-level)
- Generates embeddings using local models
- Stores chunks in pgvector for semantic search

Run indexer worker:

```bash
# Message queue mode (automatic)
python -m apps.indexer --mq

# Manual mode (index specific repository)
python -m apps.indexer <repo_id>
```

### Notifier

Google Chat integration:
- PR summary notifications (v1)
- Findings and recommendations (v2 - planned)
- Rich card formatting

### Retention Job

Scheduled job for:
- Cleaning up raw files older than retention period (90 days)
- Preserving metadata in database
- Dry-run mode for testing

## Message Queue Support

The system supports multiple message queue backends:

- **Redis**: Simple pub/sub (default for dev)
- **Kafka**: Production-ready, partitioned topics
- **RabbitMQ**: AMQP-based queue

Configure via `MQ_TYPE` environment variable.

## Storage Support

- **MinIO**: S3-compatible local storage (default for dev)
- **S3**: AWS S3 or S3-compatible services

Configure via `STORAGE_TYPE` environment variable.

## RAG Query API

The RAG (Retrieval-Augmented Generation) system allows querying the codebase using natural language.

### Example Query

```bash
curl -X POST http://localhost:8080/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How does user authentication work?",
    "repo": "org/repo",
    "top_k": 5,
    "files": ["app/auth/**"]
  }'
```

### Response Format

```json
{
  "answer": "Based on the codebase: ...",
  "citations": [
    {
      "path": "app/auth/AuthService.java",
      "commit": "abc123...",
      "lines": [10, 20],
      "score": 0.95
    }
  ],
  "chunks": [...]
}
```

The system uses hybrid retrieval (BM25 + vector search) to find relevant code snippets and provides citations for traceability.

## Observability

### Metrics

Prometheus metrics available at `/metrics`:

- `webhook_received_total`: Total webhooks received by event type and status
- `webhook_processing_seconds`: Time spent processing webhooks
- Additional metrics for ingestion, storage operations, errors

### Logging

Structured logging with Loguru:
- Console output (development)
- File rotation (production)
- JSON format for log aggregation

Configuration in `configs/logging.yaml`.

## Retention Policy

- Raw diffs and artifacts: Retained for 90 days in S3/MinIO
- Metadata: Preserved indefinitely in database
- Retention job: Runs periodically to clean up old files

Run retention job manually:

```bash
# Dry run
python -m apps.ingestion.retention.worker --dry-run

# Actual cleanup
python -m apps.ingestion.retention.worker
```

## Security

### Air-gapped Environment

- All model inference on-premise/OSS
- Network policies to block external requests (configurable)
- Secret management via environment variables
- JWT authentication for API access (planned)

### GitHub Webhook Security

- Signature verification using `X-Hub-Signature-256`
- User-Agent validation
- Configurable trusted prefixes

## Roadmap

### Phase 1 (Current) - Webhooks → Storage ✅

- [x] Infrastructure setup (Postgres, S3, MQ)
- [x] GitHub webhook handling
- [x] Event normalization
- [x] Ingestion pipeline
- [x] Storage (diffs, artifacts)
- [x] Google Chat notifications v1
- [x] Retention job
- [x] Observability (metrics, logging)

### Phase 2 (Current) - Analysis & RAG ✅

- [x] AST parsers (Java/Python/PHP)
- [x] Rule engine (architecture rules)
- [x] Secret scanning
- [x] Dependency risk analysis
- [x] Ownership inference
- [x] RAG indexing
- [x] RAG query API
- [x] Automatic indexing after analysis
- [x] Integration between analysis and indexing workers

### Phase 3 (Next) - RCA & TTF

- [ ] RCA generator (automatic on build failure)
- [ ] TTF (Time-to-Fix) prediction model
- [ ] Policy & guardrails
- [ ] Security audit polish

## License

Internal use only.
