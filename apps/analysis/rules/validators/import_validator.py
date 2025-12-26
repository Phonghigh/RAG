"""Import rule validator."""
import logging
from typing import List, Dict, Any, Set
from apps.analysis.parsers.base import ParsedFile, Import

logger = logging.getLogger(__name__)


class ImportValidator:
    """Validates import rules (forbid/allow imports)."""
    
    def validate(
        self,
        rule: Dict[str, Any],
        parsed_file: ParsedFile,
        all_imports: Dict[str, List[Import]] = None
    ) -> List[Dict[str, Any]]:
        """
        Validate import rules.
        
        Args:
            rule: Rule definition
            parsed_file: Parsed file to validate
            all_imports: Optional map of file path -> imports for cross-file validation
            
        Returns:
            List of violations (empty if none)
        """
        violations = []
        rule_type = rule.get('type')
        
        if rule_type == 'forbid_imports':
            violations.extend(self._check_forbidden_imports(rule, parsed_file))
        elif rule_type == 'allow_only':
            violations.extend(self._check_allowed_imports(rule, parsed_file))
        
        return violations
    
    def _check_forbidden_imports(
        self,
        rule: Dict[str, Any],
        parsed_file: ParsedFile
    ) -> List[Dict[str, Any]]:
        """Check for forbidden imports."""
        violations = []
        from_patterns = rule.get('from', [])
        to_patterns = rule.get('to', [])
        
        # Check if file matches 'from' pattern
        file_path = parsed_file.path
        matches_from = any(self._path_matches_pattern(file_path, pattern) for pattern in from_patterns)
        
        if not matches_from:
            return violations
        
        # Check imports against 'to' patterns
        for imp in parsed_file.imports:
            import_path = imp.module
            if any(self._import_matches_pattern(import_path, pattern) for pattern in to_patterns):
                violations.append({
                    'rule_id': rule.get('id'),
                    'severity': rule.get('severity', 'error'),
                    'message': f"Forbidden import: {import_path}",
                    'file_path': file_path,
                    'line': 0,  # Import line not tracked in current parser
                    'details': {
                        'import': import_path,
                        'forbidden_patterns': to_patterns,
                    },
                })
        
        return violations
    
    def _check_allowed_imports(
        self,
        rule: Dict[str, Any],
        parsed_file: ParsedFile
    ) -> List[Dict[str, Any]]:
        """Check that only allowed imports are used."""
        violations = []
        target_patterns = rule.get('target', [])
        caller_patterns = rule.get('callers', [])
        
        # Check if file matches 'target' pattern
        file_path = parsed_file.path
        matches_target = any(self._path_matches_pattern(file_path, pattern) for pattern in target_patterns)
        
        if not matches_target:
            return violations
        
        # Check that imports only come from allowed callers
        allowed_modules = set()
        for pattern in caller_patterns:
            # Convert path pattern to module pattern
            module_pattern = pattern.replace('/', '.').replace('**', '*')
            allowed_modules.add(module_pattern)
        
        for imp in parsed_file.imports:
            import_path = imp.module
            # Check if import matches any allowed caller pattern
            is_allowed = any(
                self._import_matches_pattern(import_path, pattern) 
                for pattern in caller_patterns
            )
            
            if not is_allowed:
                violations.append({
                    'rule_id': rule.get('id'),
                    'severity': rule.get('severity', 'error'),
                    'message': f"Import not allowed: {import_path}",
                    'file_path': file_path,
                    'line': 0,
                    'details': {
                        'import': import_path,
                        'allowed_patterns': caller_patterns,
                    },
                })
        
        return violations
    
    def _path_matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if file path matches pattern (supports ** wildcard)."""
        import fnmatch
        # Normalize path separators
        normalized_path = path.replace('\\', '/')
        return fnmatch.fnmatch(normalized_path, pattern)
    
    def _import_matches_pattern(self, import_path: str, pattern: str) -> bool:
        """Check if import path matches pattern."""
        import fnmatch
        # Convert pattern to module format if needed
        module_pattern = pattern.replace('/', '.').replace('**', '*')
        return fnmatch.fnmatch(import_path, module_pattern)
