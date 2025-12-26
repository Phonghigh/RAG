"""PR diff chunker."""
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class PRChunker:
    """Chunks PR diffs."""
    
    def chunk(self, diff_content: str, file_path: str, metadata: Dict = None) -> List[Dict]:
        """
        Chunk a PR diff.
        
        Args:
            diff_content: Diff content
            file_path: File path
            metadata: Additional metadata
            
        Returns:
            List of chunks
        """
        # For PR diffs, we create one chunk per file
        chunk = {
            'content': diff_content,
            'metadata': {
                'type': 'pr_diff',
                'file_path': file_path,
                **(metadata or {}),
            },
            'ast_signature': f"PR diff: {file_path}",
        }
        
        return [chunk]
