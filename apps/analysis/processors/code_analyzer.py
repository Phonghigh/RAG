"""Code analyzer orchestrating parsers, rules, and scanners."""
import logging
from typing import List, Dict, Any, Optional
from apps.analysis.parsers import get_parser, ParsedFile
from apps.analysis.rules import RuleEngine
from apps.analysis.security import SecretScanner
from apps.analysis.dependencies import DependencyParser, DependencyRiskAnalyzer

logger = logging.getLogger(__name__)


class CodeAnalyzer:
    """Orchestrates code analysis components."""
    
    def __init__(self, rules_config_path: Optional[str] = None):
        """Initialize code analyzer."""
        self.rule_engine = RuleEngine(rules_config_path)
        self.secret_scanner = SecretScanner()
        self.dependency_parser = DependencyParser()
        self.dependency_analyzer = DependencyRiskAnalyzer()
    
    def analyze_file(
        self,
        content: str,
        path: str,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze a single code file.
        
        Args:
            content: File content
            path: File path
            language: Optional language hint
            
        Returns:
            Analysis results with findings
        """
        results = {
            'path': path,
            'language': language,
            'parsed': None,
            'rule_violations': [],
            'secrets': [],
            'errors': [],
        }
        
        # Parse file
        parser = get_parser(path, language)
        if parser:
            try:
                parsed = parser.parse_file(content, path)
                results['parsed'] = parsed
                results['language'] = parsed.language
                
                # Run rule validation
                rule_violations = self.rule_engine.evaluate_file(parsed)
                results['rule_violations'] = rule_violations
                
            except Exception as e:
                logger.exception(f"Error parsing file {path}: {e}")
                results['errors'].append(f"Parse error: {e}")
        else:
            results['errors'].append(f"No parser available for {path}")
        
        # Scan for secrets
        try:
            secrets = self.secret_scanner.scan_file(content, path)
            results['secrets'] = secrets
        except Exception as e:
            logger.exception(f"Error scanning secrets in {path}: {e}")
            results['errors'].append(f"Secret scan error: {e}")
        
        return results
    
    def analyze_dependency_file(
        self,
        content: str,
        path: str
    ) -> Dict[str, Any]:
        """
        Analyze a dependency file.
        
        Args:
            content: File content
            path: File path
            
        Returns:
            Analysis results with dependency risks
        """
        results = {
            'path': path,
            'dependencies': [],
            'risks': [],
            'errors': [],
        }
        
        try:
            # Parse dependencies
            dependencies = self.dependency_parser.parse_file(content, path)
            results['dependencies'] = [
                {
                    'name': dep.name,
                    'version': dep.version,
                    'package_manager': dep.package_manager,
                }
                for dep in dependencies
            ]
            
            # Analyze risks
            risks = self.dependency_analyzer.analyze(dependencies)
            results['risks'] = [
                {
                    'dependency': risk.dependency.name,
                    'version': risk.dependency.version,
                    'risk_level': risk.risk_level,
                    'cve_ids': risk.cve_ids,
                    'description': risk.description,
                    'recommendation': risk.recommendation,
                }
                for risk in risks
            ]
        
        except Exception as e:
            logger.exception(f"Error analyzing dependency file {path}: {e}")
            results['errors'].append(f"Dependency analysis error: {e}")
        
        return results
