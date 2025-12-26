"""Dependency cycle validator."""
import logging
from typing import List, Dict, Any, Set, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


class CycleValidator:
    """Validates dependency cycles."""
    
    def validate(
        self,
        rule: Dict[str, Any],
        import_graph: Dict[str, Set[str]]
    ) -> List[Dict[str, Any]]:
        """
        Validate for dependency cycles.
        
        Args:
            rule: Rule definition
            import_graph: Map of module -> set of imported modules
            
        Returns:
            List of violations (cycles found)
        """
        violations = []
        
        if rule.get('check') != 'no_cycles':
            return violations
        
        cycles = self._detect_cycles(import_graph)
        
        for cycle in cycles:
            violations.append({
                'rule_id': rule.get('id'),
                'severity': rule.get('severity', 'error'),
                'message': f"Dependency cycle detected: {' -> '.join(cycle)}",
                'file_path': None,
                'details': {
                    'cycle': cycle,
                },
            })
        
        return violations
    
    def _detect_cycles(self, graph: Dict[str, Set[str]]) -> List[List[str]]:
        """Detect cycles in directed graph using DFS."""
        cycles = []
        visited = set()
        rec_stack = set()
        
        def dfs(node: str, path: List[str]) -> None:
            """DFS to detect cycles."""
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor, path.copy())
                elif neighbor in rec_stack:
                    # Cycle detected
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)
            
            rec_stack.remove(node)
            path.pop()
        
        for node in graph:
            if node not in visited:
                dfs(node, [])
        
        return cycles
