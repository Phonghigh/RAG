"""Tests for webhook handler."""
import pytest
import hmac
import hashlib
from fastapi.testclient import TestClient
from apps.gateway.main import app
from apps.shared.config import settings

client = TestClient(app)


def generate_signature(secret: str, body: bytes) -> str:
    """Generate GitHub webhook signature."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


class TestGitHubWebhook:
    """Test GitHub webhook handler."""
    
    def test_ping_event(self):
        """Test ping event handling."""
        body = b'{"zen": "Keep it logically awesome."}'
        signature = generate_signature(settings.github_webhook_secret, body)
        
        response = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-Hub-Signature-256": signature,
                "X-GitHub-Event": "ping",
                "X-GitHub-Delivery": "test-delivery-id",
                "User-Agent": "GitHub-Hookshot/test",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["pong"] is True
    
    def test_invalid_signature(self):
        """Test invalid signature rejection."""
        body = b'{"test": "data"}'
        
        response = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-Hub-Signature-256": "sha256=invalid",
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": "test-delivery-id",
                "User-Agent": "GitHub-Hookshot/test",
            },
        )
        
        assert response.status_code == 401
    
    def test_missing_signature(self):
        """Test missing signature rejection."""
        body = b'{"test": "data"}'
        
        response = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": "test-delivery-id",
            },
        )
        
        assert response.status_code == 400
    
    def test_push_event(self):
        """Test push event handling."""
        body = b'{"repository": {"full_name": "org/repo"}, "commits": []}'
        signature = generate_signature(settings.github_webhook_secret, body)
        
        response = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-Hub-Signature-256": signature,
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": "test-delivery-id",
                "User-Agent": "GitHub-Hookshot/test",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["event"] == "push"

