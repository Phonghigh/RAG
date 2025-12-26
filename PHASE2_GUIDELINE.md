# Phase 2 Implementation Guideline

## Overview

Phase 2 adds code analysis capabilities (AST parsing, rule validation, security scanning) and implements the RAG system for code intelligence queries. This guide covers setup, configuration, usage, and testing.

---

## Prerequisites

1. **Python 3.11+** with virtual environment
2. **PostgreSQL 16+** with pgvector extension
3. **Redis/Kafka/RabbitMQ** (for message queue)
4. **MinIO/S3** (for object storage)
5. **Docker & Docker Compose** (optional, for infrastructure)

---

## Installation

### 1. Install Dependencies

```bash
# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Note: sentence-transformers will download the model on first use
```

### 2. Configure Environment

```bash
# Copy example config
cp configs/app.example.env configs/.env

# Edit configs/.env and set:
# - EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2 (or your preferred model)
# - RULES_CONFIG_PATH=configs/rules.yaml
# - CVE_DB_PATH=path/to/cve-database.json (optional)
```

### 3. Setup Rules Configuration

```bash
# Copy example rules
cp configs/rules.example.yaml configs/rules.yaml

# Edit configs/rules.yaml to match your architecture
# See configs/rules.example.yaml for examples
```

### 4. Database Setup

```bash
# Run migrations (if not already done)
alembic -c infra/migrations/alembic.ini upgrade head

# Verify pgvector extension is enabled
psql -U postgres -d rca_rag -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

---

## Component Overview

### 1. AST Parsers (`apps/analysis/parsers/`)

**Purpose**: Parse code files to extract functions, classes, imports.

**Supported Languages**:
- Java (using `javalang`)
- Python (using `ast`)
- PHP (basic pattern matching)

**Usage**:
```python
from apps.analysis.parsers import get_parser

parser = get_parser("MyClass.java", "java")
parsed = parser.parse_file(code_content, "MyClass.java")

print(parsed.functions)  # List of Function objects
print(parsed.classes)    # List of Class objects
print(parsed.imports)    # List of Import objects
```

### 2. Rule Engine (`apps/analysis/rules/`)

**Purpose**: Validate architecture rules (Clean Architecture, dependency constraints).

**Rule Types**:
- `forbid_imports`: Prevent imports from certain modules
- `allow_only`: Only allow imports from specific modules
- `graph_check`: Detect dependency cycles
- `enforce_public`: Enforce public API contracts

**Usage**:
```python
from apps.analysis.rules import RuleEngine

engine = RuleEngine("configs/rules.yaml")
violations = engine.evaluate_file(parsed_file)

for violation in violations:
    print(f"Rule {violation['rule_id']}: {violation['message']}")
```

### 3. Secret Scanner (`apps/analysis/security/`)

**Purpose**: Detect secrets, API keys, passwords in code.

**Features**:
- Pattern-based detection (API keys, tokens, passwords)
- Entropy analysis for random strings
- False positive filtering
- Secret redaction

**Usage**:
```python
from apps.analysis.security import SecretScanner

scanner = SecretScanner()
findings = scanner.scan_file(code_content, "file.py")

for finding in findings:
    print(f"Secret detected: {finding['message']} at line {finding['line']}")
```

### 4. Dependency Risk Analyzer (`apps/analysis/dependencies/`)

**Purpose**: Analyze dependency files for vulnerabilities.

**Supported Files**:
- `pom.xml` (Maven)
- `requirements.txt` (pip)
- `composer.json` (Composer)

**Usage**:
```python
from apps.analysis.dependencies import DependencyParser, DependencyRiskAnalyzer

parser = DependencyParser()
dependencies = parser.parse_file(pom_xml_content, "pom.xml")

analyzer = DependencyRiskAnalyzer("path/to/cve-db.json")
risks = analyzer.analyze(dependencies)

for risk in risks:
    print(f"{risk.dependency.name}: {risk.risk_level} - {risk.cve_ids}")
```

### 5. Ownership Inference (`apps/analysis/ownership/`)

**Purpose**: Infer code ownership using multiple signals.

**Signals**:
- Git blame analysis
- Recent commit history (30-90 days)
- Reviewer patterns
- Service map configuration

**Usage**:
```python
from apps.analysis.ownership import OwnershipInferrer

inferrer = OwnershipInferrer()
candidates = inferrer.infer(
    file_path="app/domain/UserService.java",
    service_map=service_map_config,
)

for candidate in candidates[:3]:  # Top 3
    print(f"{candidate.candidate}: {candidate.score:.2%} ({candidate.reasoning})")
```

### 6. RAG Indexer (`apps/indexer/`)

**Purpose**: Chunk code, generate embeddings, store in pgvector.

**Chunking Strategies**:
- Function-level: Each function/method = 1 chunk
- File-level: Entire file for small files (<500 LOC)
- PR-level: Each file diff = 1 chunk

**Usage**:
```bash
# Index all diffs for a repository
python -m apps.indexer <repo_id>

# Or programmatically:
from apps.indexer.worker import IndexerWorker

worker = IndexerWorker()
chunks = await worker.index_repo_diffs(repo_id, session)
```

### 7. RAG Query API (`apps/gateway/api/rag.py`)

**Purpose**: Semantic search API with citation support.

**Endpoint**: `POST /rag/query`

**Request**:
```json
{
  "question": "How does user authentication work?",
  "repo": "org/repo",
  "top_k": 5,
  "files": ["app/auth/**"]  // optional
}
```

**Response**:
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

---

## Running the System

### 1. Start Infrastructure

```bash
# Using Docker Compose
docker-compose -f deployments/docker-compose.dev.yml up -d

# Or start manually:
# - PostgreSQL on port 5432
# - Redis on port 6379
# - MinIO on ports 9000, 9001
```

### 2. Start Services

**Terminal 1 - API Gateway**:
```bash
uvicorn apps.gateway.main:app --host 0.0.0.0 --port 8080
```

**Terminal 2 - Ingestion Worker**:
```bash
python -m apps.ingestion.worker
```

**Terminal 3 - Analysis Worker**:
```bash
python -m apps.analysis
```

**Terminal 4 - Indexer Worker** (optional, can run manually):
```bash
python -m apps.indexer <repo_id>
```

### 3. Verify Services

```bash
# Health check
curl http://localhost:8080/health

# API docs
open http://localhost:8080/docs
```

---

## Testing

### Unit Tests

```bash
# Run all unit tests
pytest tests/unit/

# Run specific test file
pytest tests/unit/test_parsers.py -v

# Run with coverage
pytest tests/unit/ --cov=apps --cov-report=html
```

### Integration Tests

```bash
# Run integration tests
pytest tests/integration/ -v

# Test analysis flow
pytest tests/integration/test_analysis_flow.py -v
```

### Manual Testing

**1. Test AST Parsers**:
```python
from apps.analysis.parsers import get_parser

code = """
public class Test {
    public void test() {
        System.out.println("test");
    }
}
"""

parser = get_parser("Test.java", "java")
result = parser.parse_file(code, "Test.java")
print(result.classes[0].name)  # Should print "Test"
```

**2. Test Rule Engine**:
```python
from apps.analysis.rules import RuleEngine
from apps.analysis.parsers import get_parser

# Parse file
parser = get_parser("app/domain/User.java", "java")
parsed = parser.parse_file(code, "app/domain/User.java")

# Evaluate rules
engine = RuleEngine("configs/rules.yaml")
violations = engine.evaluate_file(parsed)
print(f"Found {len(violations)} violations")
```

**3. Test Secret Scanner**:
```python
from apps.analysis.security import SecretScanner

code = 'api_key = "sk_live_1234567890abcdef"'
scanner = SecretScanner()
findings = scanner.scan_file(code, "test.py")
assert len(findings) > 0
```

**4. Test RAG Query**:
```bash
curl -X POST http://localhost:8080/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How does user authentication work?",
    "repo": "org/repo",
    "top_k": 5
  }'
```

---

## Configuration Details

### Rules Configuration (`configs/rules.yaml`)

Example rule:
```yaml
rules:
  - id: domain_no_dep_infra
    type: forbid_imports
    severity: error
    from:
      - "**/domain/**"
    to:
      - "**/infra/**"
      - "**/adapters/**"
```

### CVE Database Format

**JSON Format**:
```json
{
  "com.example:library": [
    {
      "cve_id": "CVE-2024-1234",
      "severity": "high",
      "description": "Vulnerability description"
    }
  ]
}
```

**CSV Format**:
```csv
package,cve_id,severity,description
com.example:library,CVE-2024-1234,high,Vulnerability description
```

### Service Map Format

```json
{
  "modules": {
    ":billing": {
      "team": "payments",
      "owner": "team-payments@example.com"
    }
  },
  "paths": {
    "apps/billing/**": ":billing"
  }
}
```

---

## Troubleshooting

### Common Issues

**1. Model Download Fails**:
```bash
# Set proxy if needed
export HTTP_PROXY=http://proxy:port
export HTTPS_PROXY=http://proxy:port

# Or download manually
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

**2. pgvector Extension Not Found**:
```bash
# Install pgvector extension
psql -U postgres -d rca_rag -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

**3. Parser Fails for Java**:
```bash
# Ensure javalang is installed
pip install javalang>=0.13.0

# Check Java code syntax
```

**4. BM25 Search Returns Empty**:
```bash
# Ensure PostgreSQL full-text search is configured
# Check that rag_chunks.content has text data
psql -U postgres -d rca_rag -c "SELECT COUNT(*) FROM rag_chunks WHERE content IS NOT NULL;"
```

**5. Analysis Worker Not Processing**:
```bash
# Check message queue connection
# Verify MQ_TYPE and connection settings in configs/.env
# Check worker logs for errors
```

---

## Performance Tuning

### Embedding Model Selection

- **all-MiniLM-L6-v2**: Fast, 384 dimensions (default)
- **BAAI/bge-small-en-v1.5**: Better quality, 384 dimensions
- **all-mpnet-base-v2**: Best quality, 768 dimensions (slower)

### Chunking Strategy

- **Function-level**: Best for code search, more chunks
- **File-level**: Best for small files, fewer chunks
- **PR-level**: Fallback, less semantic meaning

### Vector Search Optimization

```sql
-- Create index for faster similarity search
CREATE INDEX idx_rag_chunks_embedding ON rag_chunks 
USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 100);

-- Adjust lists parameter based on data size
-- lists = rows / 1000 (minimum 10)
```

---

## Next Steps

### Phase 3 (Future)

1. **RCA Generator**: Automatic root cause analysis on build failures
2. **TTF Prediction**: Time-to-fix estimation model
3. **Policy Engine**: Guardrails and escalation rules
4. **Security Audit**: Enhanced security scanning

### Immediate Improvements

1. **Add More Parsers**: TypeScript, Go, Rust
2. **Improve PHP Parser**: Use tree-sitter-php
3. **Enhanced Ownership**: Integrate with Git API for real blame data
4. **Better Chunking**: Overlap chunks, sliding window
5. **Response Generation**: Use LLM for better answers (air-gapped compatible)

---

## API Reference

### RAG Query Endpoint

**POST** `/rag/query`

**Request Body**:
```json
{
  "question": "string (required)",
  "repo": "string (required)",
  "branch": "string (optional)",
  "files": ["string"] (optional),
  "top_k": 5 (optional, default: 5)
}
```

**Response**:
```json
{
  "answer": "string",
  "citations": [
    {
      "path": "string",
      "commit": "string",
      "lines": [1, 2, 3],
      "score": 0.95
    }
  ],
  "chunks": [...]
}
```

---

## Support

For issues or questions:
1. Check logs: `logs/` directory
2. Review configuration: `configs/.env`
3. Test individual components using examples above
4. Check database: Verify data in `rag_chunks`, `findings` tables

---

## Quick Start Checklist

- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Configure environment: Copy and edit `configs/.env`
- [ ] Setup rules: Copy and edit `configs/rules.yaml`
- [ ] Run migrations: `alembic upgrade head`
- [ ] Start infrastructure: `docker-compose up -d`
- [ ] Start API gateway: `uvicorn apps.gateway.main:app`
- [ ] Start ingestion worker: `python -m apps.ingestion.worker`
- [ ] Start analysis worker: `python -m apps.analysis`
- [ ] Index repository: `python -m apps.indexer <repo_id>`
- [ ] Test RAG query: `curl -X POST http://localhost:8080/rag/query ...`

---

**Last Updated**: Phase 2 Implementation Complete
