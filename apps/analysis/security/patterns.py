"""Regex patterns for common secrets."""
import re
from typing import List, Tuple, Pattern

# Common secret patterns
SECRET_PATTERNS: List[Tuple[str, str, str]] = [
    # API Keys
    ("stripe_key", r'sk_(live|test)_[a-zA-Z0-9]{24,}', "Stripe API key detected"),
    ("api_key", r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?', "API key detected"),
    ("aws_key", r'AKIA[0-9A-Z]{16}', "AWS access key detected"),
    ("aws_secret", r'(?i)(aws[_-]?secret[_-]?access[_-]?key)\s*[=:]\s*["\']?([a-zA-Z0-9/+=]{40})["\']?', "AWS secret key detected"),
    
    # Tokens
    ("github_token", r'ghp_[a-zA-Z0-9]{36}', "GitHub personal access token detected"),
    ("github_oauth", r'gho_[a-zA-Z0-9]{36}', "GitHub OAuth token detected"),
    ("slack_token", r'xox[baprs]-[0-9a-zA-Z\-]{10,}', "Slack token detected"),
    ("jwt", r'eyJ[A-Za-z0-9-_=]+\.eyJ[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*', "JWT token detected"),
    
    # Passwords
    ("password", r'(?i)(password|passwd|pwd)\s*[=:]\s*["\']([^"\']+)["\']', "Password in plaintext detected"),
    
    # Database credentials
    ("db_password", r'(?i)(database[_-]?password|db[_-]?pass|db[_-]?pwd)\s*[=:]\s*["\']?([^"\'\s]{8,})["\']?', "Database password detected"),
    ("db_connection", r'(?i)(postgres|mysql|mongodb)://[^:]+:([^@]+)@', "Database connection string with credentials detected"),
    
    # Private keys
    ("private_key", r'-----BEGIN\s+(RSA|DSA|EC|OPENSSH)\s+PRIVATE KEY-----', "Private key detected"),
    
    # OAuth secrets
    ("oauth_secret", r'(?i)(oauth[_-]?secret|client[_-]?secret)\s*[=:]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?', "OAuth secret detected"),
    
    # Generic secrets (high entropy)
    ("generic_secret", r'(?i)(secret|token|key)\s*[=:]\s*["\']?([a-zA-Z0-9_\-/+=]{20,})["\']?', "Potential secret detected"),
]


def get_patterns() -> List[Tuple[str, Pattern, str]]:
    """Get compiled regex patterns."""
    compiled = []
    for name, pattern, description in SECRET_PATTERNS:
        try:
            compiled.append((name, re.compile(pattern), description))
        except re.error as e:
            print(f"Warning: Invalid pattern {name}: {e}")
    return compiled


def match_secrets(content: str) -> List[Tuple[str, str, int, str]]:
    """
    Match secrets in content using patterns.
    
    Returns:
        List of (pattern_name, matched_text, line_number, description)
    """
    matches = []
    patterns = get_patterns()
    lines = content.split('\n')
    
    for line_num, line in enumerate(lines, 1):
        for pattern_name, pattern, description in patterns:
            for match in pattern.finditer(line):
                matched_text = match.group(0)
                # Extract the actual secret value (usually group 2)
                if match.lastindex and match.lastindex >= 2:
                    secret_value = match.group(2)
                else:
                    secret_value = matched_text
                
                matches.append((pattern_name, secret_value, line_num, description))
    
    return matches
