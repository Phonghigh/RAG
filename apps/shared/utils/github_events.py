"""GitHub event normalization utilities."""
from typing import Any, Optional
from datetime import datetime
from dateutil import parser as date_parser


class GitHubEventNormalizer:
    """Normalize GitHub webhook events to internal format."""
    
    @staticmethod
    def normalize_push_event(payload: dict[str, Any]) -> dict[str, Any]:
        """Normalize push event."""
        repo = payload.get("repository", {})
        commits = payload.get("commits", [])
        
        return {
            "event_type": "push",
            "repo": {
                "name": repo.get("full_name"),
                "id": repo.get("id"),
                "default_branch": repo.get("default_branch"),
            },
            "commits": [
                {
                    "sha": commit.get("id"),
                    "message": commit.get("message"),
                    "author": commit.get("author", {}).get("name"),
                    "email": commit.get("author", {}).get("email"),
                    "authored_at": GitHubEventNormalizer._parse_datetime(
                        commit.get("timestamp")
                    ),
                    "added": commit.get("added", []),
                    "removed": commit.get("removed", []),
                    "modified": commit.get("modified", []),
                }
                for commit in commits
            ],
            "ref": payload.get("ref"),
            "before": payload.get("before"),
            "after": payload.get("after"),
            "pusher": payload.get("pusher", {}).get("name"),
        }
    
    @staticmethod
    def normalize_pull_request_event(payload: dict[str, Any]) -> dict[str, Any]:
        """Normalize pull_request event."""
        repo = payload.get("repository", {})
        pr = payload.get("pull_request", {})
        action = payload.get("action")
        
        return {
            "event_type": "pull_request",
            "action": action,  # opened, closed, synchronize, etc.
            "repo": {
                "name": repo.get("full_name"),
                "id": repo.get("id"),
                "default_branch": repo.get("default_branch"),
            },
            "pull_request": {
                "number": pr.get("number"),
                "title": pr.get("title"),
                "body": pr.get("body"),
                "state": pr.get("state"),  # open, closed
                "author": pr.get("user", {}).get("login"),
                "created_at": GitHubEventNormalizer._parse_datetime(pr.get("created_at")),
                "updated_at": GitHubEventNormalizer._parse_datetime(pr.get("updated_at")),
                "merged_at": GitHubEventNormalizer._parse_datetime(pr.get("merged_at")),
                "merged": pr.get("merged", False),
                "base_branch": pr.get("base", {}).get("ref"),
                "head_branch": pr.get("head", {}).get("ref"),
                "head_sha": pr.get("head", {}).get("sha"),
                "base_sha": pr.get("base", {}).get("sha"),
                "draft": pr.get("draft", False),
                "additions": pr.get("additions", 0),
                "deletions": pr.get("deletions", 0),
                "changed_files": pr.get("changed_files", 0),
            },
        }
    
    @staticmethod
    def normalize_pull_request_review_event(
        payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Normalize pull_request_review event."""
        repo = payload.get("repository", {})
        pr = payload.get("pull_request", {})
        review = payload.get("review", {})
        action = payload.get("action")
        
        return {
            "event_type": "pull_request_review",
            "action": action,  # submitted, edited, dismissed
            "repo": {
                "name": repo.get("full_name"),
                "id": repo.get("id"),
            },
            "pull_request": {
                "number": pr.get("number"),
                "state": pr.get("state"),
            },
            "review": {
                "id": review.get("id"),
                "state": review.get("state"),  # approved, changes_requested, commented
                "author": review.get("user", {}).get("login"),
                "body": review.get("body"),
                "submitted_at": GitHubEventNormalizer._parse_datetime(
                    review.get("submitted_at")
                ),
            },
        }
    
    @staticmethod
    def normalize_check_run_event(payload: dict[str, Any]) -> dict[str, Any]:
        """Normalize check_run event."""
        repo = payload.get("repository", {})
        check_run = payload.get("check_run", {})
        action = payload.get("action")
        
        return {
            "event_type": "check_run",
            "action": action,  # created, completed, rerequested
            "repo": {
                "name": repo.get("full_name"),
                "id": repo.get("id"),
            },
            "check_run": {
                "id": check_run.get("id"),
                "name": check_run.get("name"),
                "status": check_run.get("status"),  # queued, in_progress, completed
                "conclusion": check_run.get("conclusion"),  # success, failure, etc.
                "head_sha": check_run.get("head_sha"),
                "output": {
                    "title": check_run.get("output", {}).get("title"),
                    "summary": check_run.get("output", {}).get("summary"),
                },
                "artifacts_url": check_run.get("artifacts_url"),
                "html_url": check_run.get("html_url"),
            },
        }
    
    @staticmethod
    def normalize_event(
        event_type: str, payload: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Normalize any GitHub event based on type."""
        normalizers = {
            "push": GitHubEventNormalizer.normalize_push_event,
            "pull_request": GitHubEventNormalizer.normalize_pull_request_event,
            "pull_request_review": GitHubEventNormalizer.normalize_pull_request_review_event,
            "check_run": GitHubEventNormalizer.normalize_check_run_event,
        }
        
        normalizer = normalizers.get(event_type)
        if not normalizer:
            return None
        
        return normalizer(payload)
    
    @staticmethod
    def _parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string to datetime object."""
        if not dt_str:
            return None
        try:
            return date_parser.parse(dt_str)
        except (ValueError, TypeError):
            return None

