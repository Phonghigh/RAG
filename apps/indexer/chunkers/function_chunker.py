"""Function-level chunker."""
import logging
from typing import List, Dict
from apps.analysis.parsers import ParsedFile, Function

logger = logging.getLogger(__name__)


class FunctionChunker:
    """Chunks code at function/method level."""
    
    def chunk(self, parsed_file: ParsedFile, content: str) -> List[Dict]:
        """
        Chunk file by functions/methods.
        
        Args:
            parsed_file: Parsed file with functions extracted
            content: Original file content
            
        Returns:
            List of chunks with 'content', 'metadata', 'ast_signature'
        """
        chunks = []
        lines = content.split('\n')
        
        for func in parsed_file.functions:
            # Extract function content
            start_idx = func.start_line - 1
            end_idx = func.end_line
            
            # Ensure valid indices
            if start_idx < 0:
                start_idx = 0
            if end_idx > len(lines):
                end_idx = len(lines)
            
            func_lines = lines[start_idx:end_idx]
            func_content = '\n'.join(func_lines)
            
            # Build chunk content with context
            chunk_content = self._build_chunk_content(func, func_content, parsed_file)
            
            chunk = {
                'content': chunk_content,
                'metadata': {
                    'type': 'function',
                    'function_name': func.name,
                    'signature': func.signature,
                    'start_line': func.start_line,
                    'end_line': func.end_line,
                    'is_public': func.is_public,
                    'is_static': func.is_static,
                    'is_async': func.is_async,
                    'return_type': func.return_type,
                },
                'ast_signature': func.signature,
            }
            
            chunks.append(chunk)
        
        return chunks
    
    def _build_chunk_content(self, func: Function, func_content: str, parsed_file: ParsedFile) -> str:
        """Build chunk content with context."""
        parts = []
        
        # Add docstring if available
        if func.docstring:
            parts.append(f"# {func.docstring}")
        
        # Add function signature and content
        parts.append(func_content)
        
        # Add class context if function is a method
        if parsed_file.classes:
            # Find class containing this function
            for cls in parsed_file.classes:
                if cls.start_line <= func.start_line <= cls.end_line:
                    parts.insert(0, f"# Class: {cls.name}")
                    break
        
        return '\n'.join(parts)
