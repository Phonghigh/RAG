"""Entropy analysis for detecting random strings."""
import math
from typing import Optional


def calculate_shannon_entropy(text: str) -> float:
    """
    Calculate Shannon entropy of a string.
    
    Higher entropy indicates more randomness (potential secret).
    
    Args:
        text: Input string
        
    Returns:
        Entropy value in bits per character
    """
    if not text:
        return 0.0
    
    # Count character frequencies
    char_counts = {}
    for char in text:
        char_counts[char] = char_counts.get(char, 0) + 1
    
    # Calculate entropy
    length = len(text)
    entropy = 0.0
    
    for count in char_counts.values():
        probability = count / length
        if probability > 0:
            entropy -= probability * math.log2(probability)
    
    return entropy


def is_high_entropy(text: str, threshold: float = 3.5) -> bool:
    """
    Check if text has high entropy (likely random/secret).
    
    Args:
        text: Input string
        threshold: Entropy threshold in bits per character (default: 3.5)
        
    Returns:
        True if entropy exceeds threshold
    """
    # Filter out very short strings
    if len(text) < 8:
        return False
    
    entropy = calculate_shannon_entropy(text)
    return entropy >= threshold


def extract_high_entropy_strings(content: str, min_length: int = 16, threshold: float = 3.5) -> list[tuple[str, int, float]]:
    """
    Extract high-entropy strings from content.
    
    Args:
        content: File content
        min_length: Minimum string length to consider
        threshold: Entropy threshold
        
    Returns:
        List of (string, line_number, entropy) tuples
    """
    results = []
    lines = content.split('\n')
    
    # Pattern to match potential secret strings (alphanumeric + special chars)
    import re
    # Match strings that look like secrets: long alphanumeric sequences
    pattern = re.compile(r'[a-zA-Z0-9_\-/+=]{' + str(min_length) + r',}')
    
    for line_num, line in enumerate(lines, 1):
        for match in pattern.finditer(line):
            candidate = match.group(0)
            entropy = calculate_shannon_entropy(candidate)
            
            if entropy >= threshold:
                results.append((candidate, line_num, entropy))
    
    return results
