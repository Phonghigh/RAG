"""Dependency analysis module."""
from apps.analysis.dependencies.parser import DependencyParser
from apps.analysis.dependencies.risk_analyzer import DependencyRiskAnalyzer
from apps.analysis.dependencies.models import Dependency, DependencyRisk

__all__ = [
    "DependencyParser",
    "DependencyRiskAnalyzer",
    "Dependency",
    "DependencyRisk",
]
