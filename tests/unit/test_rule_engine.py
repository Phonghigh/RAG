"""Tests for rule engine."""
import pytest
import tempfile
import yaml
from pathlib import Path
from apps.analysis.rules import RuleEngine
from apps.analysis.parsers import get_parser


@pytest.fixture
def sample_rules_file():
    """Create temporary rules file."""
    rules = {
        'rules': [
            {
                'id': 'test_forbid',
                'type': 'forbid_imports',
                'severity': 'error',
                'from': ['**/domain/**'],
                'to': ['**/infra/**'],
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(rules, f)
        yield f.name
    
    Path(f.name).unlink()


@pytest.fixture
def sample_python_code():
    """Sample Python code with forbidden import."""
    return """# app/domain/domain_class.py
from app.infra.database import Database

class DomainClass:
    pass"""


class TestRuleEngine:
    """Test rule engine."""
    
    def test_load_rules(self, sample_rules_file):
        """Test loading rules from YAML."""
        engine = RuleEngine(sample_rules_file)
        assert len(engine.rules) > 0
    
    def test_evaluate_forbidden_import(self, sample_rules_file, sample_python_code):
        """Test evaluating forbidden import rule."""
        engine = RuleEngine(sample_rules_file)
        parser = get_parser("app/domain/domain_class.py", "python")
        parsed = parser.parse_file(sample_python_code, "app/domain/domain_class.py")
        
        violations = engine.evaluate_file(parsed)
        assert len(violations) > 0
        assert violations[0]['rule_id'] == 'test_forbid'
