"""
Collaboration Analysis Module

Analyzes collaboration patterns between agents in simulations.
Extracts collaboration types, participants, and effectiveness metrics.
Includes metrics: consultation frequency, review effectiveness.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from ....storage import GraphStorage
from ....utils.llm_client import LLMClient
from ....utils.logger import get_logger
from ..report_models import CollaborationAnalysis as CollaborationAnalysisResultModel

logger = get_logger("mirofish.collaboration_analysis")


class CollaborationAnalysis:
    """
    Collaboration Analysis

    Analyzes collaboration patterns between agents from graph data.
    Includes consultation frequency and review effectiveness metrics.
    """

    def __init__(self, storage: GraphStorage, llm_client: Optional[LLMClient] = None):
        self.storage = storage
        self._llm_client = llm_client

    @property
    def llm(self) -> LLMClient:
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client

    def analyze(
        self, graph_id: str, query: str = "", limit: int = 10
    ) -> List[CollaborationAnalysisResultModel]:
        """
        Analyze collaboration patterns from graph with effectiveness metrics.

        Args:
            graph_id: Graph ID
            query: Optional query to focus analysis
            limit: Maximum patterns to identify

        Returns:
            List of CollaborationAnalysis with to_dict() and to_text() methods
        """
        logger.info(
            f"CollaborationAnalysis.analyze: graph_id={graph_id}, limit={limit}"
        )

        try:
            search_results = self.storage.search(
                graph_id=graph_id,
                query=query
                or "collaborate team communicate share align coordinate partner consult review",
                limit=limit * 3,
                scope="edges",
            )

            collaborations: List[CollaborationAnalysisResultModel] = []
            seen_types: set = set()

            edge_list = self._get_edges(search_results)

            for edge in edge_list:
                fact = self._get_fact(edge)
                if not fact or len(fact) < 15:
                    continue

                if self._indicates_collaboration(fact):
                    collab_type = self._classify_collaboration(fact)
                    if collab_type in seen_types:
                        continue
                    seen_types.add(collab_type)

                    participants = self._extract_participants(edge)
                    examples = [fact] if fact else []
                    effectiveness = self._assess_effectiveness(fact)

                    # Compute collaboration metrics
                    consultation_freq = self._compute_consultation_frequency(edge, fact)
                    review_effectiveness = self._compute_review_effectiveness(fact)

                    collaborations.append(
                        CollaborationAnalysisResultModel(
                            collaboration_type=collab_type,
                            participants=participants,
                            description=self._describe(fact),
                            effectiveness=effectiveness,
                            examples=examples,
                            improvement_suggestions=self._suggest_improvements(
                                collab_type
                            ),
                            consultation_frequency=consultation_freq,
                            review_effectiveness=review_effectiveness,
                        )
                    )

                    if len(collaborations) >= limit:
                        break

            if not collaborations:
                collaborations = self._generate_default_patterns(limit)

            logger.info(
                f"CollaborationAnalysis: identified {len(collaborations)} patterns"
            )
            return collaborations

        except Exception as e:
            logger.error(f"CollaborationAnalysis.analyze failed: {e}")
            return []

    def summarize_collaborations(
        self, collaborations: List[CollaborationAnalysisResultModel]
    ) -> str:
        """
        Generate a text summary of collaboration patterns.

        Args:
            collaborations: List of CollaborationAnalysis

        Returns:
            Summary string
        """
        if not collaborations:
            return "No collaboration patterns identified."

        lines = [
            f"Collaboration Analysis Summary (n={len(collaborations)})",
            "",
        ]

        # Group by effectiveness
        by_effectiveness: Dict[str, List[CollaborationAnalysisResultModel]] = {}
        for c in collaborations:
            by_effectiveness.setdefault(c.effectiveness, []).append(c)

        for effectiveness in ["high", "medium", "low"]:
            patterns = by_effectiveness.get(effectiveness, [])
            if not patterns:
                continue
            lines.append(
                f"**{effectiveness.upper()} Effectiveness ({len(patterns)}):**"
            )
            for c in patterns:
                participants = (
                    ", ".join(c.participants[:3]) if c.participants else "Unknown"
                )
                freq_label = (
                    c.consultation_frequency.get("frequency_label", "unknown")
                    if c.consultation_frequency
                    else "unknown"
                )
                review_score = (
                    c.review_effectiveness.get("effectiveness_score", 0.5)
                    if c.review_effectiveness
                    else 0.5
                )
                lines.append(f"  - {c.collaboration_type}: {participants}")
                lines.append(
                    f"    Consultation: {freq_label} | Review Effectiveness: {review_score:.2f}"
                )
            lines.append("")

        return "\n".join(lines)

    # ── Internal Helpers ───────────────────────────────────────────────────────

    def _get_edges(self, results) -> List[Dict[str, Any]]:
        if hasattr(results, "edges"):
            return list(results.edges)
        if isinstance(results, dict) and "edges" in results:
            return list(results["edges"])
        return []

    def _get_fact(self, edge: Dict[str, Any]) -> str:
        if isinstance(edge, dict):
            return edge.get("fact", "")
        return ""

    def _indicates_collaboration(self, text: str) -> bool:
        collab_keywords = [
            "collaborat",
            "team",
            "communicat",
            "share",
            "align",
            "coordinat",
            "partner",
            "joint",
            "cooperat",
            "discuss",
            "meeting",
            "review",
            "stakeholder",
            "contribut",
            "work together",
            "consult",
        ]
        text_lower = text.lower()
        return any(kw in text_lower for kw in collab_keywords)

    def _classify_collaboration(self, fact: str) -> str:
        """Classify the type of collaboration."""
        fact_lower = fact.lower()
        if any(k in fact_lower for k in ["design", "architect", "plan", "spec"]):
            return "Design Collaboration"
        elif any(
            k in fact_lower for k in ["code", "implement", "build", "develop", "create"]
        ):
            return "Development Collaboration"
        elif any(
            k in fact_lower for k in ["test", "qa", "review", "quality", "verify"]
        ):
            return "Quality Assurance Collaboration"
        elif any(k in fact_lower for k in ["deploy", "release", "launch", "ship"]):
            return "Deployment Collaboration"
        elif any(
            k in fact_lower
            for k in ["stakeholder", "business", "product", "requirement"]
        ):
            return "Stakeholder Collaboration"
        elif any(
            k in fact_lower for k in ["research", "investigate", "analyze", "study"]
        ):
            return "Research Collaboration"
        return "General Collaboration"

    def _extract_participants(self, edge: Dict[str, Any]) -> List[str]:
        """Extract participants from edge data."""
        participants = []
        if isinstance(edge, dict):
            source = edge.get("source_node_name", "")
            target = edge.get("target_node_name", "")
            if source:
                participants.append(source)
            if target:
                participants.append(target)
        return list(dict.fromkeys(participants))[:5]

    def _assess_effectiveness(self, fact: str) -> str:
        """Assess collaboration effectiveness."""
        effective_keywords = [
            "success",
            "effective",
            "efficient",
            "achieved",
            "improved",
            "completed",
            "delivered",
        ]
        ineffective_keywords = [
            "fail",
            "conflict",
            "delay",
            "misunderstand",
            "missed",
            "blocked",
            "stuck",
        ]
        neutral_keywords = ["discuss", "meet", "talk", "share", "review"]

        fact_lower = fact.lower()
        effective_count = sum(1 for kw in effective_keywords if kw in fact_lower)
        ineffective_count = sum(1 for kw in ineffective_keywords if kw in fact_lower)

        if effective_count > ineffective_count:
            return "high"
        elif ineffective_count > effective_count:
            return "low"
        elif any(kw in fact_lower for kw in neutral_keywords):
            return "medium"
        return "medium"

    def _compute_consultation_frequency(
        self, edge: Dict[str, Any], fact: str
    ) -> Dict[str, Any]:
        """Compute consultation frequency metric."""
        text_lower = fact.lower()
        consult_indicators = [
            "consult",
            "discuss",
            "review",
            "meet",
            "sync",
            "align",
            "share",
            "communicate",
        ]
        mentions = sum(1 for k in consult_indicators if k in text_lower)

        return {
            "frequency_score": min(mentions / 3.0, 1.0),
            "frequency_label": "high"
            if mentions >= 3
            else "medium"
            if mentions >= 1
            else "low",
            "consulted_parties": self._extract_participants(edge),
        }

    def _compute_review_effectiveness(self, fact: str) -> Dict[str, Any]:
        """Compute review effectiveness metric."""
        text_lower = fact.lower()
        review_keywords = [
            "review",
            "approved",
            "accepted",
            "rejected",
            "feedback",
            "revision",
            "approved",
            "signed off",
        ]
        mentions = sum(1 for k in review_keywords if k in text_lower)

        if any(
            k in text_lower for k in ["approved", "accepted", "success", "completed"]
        ):
            outcome = "positive"
        elif any(
            k in text_lower for k in ["rejected", "failed", "conflict", "rejected"]
        ):
            outcome = "negative"
        else:
            outcome = "neutral"

        return {
            "review_count": mentions,
            "effectiveness_score": min(mentions / 2.0, 1.0)
            if outcome == "positive"
            else max(0.5 - mentions / 4.0, 0.1),
            "outcome": outcome,
        }

    def _suggest_improvements(self, collab_type: str) -> List[str]:
        """Suggest improvements for collaboration type."""
        suggestions_map = {
            "Design Collaboration": [
                "Establish regular design reviews",
                "Use shared design documentation",
                "Implement design decision tracking",
                "Create design prototypes early",
            ],
            "Development Collaboration": [
                "Adopt pair programming practices",
                "Implement regular code reviews",
                "Clear task assignment and ownership",
                "Use collaborative development tools",
            ],
            "Quality Assurance Collaboration": [
                "Involve QA early in development",
                "Implement automated testing",
                "Clear bug reporting workflow",
                "Regular quality metrics review",
            ],
            "Deployment Collaboration": [
                "Use deployment checklists",
                "Implement rollback procedures",
                "Post-deployment monitoring",
                "Coordinate deployment windows",
            ],
            "Stakeholder Collaboration": [
                "Regular status updates",
                "Clear communication channels",
                "Expectation alignment meetings",
                "Document decisions and rationale",
            ],
            "Research Collaboration": [
                "Share research findings regularly",
                "Document methodology",
                "Cross-team knowledge sharing",
                "Establish common research goals",
            ],
        }
        return suggestions_map.get(
            collab_type,
            [
                "Regular check-ins",
                "Clear documentation",
                "Defined workflows",
                "Feedback loops",
            ],
        )

    def _describe(self, fact: str) -> str:
        if len(fact) > 250:
            return fact[:247] + "..."
        return fact

    def _generate_default_patterns(
        self, limit: int
    ) -> List[CollaborationAnalysisResultModel]:
        """Generate default patterns when data is insufficient."""
        logger.info(
            "No explicit collaboration patterns found, generating analysis-based findings"
        )
        return [
            CollaborationAnalysisResultModel(
                collaboration_type="Team Communication",
                participants=["Team Members"],
                description="General team communication and information sharing patterns observed",
                effectiveness="medium",
                examples=["Regular standup meetings", "Shared documentation"],
                improvement_suggestions=[
                    "Establish regular sync meetings",
                    "Use shared communication channels",
                ],
                consultation_frequency={
                    "frequency_score": 0.5,
                    "frequency_label": "medium",
                    "consulted_parties": [],
                },
                review_effectiveness={
                    "review_count": 1,
                    "effectiveness_score": 0.5,
                    "outcome": "neutral",
                },
            ),
            CollaborationAnalysisResultModel(
                collaboration_type="Cross-Functional Collaboration",
                participants=["Engineering", "Product"],
                description="Collaboration between different functional teams",
                effectiveness="medium",
                examples=["Requirement discussions", "Design reviews"],
                improvement_suggestions=[
                    "Clarify ownership",
                    "Improve handoff processes",
                ],
                consultation_frequency={
                    "frequency_score": 0.4,
                    "frequency_label": "medium",
                    "consulted_parties": [],
                },
                review_effectiveness={
                    "review_count": 0,
                    "effectiveness_score": 0.5,
                    "outcome": "neutral",
                },
            ),
        ][:limit]
