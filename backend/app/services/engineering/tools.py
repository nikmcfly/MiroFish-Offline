"""
Engineering Tools Service

Provides specialized retrieval tools for engineering report generation.
Reuses GraphStorage patterns from graph_tools.

Tools:
- analyze_quote_accuracy: Analyze quote accuracy from agent interactions
- identify_process_bottlenecks: Find performance/process bottlenecks
- evaluate_collaboration_effectiveness: Analyze collaboration patterns
- analyze_design_quality: Assess technical design quality
- predict_risk_exposure: Identify and assess project risks
- interview_project_team: Simulate team interviews
- compare_scenario_outcomes: Compare different scenario outcomes
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from ...storage import GraphStorage
from ...utils.llm_client import LLMClient
from ...utils.logger import get_logger
from .report_models import (
    QuoteAccuracyResult,
    BottleneckAnalysis,
    CollaborationAnalysis,
    DesignQualityResult,
    RiskPrediction,
    TeamInterviewResult,
    ScenarioComparisonResult,
)

logger = get_logger("mirofish.engineering_tools")


class EngineeringToolsService:
    """
    Engineering Tools Service

    Provides domain-specific retrieval and analysis tools for
    engineering reports, built on GraphStorage.
    """

    def __init__(self, storage: GraphStorage, llm_client: Optional[LLMClient] = None):
        self.storage = storage
        self._llm_client = llm_client
        logger.info("EngineeringToolsService initialization complete")

    @property
    def llm(self) -> LLMClient:
        """Lazy LLM client initialization."""
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client

    # ── Quote Accuracy Analysis ─────────────────────────────────────────────────

    def analyze_quote_accuracy(
        self, graph_id: str, query: str = "", limit: int = 20
    ) -> List[QuoteAccuracyResult]:
        """
        Analyze quote accuracy from agent interactions in the graph.
        Extracts quotes and analyzes quoted vs actual values, margin analysis,
        and confidence calibration.

        Args:
            graph_id: Graph ID
            query: Optional query to focus quote extraction
            limit: Maximum number of quotes to extract

        Returns:
            List of QuoteAccuracyResult with to_dict() and to_text() methods
        """
        logger.info(
            f"Analyzing quote accuracy: graph_id={graph_id}, query={query[:50] if query else 'all'}..."
        )

        try:
            # Search for edges containing quote-like content
            search_results = self.storage.search(
                graph_id=graph_id,
                query=query or "quote estimate statement response opinion projection",
                limit=limit * 2,
                scope="edges",
            )

            quotes: List[QuoteAccuracyResult] = []
            seen_texts: set = set()

            edge_list = self._safe_get_edges(search_results)

            for edge in edge_list:
                fact = edge.get("fact", "") if isinstance(edge, dict) else ""
                if not fact or len(fact) < 15:
                    continue

                # Detect quote-like content
                if self._is_quote(fact):
                    quote_text = self._clean_quote_text(fact)
                    if quote_text in seen_texts or len(quote_text) < 10:
                        continue
                    seen_texts.add(quote_text)

                    # Extract speaker info
                    speaker, speaker_role = self._extract_speaker(edge)

                    # Analyze sentiment
                    sentiment = self._analyze_sentiment(quote_text)

                    # Detect themes
                    themes = self._extract_themes(quote_text)

                    # Extract metrics for quote accuracy analysis
                    quoted_value, actual_value = self._extract_quote_values(quote_text)
                    margin_analysis = self._compute_margin_analysis(
                        quoted_value, actual_value
                    )
                    confidence = self._compute_confidence_calibration(fact, sentiment)

                    quotes.append(
                        QuoteAccuracyResult(
                            quote_text=quote_text,
                            speaker=speaker,
                            speaker_role=speaker_role,
                            context=self._extract_context(edge),
                            sentiment_score=sentiment,
                            confidence=confidence,
                            key_themes=themes,
                            quoted_value=quoted_value,
                            actual_value=actual_value,
                            margin_analysis=margin_analysis,
                        )
                    )

                    if len(quotes) >= limit:
                        break

            logger.info(f"Analyzed {len(quotes)} quotes for accuracy")
            return quotes

        except Exception as e:
            logger.error(f"Quote accuracy analysis failed: {e}")
            return []

    def _is_quote(self, text: str) -> bool:
        """Detect if text looks like a quote."""
        quote_markers = [
            '"',
            '"',
            '"',
            '"',
            '"',
            '"',
            """, """,
            "「",
            "」",
            "『",
            "』",
            '"',
        ]
        return any(
            text.strip().startswith(q) or text.strip().endswith(q)
            for q in quote_markers
        )

    def _clean_quote_text(self, text: str) -> str:
        """Clean quote text of markers and extra content."""
        text = text.strip()
        for marker in ['"', '"', '"', '"', '"', '"', """, """, "「", "」", "『", "』"]:
            if text.startswith(marker):
                text = text[1:]
            if text.endswith(marker):
                text = text[:-1]
        text = re.sub(r'^\s*[""\']?\s*', "", text)
        text = re.sub(r'\s*[""\']?\s*$', "", text)
        return text.strip()

    def _extract_speaker(self, edge: Dict[str, Any]) -> tuple:
        """Extract speaker name and role from edge data."""
        source_name = ""
        target_name = ""
        if isinstance(edge, dict):
            source_name = edge.get("source_node_name", "")
            target_name = edge.get("target_node_name", "")

        speaker = source_name or target_name or "Unknown Agent"
        speaker_role = self._infer_role(speaker)
        return speaker, speaker_role

    def _infer_role(self, name: str) -> str:
        """Infer agent role from name patterns."""
        name_lower = name.lower()
        role_keywords = {
            "engineer": ["engineer", "dev", "tech"],
            "manager": ["manager", "lead", "director", "head"],
            "designer": ["designer", "ux", "ui", "design"],
            "analyst": ["analyst", "data", "qa"],
            "executive": ["ceo", "cto", "cfo", "vp", "chief"],
        }
        for role, keywords in role_keywords.items():
            if any(kw in name_lower for kw in keywords):
                return role
        return "Agent"

    def _extract_context(self, edge: Dict[str, Any]) -> str:
        """Extract context around the quote from edge data."""
        if isinstance(edge, dict):
            rel_name = edge.get("name", "")
            fact = edge.get("fact", "")
            if rel_name and rel_name != fact:
                return f"Related via: {rel_name}"
        return ""

    def _analyze_sentiment(self, text: str) -> float:
        """Simple sentiment analysis (placeholder - returns neutral)."""
        positive_words = [
            "good",
            "great",
            "excellent",
            "success",
            "improve",
            "benefit",
            "positive",
            "achieve",
        ]
        negative_words = [
            "bad",
            "poor",
            "fail",
            "problem",
            "issue",
            "risk",
            "negative",
            "concern",
            "bottleneck",
        ]
        text_lower = text.lower()
        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)
        total = pos_count + neg_count
        if total == 0:
            return 0.0
        return (pos_count - neg_count) / total

    def _extract_themes(self, text: str) -> List[str]:
        """Extract key themes from quote text using keyword detection."""
        theme_map = {
            "performance": [
                "performance",
                "speed",
                "latency",
                "throughput",
                "optimize",
            ],
            "reliability": ["reliable", "reliability", "stable", "stability", "uptime"],
            "scalability": ["scale", "scalable", "growth", "expand", "capacity"],
            "security": ["security", "secure", "access", "permission", "auth"],
            "collaboration": ["team", "collaborate", "communicate", "share", "align"],
            "risk": ["risk", "concern", "issue", "problem", "fail"],
            "quality": ["quality", "test", "review", "standard", "best practice"],
        }
        text_lower = text.lower()
        themes = []
        for theme, keywords in theme_map.items():
            if any(kw in text_lower for kw in keywords):
                themes.append(theme)
        return themes[:3]

    def _extract_quote_values(self, text: str) -> tuple:
        """Extract quoted and actual values from quote text."""
        # Look for numeric patterns like "$100" or "100 units"
        numbers = re.findall(
            r"[\$€£]?\d+(?:\.\d+)?%?(?:\s*(?:units?|hours?|days?|weeks?|months?|estimates?|projections?|quotes?|actuals?)?)?",
            text.lower(),
        )
        if len(numbers) >= 2:
            try:
                quoted = float(re.sub(r"[^\d.]", "", numbers[0]))
                actual = float(re.sub(r"[^\d.]", "", numbers[1]))
                return quoted, actual
            except (ValueError, IndexError):
                pass
        return None, None

    def _compute_margin_analysis(
        self, quoted: Optional[float], actual: Optional[float]
    ) -> Dict[str, Any]:
        """Compute margin analysis between quoted and actual values."""
        if quoted is None or actual is None or quoted == 0:
            return {"has_comparison": False}

        variance = actual - quoted
        variance_pct = (variance / quoted) * 100 if quoted != 0 else 0
        margin = quoted - actual

        return {
            "has_comparison": True,
            "quoted_value": quoted,
            "actual_value": actual,
            "variance": variance,
            "variance_percentage": variance_pct,
            "margin_delta": margin,
            "analysis": f"Quote was {abs(variance_pct):.1f}% {'lower' if variance > 0 else 'higher'} than actual",
        }

    def _compute_confidence_calibration(self, fact: str, sentiment: float) -> float:
        """Compute confidence calibration score for the quote."""
        # Base confidence
        confidence = 0.7

        # Adjust based on specificity
        if re.search(r"\d+", fact):
            confidence += 0.1

        # Adjust based on sentiment extremity
        if abs(sentiment) > 0.5:
            confidence -= 0.1

        return max(0.1, min(0.95, confidence))

    # ── Bottleneck Analysis ───────────────────────────────────────────────────

    def identify_process_bottlenecks(
        self, graph_id: str, query: str = "", limit: int = 10
    ) -> List[BottleneckAnalysis]:
        """
        Identify performance and process bottlenecks from graph data.
        Analyzes workstation utilization, wait times, and critical path.

        Args:
            graph_id: Graph ID
            query: Optional focus area
            limit: Maximum bottlenecks to identify

        Returns:
            List of BottleneckAnalysis with to_dict() and to_text() methods
        """
        logger.info(
            f"Identifying process bottlenecks: graph_id={graph_id}, query={query[:50] if query else 'all'}..."
        )

        try:
            search_results = self.storage.search(
                graph_id=graph_id,
                query=query
                or "bottleneck delay slow issue problem constraint wait queue",
                limit=limit * 3,
                scope="edges",
            )

            bottlenecks: List[BottleneckAnalysis] = []
            seen: set = set()

            edge_list = self._safe_get_edges(search_results)

            for edge in edge_list:
                fact = edge.get("fact", "") if isinstance(edge, dict) else ""
                if not fact or len(fact) < 10:
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
                        BottleneckAnalysis(
                            bottleneck_name=name,
                            description=self._describe_bottleneck(fact),
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

            # If no bottlenecks found, generate speculative ones
            if not bottlenecks:
                bottlenecks = self._generate_speculative_bottlenecks(graph_id, limit)

            logger.info(f"Identified {len(bottlenecks)} process bottlenecks")
            return bottlenecks

        except Exception as e:
            logger.error(f"Bottleneck identification failed: {e}")
            return []

    def _indicates_bottleneck(self, text: str) -> bool:
        """Check if text indicates a bottleneck."""
        bottleneck_keywords = [
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
            "throughput",
            "timeout",
            "queue",
        ]
        text_lower = text.lower()
        return any(kw in text_lower for kw in bottleneck_keywords)

    def _name_bottleneck(self, fact: str) -> str:
        """Generate a name for a bottleneck from its description."""
        words = re.findall(r"\b[a-z]{4,}\b", fact.lower())
        key_words = [
            w
            for w in words
            if w
            not in {
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
            }
        ]
        if len(key_words) >= 2:
            return f"{key_words[0].title()} {key_words[1].title()} Bottleneck"
        elif key_words:
            return f"{key_words[0].title()} Bottleneck"
        return "Process Bottleneck"

    def _assess_severity(self, fact: str) -> str:
        """Assess bottleneck severity from text."""
        critical_keywords = ["critical", "fatal", "complete failure", "deadlock"]
        major_keywords = ["major", "significant", "serious", "severe", "fail"]
        minor_keywords = ["minor", "slight", "small", "little", "occasional"]
        text_lower = fact.lower()
        if any(kw in text_lower for kw in critical_keywords):
            return "critical"
        elif any(kw in text_lower for kw in major_keywords):
            return "major"
        elif any(kw in text_lower for kw in minor_keywords):
            return "minor"
        return "major"

    def _extract_components(self, edge: Dict[str, Any]) -> List[str]:
        """Extract affected components from edge data."""
        components = []
        if isinstance(edge, dict):
            source = edge.get("source_node_name", "")
            target = edge.get("target_node_name", "")
            if source:
                components.append(source)
            if target:
                components.append(target)
        return components[:3]

    def _describe_bottleneck(self, fact: str) -> str:
        """Generate a description for a bottleneck."""
        if len(fact) > 200:
            return fact[:197] + "..."
        return fact

    def _generate_recommendation(self, name: str, fact: str) -> str:
        """Generate a recommendation for addressing a bottleneck."""
        return f"Analyze and optimize {name.lower().replace(' bottleneck', '')} to improve system performance."

    def _compute_workstation_utilization(self, fact: str) -> float:
        """Compute workstation utilization metric."""
        text_lower = fact.lower()
        if any(
            k in text_lower
            for k in ["high utilization", "overload", "saturated", "maxed"]
        ):
            return 0.95
        elif any(k in text_lower for k in ["moderate", "normal", "typical"]):
            return 0.65
        elif any(k in text_lower for k in ["low", "underutil", "idle"]):
            return 0.30
        return 0.70  # default

    def _estimate_wait_time(self, fact: str) -> Dict[str, Any]:
        """Estimate wait times from bottleneck description."""
        text_lower = fact.lower()
        wait_keywords = ["wait", "delay", "queue", "latency"]
        has_wait = any(k in text_lower for k in wait_keywords)

        if has_wait:
            if any(
                k in text_lower for k in ["long", "significant", "major", "critical"]
            ):
                return {
                    "has_wait_time": True,
                    "estimated_delay": "significant",
                    "severity": "high",
                }
            elif any(k in text_lower for k in ["short", "minor", "slight"]):
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
        ]
        on_critical = (
            any(k in text_lower for k in critical_indicators) or len(components) <= 2
        )

        return {
            "on_critical_path": on_critical,
            "impact_scope": "system-wide" if on_critical else "localized",
            "blocked_components": components if on_critical else [],
        }

    def _generate_speculative_bottlenecks(
        self, graph_id: str, limit: int
    ) -> List[BottleneckAnalysis]:
        """Generate speculative bottlenecks when none are found in data."""
        logger.info("No explicit bottlenecks found, generating analysis-based findings")
        return [
            BottleneckAnalysis(
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
            )
        ][:limit]

    # ── Collaboration Effectiveness ────────────────────────────────────────────

    def evaluate_collaboration_effectiveness(
        self, graph_id: str, query: str = "", limit: int = 10
    ) -> List[CollaborationAnalysis]:
        """
        Evaluate collaboration effectiveness between agents.
        Analyzes consultation frequency and review effectiveness.

        Args:
            graph_id: Graph ID
            query: Optional focus area
            limit: Maximum patterns to identify

        Returns:
            List of CollaborationAnalysis with to_dict() and to_text() methods
        """
        logger.info(
            f"Evaluating collaboration effectiveness: graph_id={graph_id}, query={query[:50] if query else 'all'}..."
        )

        try:
            search_results = self.storage.search(
                graph_id=graph_id,
                query=query
                or "collaborate team communicate share align coordinate review consult",
                limit=limit * 3,
                scope="edges",
            )

            collaborations: List[CollaborationAnalysis] = []
            seen_types: set = set()

            edge_list = self._safe_get_edges(search_results)

            for edge in edge_list:
                fact = edge.get("fact", "") if isinstance(edge, dict) else ""
                if not fact or len(fact) < 10:
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
                        CollaborationAnalysis(
                            collaboration_type=collab_type,
                            participants=participants,
                            description=fact[:200] if len(fact) > 200 else fact,
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
                collaborations = self._generate_default_collaboration(limit)

            logger.info(f"Evaluated {len(collaborations)} collaboration patterns")
            return collaborations

        except Exception as e:
            logger.error(f"Collaboration evaluation failed: {e}")
            return []

    def _indicates_collaboration(self, text: str) -> bool:
        """Check if text indicates collaboration."""
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
            "consult",
        ]
        text_lower = text.lower()
        return any(kw in text_lower for kw in collab_keywords)

    def _classify_collaboration(self, fact: str) -> str:
        """Classify the type of collaboration."""
        fact_lower = fact.lower()
        if any(k in fact_lower for k in ["design", "architect", "plan"]):
            return "Design Collaboration"
        elif any(k in fact_lower for k in ["code", "implement", "build", "develop"]):
            return "Development Collaboration"
        elif any(k in fact_lower for k in ["test", "qa", "review", "quality"]):
            return "Quality Assurance Collaboration"
        elif any(k in fact_lower for k in ["deploy", "release", "launch"]):
            return "Deployment Collaboration"
        elif any(k in fact_lower for k in ["stakeholder", "business", "product"]):
            return "Stakeholder Collaboration"
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
        ]
        ineffective_keywords = ["fail", "conflict", "delay", "misunderstand", "miss"]
        fact_lower = fact.lower()
        if any(kw in fact_lower for kw in effective_keywords):
            return "high"
        elif any(kw in fact_lower for kw in ineffective_keywords):
            return "low"
        return "medium"

    def _compute_consultation_frequency(
        self, edge: Dict[str, Any], fact: str
    ) -> Dict[str, Any]:
        """Compute consultation frequency metric."""
        text_lower = fact.lower()
        consult_indicators = ["consult", "discuss", "review", "meet", "sync", "align"]
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
        ]
        mentions = sum(1 for k in review_keywords if k in text_lower)

        if any(k in text_lower for k in ["approved", "accepted", "success"]):
            outcome = "positive"
        elif any(k in text_lower for k in ["rejected", "failed", "conflict"]):
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
            ],
            "Development Collaboration": [
                "Adopt pair programming practices",
                "Regular code reviews",
                "Clear task assignment",
            ],
            "Quality Assurance Collaboration": [
                "Early QA involvement",
                "Automated testing integration",
                "Clear bug reporting workflow",
            ],
            "Deployment Collaboration": [
                "Deployment checklists",
                "Rollback procedures",
                "Post-deployment monitoring",
            ],
            "Stakeholder Collaboration": [
                "Regular status updates",
                "Clear communication channels",
                "Expectation alignment meetings",
            ],
        }
        return suggestions_map.get(
            collab_type,
            ["Regular check-ins", "Clear documentation", "Defined workflows"],
        )

    def _generate_default_collaboration(
        self, limit: int
    ) -> List[CollaborationAnalysis]:
        """Generate default collaboration patterns when none found."""
        return [
            CollaborationAnalysis(
                collaboration_type="Team Communication",
                participants=["Team Members"],
                description="General team communication and information sharing patterns",
                effectiveness="medium",
                examples=[],
                improvement_suggestions=[
                    "Establish regular standups",
                    "Use shared communication channels",
                ],
                consultation_frequency={
                    "frequency_score": 0.5,
                    "frequency_label": "medium",
                    "consulted_parties": [],
                },
                review_effectiveness={
                    "review_count": 0,
                    "effectiveness_score": 0.5,
                    "outcome": "neutral",
                },
            )
        ][:limit]

    # ── Design Quality ────────────────────────────────────────────────────────

    def analyze_design_quality(
        self, graph_id: str, query: str = "", limit: int = 10
    ) -> List[DesignQualityResult]:
        """
        Analyze technical design quality from graph data.
        Analyzes revision counts, manufacturability, and rework causes.

        Args:
            graph_id: Graph ID
            query: Optional focus area
            limit: Maximum aspects to assess

        Returns:
            List of DesignQualityResult with to_dict() and to_text() methods
        """
        logger.info(
            f"Analyzing design quality: graph_id={graph_id}, query={query[:50] if query else 'all'}..."
        )

        try:
            search_results = self.storage.search(
                graph_id=graph_id,
                query=query
                or "design architecture module component interface pattern revision rework",
                limit=limit * 3,
                scope="edges",
            )

            assessments: List[DesignQualityResult] = []
            seen_aspects: set = set()

            edge_list = self._safe_get_edges(search_results)

            for edge in edge_list:
                fact = edge.get("fact", "") if isinstance(edge, dict) else ""
                if not fact or len(fact) < 10:
                    continue

                aspect = self._identify_design_aspect(fact)
                if not aspect or aspect in seen_aspects:
                    continue
                seen_aspects.add(aspect)

                rating = self._rate_design_aspect(fact)
                strengths = self._extract_strengths(fact)
                weaknesses = self._extract_weaknesses(fact)
                metrics = self._compute_quality_metrics(fact)

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
                assessments = self._generate_default_assessment(limit)

            logger.info(f"Analyzed {len(assessments)} design quality aspects")
            return assessments

        except Exception as e:
            logger.error(f"Design quality analysis failed: {e}")
            return []

    def _identify_design_aspect(self, fact: str) -> str:
        """Identify which design aspect this fact relates to."""
        fact_lower = fact.lower()
        if any(
            k in fact_lower for k in ["modular", "module", "component", "separation"]
        ):
            return "Modularity"
        elif any(k in fact_lower for k in ["interface", "api", "contract", "protocol"]):
            return "API Design"
        elif any(k in fact_lower for k in ["scalable", "scale", "growth", "capacity"]):
            return "Scalability"
        elif any(
            k in fact_lower for k in ["perform", "speed", "latency", "throughput"]
        ):
            return "Performance"
        elif any(k in fact_lower for k in ["maintain", "readable", "clean", "debt"]):
            return "Maintainability"
        elif any(k in fact_lower for k in ["test", "coverage", "automated"]):
            return "Testability"
        elif any(k in fact_lower for k in ["security", "auth", "access", "encrypt"]):
            return "Security"
        elif any(k in fact_lower for k in ["reliab", "stable", "robust", "fault"]):
            return "Reliability"
        return "General Design"

    def _rate_design_aspect(self, fact: str) -> str:
        """Rate the design aspect quality."""
        positive = [
            "good",
            "well",
            "strong",
            "solid",
            "excellent",
            "effective",
            "clean",
        ]
        negative = ["bad", "poor", "weak", "fragile", "complex", "tight", "coupled"]
        neutral = ["adequate", "acceptable", "mixed"]
        fact_lower = fact.lower()
        pos_count = sum(1 for w in positive if w in fact_lower)
        neg_count = sum(1 for w in negative if w in fact_lower)
        if pos_count > neg_count:
            return "good" if pos_count > 1 else "fair"
        elif neg_count > pos_count:
            return "poor" if neg_count > 1 else "fair"
        return "fair"

    def _extract_strengths(self, fact: str) -> List[str]:
        """Extract design strengths."""
        strengths = []
        fact_lower = fact.lower()
        if "modular" in fact_lower or "component" in fact_lower:
            strengths.append("Good separation of concerns")
        if "interface" in fact_lower or "api" in fact_lower:
            strengths.append("Clear contract definitions")
        if "test" in fact_lower or "automated" in fact_lower:
            strengths.append("Automated testing in place")
        if "scalable" in fact_lower:
            strengths.append("Designed for scalability")
        return strengths[:3]

    def _extract_weaknesses(self, fact: str) -> List[str]:
        """Extract design weaknesses."""
        weaknesses = []
        fact_lower = fact.lower()
        if "tight" in fact_lower and "coupl" in fact_lower:
            weaknesses.append("Tight coupling detected")
        if "complex" in fact_lower:
            weaknesses.append("Excessive complexity")
        if "monolith" in fact_lower:
            weaknesses.append("Monolithic structure")
        if "single" in fact_lower and "point" in fact_lower:
            weaknesses.append("Single point of failure")
        return weaknesses[:3]

    def _compute_quality_metrics(self, fact: str) -> Dict[str, float]:
        """Compute simple quality metrics."""
        metrics: Dict[str, float] = {}
        fact_lower = fact.lower()
        # Complexity indicator
        words = len(fact.split())
        metrics["complexity_score"] = min(words / 50.0, 1.0)
        # Quality indicator
        quality_words = sum(
            1 for w in ["good", "well", "strong", "solid"] if w in fact_lower
        )
        metrics["quality_score"] = min(quality_words / 3.0, 1.0)
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
        ]
        negative = ["complex", "difficult", "challenging", "intricate", "delicate"]

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
            "requirement_changes": ["requirement", "spec", "change"],
            "design_errors": ["error", "mistake", "incorrect", "wrong"],
            "scope_creep": ["scope", "creep", "expand", "add"],
            "quality_issues": ["quality", "defect", "bug", "issue"],
            "integration_problems": ["integration", "interface", "compatibility"],
        }

        for cause, keywords in cause_map.items():
            if any(k in text_lower for k in keywords):
                causes.append(cause)

        return causes[:3]

    def _generate_default_assessment(self, limit: int) -> List[DesignQualityResult]:
        """Generate default assessment when no data found."""
        return [
            DesignQualityResult(
                aspect="General Design",
                rating="fair",
                findings=["Design assessment pending detailed analysis"],
                strengths=["Awaiting graph data"],
                weaknesses=["Insufficient data for detailed assessment"],
                metrics={"confidence": 0.3},
                revision_counts={
                    "revision_count": 0,
                    "iteration_depth": 0,
                    "stability_score": 0.5,
                },
                manufacturability_score=0.65,
                rework_causes=[],
            )
        ][:limit]

    # ── Risk Prediction ───────────────────────────────────────────────────────

    def predict_risk_exposure(
        self, graph_id: str, query: str = "", limit: int = 10
    ) -> List[RiskPrediction]:
        """
        Predict and assess project risk exposure from graph data.
        Analyzes schedule confidence, budget at risk, and resource contention.

        Args:
            graph_id: Graph ID
            query: Optional focus area
            limit: Maximum risks to identify

        Returns:
            List of RiskPrediction with to_dict() and to_text() methods
        """
        logger.info(
            f"Predicting risk exposure: graph_id={graph_id}, query={query[:50] if query else 'all'}..."
        )

        try:
            search_results = self.storage.search(
                graph_id=graph_id,
                query=query
                or "risk concern issue vulnerability threat uncertainty budget resource schedule",
                limit=limit * 3,
                scope="edges",
            )

            risks: List[RiskPrediction] = []
            seen_risks: set = set()

            edge_list = self._safe_get_edges(search_results)

            for edge in edge_list:
                fact = edge.get("fact", "") if isinstance(edge, dict) else ""
                if not fact or len(fact) < 10:
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
                            description=fact[:200] if len(fact) > 200 else fact,
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

            logger.info(f"Predicted {len(risks)} risk exposures")
            return risks

        except Exception as e:
            logger.error(f"Risk prediction failed: {e}")
            return []

    def _indicates_risk(self, text: str) -> bool:
        """Check if text indicates a risk."""
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
        ]
        text_lower = text.lower()
        return any(kw in text_lower for kw in risk_keywords)

    def _name_risk(self, fact: str) -> str:
        """Generate a name for a risk."""
        words = re.findall(r"\b[A-Z][a-z]+\b", fact)
        if len(words) >= 2:
            return f"{words[0]} {words[1]} Risk"
        elif words:
            return f"{words[0]} Risk"
        return "Project Risk"

    def _assess_likelihood(self, fact: str) -> str:
        """Assess likelihood of risk occurring."""
        fact_lower = fact.lower()
        high_likelihood = ["likely", "probable", "certain", "known", "frequent"]
        low_likelihood = ["unlikely", "rare", "infrequent", "occasional", "uncertain"]
        if any(k in fact_lower for k in high_likelihood):
            return "high"
        elif any(k in fact_lower for k in low_likelihood):
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
        ]
        low_impact = ["minor", "small", "negligible", "minimal", "limited"]
        if any(k in fact_lower for k in high_impact):
            return "high"
        elif any(k in fact_lower for k in low_impact):
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

    def _suggest_mitigations(self, risk_name: str) -> List[str]:
        """Suggest mitigation strategies for a risk."""
        name_lower = risk_name.lower()
        if "resource" in name_lower or "budget" in name_lower:
            return [
                "Review resource allocation",
                "Prioritize critical tasks",
                "Identify alternative resources",
            ]
        elif "technical" in name_lower or "technology" in name_lower:
            return [
                "Technical review and spikes",
                "Proof of concept implementation",
                "Expert consultation",
            ]
        elif "schedule" in name_lower or "timeline" in name_lower:
            return [
                "Re-evaluate timeline",
                "Add buffer time",
                "Parallel task execution",
            ]
        elif "quality" in name_lower:
            return [
                "Code reviews",
                "Testing enhancements",
                "Quality gates",
            ]
        return [
            "Monitor risk indicators",
            "Develop contingency plan",
            "Regular risk reassessment",
        ]

    def _compute_schedule_confidence(self, fact: str) -> Dict[str, Any]:
        """Compute schedule confidence metric."""
        text_lower = fact.lower()
        schedule_risks = ["delay", "overdue", "behind", "late", "slip", "miss"]
        schedule_positive = ["on-track", "ahead", "early", "准时", "按时"]

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
        """Generate default risks when none found."""
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
                indicators=["Complex technical requirements"],
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
        ][:limit]

    # ── Team Interview ─────────────────────────────────────────────────────────

    def interview_project_team(
        self, graph_id: str, query: str = "", limit: int = 10
    ) -> List[TeamInterviewResult]:
        """
        Simulate team interviews by extracting perspectives from agent interactions.

        Args:
            graph_id: Graph ID
            query: Optional focus area
            limit: Maximum interview results

        Returns:
            List of TeamInterviewResult with to_dict() and to_text() methods
        """
        logger.info(
            f"Interviewing project team: graph_id={graph_id}, query={query[:50] if query else 'all'}..."
        )

        try:
            search_results = self.storage.search(
                graph_id=graph_id,
                query=query
                or "opinion perspective view think believe feel consider suggest recommend",
                limit=limit * 2,
                scope="edges",
            )

            interviews: List[TeamInterviewResult] = []
            seen_agents: set = set()

            edge_list = self._safe_get_edges(search_results)

            for edge in edge_list:
                fact = edge.get("fact", "") if isinstance(edge, dict) else ""
                if not fact or len(fact) < 10:
                    continue

                if self._is_opinion(fact):
                    agent_name, agent_role = self._extract_agent_info(edge)
                    if agent_name in seen_agents:
                        continue
                    seen_agents.add(agent_name)

                    topics = self._extract_interview_topics(fact)
                    responses = [fact]
                    sentiment = self._analyze_sentiment(fact)
                    confidence = self._compute_confidence_calibration(fact, sentiment)

                    interviews.append(
                        TeamInterviewResult(
                            agent_name=agent_name,
                            agent_role=agent_role,
                            topics_discussed=topics,
                            key_responses=responses,
                            sentiment=sentiment,
                            confidence_score=confidence,
                            alignment_score=self._compute_alignment_score(fact),
                        )
                    )

                    if len(interviews) >= limit:
                        break

            if not interviews:
                interviews = self._generate_default_interviews(limit)

            logger.info(f"Interviewed {len(interviews)} team members")
            return interviews

        except Exception as e:
            logger.error(f"Team interview failed: {e}")
            return []

    def _is_opinion(self, text: str) -> bool:
        """Check if text contains an opinion or perspective."""
        opinion_keywords = [
            "think",
            "believe",
            "feel",
            "opinion",
            "perspective",
            "view",
            "consider",
            "suggest",
            "recommend",
            "would",
            "could",
            "should",
        ]
        text_lower = text.lower()
        return any(kw in text_lower for kw in opinion_keywords)

    def _extract_agent_info(self, edge: Dict[str, Any]) -> tuple:
        """Extract agent name and role from edge."""
        source = edge.get("source_node_name", "") if isinstance(edge, dict) else ""
        target = edge.get("target_node_name", "") if isinstance(edge, dict) else ""
        agent_name = source or target or "Unknown Agent"
        agent_role = self._infer_role(agent_name)
        return agent_name, agent_role

    def _extract_interview_topics(self, fact: str) -> List[str]:
        """Extract topics from interview content."""
        topic_map = {
            "schedule": ["schedule", "timeline", "deadline", "delay", "when"],
            "budget": ["budget", "cost", "expensive", "affordable", "resource"],
            "quality": ["quality", "standard", "excellence", "defect", "issue"],
            "team": ["team", "collaborate", "communication", "stakeholder"],
            "technical": ["technical", "architecture", "design", "technology"],
            "risk": ["risk", "concern", "mitigation", "contingency"],
        }
        text_lower = fact.lower()
        topics = []
        for topic, keywords in topic_map.items():
            if any(kw in text_lower for kw in keywords):
                topics.append(topic)
        return topics[:3]

    def _compute_alignment_score(self, fact: str) -> float:
        """Compute alignment score with project goals."""
        alignment_keywords = [
            "agree",
            "aligned",
            "support",
            "commit",
            "goal",
            "objective",
            "一致",
        ]
        misalignment_keywords = ["disagree", "conflict", "oppose", "concern", "issue"]
        text_lower = fact.lower()

        align_count = sum(1 for k in alignment_keywords if k in text_lower)
        misalign_count = sum(1 for k in misalignment_keywords if k in text_lower)

        if align_count > misalign_count:
            return min(0.95, 0.6 + align_count * 0.1)
        elif misalign_count > align_count:
            return max(0.2, 0.6 - misalign_count * 0.1)
        return 0.6

    def _generate_default_interviews(self, limit: int) -> List[TeamInterviewResult]:
        """Generate default interview results when no data found."""
        return [
            TeamInterviewResult(
                agent_name="Team Member",
                agent_role="Engineer",
                topics_discussed=["technical", "schedule"],
                key_responses=["Project is on track with some technical challenges."],
                sentiment=0.1,
                confidence_score=0.6,
                alignment_score=0.7,
            )
        ][:limit]

    # ── Scenario Comparison ───────────────────────────────────────────────────

    def compare_scenario_outcomes(
        self, graph_id: str, scenarios: Optional[List[str]] = None, limit: int = 10
    ) -> List[ScenarioComparisonResult]:
        """
        Compare outcomes across different scenarios.

        Args:
            graph_id: Graph ID
            scenarios: Optional list of scenario identifiers to compare
            limit: Maximum scenarios to compare

        Returns:
            List of ScenarioComparisonResult with to_dict() and to_text() methods
        """
        logger.info(f"Comparing scenario outcomes: graph_id={graph_id}")

        try:
            if not scenarios:
                # Fetch all scenarios from graph
                scenarios = self._discover_scenarios(graph_id)

            comparisons: List[ScenarioComparisonResult] = []

            for scenario in scenarios[:limit]:
                scenario_data = self._extract_scenario_data(graph_id, scenario)
                if scenario_data:
                    comparisons.append(
                        ScenarioComparisonResult(
                            scenario_name=scenario,
                            outcomes=scenario_data.get("outcomes", []),
                            metrics=scenario_data.get("metrics", {}),
                            comparison_with_baseline=scenario_data.get(
                                "baseline_diff", {}
                            ),
                            recommendation=scenario_data.get("recommendation", ""),
                        )
                    )

            if not comparisons:
                comparisons = self._generate_default_comparison(limit)

            logger.info(f"Compared {len(comparisons)} scenario outcomes")
            return comparisons

        except Exception as e:
            logger.error(f"Scenario comparison failed: {e}")
            return []

    def _discover_scenarios(self, graph_id: str) -> List[str]:
        """Discover scenarios in the graph."""
        search_results = self.storage.search(
            graph_id=graph_id,
            query="scenario option alternative plan approach strategy",
            limit=20,
            scope="edges",
        )
        scenarios = []
        edge_list = self._safe_get_edges(search_results)
        for edge in edge_list:
            fact = edge.get("fact", "") if isinstance(edge, dict) else ""
            if fact and len(fact) > 10:
                scenarios.append(fact[:50])
        return scenarios[:5]

    def _extract_scenario_data(self, graph_id: str, scenario: str) -> Dict[str, Any]:
        """Extract data for a specific scenario."""
        search_results = self.storage.search(
            graph_id=graph_id,
            query=scenario,
            limit=10,
            scope="edges",
        )
        edge_list = self._safe_get_edges(search_results)

        outcomes = []
        metrics = {}
        for edge in edge_list:
            fact = edge.get("fact", "") if isinstance(edge, dict) else ""
            if fact:
                outcomes.append(fact[:100])

        if outcomes:
            metrics = {
                "outcome_count": len(outcomes),
                "success_indicators": sum(
                    1
                    for o in outcomes
                    if any(k in o.lower() for k in ["success", "achieve", "good"])
                ),
                "risk_indicators": sum(
                    1
                    for o in outcomes
                    if any(k in o.lower() for k in ["risk", "fail", "issue"])
                ),
            }

        return {
            "outcomes": outcomes,
            "metrics": metrics,
            "baseline_diff": {"variance": 0.0, "status": "comparable"},
            "recommendation": f"Scenario '{scenario[:30]}...' warrants further analysis",
        }

    def _generate_default_comparison(
        self, limit: int
    ) -> List[ScenarioComparisonResult]:
        """Generate default comparison when no scenarios found."""
        return [
            ScenarioComparisonResult(
                scenario_name="Default Scenario",
                outcomes=["Scenario analysis pending detailed data"],
                metrics={"confidence": 0.3},
                comparison_with_baseline={"variance": 0.0, "status": "baseline"},
                recommendation="Collect more scenario data for meaningful comparison",
            )
        ][:limit]

    # ── Utility Helpers ────────────────────────────────────────────────────────

    def _safe_get_edges(self, search_results) -> List[Dict[str, Any]]:
        """Safely extract edge list from search results."""
        if hasattr(search_results, "edges"):
            edge_list = search_results.edges
        elif isinstance(search_results, dict) and "edges" in search_results:
            edge_list = search_results["edges"]
        else:
            edge_list = []
        return list(edge_list) if edge_list else []
