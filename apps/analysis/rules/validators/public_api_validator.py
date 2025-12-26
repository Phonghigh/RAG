"""Public API validator."""
import logging
from typing import List, Dict, Any
from apps.analysis.parsers.base import ParsedFile

logger = logging.getLogger(__name__)


class PublicAPIValidator:
    """Validates public API contracts."""
    
    def validate(
        self,
        rule: Dict[str, Any],
        parsed_file: ParsedFile
    ) -> List[Dict[str, Any]]:
        """
        Validate public API rules.
        
        Args:
            rule: Rule definition
            parsed_file: Parsed file to validate
            
        Returns:
            List of violations
        """
        violations = []
        packages = rule.get('packages', [])
        
        # Check if file is in one of the specified packages
        file_path = parsed_file.path
        matches_package = any(self._path_matches_pattern(file_path, pattern) for pattern in packages)
        
        if not matches_package:
            return violations
        
        # Check that public classes/functions follow naming conventions
        for cls in parsed_file.classes:
            if not cls.is_public and not cls.name.startswith('_'):
                violations.append({
                    'rule_id': rule.get('id'),
                    'severity': rule.get('severity', 'warning'),
                    'message': f"Class {cls.name} should be public or explicitly private",
                    'file_path': file_path,
                    'line': cls.start_line,
                    'details': {
                        'class': cls.name,
                    },
                })
        
        for func in parsed_file.functions:
            if not func.is_public and not func.name.startswith('_'):
                violations.append({
                    'rule_id': rule.get('id'),
                    'severity': rule.get('severity', 'warning'),
                    'message': f"Function {func.name} should be public or explicitly private",
                    'file_path': file_path,
                    'line': func.start_line,
                    'details': {
                        'function': func.name,
                    },
                })
        
        return violations
    
    def _path_matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if file path matches pattern."""
        import fnmatch
        normalized_path = path.replace('\\', '/')
        return fnmatch.fnmatch(normalized_path, pattern)
