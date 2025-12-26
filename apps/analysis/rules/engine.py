"""Rule engine for evaluating architecture rules."""
import logging
from typing import List, Dict, Any, Optional
from apps.analysis.parsers.base import ParsedFile
from apps.analysis.rules.loader import load_rules_from_yaml
from apps.analysis.rules.validators import (
    ImportValidator,
    CycleValidator,
    PublicAPIValidator,
)

logger = logging.getLogger(__name__)


class RuleEngine:
    """Engine for evaluating architecture rules."""
    
    def __init__(self, rules_config_path: Optional[str] = None):
        """Initialize rule engine."""
        self.rules = load_rules_from_yaml(rules_config_path)
        self.import_validator = ImportValidator()
        self.cycle_validator = CycleValidator()
        self.public_api_validator = PublicAPIValidator()
        
        logger.info(f"Rule engine initialized with {len(self.rules)} rules")
    
    def evaluate_file(self, parsed_file: ParsedFile) -> List[Dict[str, Any]]:
        """
        Evaluate all rules against a parsed file.
        
        Args:
            parsed_file: Parsed file to evaluate
            
        Returns:
            List of violations
        """
        violations = []
        
        for rule in self.rules:
            rule_type = rule.get('type')
            
            try:
                if rule_type == 'forbid_imports' or rule_type == 'allow_only':
                    rule_violations = self.import_validator.validate(rule, parsed_file)
                    violations.extend(rule_violations)
                
                elif rule_type == 'enforce_public':
                    rule_violations = self.public_api_validator.validate(rule, parsed_file)
                    violations.extend(rule_violations)
                
            except Exception as e:
                logger.exception(f"Error evaluating rule {rule.get('id')}: {e}")
        
        return violations
    
    def evaluate_import_graph(
        self,
        import_graph: Dict[str, set[str]]
    ) -> List[Dict[str, Any]]:
        """
        Evaluate cycle detection rules against import graph.
        
        Args:
            import_graph: Map of module -> set of imported modules
            
        Returns:
            List of violations
        """
        violations = []
        
        for rule in self.rules:
            if rule.get('type') == 'graph_check':
                try:
                    rule_violations = self.cycle_validator.validate(rule, import_graph)
                    violations.extend(rule_violations)
                except Exception as e:
                    logger.exception(f"Error evaluating rule {rule.get('id')}: {e}")
        
        return violations
    
    def reload_rules(self, rules_config_path: Optional[str] = None):
        """Reload rules from configuration."""
        self.rules = load_rules_from_yaml(rules_config_path)
        logger.info(f"Reloaded {len(self.rules)} rules")
