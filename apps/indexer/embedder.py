"""Embedding generation using local models."""
import logging
from typing import List, Optional
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class Embedder:
    """Generates embeddings using local models."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize embedder.
        
        Args:
            model_name: Model name or path (must be compatible with sentence-transformers)
        """
        self.model_name = model_name
        self.model: Optional[SentenceTransformer] = None
        self._load_model()
    
    def _load_model(self):
        """Load embedding model."""
        try:
            logger.info(f"Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            logger.info(f"Model loaded successfully, dimension: {self.model.get_sentence_embedding_dimension()}")
        except Exception as e:
            logger.exception(f"Error loading embedding model: {e}")
            raise
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for texts.
        
        Args:
            texts: List of text strings
            
        Returns:
            List of embedding vectors
        """
        if not self.model:
            raise RuntimeError("Model not loaded")
        
        try:
            embeddings = self.model.encode(texts, convert_to_numpy=True)
            return embeddings.tolist()
        except Exception as e:
            logger.exception(f"Error generating embeddings: {e}")
            raise
    
    def embed_single(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        return self.embed([text])[0]
    
    def get_dimension(self) -> int:
        """Get embedding dimension."""
        if not self.model:
            return 384  # Default for all-MiniLM-L6-v2
        return self.model.get_sentence_embedding_dimension()
