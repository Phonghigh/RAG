# Getting Started Guide - Windows

This guide will help you set up and run the RCA-RAG Code Intelligence system on Windows.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Database Setup](#database-setup)
5. [Running the System](#running-the-system)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)
8. [Next Steps](#next-steps)

## Prerequisites

Before starting, ensure you have the following installed:

### Required Software

- **Python 3.11+** - Download from [python.org](https://www.python.org/downloads/)
  - ✅ Check "Add Python to PATH" during installation
  - Verify: `python --version` in PowerShell
- **Docker Desktop** - Download from [docker.com](https://www.docker.com/products/docker-desktop/)
  - Install and start Docker Desktop
  - Verify: `docker --version` in PowerShell
- **Git** - Download from [git-scm.com](https://git-scm.com/download/win)
  - Verify: `git --version` in PowerShell

### System Requirements

- **RAM**: Minimum 4GB, recommended 8GB+
- **Disk Space**: At least 10GB free (for Docker images and data)
- **Network**: Internet connection for downloading dependencies (unless air-gapped)

### Optional Dependencies

- **Kafka** or **RabbitMQ** (optional, Redis is default)
- **AWS S3** or compatible storage (optional, MinIO is default)

## Installation

### Step 1: Clone the Repository

```powershell
git clone <repository-url>
cd rca-rag
```

### Step 2: Create Virtual Environment

```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\activate
```

**Note**: Always activate the virtual environment before running any Python commands. You'll need to do this in each PowerShell window.

### Step 3: Install Dependencies

```powershell
# Upgrade pip
pip install --upgrade pip

# Install the project and dependencies
pip install -e .

# Or install from requirements.txt
pip install -r requirements.txt
```

**Note**: The first time you run the system, `sentence-transformers` will download the embedding model (all-MiniLM-L6-v2, ~90MB). This happens automatically.

### Step 4: Verify Installation

```powershell
# Check Python version
python --version  # Should be 3.11+

# Verify key packages
python -c "import fastapi; print('FastAPI OK')"
python -c "import sqlalchemy; print('SQLAlchemy OK')"
python -c "import sentence_transformers; print('Sentence Transformers OK')"
```

## Configuration

### Step 1: Create Environment File

```powershell
# Copy the example configuration
Copy-Item configs\app.example.env configs\.env

# Edit the configuration file
notepad configs\.env
# or use VS Code
code configs\.env
```

### Step 2: Configure Key Settings

Edit `configs\.env` and update at minimum:

```env
# Database connection (matches Docker Compose defaults)
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rca_rag

# Message Queue (Redis is default, works with Docker Compose)
MQ_TYPE=redis
REDIS_URL=redis://localhost:6379/0

# Storage (MinIO is default, works with Docker Compose)
STORAGE_TYPE=minio
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET_NAME=rca-rag

# GitHub Webhook Secret (REQUIRED for webhooks)
GITHUB_WEBHOOK_SECRET=your-secret-key-here-change-this

# Embedding Model (default is fine for most cases)
EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2
```

### Step 3: Configure Rules (Optional)

```powershell
# Copy example rules configuration
Copy-Item configs\rules.example.yaml configs\rules.yaml

# Edit rules.yaml
notepad configs\rules.yaml
# or
code configs\rules.yaml
```

## Database Setup

### Option 1: Using Docker Compose (Recommended)

This is the easiest way to get started. Docker Compose includes pgvector pre-installed, avoiding manual installation complexity:

```powershell
# Start all infrastructure services
docker-compose -f deployments\docker-compose.dev.yml up -d

# Wait for services to be healthy (check status)
docker-compose -f deployments\docker-compose.dev.yml ps

# Verify PostgreSQL is ready
docker-compose -f deployments\docker-compose.dev.yml exec db pg_isready -U postgres

# Verify pgvector extension is available
docker-compose -f deployments\docker-compose.dev.yml exec db psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

This will start:
- **PostgreSQL 16** with pgvector pre-installed (port 5432)
- **Redis** (port 6379)
- **MinIO** (ports 9000, 9001)

**Note**: The Docker Compose setup uses the `pgvector/pgvector:pg16` image which includes pgvector extension. This avoids the need to manually install pgvector on Windows PostgreSQL.

### Option 2: Manual PostgreSQL Setup (Not Recommended)

If you must use local PostgreSQL on Windows (not recommended due to pgvector complexity):

1. **Download pre-built pgvector for Windows:**
   - Visit: https://github.com/pgvector/pgvector/releases
   - Download the Windows binary matching your PostgreSQL version (e.g., `pgvector-v0.5.1-pg16-windows-x64.zip`)
   - Extract files to your PostgreSQL installation directory:
     - `vector.dll` → `C:\Program Files\PostgreSQL\16\lib\`
     - `vector.control` → `C:\Program Files\PostgreSQL\16\share\extension\`
     - `vector--*.sql` → `C:\Program Files\PostgreSQL\16\share\extension\`

2. **Or use pgvector Docker container:**
   ```powershell
   # Run PostgreSQL with pgvector in Docker
   docker run -d `
     --name postgres-pgvector `
     -e POSTGRES_PASSWORD=postgres `
     -e POSTGRES_DB=rca_rag `
     -p 5432:5432 `
     pgvector/pgvector:pg16
   ```

3. **Then create extension:**
   ```powershell
   psql -U postgres -d rca_rag -c "CREATE EXTENSION IF NOT EXISTS vector;"
   ```

**We strongly recommend using Docker Compose instead** (Option 1).

### Step 2: Run Database Migrations

```powershell
# Run Alembic migrations
alembic -c infra\migrations\alembic.ini upgrade head

# Verify tables were created (using Docker)
docker-compose -f deployments\docker-compose.dev.yml exec db psql -U postgres -d rca_rag -c "\dt"
```

You should see tables: `repos`, `commits`, `pull_requests`, `diffs`, `findings`, `rag_chunks`, etc.

### Step 3: Verify pgvector Extension

```powershell
# Using Docker Compose
docker-compose -f deployments\docker-compose.dev.yml exec db psql -U postgres -d rca_rag -c "SELECT * FROM pg_extension WHERE extname = 'vector';"
```

## Running the System

### Development Mode (Recommended for First Run)

Run each service in a separate PowerShell window:

#### PowerShell Window 1: API Gateway

```powershell
# Navigate to project directory
cd D:\AI\RAG  # Adjust path as needed

# Activate virtual environment
.venv\Scripts\activate

# Start API gateway
# Note: If you get WinError 10013, try using 127.0.0.1 or a different port (8081)
uvicorn apps.gateway.main:app --host 127.0.0.1 --port 8080 --reload
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8080
INFO:     Application startup complete.
```

**Troubleshooting**: If you see `WinError 10013`, see [Port Access Permission Error](#8-port-access-permission-error-winerror-10013) in the Troubleshooting section.

#### PowerShell Window 2: Ingestion Worker

```powershell
cd D:\AI\RAG
.venv\Scripts\activate
python -m apps.ingestion.worker
```

#### PowerShell Window 3: Analysis Worker

```powershell
cd D:\AI\RAG
.venv\Scripts\activate
python -m apps.analysis
```

#### PowerShell Window 4: Indexer Worker (Message Queue Mode)

```powershell
cd D:\AI\RAG
.venv\Scripts\activate
python -m apps.indexer --mq
```

### Verify Services Are Running

```powershell
# Check API health
curl http://localhost:8080/health

# Open API docs in browser
start http://localhost:8080/docs
```

### Production Mode (Docker Compose)

```powershell
# Build and start all services
docker-compose -f deployments\docker-compose.dev.yml up --build

# Or run in background
docker-compose -f deployments\docker-compose.dev.yml up -d

# View logs
docker-compose -f deployments\docker-compose.dev.yml logs -f

# Stop services
docker-compose -f deployments\docker-compose.dev.yml down
```

## Testing

### Run Unit Tests

```powershell
# Run all tests


# Run with coverage
pytest --cov=apps --cov-report=html

# Run specific test file
pytest tests\unit\test_parsers.py -v

# Run integration tests
pytest tests\integration\ -v
```

### Manual Testing

#### 1. Test Webhook Endpoint

```powershell
# Send a test webhook (requires valid signature)
curl -X POST http://localhost:8080/webhooks/github `
  -H "Content-Type: application/json" `
  -H "X-GitHub-Event: pull_request" `
  -H "X-Hub-Signature-256: sha256=..." `
  -d "@tests\fixtures\github_events.py"
```

#### 2. Test RAG Query API

First, ensure you have indexed some code:

```powershell
# Manually index a repository (if you have repo_id)
python -m apps.indexer <repo_id>
```

Then query:

```powershell
curl -X POST http://localhost:8080/rag/query `
  -H "Content-Type: application/json" `
  -d '{\"question\": \"How does authentication work?\", \"repo\": \"org/repo\", \"top_k\": 5}'
```

#### 3. Test Analysis Components

```powershell
# Test AST parser
python -c "from apps.analysis.parsers import get_parser; parser = get_parser('Test.java', 'java'); code = 'public class Test { public void test() {} }'; result = parser.parse_file(code, 'Test.java'); print(f'Found {len(result.classes)} classes')"

# Test secret scanner
python -c "from apps.analysis.security import SecretScanner; scanner = SecretScanner(); findings = scanner.scan_file('api_key = \"sk_live_1234567890\"', 'test.py'); print(f'Found {len(findings)} secrets')"
```

## Troubleshooting

### Common Issues

#### 1. Database Connection Error

**Error**: `could not connect to server` or `connection refused`

**Solutions**:
```powershell
# Check if PostgreSQL is running
docker-compose -f deployments\docker-compose.dev.yml ps db

# Check connection string in configs\.env
# Verify DATABASE_URL format: postgresql+psycopg://user:pass@host:port/dbname

# Test connection manually (using Docker)
docker-compose -f deployments\docker-compose.dev.yml exec db psql -U postgres -d rca_rag
```

#### 2. pgvector Extension Not Found

**Error**: `extension "vector" does not exist` or `extension "vector" is not available`

**Solutions**:

```powershell
# Option 1: Use Docker Compose (RECOMMENDED - Easiest)
# Docker Compose includes pgvector automatically
docker-compose -f deployments\docker-compose.dev.yml up -d db

# Option 2: Use pgvector Docker image directly
docker run -d `
  --name postgres-pgvector `
  -e POSTGRES_PASSWORD=postgres `
  -e POSTGRES_DB=rca_rag `
  -p 5432:5432 `
  pgvector/pgvector:pg16

# Then update DATABASE_URL in configs\.env to use localhost:5432
```

**Manual Installation (if you must use local PostgreSQL):**
1. Download pgvector Windows binaries from: https://github.com/pgvector/pgvector/releases
2. Extract to PostgreSQL installation directory (see Database Setup section)
3. Restart PostgreSQL service
4. Run: `psql -U postgres -d rca_rag -c "CREATE EXTENSION IF NOT EXISTS vector;"`

**Verify Installation:**
```powershell
# Check if extension exists (using Docker)
docker-compose -f deployments\docker-compose.dev.yml exec db psql -U postgres -d rca_rag -c "SELECT * FROM pg_extension WHERE extname = 'vector';"
```

#### 3. Embedding Model Download Fails

**Error**: `Error loading embedding model` or network timeout

**Solutions**:
```powershell
# Set proxy if needed (PowerShell)
$env:HTTP_PROXY="http://proxy:port"
$env:HTTPS_PROXY="http://proxy:port"

# Or download manually
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Or use a different model
# Edit configs\.env: EMBEDDING_MODEL_NAME=BAAI/bge-small-en-v1.5
```

#### 4. Message Queue Connection Error

**Error**: `Error connecting to Redis` or `Connection refused`

**Solutions**:
```powershell
# Check if Redis is running
docker-compose -f deployments\docker-compose.dev.yml ps mq

# Test Redis connection (using Docker)
docker-compose -f deployments\docker-compose.dev.yml exec mq redis-cli ping  # Should return PONG

# Check REDIS_URL in configs\.env
# Format: redis://localhost:6379/0
```

#### 5. Storage Connection Error

**Error**: `Failed to upload file` or `Failed to download file`

**Solutions**:
```powershell
# Check if MinIO is running
docker-compose -f deployments\docker-compose.dev.yml ps s3

# Access MinIO console: http://localhost:9001
# Login: minioadmin / minioadmin

# Verify S3 settings in configs\.env
# Check S3_ENDPOINT_URL, S3_ACCESS_KEY, S3_SECRET_KEY
```

#### 6. Analysis Worker Not Processing PRs

**Symptoms**: No findings in database after PR events

**Solutions**:
```powershell
# Check worker logs for errors
# Look for: "No diffs found" or "Error fetching diff content"

# Verify diffs exist in database (using Docker)
docker-compose -f deployments\docker-compose.dev.yml exec db psql -U postgres -d rca_rag -c "SELECT COUNT(*) FROM diffs;"

# Check object_uri format in diffs table
docker-compose -f deployments\docker-compose.dev.yml exec db psql -U postgres -d rca_rag -c "SELECT id, path, object_uri FROM diffs LIMIT 5;"

# Verify storage is accessible
python -c "from apps.shared.storage import get_storage_client; storage = get_storage_client(); print('Storage client OK')"
```

#### 7. Indexer Worker Not Indexing

**Symptoms**: No chunks in rag_chunks table

**Solutions**:
```powershell
# Check if indexer worker is running
# Verify it's subscribed to 'indexing.requested' topic

# Manually trigger indexing
python -m apps.indexer <repo_id>

# Check for errors in logs
# Verify embedding model is loaded
```

#### 8. Port Access Permission Error (WinError 10013)

**Error**: `[WinError 10013] An attempt was made to access a socket in a way forbidden by its access permissions`

**Solutions**:

**Option 1: Check if port is already in use**
```powershell
# Check what's using port 8080
netstat -ano | findstr :8080

# If something is using it, either stop that service or change the port
# To change port, edit configs\.env: APP_PORT=8081
```

**Option 2: Use a different port**
```powershell
# Edit configs\.env and change:
APP_PORT=8081

# Then start with new port
uvicorn apps.gateway.main:app --host 0.0.0.0 --port 8081 --reload
```

**Option 3: Check Windows reserved ports**
```powershell
# Check if Windows has reserved the port range
netsh interface ipv4 show excludedportrange protocol=tcp

# If 8080 is in a reserved range, use a different port (like 8081, 8082, etc.)
```

**Option 4: Run as Administrator (if needed)**
```powershell
# Right-click PowerShell and select "Run as Administrator"
# Then try again
uvicorn apps.gateway.main:app --host 0.0.0.0 --port 8080 --reload
```

**Option 5: Use localhost instead of 0.0.0.0**
```powershell
# Sometimes 0.0.0.0 causes issues on Windows, try localhost
uvicorn apps.gateway.main:app --host 127.0.0.1 --port 8080 --reload
```

**Most Common Solution**: Use port 8081 or 8082 instead of 8080, as Windows often reserves lower ports.

#### 9. RAG Query Returns Empty Results

**Solutions**:
```powershell
# Verify chunks exist (using Docker)
docker-compose -f deployments\docker-compose.dev.yml exec db psql -U postgres -d rca_rag -c "SELECT COUNT(*) FROM rag_chunks;"

# Check if chunks have embeddings
docker-compose -f deployments\docker-compose.dev.yml exec db psql -U postgres -d rca_rag -c "SELECT COUNT(*) FROM rag_chunks WHERE embedding IS NOT NULL;"

# Ensure repository is indexed
python -m apps.indexer <repo_id>

# Try a simpler query
curl -X POST http://localhost:8080/rag/query `
  -H "Content-Type: application/json" `
  -d '{\"question\": \"test\", \"repo\": \"org/repo\", \"top_k\": 10}'
```

### Debug Mode

Enable debug logging:

```powershell
# Edit configs\.env
# Change: LOG_LEVEL=DEBUG

# Restart services
```

### Check Service Logs

**Docker Compose:**
```powershell
# All services
docker-compose -f deployments\docker-compose.dev.yml logs -f

# Specific service
docker-compose -f deployments\docker-compose.dev.yml logs -f api
docker-compose -f deployments\docker-compose.dev.yml logs -f worker
```

**Manual services:**
- Check console output in each PowerShell window
- Logs are also written to `logs\` directory (if configured)

## Next Steps

### 1. Configure GitHub Webhook

1. Go to your GitHub repository → Settings → Webhooks
2. Add webhook URL: `http://your-server:8080/webhooks/github`
3. Set secret to match `GITHUB_WEBHOOK_SECRET` in `configs\.env`
4. Select events: `push`, `pull_request`, `pull_request_review`, `check_run`

### 2. Set Up Rules Configuration

Edit `configs\rules.yaml` to match your architecture:

```yaml
rules:
  - id: domain_no_dep_infra
    type: forbid_imports
    severity: error
    from:
      - "**/domain/**"
    to:
      - "**/infra/**"
```

### 3. Configure Service Map

```powershell
# Via API
curl -X POST http://localhost:8080/admin/service-map `
  -H "Content-Type: application/json" `
  -d '{\"repo_name\": \"org/repo\", \"service_map\": {\"modules\": {\":billing\": {\"team\": \"payments\", \"owner\": \"team-payments@example.com\"}}}}'
```

### 4. Index Existing Repository

```powershell
# First, ensure repository exists in database (via webhook or manual)
# Get repo_id from database (using Docker)
docker-compose -f deployments\docker-compose.dev.yml exec db psql -U postgres -d rca_rag -c "SELECT id, name FROM repos;"

# Index repository
python -m apps.indexer <repo_id>
```

### 5. Explore API Documentation

Visit `http://localhost:8080/docs` for interactive API documentation.

### 6. Monitor Metrics

```powershell
# Prometheus metrics endpoint
curl http://localhost:8080/metrics

# Health checks
curl http://localhost:8080/health
curl http://localhost:8080/health/ready
curl http://localhost:8080/health/live
```

### 7. Set Up Google Chat Notifications (Optional)

1. Create Google Chat webhook
2. Add `GOOGLE_CHAT_WEBHOOK_URL` to `configs\.env`
3. Restart services

## Additional Resources

- **README.md** - Project overview and API documentation
- **PHASE2_GUIDELINE.md** - Phase 2 implementation details
- **configs/app.example.env** - All configuration options
- **configs/rules.example.yaml** - Rules configuration examples

## Getting Help

If you encounter issues:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review service logs for error messages
3. Verify all prerequisites are installed
4. Ensure configuration matches your environment
5. Check that all services are running and healthy

## Quick Start Checklist

- [ ] Python 3.11+ installed
- [ ] Docker Desktop installed and running
- [ ] Repository cloned
- [ ] Virtual environment created and activated
- [ ] Dependencies installed (`pip install -e .`)
- [ ] Configuration file created (`configs\.env`)
- [ ] Infrastructure started (`docker-compose up -d`)
- [ ] Database migrations run (`alembic upgrade head`)
- [ ] API gateway running (`uvicorn apps.gateway.main:app`)
- [ ] Ingestion worker running (`python -m apps.ingestion.worker`)
- [ ] Analysis worker running (`python -m apps.analysis`)
- [ ] Indexer worker running (`python -m apps.indexer --mq`)
- [ ] Health check passes (`curl http://localhost:8080/health`)
- [ ] API docs accessible (`http://localhost:8080/docs`)

Once all checkboxes are complete, you're ready to use the system!

## Windows-Specific Notes

- **PowerShell vs CMD**: Use PowerShell (recommended) or Command Prompt
- **Path Separators**: Use backslashes (`\`) in paths, forward slashes (`/`) work too
- **Line Endings**: Git should handle this automatically
- **pgvector**: Use Docker Compose - it includes pgvector automatically (no manual installation needed)
- **Virtual Environment**: Always activate with `.venv\Scripts\activate` (not `.venv/bin/activate`)
- **Docker Commands**: Use backslashes for line continuation in PowerShell: `` ` ``

## Common Windows Issues

- **"python is not recognized"**: Add Python to PATH or use full path: `C:\Python311\python.exe`
- **"docker is not recognized"**: Restart PowerShell after installing Docker Desktop
- **Port already in use**: Change port in `configs\.env` or stop conflicting services
- **WinError 10013 (Port permission)**: Use a different port (8081, 8082) or check Windows reserved ports (see [Troubleshooting](#troubleshooting))
- **pgvector extension error**: Use Docker Compose (see [Troubleshooting](#troubleshooting))
