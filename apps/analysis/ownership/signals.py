"""Ownership inference signals."""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class GitBlameSignal:
    """Git blame-based ownership signal."""
    
    def calculate(self, file_path: str, blame_data: List[Dict]) -> Dict[str, float]:
        """
        Calculate ownership scores based on git blame.
        
        Args:
            file_path: File path
            blame_data: List of blame entries with 'author', 'lines' keys
            
        Returns:
            Dict mapping author -> score (0.0 to 1.0)
        """
        scores = defaultdict(float)
        total_lines = 0
        
        for entry in blame_data:
            author = entry.get('author', 'unknown')
            lines = entry.get('lines', 0)
            total_lines += lines
            
            # Decay by age (more recent = higher weight)
            age_days = entry.get('age_days', 0)
            decay_factor = self._calculate_decay(age_days)
            
            scores[author] += lines * decay_factor
        
        # Normalize to 0-1
        if total_lines > 0:
            return {author: score / total_lines for author, score in scores.items()}
        
        return {}
    
    def _calculate_decay(self, age_days: int) -> float:
        """Calculate decay factor based on age (exponential decay)."""
        # Half-life of 90 days
        half_life = 90
        return 0.5 ** (age_days / half_life)


class CommitHistorySignal:
    """Recent commit history signal."""
    
    def calculate(
        self,
        file_path: str,
        commits: List[Dict],
        window_days: int = 90
    ) -> Dict[str, float]:
        """
        Calculate ownership based on recent commits.
        
        Args:
            file_path: File path
            commits: List of commits with 'author', 'date', 'files_changed' keys
            window_days: Time window in days (default: 90)
            
        Returns:
            Dict mapping author -> score
        """
        cutoff_date = datetime.utcnow() - timedelta(days=window_days)
        scores = defaultdict(float)
        total_commits = 0
        
        for commit in commits:
            commit_date = commit.get('date')
            if isinstance(commit_date, str):
                try:
                    commit_date = datetime.fromisoformat(commit_date.replace('Z', '+00:00'))
                except:
                    continue
            
            if commit_date < cutoff_date:
                continue
            
            author = commit.get('author', 'unknown')
            files_changed = commit.get('files_changed', [])
            
            # Check if this commit touched the file
            if file_path in files_changed or any(file_path.endswith(f) for f in files_changed):
                scores[author] += 1.0
                total_commits += 1
        
        # Normalize
        if total_commits > 0:
            return {author: score / total_commits for author, score in scores.items()}
        
        return {}


class ReviewerHistorySignal:
    """Reviewer history signal."""
    
    def calculate(
        self,
        file_path: str,
        pr_history: List[Dict]
    ) -> Dict[str, float]:
        """
        Calculate ownership based on reviewer patterns.
        
        Args:
            file_path: File path
            pr_history: List of PRs with 'reviewers', 'files_changed' keys
            
        Returns:
            Dict mapping reviewer -> score
        """
        scores = defaultdict(float)
        total_reviews = 0
        
        for pr in pr_history:
            files_changed = pr.get('files_changed', [])
            
            # Check if PR touched this file
            if file_path in files_changed or any(file_path.endswith(f) for f in files_changed):
                reviewers = pr.get('reviewers', [])
                for reviewer in reviewers:
                    scores[reviewer] += 1.0
                    total_reviews += 1
        
        # Normalize
        if total_reviews > 0:
            return {reviewer: score / total_reviews for reviewer, score in scores.items()}
        
        return {}


class ServiceMapSignal:
    """Service map-based ownership signal."""
    
    def calculate(
        self,
        file_path: str,
        service_map: Dict
    ) -> Dict[str, float]:
        """
        Calculate ownership based on service map configuration.
        
        Args:
            file_path: File path
            service_map: Service map dict with 'modules' and 'paths' keys
            
        Returns:
            Dict mapping team/owner -> score
        """
        scores = {}
        
        # Check path-based mappings
        paths = service_map.get('paths', {})
        for pattern, module in paths.items():
            if self._path_matches_pattern(file_path, pattern):
                module_info = service_map.get('modules', {}).get(module, {})
                team = module_info.get('team')
                if team:
                    scores[team] = 1.0  # High confidence from service map
                owner = module_info.get('owner')
                if owner:
                    scores[owner] = 1.0
        
        return scores
    
    def _path_matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if path matches pattern."""
        import fnmatch
        normalized_path = path.replace('\\', '/')
        return fnmatch.fnmatch(normalized_path, pattern)


class ModuleAffinitySignal:
    """Module affinity signal based on call graph."""
    
    def calculate(
        self,
        file_path: str,
        call_graph: Dict[str, List[str]]
    ) -> Dict[str, float]:
        """
        Calculate ownership based on module/call graph relationships.
        
        Args:
            file_path: File path
            call_graph: Map of file -> list of called files
            
        Returns:
            Dict mapping owner -> score (based on related files)
        """
        # This is a placeholder - would need actual call graph analysis
        # For now, return empty dict
        return {}
