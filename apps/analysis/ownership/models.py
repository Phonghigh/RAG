"""Ownership inference models."""
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class OwnershipScore:
    """Ownership score for a candidate."""
    candidate: str  # Username or email
    score: float  # 0.0 to 1.0
    signals: dict  # Breakdown of individual signal scores
    confidence: float  # Overall confidence (0.0 to 1.0)


@dataclass
class OwnershipCandidate:
    """Top ownership candidate."""
    candidate: str
    score: float
    confidence: float
    reasoning: str  # Human-readable explanation
