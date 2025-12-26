"""Parser factory for creating language-specific parsers."""
import logging
from typing import Optional
from pathlib import Path
from apps.analysis.parsers.base import BaseParser
from apps.analysis.parsers.python_parser import PythonParser

logger = logging.getLogger(__name__)

# Registry of parsers
_PARSERS: list[BaseParser] = [
    PythonParser(),
]


def get_parser(path: str, language: Optional[str] = None) -> Optional[BaseParser]:
    """
    Get appropriate parser for a file.
    
    Args:
        path: File path
        language: Optional language hint (python)
        
    Returns:
        Parser instance or None if no parser found
    """
    # Determine language from path if not provided
    if not language:
        ext = Path(path).suffix.lower()
        language_map = {
            '.py': 'python',
        }
        language = language_map.get(ext)
    
    if not language:
        return None
    
    # Find parser that supports this language
    for parser in _PARSERS:
        if parser.supports_language(language) or parser.can_parse(path):
            return parser
    
    logger.warning(f"No parser found for language={language}, path={path}")
    return None


def register_parser(parser: BaseParser):
    """Register a custom parser."""
    _PARSERS.append(parser)
    logger.info(f"Registered parser for language: {parser.language}")
