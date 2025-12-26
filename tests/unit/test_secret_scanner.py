"""Tests for secret scanner."""
import pytest
from apps.analysis.security import SecretScanner


class TestSecretScanner:
    """Test secret scanner."""
    
    def test_detect_api_key(self):
        """Test detecting API key."""
        code = 'api_key = "sk_live_1234567890abcdef"'
        scanner = SecretScanner()
        findings = scanner.scan_file(code, "app.py")
        
        assert len(findings) > 0
        assert any('api' in f['pattern'].lower() for f in findings)
    
    def test_detect_password(self):
        """Test detecting password."""
        code = 'password = "mypassword123"'
        scanner = SecretScanner()
        findings = scanner.scan_file(code, "config.py")
        
        assert len(findings) > 0
    
    def test_false_positive_filtering(self):
        """Test false positive filtering."""
        code = 'test_password = "test123"'
        scanner = SecretScanner()
        findings = scanner.scan_file(code, "tests/test_file.py")
        
        # Should be filtered as false positive
        assert len(findings) == 0
    
    def test_redact_secret(self):
        """Test secret redaction."""
        from apps.analysis.security.allowlist import redact_secret
        
        secret = "sk_live_1234567890abcdefghijklmnop"
        redacted = redact_secret(secret)
        
        assert "..." in redacted
        assert len(redacted) < len(secret)
