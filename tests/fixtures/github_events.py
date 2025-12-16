"""Sample GitHub webhook event payloads for testing."""
from typing import Any

PUSH_EVENT: dict[str, Any] = {
    "ref": "refs/heads/main",
    "before": "abc123",
    "after": "def456",
    "repository": {
        "id": 123456,
        "full_name": "org/repo",
        "name": "repo",
        "default_branch": "main",
    },
    "pusher": {"name": "testuser"},
    "commits": [
        {
            "id": "def456",
            "message": "Test commit",
            "timestamp": "2025-01-15T10:00:00Z",
            "author": {"name": "Test User", "email": "test@example.com"},
            "added": ["file1.py"],
            "removed": [],
            "modified": ["file2.py"],
        }
    ],
}

PULL_REQUEST_OPENED_EVENT: dict[str, Any] = {
    "action": "opened",
    "number": 42,
    "pull_request": {
        "number": 42,
        "title": "Test PR",
        "body": "Test PR description",
        "state": "open",
        "user": {"login": "testuser"},
        "created_at": "2025-01-15T10:00:00Z",
        "updated_at": "2025-01-15T10:00:00Z",
        "merged_at": None,
        "merged": False,
        "base": {"ref": "main", "sha": "abc123"},
        "head": {"ref": "feature", "sha": "def456"},
        "draft": False,
        "additions": 100,
        "deletions": 50,
        "changed_files": 5,
    },
    "repository": {
        "id": 123456,
        "full_name": "org/repo",
        "name": "repo",
        "default_branch": "main",
    },
}

PULL_REQUEST_CLOSED_EVENT: dict[str, Any] = {
    "action": "closed",
    "number": 42,
    "pull_request": {
        "number": 42,
        "title": "Test PR",
        "state": "closed",
        "merged": True,
        "merged_at": "2025-01-15T11:00:00Z",
        "user": {"login": "testuser"},
        "base": {"ref": "main", "sha": "abc123"},
        "head": {"ref": "feature", "sha": "def456"},
    },
    "repository": {
        "id": 123456,
        "full_name": "org/repo",
        "name": "repo",
    },
}

CHECK_RUN_COMPLETED_EVENT: dict[str, Any] = {
    "action": "completed",
    "check_run": {
        "id": 789,
        "name": "CI Tests",
        "status": "completed",
        "conclusion": "success",
        "head_sha": "def456",
        "output": {
            "title": "All tests passed",
            "summary": "10 tests passed",
        },
        "html_url": "https://github.com/org/repo/checks/789",
    },
    "repository": {
        "id": 123456,
        "full_name": "org/repo",
        "name": "repo",
    },
}

PING_EVENT: dict[str, Any] = {
    "zen": "Keep it logically awesome.",
    "repository": {
        "id": 123456,
        "full_name": "org/repo",
        "name": "repo",
    },
}

