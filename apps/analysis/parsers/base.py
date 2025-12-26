"""Base parser interface."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Function:
    """Represents a function or method."""
    name: str
    signature: str  # Full signature including parameters
    return_type: Optional[str] = None
    docstring: Optional[str] = None
    start_line: int = 0
    end_line: int = 0
    parameters: List[str] = field(default_factory=list)
    is_public: bool = True
    is_static: bool = False
    is_async: bool = False


@dataclass
class Class:
    """Represents a class."""
    name: str
    docstring: Optional[str] = None
    start_line: int = 0
    end_line: int = 0
    base_classes: List[str] = field(default_factory=list)
    is_public: bool = True


@dataclass
class Import:
    """Represents an import statement."""
    module: str
    alias: Optional[str] = None
    imported_items: List[str] = field(default_factory=list)
    is_from_import: bool = False


@dataclass
class ParsedFile:
    """Result of parsing a code file."""
    path: str
    language: str
    functions: List[Function] = field(default_factory=list)
    classes: List[Class] = field(default_factory=list)
    imports: List[Import] = field(default_factory=list)
    ast_signature: Optional[str] = None  # Summary signature for RAG
    errors: List[str] = field(default_factory=list)
    
    def get_ast_signature(self) -> str:
        """Generate AST signature for RAG indexing."""
        if self.ast_signature:
            return self.ast_signature
        
        parts = []
        if self.classes:
            parts.append(f"Classes: {', '.join(c.name for c in self.classes)}")
        if self.functions:
            parts.append(f"Functions: {', '.join(f.name for f in self.functions)}")
        if self.imports:
            parts.append(f"Imports: {len(self.imports)} modules")
        
        return " | ".join(parts) if parts else "Empty file"


class BaseParser(ABC):
    """Abstract base class for language parsers."""
    
    def __init__(self, language: str):
        """Initialize parser."""
        self.language = language
    
    @abstractmethod
    def parse_file(self, content: str, path: str) -> ParsedFile:
        """
        Parse a code file and extract structured information.
        
        Args:
            content: File content as string
            path: File path for context
            
        Returns:
            ParsedFile with extracted information
        """
        pass
    
    @abstractmethod
    def supports_language(self, language: str) -> bool:
        """Check if parser supports the given language."""
        pass
    
    def can_parse(self, path: str) -> bool:
        """Check if parser can parse the given file path."""
        return False
