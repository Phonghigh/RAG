"""Ownership inference engine."""
import logging
from typing import List, Dict, Optional
from apps.analysis.ownership.models import OwnershipScore, OwnershipCandidate
from apps.analysis.ownership.signals import (
    GitBlameSignal,
    CommitHistorySignal,
    ReviewerHistorySignal,
    ServiceMapSignal,
    ModuleAffinitySignal,
)

logger = logging.getLogger(__name__)


class OwnershipInferrer:
    """Infers code ownership using multiple signals."""
    
    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None
    ):
        """
        Initialize ownership inferrer.
        
        Args:
            weights: Signal weights (default: equal weights)
        """
        # Default weights
        self.weights = weights or {
            'recent_commit_share': 0.3,
            'lines_authored_share': 0.25,
            'reviewer_history': 0.2,
            'module_affinity': 0.15,
            'service_map_hint': 0.1,
        }
        
        # Normalize weights
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}
        
        self.git_blame_signal = GitBlameSignal()
        self.commit_history_signal = CommitHistorySignal()
        self.reviewer_history_signal = ReviewerHistorySignal()
        self.service_map_signal = ServiceMapSignal()
        self.module_affinity_signal = ModuleAffinitySignal()
    
    def infer(
        self,
        file_path: str,
        git_blame: Optional[List[Dict]] = None,
        commit_history: Optional[List[Dict]] = None,
        pr_history: Optional[List[Dict]] = None,
        service_map: Optional[Dict] = None,
        call_graph: Optional[Dict] = None
    ) -> List[OwnershipCandidate]:
        """
        Infer ownership for a file.
        
        Args:
            file_path: File path
            git_blame: Git blame data
            commit_history: Recent commit history
            pr_history: PR review history
            service_map: Service map configuration
            call_graph: Call graph data
            
        Returns:
            List of ownership candidates sorted by score
        """
        # Calculate individual signals
        signals = {}
        
        # Recent commit share
        if commit_history:
            commit_scores = self.commit_history_signal.calculate(file_path, commit_history)
            signals['recent_commit_share'] = commit_scores
        else:
            signals['recent_commit_share'] = {}
        
        # Lines authored (git blame)
        if git_blame:
            blame_scores = self.git_blame_signal.calculate(file_path, git_blame)
            signals['lines_authored_share'] = blame_scores
        else:
            signals['lines_authored_share'] = {}
        
        # Reviewer history
        if pr_history:
            reviewer_scores = self.reviewer_history_signal.calculate(file_path, pr_history)
            signals['reviewer_history'] = reviewer_scores
        else:
            signals['reviewer_history'] = {}
        
        # Service map
        if service_map:
            service_scores = self.service_map_signal.calculate(file_path, service_map)
            signals['service_map_hint'] = service_scores
        else:
            signals['service_map_hint'] = {}
        
        # Module affinity
        if call_graph:
            module_scores = self.module_affinity_signal.calculate(file_path, call_graph)
            signals['module_affinity'] = module_scores
        else:
            signals['module_affinity'] = {}
        
        # Combine signals with weights
        combined_scores = self._combine_signals(signals)
        
        # Convert to candidates
        candidates = []
        for candidate, score_data in combined_scores.items():
            score = score_data['score']
            signal_breakdown = score_data['signals']
            confidence = self._calculate_confidence(signal_breakdown)
            
            reasoning = self._generate_reasoning(candidate, signal_breakdown)
            
            candidates.append(OwnershipCandidate(
                candidate=candidate,
                score=score,
                confidence=confidence,
                reasoning=reasoning,
            ))
        
        # Sort by score descending
        candidates.sort(key=lambda x: x.score, reverse=True)
        
        return candidates
    
    def _combine_signals(self, signals: Dict[str, Dict[str, float]]) -> Dict[str, Dict]:
        """Combine multiple signals with weights."""
        combined = {}
        
        # Collect all candidates
        all_candidates = set()
        for signal_scores in signals.values():
            all_candidates.update(signal_scores.keys())
        
        # Calculate weighted scores
        for candidate in all_candidates:
            total_score = 0.0
            signal_breakdown = {}
            
            for signal_name, signal_scores in signals.items():
                weight = self.weights.get(signal_name, 0.0)
                candidate_score = signal_scores.get(candidate, 0.0)
                
                weighted_score = candidate_score * weight
                total_score += weighted_score
                signal_breakdown[signal_name] = candidate_score
            
            combined[candidate] = {
                'score': total_score,
                'signals': signal_breakdown,
            }
        
        return combined
    
    def _calculate_confidence(self, signal_breakdown: Dict[str, float]) -> float:
        """Calculate confidence based on signal diversity."""
        # More signals with non-zero values = higher confidence
        non_zero_signals = sum(1 for v in signal_breakdown.values() if v > 0)
        max_signals = len(signal_breakdown)
        
        if max_signals == 0:
            return 0.0
        
        # Base confidence from signal diversity
        diversity_confidence = non_zero_signals / max_signals
        
        # Boost confidence if service_map_hint is present (high confidence signal)
        if signal_breakdown.get('service_map_hint', 0) > 0:
            diversity_confidence = min(1.0, diversity_confidence + 0.3)
        
        return diversity_confidence
    
    def _generate_reasoning(self, candidate: str, signal_breakdown: Dict[str, float]) -> str:
        """Generate human-readable reasoning for ownership."""
        reasons = []
        
        if signal_breakdown.get('recent_commit_share', 0) > 0.3:
            reasons.append(f"recent commits ({signal_breakdown['recent_commit_share']:.0%})")
        
        if signal_breakdown.get('lines_authored_share', 0) > 0.3:
            reasons.append(f"lines authored ({signal_breakdown['lines_authored_share']:.0%})")
        
        if signal_breakdown.get('reviewer_history', 0) > 0.2:
            reasons.append(f"review history ({signal_breakdown['reviewer_history']:.0%})")
        
        if signal_breakdown.get('service_map_hint', 0) > 0:
            reasons.append("service map configuration")
        
        if reasons:
            return f"Ownership inferred from: {', '.join(reasons)}"
        else:
            return "Low confidence ownership inference"
