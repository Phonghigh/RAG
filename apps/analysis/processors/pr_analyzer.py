"""PR-level analysis coordinator."""
import logging
from typing import List, Dict, Any, Optional
from apps.analysis.processors.code_analyzer import CodeAnalyzer
from apps.analysis.ownership import OwnershipInferrer

logger = logging.getLogger(__name__)


class PRAnalyzer:
    """Coordinates PR-level analysis."""
    
    def __init__(self, rules_config_path: Optional[str] = None):
        """Initialize PR analyzer."""
        self.code_analyzer = CodeAnalyzer(rules_config_path)
        self.ownership_inferrer = OwnershipInferrer()
    
    def analyze_pr(
        self,
        pr_data: Dict[str, Any],
        diffs: List[Dict[str, Any]],
        service_map: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Analyze a pull request.
        
        Args:
            pr_data: PR metadata
            diffs: List of file diffs with 'path', 'content', 'language' keys
            service_map: Optional service map configuration
            
        Returns:
            Analysis results with findings and ownership
        """
        results = {
            'pr_id': pr_data.get('number'),
            'repo': pr_data.get('repo'),
            'files_analyzed': 0,
            'findings': [],
            'ownership': {},
            'errors': [],
        }
        
        all_parsed_files = []
        dependency_files = []
        
        # Analyze each file
        for diff in diffs:
            file_path = diff.get('path', '')
            content = diff.get('content', '')
            language = diff.get('language')
            
            if not content:
                continue
            
            # Check if it's a dependency file
            is_dependency_file = self._is_dependency_file(file_path)
            
            if is_dependency_file:
                dep_result = self.code_analyzer.analyze_dependency_file(content, file_path)
                dependency_files.append(dep_result)
                
                # Convert dependency risks to findings
                for risk in dep_result.get('risks', []):
                    results['findings'].append({
                        'type': 'dependency_risk',
                        'file_path': file_path,
                        'severity': risk['risk_level'],
                        'message': risk['description'],
                        'details': {
                            'dependency': risk['dependency'],
                            'version': risk['version'],
                            'cve_ids': risk['cve_ids'],
                            'recommendation': risk['recommendation'],
                        },
                    })
            else:
                # Regular code file analysis
                file_result = self.code_analyzer.analyze_file(content, file_path, language)
                results['files_analyzed'] += 1
                
                if file_result.get('parsed'):
                    all_parsed_files.append(file_result['parsed'])
                
                # Convert rule violations to findings
                for violation in file_result.get('rule_violations', []):
                    results['findings'].append({
                        'type': 'rule_violation',
                        'file_path': file_path,
                        'rule_id': violation.get('rule_id'),
                        'severity': violation.get('severity', 'error'),
                        'message': violation.get('message'),
                        'details': violation.get('details', {}),
                    })
                
                # Convert secrets to findings
                for secret in file_result.get('secrets', []):
                    results['findings'].append({
                        'type': 'secret',
                        'file_path': file_path,
                        'severity': secret.get('severity', 'high'),
                        'message': secret.get('message'),
                        'details': secret.get('details', {}),
                    })
        
        # Infer ownership for changed files
        if all_parsed_files:
            ownership_results = {}
            for parsed_file in all_parsed_files:
                file_path = parsed_file.path
                candidates = self.ownership_inferrer.infer(
                    file_path=file_path,
                    service_map=service_map,
                    # Note: git_blame, commit_history, pr_history would come from external data
                )
                
                if candidates:
                    ownership_results[file_path] = [
                        {
                            'candidate': c.candidate,
                            'score': c.score,
                            'confidence': c.confidence,
                            'reasoning': c.reasoning,
                        }
                        for c in candidates[:3]  # Top 3 candidates
                    ]
            
            results['ownership'] = ownership_results
        
        return results
    
    def _is_dependency_file(self, path: str) -> bool:
        """Check if file is a dependency file."""
        dependency_files = [
            'pom.xml',
            'requirements.txt',
            'composer.json',
            'package.json',
            'go.mod',
            'Cargo.toml',
        ]
        
        import os
        filename = os.path.basename(path)
        return filename.lower() in [f.lower() for f in dependency_files]
