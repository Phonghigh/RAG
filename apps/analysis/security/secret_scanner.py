"""Secret scanner for detecting secrets in code."""
import logging
from typing import List, Dict, Any, Optional
from apps.analysis.security.patterns import match_secrets
from apps.analysis.security.entropy import extract_high_entropy_strings, is_high_entropy
from apps.analysis.security.allowlist import is_false_positive, redact_secret

logger = logging.getLogger(__name__)


class SecretScanner:
    """Scanner for detecting secrets in code."""
    
    def __init__(self, entropy_threshold: float = 3.5, min_secret_length: int = 16):
        """
        Initialize secret scanner.
        
        Args:
            entropy_threshold: Entropy threshold for detecting random strings
            min_secret_length: Minimum length for entropy-based detection
        """
        self.entropy_threshold = entropy_threshold
        self.min_secret_length = min_secret_length
    
    def scan_file(self, content: str, path: str) -> List[Dict[str, Any]]:
        """
        Scan a file for secrets.
        
        Args:
            content: File content
            path: File path
            
        Returns:
            List of detected secrets (violations)
        """
        findings = []
        
        # Pattern-based detection
        pattern_matches = match_secrets(content)
        for pattern_name, matched_text, line_num, description in pattern_matches:
            if not is_false_positive(path, matched_text, pattern_name):
                findings.append({
                    'type': 'secret',
                    'pattern': pattern_name,
                    'severity': self._get_severity(pattern_name),
                    'message': description,
                    'file_path': path,
                    'line': line_num,
                    'details': {
                        'matched_text': redact_secret(matched_text),
                        'pattern_name': pattern_name,
                    },
                })
        
        # Entropy-based detection
        high_entropy_strings = extract_high_entropy_strings(
            content,
            min_length=self.min_secret_length,
            threshold=self.entropy_threshold
        )
        
        for secret_text, line_num, entropy in high_entropy_strings:
            # Skip if already detected by patterns
            if any(f['line'] == line_num and secret_text in f['details'].get('matched_text', '') 
                   for f in findings):
                continue
            
            if not is_false_positive(path, secret_text, 'high_entropy'):
                findings.append({
                    'type': 'secret',
                    'pattern': 'high_entropy',
                    'severity': 'medium',
                    'message': f"High entropy string detected (entropy: {entropy:.2f})",
                    'file_path': path,
                    'line': line_num,
                    'details': {
                        'matched_text': redact_secret(secret_text),
                        'entropy': round(entropy, 2),
                    },
                })
        
        return findings
    
    def _get_severity(self, pattern_name: str) -> str:
        """Get severity level for a pattern."""
        high_severity_patterns = [
            'private_key',
            'aws_secret',
            'db_password',
            'oauth_secret',
        ]
        
        if pattern_name in high_severity_patterns:
            return 'high'
        elif pattern_name in ['password', 'api_key', 'github_token']:
            return 'medium'
        else:
            return 'low'
    
    def redact_content(self, content: str, findings: List[Dict[str, Any]]) -> str:
        """
        Redact secrets from content before storing in RAG.
        
        Args:
            content: Original content
            findings: List of secret findings
            
        Returns:
            Content with secrets redacted
        """
        redacted = content
        lines = redacted.split('\n')
        
        for finding in findings:
            line_idx = finding['line'] - 1
            if 0 <= line_idx < len(lines):
                matched_text = finding['details'].get('matched_text', '')
                if matched_text:
                    # Try to find and replace the secret
                    original_line = lines[line_idx]
                    redacted_line = original_line.replace(
                        matched_text,
                        redact_secret(matched_text)
                    )
                    lines[line_idx] = redacted_line
        
        return '\n'.join(lines)
