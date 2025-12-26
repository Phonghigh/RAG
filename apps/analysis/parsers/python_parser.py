"""Python parser using AST and tree-sitter."""
import ast
import logging
from typing import Optional
from apps.analysis.parsers.base import BaseParser, ParsedFile, Function, Class, Import

logger = logging.getLogger(__name__)


class PythonParser(BaseParser):
    """Python code parser."""
    
    def __init__(self):
        """Initialize Python parser."""
        super().__init__("python")
        # Tree-sitter support can be added later
        # For now, we use Python's built-in AST module
    
    def parse_file(self, content: str, path: str) -> ParsedFile:
        """Parse Python file."""
        parsed = ParsedFile(path=path, language="python")
        
        try:
            tree = ast.parse(content, filename=path)
            
            # Single pass through AST to extract all information
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_obj = self._extract_class(node)
                    parsed.classes.append(class_obj)
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func = self._extract_function(node)
                    parsed.functions.append(func)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        import_obj = Import(
                            module=alias.name,
                            alias=alias.asname,
                            is_from_import=False,
                        )
                        parsed.imports.append(import_obj)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imported_items = [alias.name for alias in (node.names or [])]
                        import_obj = Import(
                            module=node.module,
                            imported_items=imported_items,
                            is_from_import=True,
                        )
                        parsed.imports.append(import_obj)
            
            parsed.ast_signature = parsed.get_ast_signature()
            
        except SyntaxError as e:
            parsed.errors.append(f"Python syntax error: {e}")
            logger.warning(f"Failed to parse Python file {path}: {e}")
        except Exception as e:
            parsed.errors.append(f"Parse error: {e}")
            logger.exception(f"Error parsing Python file {path}: {e}")
        
        return parsed
    
    def _extract_class(self, node: ast.ClassDef) -> Class:
        """Extract class information."""
        base_classes = [ast.unparse(base) if hasattr(ast, 'unparse') else self._unparse_node(base) 
                       for base in node.bases]
        
        # Determine visibility (Python convention: no leading underscore = public)
        is_public = not node.name.startswith('_')
        
        # Extract docstring
        docstring = ast.get_docstring(node)
        
        # Get line numbers
        start_line = node.lineno
        end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line
        
        return Class(
            name=node.name,
            docstring=docstring,
            start_line=start_line,
            end_line=end_line,
            base_classes=base_classes,
            is_public=is_public,
        )
    
    def _extract_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> Function:
        """Extract function information."""
        # Build signature
        params = []
        if node.args.args:
            for arg in node.args.args:
                param_name = arg.arg
                if arg.annotation:
                    param_type = ast.unparse(arg.annotation) if hasattr(ast, 'unparse') else self._unparse_node(arg.annotation)
                    params.append(f"{param_name}: {param_type}")
                else:
                    params.append(param_name)
        
        signature = f"{node.name}({', '.join(params)})"
        
        # Return type
        return_type = None
        if node.returns:
            return_type = ast.unparse(node.returns) if hasattr(ast, 'unparse') else self._unparse_node(node.returns)
        
        # Check if async
        is_async = isinstance(node, ast.AsyncFunctionDef)
        
        # Determine visibility
        is_public = not node.name.startswith('_')
        
        # Check if static method (decorator)
        is_static = any(
            (isinstance(dec, ast.Name) and dec.id == 'staticmethod') or
            (isinstance(dec, ast.Attribute) and dec.attr == 'staticmethod')
            for dec in (node.decorator_list or [])
        )
        
        # Extract docstring
        docstring = ast.get_docstring(node)
        
        # Get line numbers
        start_line = node.lineno
        end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line
        
        return Function(
            name=node.name,
            signature=signature,
            return_type=return_type,
            docstring=docstring,
            start_line=start_line,
            end_line=end_line,
            parameters=params,
            is_public=is_public,
            is_static=is_static,
            is_async=is_async,
        )
    
    def _unparse_node(self, node: ast.AST) -> str:
        """Fallback unparse for older Python versions."""
        # Simple fallback - just return the type name
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._unparse_node(node.value)}.{node.attr}"
        elif isinstance(node, ast.Constant):
            return repr(node.value)
        else:
            return str(type(node).__name__)
    
    def supports_language(self, language: str) -> bool:
        """Check if parser supports Python."""
        return language.lower() == "python"
    
    def can_parse(self, path: str) -> bool:
        """Check if file is Python."""
        return path.endswith('.py')
