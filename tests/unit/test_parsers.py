"""Tests for AST parsers."""
import pytest
from apps.analysis.parsers import get_parser, ParsedFile
from apps.analysis.parsers.python_parser import PythonParser


class TestParserFactory:
    """Test parser factory."""
    
    def test_get_python_parser(self):
        """Test getting Python parser."""
        parser = get_parser("test.py", "python")
        assert parser is not None
        assert isinstance(parser, PythonParser)
    
    def test_get_parser_by_extension(self):
        """Test getting parser by file extension."""
        parser = get_parser("test.py")
        assert parser is not None
        assert isinstance(parser, PythonParser)
    
    def test_get_parser_unsupported_language(self):
        """Test getting parser for unsupported language."""
        parser = get_parser("test.java", "java")
        assert parser is None


class TestPythonParser:
    """Test Python parser."""
    
    def test_parse_simple_function(self):
        """Test parsing simple Python function."""
        code = """def test_function(x: int) -> int:
    return x + 1"""
        parser = PythonParser()
        result = parser.parse_file(code, "test.py")
        
        assert isinstance(result, ParsedFile)
        assert len(result.functions) > 0
        assert result.functions[0].name == "test_function"
