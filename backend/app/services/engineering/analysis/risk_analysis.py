"""
Risk Analysis Module

Identifies and assesses project risks from simulation data.
Analyzes likelihood, impact, and mitigation strategies.
Includes metrics: schedule confidence, budget at risk, resource contention.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from ....storage import GraphStorage
from ....utils.llm_client import LLMClient
from ....utils.logger import get_logger
from ..report_models import RiskPrediction

logger = get_logger("mirofish.risk_analysis")


class RiskAnalysis:
    """
    Risk Analysis

    Identifies and assesses project risks from graph data.
    Includes schedule confidence, budget at risk, and resource contention metrics.
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
    ) -> List[RiskPrediction]:
        """
        Analyze risks from graph with exposure and contention metrics.

        Args:
            graph_id: Graph ID
            query: Optional query to focus analysis
            limit: Maximum risks to identify

        Returns:
            List of RiskPrediction with to_dict() and to_text() methods
        """
        logger.info(f"RiskAnalysis.analyze: graph_id={graph_id}, limit={limit}")

        try:
            search_results = self.storage.search(
                graph_id=graph_id,
                query=query
                or "risk concern issue vulnerability threat uncertainty problem challenge budget resource schedule",
                limit=limit * 3,
                scope="edges",
            )

            risks: List[RiskPrediction] = []
            seen_risks: set = set()

            edge_list = self._get_edges(search_results)

            for edge in edge_list:
                fact = self._get_fact(edge)
                if not fact or len(fact) < 15:
                    continue

                if self._indicates_risk(fact):
                    risk_name = self._name_risk(fact)
                    if risk_name in seen_risks:
                        continue
                    seen_risks.add(risk_name)

                    likelihood = self._assess_likelihood(fact)
                    impact = self._assess_impact(fact)
                    indicators = [fact] if fact else []
                    stakeholders = self._extract_stakeholders(edge)

                    # Compute risk exposure metrics
                    schedule_confidence = self._compute_schedule_confidence(fact)
                    budget_at_risk = self._compute_budget_at_risk(fact)
                    resource_contention = self._compute_resource_contention(fact)

                    risks.append(
                        RiskPrediction(
                            risk_name=risk_name,
                            description=self._describe(fact),
                            likelihood=likelihood,
                            impact=impact,
                            indicators=indicators,
                            mitigation_strategies=self._suggest_mitigations(risk_name),
                            affected_stakeholders=stakeholders,
                            schedule_confidence=schedule_confidence,
                            budget_at_risk=budget_at_risk,
                            resource_contention=resource_contention,
                        )
                    )

                    if len(risks) >= limit:
                        break

            if not risks:
                risks = self._generate_default_risks(limit)

            logger.info(f"RiskAnalysis: identified {len(risks)} risks")
            return risks

        except Exception as e:
            logger.error(f"RiskAnalysis.analyze failed: {e}")
            return []

    def summarize_risks(self, risks: List[RiskPrediction]) -> str:
        """
        Generate a text summary of risks.

        Args:
            risks: List of RiskPrediction

        Returns:
            Summary string
        """
        if not risks:
            return "No risks identified."

        lines = [
            f"Risk Analysis Summary (n={len(risks)})",
            "",
        ]

        # Sort by risk level (critical first)
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_risks = sorted(risks, key=lambda r: severity_order.get(r.risk_level, 4))

        lines.append("**Risks by Severity:**")
        for r in sorted_risks:
            stakeholders = (
                ", ".join(r.affected_stakeholders[:2])
                if r.affected_stakeholders
                else "Unknown"
            )
            sched = (
                r.schedule_confidence.get("confidence_label", "unknown")
                if r.schedule_confidence
                else "unknown"
            )
            lines.append(
                f"  - {r.risk_name} [{r.risk_level.upper()}]: {stakeholders} (Schedule: {sched})"
            )

        # Count by level
        by_level: Dict[str, int] = {}
        for r in risks:
            by_level[r.risk_level] = by_level.get(r.risk_level, 0) + 1

        lines.append("")
        lines.append("**Risk Distribution:**")
        for level in ["critical", "high", "medium", "low"]:
            count = by_level.get(level, 0)
            if count > 0:
                lines.append(f"  - {level.upper()}: {count}")

        # Budget at risk summary
        total_budget_at_risk = sum(
            r.budget_at_risk.get("exposure_percentage", 0)
            for r in risks
            if r.budget_at_risk and r.budget_at_risk.get("has_budget_risk")
        )
        if total_budget_at_risk > 0:
            lines.append("")
            lines.append(
                f"**Total Budget at Risk**: ~{int(total_budget_at_risk * 100)}%"
            )

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

    def _indicates_risk(self, text: str) -> bool:
        risk_keywords = [
            "risk",
            "concern",
            "vulnerability",
            "threat",
            "uncertainty",
            "fail",
            "loss",
            "impact",
            "issue",
            "problem",
            "unforeseen",
            "overdue",
            "budget",
            "resource",
            "dependency",
            "blocker",
            "challenge",
            "threaten",
            "critical",
            "danger",
            "peril",
        ]
        text_lower = text.lower()
        return any(kw in text_lower for kw in risk_keywords)

    def _name_risk(self, fact: str) -> str:
        """Generate a name for a risk from its description."""
        # Try to extract meaningful words
        words = re.findall(r"\b[A-Z][a-z]+\b", fact)
        if len(words) >= 2:
            return f"{words[0]} {words[1]} Risk"
        elif words:
            return f"{words[0]} Risk"

        # Fallback: extract key noun phrases
        words = re.findall(r"\b[a-z]{4,}\b", fact.lower())
        stopwords = {
            "this",
            "that",
            "with",
            "from",
            "have",
            "been",
            "were",
            "they",
            "their",
            "would",
            "could",
            "should",
            "there",
            "which",
            "what",
            "when",
            "where",
            "been",
            "have",
            "risk",
            "concern",
            "issue",
            "problem",
            "there",
            "here",
        }
        key_words = [w for w in words if w not in stopwords]
        if len(key_words) >= 2:
            return f"{key_words[0].title()} {key_words[1].title()} Risk"
        elif key_words:
            return f"{key_words[0].title()} Risk"
        return "Project Risk"

    def _assess_likelihood(self, fact: str) -> str:
        """Assess likelihood of risk occurring."""
        fact_lower = fact.lower()

        high_likelihood = [
            "likely",
            "probable",
            "certain",
            "known",
            "frequent",
            "consistent",
            "regular",
            "common",
            "always",
            "certainly",
        ]
        low_likelihood = [
            "unlikely",
            "rare",
            "infrequent",
            "occasional",
            "seldom",
            "sometimes",
            "possibly",
            "perhaps",
            "maybe",
            "uncertain",
        ]

        high_count = sum(1 for k in high_likelihood if k in fact_lower)
        low_count = sum(1 for k in low_likelihood if k in fact_lower)

        if high_count > low_count:
            return "high"
        elif low_count > high_count:
            return "low"
        return "medium"

    def _assess_impact(self, fact: str) -> str:
        """Assess impact of risk."""
        fact_lower = fact.lower()

        high_impact = [
            "critical",
            "severe",
            "major",
            "fatal",
            "catastrophic",
            "significant",
            "enormous",
            "huge",
            "substantial",
            "considerable",
        ]
        low_impact = [
            "minor",
            "small",
            "negligible",
            "minimal",
            "limited",
            "slight",
            "low",
            "minimal",
            "negligible",
            "insignificant",
        ]

        high_count = sum(1 for k in high_impact if k in fact_lower)
        low_count = sum(1 for k in low_impact if k in fact_lower)

        if high_count > low_count:
            return "high"
        elif low_count > high_count:
            return "low"
        return "medium"

    def _extract_stakeholders(self, edge: Dict[str, Any]) -> List[str]:
        """Extract affected stakeholders from edge data."""
        stakeholders = []
        if isinstance(edge, dict):
            source = edge.get("source_node_name", "")
            target = edge.get("target_node_name", "")
            if source:
                stakeholders.append(source)
            if target:
                stakeholders.append(target)
        return list(dict.fromkeys(stakeholders))[:4]

    def _describe(self, fact: str) -> str:
        if len(fact) > 250:
            return fact[:247] + "..."
        return fact

    def _suggest_mitigations(self, risk_name: str) -> List[str]:
        """Suggest mitigation strategies for a risk."""
        name_lower = risk_name.lower()

        if "resource" in name_lower or "budget" in name_lower:
            return [
                "Review resource allocation",
                "Prioritize critical tasks",
                "Identify alternative resources",
                "Negotiate additional budget",
            ]
        elif "technical" in name_lower or "technology" in name_lower:
            return [
                "Technical review and spikes",
                "Proof of concept implementation",
                "Expert consultation",
                "Alternative technology evaluation",
            ]
        elif (
            "schedule" in name_lower
            or "timeline" in name_lower
            or "delay" in name_lower
        ):
            return [
                "Re-evaluate timeline",
                "Add buffer time",
                "Parallel task execution",
                "Critical path analysis",
            ]
        elif "quality" in name_lower:
            return [
                "Code reviews",
                "Testing enhancements",
                "Quality gates",
                "Defect prevention",
            ]
        elif "security" in name_lower or "vulnerability" in name_lower:
            return [
                "Security audit",
                "Vulnerability assessment",
                "Penetration testing",
                "Security training",
            ]
        elif "team" in name_lower or "personnel" in name_lower:
            return [
                "Cross-training",
                "Knowledge sharing",
                "Succession planning",
                "Team building",
            ]
        elif "integration" in name_lower or "dependency" in name_lower:
            return [
                "Early integration testing",
                "Contract testing",
                "Dependency mapping",
                "Fallback planning",
            ]
        return [
            "Monitor risk indicators",
            "Develop contingency plan",
            "Regular risk reassessment",
            "Stakeholder communication",
        ]

    def _compute_schedule_confidence(self, fact: str) -> Dict[str, Any]:
        """Compute schedule confidence metric."""
        text_lower = fact.lower()
        schedule_risks = [
            "delay",
            "overdue",
            "behind",
            "late",
            "slip",
            "miss",
            "extend",
            "overrun",
        ]
        schedule_positive = [
            "on-track",
            "ahead",
            "early",
            "准时",
            "按时",
            "on schedule",
            "on time",
        ]

        risk_count = sum(1 for k in schedule_risks if k in text_lower)
        positive_count = sum(1 for k in schedule_positive if k in text_lower)

        if positive_count > risk_count:
            confidence = min(0.95, 0.8 + positive_count * 0.05)
        elif risk_count > 0:
            confidence = max(0.2, 0.7 - risk_count * 0.15)
        else:
            confidence = 0.65

        return {
            "confidence_score": confidence,
            "confidence_label": "high"
            if confidence > 0.75
            else "medium"
            if confidence > 0.45
            else "low",
            "schedule_risk_factors": risk_count,
        }

    def _compute_budget_at_risk(self, fact: str) -> Dict[str, Any]:
        """Compute budget at risk metric."""
        text_lower = fact.lower()
        budget_risks = [
            "budget",
            "cost",
            "expensive",
            "overspend",
            "underestimate",
            "expensive",
            "costly",
            "fund",
        ]

        risk_mentions = sum(1 for k in budget_risks if k in text_lower)

        if risk_mentions >= 2:
            exposure_pct = min(0.8, 0.3 + risk_mentions * 0.1)
            amount_at_risk = f"{int(exposure_pct * 100)}% of budget"
        elif risk_mentions == 1:
            exposure_pct = 0.25
            amount_at_risk = "~25% of budget"
        else:
            exposure_pct = 0.0
            amount_at_risk = "Minimal"

        return {
            "has_budget_risk": risk_mentions > 0,
            "exposure_percentage": exposure_pct,
            "amount_at_risk": amount_at_risk,
            "risk_level": "high"
            if exposure_pct > 0.5
            else "medium"
            if exposure_pct > 0.2
            else "low",
        }

    def _compute_resource_contention(self, fact: str) -> Dict[str, Any]:
        """Compute resource contention metric."""
        text_lower = fact.lower()
        contention_keywords = [
            "resource",
            "compete",
            "contention",
            "shared",
            "limited",
            "bottleneck",
            "constraint",
            "capacity",
        ]

        mentions = sum(1 for k in contention_keywords if k in text_lower)

        return {
            "has_contention": mentions > 0,
            "contention_score": min(mentions / 3.0, 1.0),
            "severity": "high"
            if mentions >= 3
            else "medium"
            if mentions >= 1
            else "low",
            "affected_resources": [],
        }

    def _generate_default_risks(self, limit: int) -> List[RiskPrediction]:
        """Generate default risks when data is insufficient."""
        logger.info("No explicit risks found, generating analysis-based assessments")
        return [
            RiskPrediction(
                risk_name="Schedule Risk",
                description="Potential timeline deviations due to dependencies and unknowns",
                likelihood="medium",
                impact="medium",
                indicators=[
                    "Multiple dependencies identified",
                    "Complex integration points",
                ],
                mitigation_strategies=[
                    "Regular progress tracking",
                    "Buffer time allocation",
                    "Parallel workstreams",
                ],
                affected_stakeholders=["Project Team", "Management"],
                schedule_confidence={
                    "confidence_score": 0.6,
                    "confidence_label": "medium",
                    "schedule_risk_factors": 1,
                },
                budget_at_risk={
                    "has_budget_risk": False,
                    "exposure_percentage": 0.0,
                    "amount_at_risk": "Minimal",
                    "risk_level": "low",
                },
                resource_contention={
                    "has_contention": False,
                    "contention_score": 0.2,
                    "severity": "low",
                    "affected_resources": [],
                },
            ),
            RiskPrediction(
                risk_name="Technical Risk",
                description="Technology or architecture challenges may impact delivery",
                likelihood="medium",
                impact="high",
                indicators=["Complex technical requirements", "Unproven technologies"],
                mitigation_strategies=[
                    "Technical spikes",
                    "Expert review",
                    "Prototype validation",
                ],
                affected_stakeholders=["Engineering Team"],
                schedule_confidence={
                    "confidence_score": 0.5,
                    "confidence_label": "medium",
                    "schedule_risk_factors": 2,
                },
                budget_at_risk={
                    "has_budget_risk": True,
                    "exposure_percentage": 0.3,
                    "amount_at_risk": "~30% of budget",
                    "risk_level": "medium",
                },
                resource_contention={
                    "has_contention": True,
                    "contention_score": 0.5,
                    "severity": "medium",
                    "affected_resources": [],
                },
            ),
            RiskPrediction(
                risk_name="Resource Risk",
                description="Insufficient resources or competing priorities may affect delivery",
                likelihood="medium",
                impact="medium",
                indicators=["Limited team capacity", "Multiple competing initiatives"],
                mitigation_strategies=[
                    "Resource leveling",
                    "Priority alignment",
                    "Stakeholder negotiation",
                ],
                affected_stakeholders=["Project Team", "Management", "Stakeholders"],
                schedule_confidence={
                    "confidence_score": 0.55,
                    "confidence_label": "medium",
                    "schedule_risk_factors": 1,
                },
                budget_at_risk={
                    "has_budget_risk": True,
                    "exposure_percentage": 0.2,
                    "amount_at_risk": "~20% of budget",
                    "risk_level": "medium",
                },
                resource_contention={
                    "has_contention": True,
                    "contention_score": 0.7,
                    "severity": "high",
                    "affected_resources": [],
                },
            ),
        ][:limit]
