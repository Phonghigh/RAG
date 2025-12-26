"""Allowlist for filtering false positives."""
import re
from typing import List, Set
from pathlib import Path


# Common false positive patterns
FALSE_POSITIVE_PATTERNS: List[str] = [
    # Test files
    r'.*test.*',
    r'.*spec.*',
    r'.*mock.*',
    r'.*fixture.*',
    r'.*example.*',
    
    # Common test values
    r'test.*password',
    r'example.*key',
    r'sample.*token',
    r'dummy.*secret',
    r'fake.*api',
    
    # Configuration templates
    r'.*\.template\..*',
    r'.*\.example\..*',
    r'.*\.sample\..*',
    
    # Documentation
    r'.*\.md$',
    r'.*\.txt$',
    r'.*\.rst$',
]


# Common false positive strings (exact matches)
FALSE_POSITIVE_STRINGS: Set[str] = {
    'test123',
    'password123',
    'changeme',
    'example',
    'dummy',
    'placeholder',
    'your_key_here',
    'your_secret_here',
    'api_key_here',
    'test_api_key',
    'example_password',
    'sample_token',
}


def is_false_positive(path: str, matched_text: str, pattern_name: str) -> bool:
    """
    Check if a detected secret is a false positive.
    
    Args:
        path: File path
        matched_text: Matched secret text
        pattern_name: Name of the pattern that matched
        
    Returns:
        True if this is likely a false positive
    """
    # Check file path patterns
    path_lower = path.lower()
    for pattern in FALSE_POSITIVE_PATTERNS:
        if re.match(pattern, path_lower, re.IGNORECASE):
            return True
    
    # Check exact string matches
    matched_lower = matched_text.lower()
    if matched_lower in FALSE_POSITIVE_STRINGS:
        return True
    
    # Check common test patterns in matched text
    test_indicators = ['test', 'example', 'sample', 'dummy', 'fake', 'mock', 'placeholder']
    if any(indicator in matched_lower for indicator in test_indicators):
        return True
    
    # Check if path contains test directories
    path_parts = Path(path).parts
    test_dirs = {'test', 'tests', 'spec', 'specs', 'fixtures', 'examples', 'samples'}
    if any(part.lower() in test_dirs for part in path_parts):
        return True
    
    return False


def redact_secret(text: str, keep_chars: int = 4) -> str:
    """
    Redact a secret, keeping only first and last few characters.
    
    Args:
        text: Secret text to redact
        keep_chars: Number of characters to keep at start/end
        
    Returns:
        Redacted string (e.g., "abcd...xyz")
    """
    if len(text) <= keep_chars * 2:
        return '*' * len(text)
    
    return f"{text[:keep_chars]}...{text[-keep_chars:]}"
