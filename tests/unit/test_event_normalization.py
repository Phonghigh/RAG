"""Tests for event normalization."""
import pytest
from datetime import datetime
from apps.shared.utils.github_events import GitHubEventNormalizer
from tests.fixtures.github_events import (
    PUSH_EVENT,
    PULL_REQUEST_OPENED_EVENT,
    CHECK_RUN_COMPLETED_EVENT,
)


class TestGitHubEventNormalizer:
    """Test GitHub event normalization."""
    
    def test_normalize_push_event(self):
        """Test push event normalization."""
        normalized = GitHubEventNormalizer.normalize_push_event(PUSH_EVENT)
        
        assert normalized["event_type"] == "push"
        assert normalized["repo"]["name"] == "org/repo"
        assert len(normalized["commits"]) == 1
        assert normalized["commits"][0]["sha"] == "def456"
        assert normalized["commits"][0]["author"] == "Test User"
        assert isinstance(normalized["commits"][0]["authored_at"], datetime)
    
    def test_normalize_pull_request_event(self):
        """Test pull_request event normalization."""
        normalized = GitHubEventNormalizer.normalize_pull_request_event(
            PULL_REQUEST_OPENED_EVENT
        )
        
        assert normalized["event_type"] == "pull_request"
        assert normalized["action"] == "opened"
        assert normalized["repo"]["name"] == "org/repo"
        assert normalized["pull_request"]["number"] == 42
        assert normalized["pull_request"]["title"] == "Test PR"
        assert normalized["pull_request"]["state"] == "open"
        assert normalized["pull_request"]["additions"] == 100
        assert normalized["pull_request"]["deletions"] == 50
        assert isinstance(normalized["pull_request"]["created_at"], datetime)
    
    def test_normalize_check_run_event(self):
        """Test check_run event normalization."""
        normalized = GitHubEventNormalizer.normalize_check_run_event(
            CHECK_RUN_COMPLETED_EVENT
        )
        
        assert normalized["event_type"] == "check_run"
        assert normalized["action"] == "completed"
        assert normalized["repo"]["name"] == "org/repo"
        assert normalized["check_run"]["name"] == "CI Tests"
        assert normalized["check_run"]["status"] == "completed"
        assert normalized["check_run"]["conclusion"] == "success"
    
    def test_normalize_event_dispatcher(self):
        """Test event normalization dispatcher."""
        push_norm = GitHubEventNormalizer.normalize_event("push", PUSH_EVENT)
        assert push_norm is not None
        assert push_norm["event_type"] == "push"
        
        pr_norm = GitHubEventNormalizer.normalize_event(
            "pull_request", PULL_REQUEST_OPENED_EVENT
        )
        assert pr_norm is not None
        assert pr_norm["event_type"] == "pull_request"
        
        unknown_norm = GitHubEventNormalizer.normalize_event("unknown", {})
        assert unknown_norm is None

