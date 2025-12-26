# How to Set Up Your Repository for Testing Commits

This guide explains how to configure your repository to test commits with the RCA-RAG system.

## Overview

The system processes commits through **GitHub webhooks**. When you push commits or create pull requests, GitHub sends webhook events to your API, which then:
1. Ingests the commit/PR data
2. Analyzes the code changes
3. Indexes the code for RAG queries

## Setup Steps

### 1. Configure GitHub Webhook Secret

First, set up your webhook secret in the configuration file:

```powershell
# Edit configs/.env
notepad configs\.env
```

Set the `GITHUB_WEBHOOK_SECRET`:
```env
GITHUB_WEBHOOK_SECRET=your-secret-key-here-make-it-random-and-secure
```

**Important**: Use a strong, random secret (at least 32 characters). You can generate one:
```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. Start the API Gateway

The webhook endpoint needs to be running:

```powershell
cd D:\AI\RAG
.venv\Scripts\activate
uvicorn apps.gateway.main:app --host 0.0.0.0 --port 8080
```

The webhook endpoint will be available at: `http://your-server:8080/webhooks/github`

### 3. Configure GitHub Webhook

#### Option A: Using GitHub Web Interface (Recommended)

1. Go to your GitHub repository
2. Navigate to **Settings** → **Webhooks** → **Add webhook**
3. Configure:
   - **Payload URL**: `http://your-server-ip:8080/webhooks/github`
     - For local testing: Use `ngrok` or similar tunnel (see below)
     - For production: Use your actual server URL
   - **Content type**: `application/json`
   - **Secret**: The same secret you set in `GITHUB_WEBHOOK_SECRET`
   - **Events**: Select:
     - ✅ `push` - For commit analysis
     - ✅ `pull_request` - For PR analysis
     - ✅ `pull_request_review` - For review events
     - ✅ `check_run` - For CI/CD integration
   - **Active**: ✅ Checked
4. Click **Add webhook**

#### Option B: Using GitHub CLI

```bash
gh api repos/:owner/:repo/hooks \
  -X POST \
  -f name=web \
  -f config[url]=http://your-server:8080/webhooks/github \
  -f config[content_type]=json \
  -f config[secret]=your-secret-key-here \
  -f events[]=push \
  -f events[]=pull_request \
  -f events[]=pull_request_review \
  -f events[]=check_run \
  -f active=true
```

### 4. Expose Local Server (For Local Testing)

If testing locally, use a tunnel service to expose your localhost:

#### Using ngrok (Recommended)

1. Download ngrok from https://ngrok.com/
2. Start tunnel:
   ```powershell
   ngrok http 8080
   ```
3. Copy the forwarding URL (e.g., `https://abc123.ngrok.io`)
4. Use this URL in GitHub webhook configuration

#### Using Cloudflare Tunnel (Alternative)

```powershell
cloudflared tunnel --url http://localhost:8080
```

### 5. Start All Workers

Make sure all workers are running to process events:

```powershell
# Terminal 1: API Gateway (already running)
uvicorn apps.gateway.main:app --host 0.0.0.0 --port 8080

# Terminal 2: Ingestion Worker
python -m apps.ingestion.worker

# Terminal 3: Analysis Worker
python -m apps.analysis

# Terminal 4: Indexer Worker (optional, for RAG)
python -m apps.indexer --mq
```

### 6. Test the Setup

#### Test 1: Send a Test Webhook (Ping)

GitHub automatically sends a `ping` event when you create a webhook. Check your API logs to see if it was received.

Or manually test:
```powershell
# Test ping endpoint
curl http://localhost:8080/health
```

#### Test 2: Make a Test Commit

1. Make a change in your repository:
   ```bash
   echo "# Test commit" >> README.md
   git add README.md
   git commit -m "Test commit for RCA-RAG"
   git push
   ```

2. Check the logs:
   - **API Gateway**: Should show webhook received
   - **Ingestion Worker**: Should show processing the push event
   - **Analysis Worker**: Should show analyzing the commit/PR

#### Test 3: Create a Test Pull Request

1. Create a new branch:
   ```bash
   git checkout -b test-pr
   echo "def test_function():\n    return 'test'" > test.py
   git add test.py
   git commit -m "Add test function"
   git push origin test-pr
   ```

2. Create a PR on GitHub

3. Check logs - you should see:
   - Webhook received
   - PR created in database
   - Diffs fetched and stored
   - Analysis running (secret scanning, rule validation, etc.)
   - Findings stored in database

### 7. Verify Data in Database

Check that commits and PRs are being stored:

```powershell
# Connect to database (using Docker)
docker-compose -f deployments\docker-compose.dev.yml exec db psql -U postgres -d rca_rag

# In PostgreSQL:
SELECT * FROM repos;
SELECT * FROM commits ORDER BY created_at DESC LIMIT 5;
SELECT * FROM pull_requests ORDER BY created_at_db DESC LIMIT 5;
SELECT * FROM diffs ORDER BY created_at DESC LIMIT 5;
SELECT * FROM findings ORDER BY created_at DESC LIMIT 10;
```

### 8. Query Analysis Results

#### View Findings via API

```powershell
# Get findings for a repository (if API endpoint exists)
# Or query database directly:
SELECT 
    f.id,
    f.file_path,
    f.severity,
    f.message,
    f.rule_id,
    pr.number as pr_number
FROM findings f
JOIN pull_requests pr ON f.pr_id = pr.id
WHERE pr.repo_id = (SELECT id FROM repos WHERE name = 'your-org/your-repo')
ORDER BY f.created_at DESC;
```

#### Query RAG (if indexed)

```powershell
curl -X POST http://localhost:8080/rag/query `
  -H "Content-Type: application/json" `
  -d '{
    "question": "How does authentication work?",
    "repo": "your-org/your-repo",
    "top_k": 5
  }'
```

## Manual Repository Registration (Alternative)

If you want to manually register a repository without webhooks:

### Option 1: Using Python Script

Create a script `register_repo.py`:

```python
"""Manually register a repository."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from apps.shared.db.models import Repo
from apps.shared.config import settings

async def register_repo(repo_name: str, monorepo: bool = True):
    """Register a repository."""
    engine = create_async_engine(settings.database_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    async with async_session() as session:
        # Check if repo exists
        from sqlalchemy import select
        existing = await session.scalar(
            select(Repo).where(Repo.name == repo_name)
        )
        
        if existing:
            print(f"Repository {repo_name} already exists (ID: {existing.id})")
            return existing.id
        
        # Create new repo
        repo = Repo(
            name=repo_name,
            monorepo=monorepo,
            service_map={}
        )
        session.add(repo)
        await session.commit()
        print(f"Registered repository: {repo_name} (ID: {repo.id})")
        return repo.id

if __name__ == "__main__":
    import sys
    repo_name = sys.argv[1] if len(sys.argv) > 1 else "your-org/your-repo"
    repo_id = asyncio.run(register_repo(repo_name))
    print(f"Repository ID: {repo_id}")
```

Run it:
```powershell
python register_repo.py your-org/your-repo
```

### Option 2: Using SQL Directly

```sql
INSERT INTO repos (name, monorepo, service_map)
VALUES ('your-org/your-repo', true, '{}')
ON CONFLICT (name) DO NOTHING
RETURNING id;
```

## Troubleshooting

### Webhook Not Received

1. **Check webhook secret matches**: Must be identical in GitHub and config
2. **Check firewall/network**: Ensure port 8080 is accessible
3. **Check logs**: Look for errors in API gateway logs
4. **Test with curl**: See manual testing section above

### Commits Not Being Processed

1. **Check ingestion worker is running**: `python -m apps.ingestion.worker`
2. **Check message queue**: Verify Redis/Kafka is running
3. **Check database connection**: Verify `DATABASE_URL` is correct
4. **Check storage**: Verify MinIO/S3 is accessible

### Analysis Not Running

1. **Check analysis worker is running**: `python -m apps.analysis`
2. **Check webhook events**: Ensure `pull_request` events are enabled
3. **Check logs**: Look for errors in analysis worker logs
4. **Verify PR exists**: Check `pull_requests` table in database

### Common Issues

**Issue**: `signature mismatch` error
- **Solution**: Ensure `GITHUB_WEBHOOK_SECRET` matches GitHub webhook secret exactly

**Issue**: `invalid user-agent` error  
- **Solution**: Check `GITHUB_TRUSTED_UA_PREFIX` in config (default: `GitHub-Hookshot/`)

**Issue**: Webhook received but no processing
- **Solution**: Check that workers are running and message queue is connected

## Next Steps

After setup:
1. ✅ Make test commits and verify they're processed
2. ✅ Create test PRs and verify analysis runs
3. ✅ Check findings in database
4. ✅ Test RAG queries on your codebase
5. ✅ Configure service maps for monorepo (if needed)

## Configuration Files Reference

- **Webhook Configuration**: `configs/.env` → `GITHUB_WEBHOOK_SECRET`
- **Database**: `configs/.env` → `DATABASE_URL`
- **Message Queue**: `configs/.env` → `MQ_TYPE`, `REDIS_URL`
- **Storage**: `configs/.env` → `STORAGE_TYPE`, `S3_ENDPOINT_URL`

## API Endpoints

- **Webhook**: `POST /webhooks/github`
- **Health Check**: `GET /health`
- **RAG Query**: `POST /rag/query`
- **Service Map**: `POST /admin/service-map`, `GET /admin/service-map/{repo_name}`

For more details, see [README.md](README.md) and [GETTING_STARTED.md](GETTING_STARTED.md).

