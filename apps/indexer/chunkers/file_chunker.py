"""File-level chunker."""
import logging
from typing import List, Dict
from apps.analysis.parsers import ParsedFile

logger = logging.getLogger(__name__)


class FileChunker:
    """Chunks code at file level (for small files)."""
    
    def __init__(self, max_lines: int = 500):
        """
        Initialize file chunker.
        
        Args:
            max_lines: Maximum lines for file-level chunking
        """
        self.max_lines = max_lines
    
    def chunk(self, parsed_file: ParsedFile, content: str) -> List[Dict]:
        """
        Chunk entire file if small enough.
        
        Args:
            parsed_file: Parsed file
            content: File content
            
        Returns:
            List of chunks (single chunk if file is small)
        """
        lines = content.split('\n')
        
        # Only chunk as file if small enough
        if len(lines) > self.max_lines:
            return []
        
        chunk = {
            'content': content,
            'metadata': {
                'type': 'file',
                'classes': [cls.name for cls in parsed_file.classes],
                'functions': [func.name for func in parsed_file.functions],
                'imports_count': len(parsed_file.imports),
            },
            'ast_signature': parsed_file.get_ast_signature(),
        }
        
        return [chunk]
