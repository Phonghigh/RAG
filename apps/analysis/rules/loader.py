"""Load rules from YAML configuration."""
import yaml
import logging
from pathlib import Path
from typing import List, Dict, Any
from apps.shared.config import settings

logger = logging.getLogger(__name__)


def load_rules_from_yaml(config_path: str = None) -> List[Dict[str, Any]]:
    """
    Load rules from YAML file.
    
    Args:
        config_path: Path to rules YAML file. If None, uses default from config.
        
    Returns:
        List of rule dictionaries
    """
    if config_path is None:
        config_path = getattr(settings, 'rules_config_path', 'configs/rules.yaml')
    
    path = Path(config_path)
    if not path.exists():
        logger.warning(f"Rules config file not found: {config_path}")
        return []
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        rules = data.get('rules', [])
        logger.info(f"Loaded {len(rules)} rules from {config_path}")
        return rules
    
    except Exception as e:
        logger.exception(f"Error loading rules from {config_path}: {e}")
        return []


def validate_rule_schema(rule: Dict[str, Any]) -> bool:
    """Validate rule schema."""
    required_fields = ['id', 'type']
    if not all(field in rule for field in required_fields):
        return False
    
    rule_type = rule.get('type')
    
    if rule_type == 'forbid_imports':
        return 'from' in rule and 'to' in rule
    elif rule_type == 'allow_only':
        return 'target' in rule and 'callers' in rule
    elif rule_type == 'graph_check':
        return 'check' in rule
    elif rule_type == 'enforce_public':
        return 'packages' in rule
    
    return True
