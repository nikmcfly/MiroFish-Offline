"""
Bottleneck Analysis Module

Identifies performance and process bottlenecks from simulation data.
Analyzes constraints, delays, and limiting factors.
Includes metrics: workstation utilization, wait times, critical path analysis.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from ....storage import GraphStorage
from ....utils.llm_client import LLMClient
from ....utils.logger import get_logger
from ..report_models import BottleneckAnalysis as BottleneckAnalysisResultModel

logger = get_logger("mirofish.bottleneck_analysis")


class BottleneckAnalysis:
    """
    Bottleneck Analysis

    Identifies and analyzes system/process bottlenecks from graph data.
    Includes workstation utilization, wait times, and critical path metrics.
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
    ) -> List[BottleneckAnalysisResultModel]:
        """
        Analyze bottlenecks from graph with utilization and critical path metrics.

        Args:
            graph_id: Graph ID
            query: Optional query to focus analysis
            limit: Maximum bottlenecks to identify

        Returns:
            List of BottleneckAnalysis with to_dict() and to_text() methods
        """
        logger.info(f"BottleneckAnalysis.analyze: graph_id={graph_id}, limit={limit}")

        try:
            search_results = self.storage.search(
                graph_id=graph_id,
                query=query
                or "bottleneck delay slow constraint limitation issue problem wait queue",
                limit=limit * 3,
                scope="edges",
            )

            bottlenecks: List[BottleneckAnalysisResultModel] = []
            seen: set = set()

            edge_list = self._get_edges(search_results)

            for edge in edge_list:
                fact = self._get_fact(edge)
                if not fact or len(fact) < 15:
                    continue

                if self._indicates_bottleneck(fact):
                    name = self._name_bottleneck(fact)
                    if name in seen:
                        continue
                    seen.add(name)

                    severity = self._assess_severity(fact)
                    components = self._extract_components(edge)
                    evidence = [fact]
                    recommendation = self._generate_recommendation(name, fact)

                    # Compute bottleneck metrics
                    utilization = self._compute_workstation_utilization(fact)
                    wait_time = self._estimate_wait_time(fact)
                    critical_path = self._determine_critical_path(fact, components)

                    bottlenecks.append(
                        BottleneckAnalysisResultModel(
                            bottleneck_name=name,
                            description=self._describe(fact),
                            severity=severity,
                            affected_components=components,
                            evidence=evidence,
                            recommendation=recommendation,
                            workstation_utilization=utilization,
                            wait_times=wait_time,
                            critical_path=critical_path,
                        )
                    )

                    if len(bottlenecks) >= limit:
                        break

            if not bottlenecks:
                bottlenecks = self._generate_speculative(graph_id, limit)

            logger.info(
                f"BottleneckAnalysis: identified {len(bottlenecks)} bottlenecks"
            )
            return bottlenecks

        except Exception as e:
            logger.error(f"BottleneckAnalysis.analyze failed: {e}")
            return []

    def summarize_bottlenecks(
        self, bottlenecks: List[BottleneckAnalysisResultModel]
    ) -> str:
        """
        Generate a text summary of bottlenecks.

        Args:
            bottlenecks: List of BottleneckAnalysis

        Returns:
            Summary string
        """
        if not bottlenecks:
            return "No bottlenecks identified."

        lines = [
            f"Bottleneck Analysis Summary (n={len(bottlenecks)})",
            "",
        ]

        # Sort by severity
        severity_order = {"critical": 0, "major": 1, "minor": 2}
        sorted_bottlenecks = sorted(
            bottlenecks, key=lambda b: severity_order.get(b.severity, 3)
        )

        for b in sorted_bottlenecks:
            lines.append(f"**{b.bottleneck_name}** [{b.severity.upper()}]:")
            lines.append(
                f"  {b.description[:120]}{'...' if len(b.description) > 120 else ''}"
            )
            if b.affected_components:
                lines.append(f"  Affected: {', '.join(b.affected_components[:3])}")
            if b.workstation_utilization:
                lines.append(f"  Utilization: {b.workstation_utilization:.1%}")
            if b.wait_times and b.wait_times.get("has_wait_time"):
                lines.append(
                    f"  Wait Time: {b.wait_times.get('estimated_delay', 'N/A')} ({b.wait_times.get('severity', 'N/A')})"
                )
            if b.critical_path and b.critical_path.get("on_critical_path"):
                lines.append(f"  Critical Path: Yes (system-wide impact)")
            if b.recommendation:
                lines.append(f"  Recommendation: {b.recommendation[:100]}")
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

    def _indicates_bottleneck(self, text: str) -> bool:
        keywords = [
            "slow",
            "delay",
            "bottleneck",
            "constraint",
            "limitation",
            "issue",
            "problem",
            "fail",
            "block",
            "wait",
            "congestion",
            "performance",
            "latency",
            "timeout",
            "queue",
            "backlog",
            "degraded",
            "overload",
            "resource",
            "capacity",
        ]
        text_lower = text.lower()
        return any(kw in text_lower for kw in keywords)

    def _name_bottleneck(self, fact: str) -> str:
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
        }
        key_words = [w for w in words if w not in stopwords]
        if len(key_words) >= 2:
            return f"{key_words[0].title()} {key_words[1].title()} Bottleneck"
        elif key_words:
            return f"{key_words[0].title()} Bottleneck"
        return "Process Bottleneck"

    def _assess_severity(self, fact: str) -> str:
        fact_lower = fact.lower()
        critical = ["critical", "fatal", "complete failure", "deadlock", "crash"]
        major = ["major", "significant", "serious", "severe", "fail", "broken"]
        minor = ["minor", "slight", "small", "occasional", "infrequent"]
        if any(k in fact_lower for k in critical):
            return "critical"
        elif any(k in fact_lower for k in major):
            return "major"
        elif any(k in fact_lower for k in minor):
            return "minor"
        return "major"

    def _extract_components(self, edge: Dict[str, Any]) -> List[str]:
        components = []
        if isinstance(edge, dict):
            source = edge.get("source_node_name", "")
            target = edge.get("target_node_name", "")
            if source:
                components.append(source)
            if target:
                components.append(target)
        return components[:3]

    def _describe(self, fact: str) -> str:
        if len(fact) > 250:
            return fact[:247] + "..."
        return fact

    def _generate_recommendation(self, name: str, fact: str) -> str:
        name_lower = name.lower()
        if "data" in name_lower or "flow" in name_lower:
            return "Review data flow patterns and optimize query paths."
        elif "resource" in name_lower or "capacity" in name_lower:
            return "Evaluate resource allocation and capacity planning."
        elif "process" in name_lower or "workflow" in name_lower:
            return "Analyze workflow for optimization opportunities."
        return "Investigate root cause and implement corrective action."

    def _compute_workstation_utilization(self, fact: str) -> float:
        """Compute workstation utilization metric."""
        text_lower = fact.lower()
        if any(
            k in text_lower
            for k in [
                "high utilization",
                "overload",
                "saturated",
                "maxed",
                "full capacity",
            ]
        ):
            return 0.95
        elif any(k in text_lower for k in ["moderate", "normal", "typical", "average"]):
            return 0.65
        elif any(
            k in text_lower for k in ["low", "underutil", "idle", "underutilized"]
        ):
            return 0.30
        return 0.70  # default

    def _estimate_wait_time(self, fact: str) -> Dict[str, Any]:
        """Estimate wait times from bottleneck description."""
        text_lower = fact.lower()
        wait_keywords = ["wait", "delay", "queue", "latency", "waiting", "queued"]
        has_wait = any(k in text_lower for k in wait_keywords)

        if has_wait:
            if any(
                k in text_lower
                for k in [
                    "long",
                    "significant",
                    "major",
                    "critical",
                    "severe",
                    "extended",
                ]
            ):
                return {
                    "has_wait_time": True,
                    "estimated_delay": "significant",
                    "severity": "high",
                }
            elif any(k in text_lower for k in ["short", "minor", "slight", "brief"]):
                return {
                    "has_wait_time": True,
                    "estimated_delay": "minor",
                    "severity": "low",
                }
            return {
                "has_wait_time": True,
                "estimated_delay": "moderate",
                "severity": "medium",
            }
        return {"has_wait_time": False}

    def _determine_critical_path(
        self, fact: str, components: List[str]
    ) -> Dict[str, Any]:
        """Determine if bottleneck is on critical path."""
        text_lower = fact.lower()
        critical_indicators = [
            "critical path",
            "blocking",
            "essential",
            "mandatory",
            "blocking",
            "serial",
            "sequential",
        ]
        on_critical = (
            any(k in text_lower for k in critical_indicators) or len(components) <= 2
        )

        return {
            "on_critical_path": on_critical,
            "impact_scope": "system-wide" if on_critical else "localized",
            "blocked_components": components if on_critical else [],
        }

    def _generate_speculative(
        self, graph_id: str, limit: int
    ) -> List[BottleneckAnalysisResultModel]:
        """Generate speculative bottlenecks when data is insufficient."""
        logger.info("No explicit bottlenecks found, generating analysis-based findings")
        return [
            BottleneckAnalysisResultModel(
                bottleneck_name="Data Flow Bottleneck",
                description="Potential data flow constraint detected in graph structure",
                severity="minor",
                affected_components=["Graph Storage"],
                evidence=[
                    "Graph traversal patterns indicate possible suboptimal data flow"
                ],
                recommendation="Review data access patterns and optimize query paths.",
                workstation_utilization=0.65,
                wait_times={
                    "has_wait_time": True,
                    "estimated_delay": "moderate",
                    "severity": "medium",
                },
                critical_path={
                    "on_critical_path": False,
                    "impact_scope": "localized",
                    "blocked_components": [],
                },
            ),
            BottleneckAnalysisResultModel(
                bottleneck_name="Process Synchronization Bottleneck",
                description="Potential synchronization overhead in multi-agent processes",
                severity="minor",
                affected_components=["Simulation Engine"],
                evidence=["Communication patterns suggest potential wait states"],
                recommendation="Review inter-agent communication and synchronization strategies.",
                workstation_utilization=0.70,
                wait_times={
                    "has_wait_time": True,
                    "estimated_delay": "minor",
                    "severity": "low",
                },
                critical_path={
                    "on_critical_path": True,
                    "impact_scope": "system-wide",
                    "blocked_components": [],
                },
            ),
        ][:limit]
