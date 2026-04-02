"""
Design Quality Analysis Module

Assesses technical design quality from simulation data.
Analyzes modularity, scalability, maintainability, and other quality aspects.
Includes metrics: revision counts, manufacturability score, rework causes.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from ....storage import GraphStorage
from ....utils.llm_client import LLMClient
from ....utils.logger import get_logger
from ..report_models import DesignQualityResult

logger = get_logger("mirofish.design_quality")


class DesignQualityAnalysis:
    """
    Design Quality Analysis

    Assesses technical design quality from graph data.
    Includes revision counts, manufacturability, and rework causes metrics.
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
    ) -> List[DesignQualityResult]:
        """
        Analyze design quality from graph with revision and rework metrics.

        Args:
            graph_id: Graph ID
            query: Optional query to focus analysis
            limit: Maximum aspects to assess

        Returns:
            List of DesignQualityResult with to_dict() and to_text() methods
        """
        logger.info(
            f"DesignQualityAnalysis.analyze: graph_id={graph_id}, limit={limit}"
        )

        try:
            search_results = self.storage.search(
                graph_id=graph_id,
                query=query
                or "design architecture module component interface pattern revision rework structure",
                limit=limit * 3,
                scope="edges",
            )

            assessments: List[DesignQualityResult] = []
            seen_aspects: set = set()

            edge_list = self._get_edges(search_results)

            for edge in edge_list:
                fact = self._get_fact(edge)
                if not fact or len(fact) < 15:
                    continue

                aspect = self._identify_design_aspect(fact)
                if not aspect or aspect in seen_aspects:
                    continue
                seen_aspects.add(aspect)

                rating = self._rate_aspect(fact)
                strengths = self._extract_strengths(fact, aspect)
                weaknesses = self._extract_weaknesses(fact, aspect)
                metrics = self._compute_metrics(fact)

                # Compute design quality metrics
                revision_counts = self._compute_revision_counts(fact)
                manufacturability = self._assess_manufacturability(fact)
                rework_causes = self._identify_rework_causes(fact)

                assessments.append(
                    DesignQualityResult(
                        aspect=aspect,
                        rating=rating,
                        findings=[fact[:150] for fact in [fact] if fact],
                        strengths=strengths,
                        weaknesses=weaknesses,
                        metrics=metrics,
                        revision_counts=revision_counts,
                        manufacturability_score=manufacturability,
                        rework_causes=rework_causes,
                    )
                )

                if len(assessments) >= limit:
                    break

            if not assessments:
                assessments = self._generate_default_assessments(limit)

            logger.info(f"DesignQualityAnalysis: assessed {len(assessments)} aspects")
            return assessments

        except Exception as e:
            logger.error(f"DesignQualityAnalysis.analyze failed: {e}")
            return []

    def summarize_quality(self, assessments: List[DesignQualityResult]) -> str:
        """
        Generate a text summary of design quality assessments.

        Args:
            assessments: List of DesignQualityResult

        Returns:
            Summary string
        """
        if not assessments:
            return "No design quality assessments available."

        lines = [
            f"Design Quality Summary (n={len(assessments)})",
            "",
        ]

        # Group by rating
        by_rating: Dict[str, List[DesignQualityResult]] = {}
        for a in assessments:
            by_rating.setdefault(a.rating, []).append(a)

        for rating in ["excellent", "good", "fair", "poor"]:
            aspects = by_rating.get(rating, [])
            if not aspects:
                continue
            lines.append(f"**{rating.upper()} ({len(aspects)}):**")
            for a in aspects:
                rev_count = (
                    a.revision_counts.get("revision_count", 0)
                    if a.revision_counts
                    else 0
                )
                mfg_score = a.manufacturability_score
                lines.append(
                    f"  - {a.aspect} (Revisions: {rev_count}, Manufacturability: {mfg_score:.2f})"
                )
            lines.append("")

        # Overall metrics
        all_metrics: Dict[str, List[float]] = {}
        for a in assessments:
            for k, v in a.metrics.items():
                all_metrics.setdefault(k, []).append(v)

        if all_metrics:
            lines.append("**Metrics Overview:**")
            for metric, values in all_metrics.items():
                avg = sum(values) / len(values) if values else 0
                lines.append(f"  - {metric}: {avg:.2f} (avg)")

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

    def _identify_design_aspect(self, fact: str) -> Optional[str]:
        """Identify which design aspect this fact relates to."""
        fact_lower = fact.lower()

        aspect_keywords = {
            "Modularity": [
                "modular",
                "module",
                "component",
                "separation",
                "decouple",
                "encapsulat",
            ],
            "API Design": [
                "interface",
                "api",
                "contract",
                "protocol",
                "endpoint",
                "service",
            ],
            "Scalability": [
                "scalable",
                "scale",
                "growth",
                "capacity",
                "expand",
                "load",
            ],
            "Performance": [
                "performance",
                "speed",
                "latency",
                "throughput",
                "optimize",
                "fast",
            ],
            "Maintainability": [
                "maintain",
                "readable",
                "clean",
                "debt",
                "refactor",
                "understand",
            ],
            "Testability": [
                "test",
                "coverage",
                "automated",
                "unit",
                "integration",
                "mock",
            ],
            "Security": [
                "security",
                "secure",
                "access",
                "permission",
                "auth",
                "encrypt",
                "vulnerability",
            ],
            "Reliability": [
                "reliable",
                "stable",
                "stability",
                "robust",
                "fault",
                "tolerance",
                "uptime",
            ],
            "Data Modeling": [
                "data",
                "model",
                "schema",
                "entity",
                "relationship",
                "database",
            ],
            "Error Handling": [
                "error",
                "exception",
                "fail",
                "graceful",
                "recovery",
                "retry",
            ],
        }

        for aspect, keywords in aspect_keywords.items():
            if any(kw in fact_lower for kw in keywords):
                return aspect
        return None

    def _rate_aspect(self, fact: str) -> str:
        """Rate the design aspect quality."""
        positive = [
            "good",
            "well",
            "strong",
            "solid",
            "excellent",
            "effective",
            "clean",
            "clear",
            "robust",
        ]
        negative = [
            "bad",
            "poor",
            "weak",
            "fragile",
            "complex",
            "tight",
            "coupled",
            "brittle",
            "critical",
        ]
        neutral = ["adequate", "acceptable", "mixed", "some", "certain"]

        fact_lower = fact.lower()
        pos_count = sum(1 for w in positive if w in fact_lower)
        neg_count = sum(1 for w in negative if w in fact_lower)
        neu_count = sum(1 for w in neutral if w in fact_lower)

        if pos_count > neg_count and pos_count > neu_count:
            return "good" if pos_count > 1 else "fair"
        elif neg_count > pos_count and neg_count > neu_count:
            return "poor" if neg_count > 1 else "fair"
        elif neu_count > pos_count and neu_count > neg_count:
            return "fair"
        elif pos_count > neg_count:
            return "fair"
        elif neg_count > pos_count:
            return "poor"
        return "fair"

    def _extract_strengths(self, fact: str, aspect: str) -> List[str]:
        """Extract design strengths."""
        strengths = []
        fact_lower = fact.lower()

        # General strengths
        if "modular" in fact_lower or "component" in fact_lower:
            strengths.append("Good separation of concerns")
        if "interface" in fact_lower or "api" in fact_lower:
            strengths.append("Clear contract definitions")
        if "test" in fact_lower or "automated" in fact_lower:
            strengths.append("Automated testing in place")
        if "scalable" in fact_lower or "scale" in fact_lower:
            strengths.append("Designed for scalability")
        if "clean" in fact_lower or "clear" in fact_lower:
            strengths.append("Clean and clear implementation")
        if "robust" in fact_lower or "solid" in fact_lower:
            strengths.append("Robust error handling")
        if "secure" in fact_lower or "auth" in fact_lower:
            strengths.append("Security considerations in place")
        if "document" in fact_lower:
            strengths.append("Well documented")

        return strengths[:3]

    def _extract_weaknesses(self, fact: str, aspect: str) -> List[str]:
        """Extract design weaknesses."""
        weaknesses = []
        fact_lower = fact.lower()

        # General weaknesses
        if "tight" in fact_lower and "coupl" in fact_lower:
            weaknesses.append("Tight coupling detected")
        if "complex" in fact_lower:
            weaknesses.append("Excessive complexity")
        if "monolith" in fact_lower:
            weaknesses.append("Monolithic structure")
        if "single" in fact_lower and "point" in fact_lower:
            weaknesses.append("Single point of failure")
        if "brittle" in fact_lower:
            weaknesses.append("Brittle implementation")
        if "duplic" in fact_lower:
            weaknesses.append("Code duplication present")
        if "spaghetti" in fact_lower:
            weaknesses.append("Spaghetti code structure")
        if "tech debt" in fact_lower or "technical debt" in fact_lower:
            weaknesses.append("Technical debt accumulated")
        if "no test" in fact_lower or "not test" in fact_lower:
            weaknesses.append("Lack of testing")

        return weaknesses[:3]

    def _compute_metrics(self, fact: str) -> Dict[str, float]:
        """Compute simple quality metrics."""
        metrics: Dict[str, float] = {}
        fact_lower = fact.lower()

        # Complexity indicator (normalized word count)
        words = len(fact.split())
        metrics["complexity_score"] = min(words / 50.0, 1.0)

        # Quality indicator
        quality_words = sum(
            1
            for w in ["good", "well", "strong", "solid", "clean", "clear", "robust"]
            if w in fact_lower
        )
        metrics["quality_score"] = min(quality_words / 4.0, 1.0)

        # Design indicator
        design_words = sum(
            1
            for w in ["design", "pattern", "architecture", "structure", "modular"]
            if w in fact_lower
        )
        metrics["design_score"] = min(design_words / 3.0, 1.0)

        return metrics

    def _compute_revision_counts(self, fact: str) -> Dict[str, Any]:
        """Compute revision count metrics from design fact."""
        text_lower = fact.lower()
        revision_indicators = [
            "revision",
            "revise",
            "iterate",
            "iteration",
            "version",
            "update",
            "modify",
            "change",
            "revised",
        ]
        mentions = sum(1 for k in revision_indicators if k in text_lower)

        return {
            "revision_count": mentions,
            "iteration_depth": min(mentions, 5),
            "stability_score": max(1.0 - mentions * 0.15, 0.1),
        }

    def _assess_manufacturability(self, fact: str) -> float:
        """Assess manufacturability/producibility score."""
        text_lower = fact.lower()
        positive = [
            "manufactur",
            "producible",
            "buildable",
            "implementable",
            "feasible",
            "practical",
            "simple",
            "straightforward",
        ]
        negative = [
            "complex",
            "difficult",
            "challenging",
            "intricate",
            "delicate",
            "complicated",
            "elaborate",
        ]

        pos_count = sum(1 for w in positive if w in text_lower)
        neg_count = sum(1 for w in negative if w in text_lower)

        if pos_count > neg_count:
            return min(0.5 + pos_count * 0.15, 0.95)
        elif neg_count > pos_count:
            return max(0.5 - neg_count * 0.15, 0.15)
        return 0.65

    def _identify_rework_causes(self, fact: str) -> List[str]:
        """Identify causes of rework from design fact."""
        causes = []
        text_lower = fact.lower()

        cause_map = {
            "requirement_changes": ["requirement", "spec", "change", "specification"],
            "design_errors": ["error", "mistake", "incorrect", "wrong", "faulty"],
            "scope_creep": ["scope", "creep", "expand", "add", "additional"],
            "quality_issues": ["quality", "defect", "bug", "issue", "problem"],
            "integration_problems": [
                "integration",
                "interface",
                "compatibility",
                "interoperability",
            ],
            "performance_issues": ["performance", "slow", "optimize", "bottleneck"],
        }

        for cause, keywords in cause_map.items():
            if any(k in text_lower for k in keywords):
                causes.append(cause)

        return causes[:3]

    def _generate_default_assessments(self, limit: int) -> List[DesignQualityResult]:
        """Generate default assessments when data is insufficient."""
        logger.info(
            "No explicit design quality data found, generating analysis-based assessments"
        )
        return [
            DesignQualityResult(
                aspect="Architecture Design",
                rating="fair",
                findings=["Design assessment pending detailed analysis"],
                strengths=["Awaiting graph data for detailed assessment"],
                weaknesses=["Insufficient data for detailed evaluation"],
                metrics={"confidence": 0.3},
                revision_counts={
                    "revision_count": 0,
                    "iteration_depth": 0,
                    "stability_score": 0.5,
                },
                manufacturability_score=0.65,
                rework_causes=[],
            ),
            DesignQualityResult(
                aspect="Code Organization",
                rating="fair",
                findings=["Code organization review needed"],
                strengths=["Basic structure present"],
                weaknesses=["Further analysis required"],
                metrics={"confidence": 0.3},
                revision_counts={
                    "revision_count": 0,
                    "iteration_depth": 0,
                    "stability_score": 0.5,
                },
                manufacturability_score=0.65,
                rework_causes=[],
            ),
        ][:limit]
