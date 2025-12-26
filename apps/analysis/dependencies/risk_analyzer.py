"""Analyze dependencies for security risks."""
import logging
import json
import csv
from pathlib import Path
from typing import List, Dict, Optional
from apps.analysis.dependencies.models import Dependency, DependencyRisk
from apps.shared.config import settings

logger = logging.getLogger(__name__)


class DependencyRiskAnalyzer:
    """Analyzer for dependency security risks."""
    
    def __init__(self, cve_db_path: Optional[str] = None):
        """
        Initialize risk analyzer.
        
        Args:
            cve_db_path: Path to CVE database file (JSON or CSV)
        """
        if cve_db_path is None:
            cve_db_path = getattr(settings, 'cve_db_path', None)
        
        self.cve_db_path = cve_db_path
        self.cve_db: Dict[str, List[Dict]] = {}
        self._load_cve_db()
    
    def _load_cve_db(self):
        """Load CVE database from file."""
        if not self.cve_db_path:
            logger.warning("No CVE database path configured, skipping CVE checks")
            return
        
        path = Path(self.cve_db_path)
        if not path.exists():
            logger.warning(f"CVE database file not found: {self.cve_db_path}")
            return
        
        try:
            if path.suffix.lower() == '.json':
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Expected format: {"package_name": [{"cve_id": "...", "severity": "...", ...}]}
                    self.cve_db = data
            elif path.suffix.lower() == '.csv':
                with open(path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        package = row.get('package', '')
                        if package not in self.cve_db:
                            self.cve_db[package] = []
                        self.cve_db[package].append({
                            'cve_id': row.get('cve_id', ''),
                            'severity': row.get('severity', 'unknown'),
                            'description': row.get('description', ''),
                        })
            
            logger.info(f"Loaded CVE database with {len(self.cve_db)} packages")
        
        except Exception as e:
            logger.exception(f"Error loading CVE database: {e}")
    
    def analyze(self, dependencies: List[Dependency]) -> List[DependencyRisk]:
        """
        Analyze dependencies for risks.
        
        Args:
            dependencies: List of dependencies to analyze
            
        Returns:
            List of risk findings
        """
        risks = []
        
        for dep in dependencies:
            risk = self._check_dependency(dep)
            if risk:
                risks.append(risk)
        
        return risks
    
    def _check_dependency(self, dependency: Dependency) -> Optional[DependencyRisk]:
        """Check a single dependency for risks."""
        # Normalize package name for lookup
        package_key = self._normalize_package_name(dependency.name, dependency.package_manager)
        
        # Check CVE database
        cve_entries = self.cve_db.get(package_key, [])
        
        if not cve_entries:
            # Also try without version/group
            if ':' in package_key:
                # Maven format: group:artifact
                parts = package_key.split(':')
                if len(parts) >= 2:
                    artifact_only = parts[-1]
                    cve_entries = self.cve_db.get(artifact_only, [])
        
        if cve_entries:
            # Determine highest risk level
            severities = [entry.get('severity', 'unknown').lower() for entry in cve_entries]
            risk_level = self._get_highest_severity(severities)
            
            cve_ids = [entry.get('cve_id', '') for entry in cve_entries if entry.get('cve_id')]
            description = f"Found {len(cve_entries)} CVE(s) for {dependency.name}"
            
            recommendation = f"Update {dependency.name} to a version without known CVEs"
            
            return DependencyRisk(
                dependency=dependency,
                risk_level=risk_level,
                cve_ids=cve_ids,
                description=description,
                recommendation=recommendation,
            )
        
        return None
    
    def _normalize_package_name(self, name: str, package_manager: str) -> str:
        """Normalize package name for CVE lookup."""
        if package_manager == 'maven':
            # Keep as group:artifact
            return name.lower()
        elif package_manager == 'pip':
            # Use lowercase
            return name.lower()
        elif package_manager == 'composer':
            # Composer uses vendor/package format
            return name.lower()
        else:
            return name.lower()
    
    def _get_highest_severity(self, severities: List[str]) -> str:
        """Get highest severity level from list."""
        severity_order = ['critical', 'high', 'medium', 'low', 'unknown']
        
        for severity in severity_order:
            if severity in severities:
                return severity
        
        return 'unknown'
    
    def reload_cve_db(self, cve_db_path: Optional[str] = None):
        """Reload CVE database."""
        if cve_db_path:
            self.cve_db_path = cve_db_path
        self._load_cve_db()
