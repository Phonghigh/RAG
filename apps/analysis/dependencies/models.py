"""Dependency data models."""
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class Dependency:
    """Represents a dependency."""
    name: str
    version: str
    package_manager: str  # 'maven', 'pip', 'composer'
    license: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None


@dataclass
class DependencyRisk:
    """Represents a dependency risk finding."""
    dependency: Dependency
    risk_level: str  # 'low', 'medium', 'high', 'critical'
    cve_ids: List[str]
    description: str
    recommendation: Optional[str] = None
