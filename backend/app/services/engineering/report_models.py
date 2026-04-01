"""
Engineering Report Data Models

Dataclasses for engineering report tooling with to_dict / to_text methods.
Follows graph_tools/report_agent patterns.

Required dataclass names (EXACT):
- QuoteAccuracyResult
- BottleneckAnalysis
- CollaborationAnalysis
- DesignQualityResult
- RiskPrediction
- TeamInterviewResult
- ScenarioComparisonResult
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("mirofish.engineering")


class EngineeringReportStatus(str, Enum):
    """Engineering report status."""

    PENDING = "pending"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


# ── Analysis Result Dataclasses ──────────────────────────────────────────────


@dataclass
class QuoteAccuracyResult:
    """Quote accuracy analysis result with quoted vs actual, margin analysis, and confidence calibration."""

    quote_text: str
    speaker: str
    speaker_role: str
    context: str
    sentiment_score: float = 0.0
    confidence: float = 0.0
    key_themes: List[str] = field(default_factory=list)
    quoted_value: Optional[float] = None
    actual_value: Optional[float] = None
    margin_analysis: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "quote_text": self.quote_text,
            "speaker": self.speaker,
            "speaker_role": self.speaker_role,
            "context": self.context,
            "sentiment_score": self.sentiment_score,
            "confidence": self.confidence,
            "key_themes": self.key_themes,
            "quoted_value": self.quoted_value,
            "actual_value": self.actual_value,
            "margin_analysis": self.margin_analysis,
        }

    def to_text(self) -> str:
        themes = ", ".join(self.key_themes) if self.key_themes else "None"
        margin_info = ""
        if self.margin_analysis and self.margin_analysis.get("has_comparison"):
            margin_info = f"\nMargin: {self.margin_analysis.get('analysis', 'N/A')}"
        return (
            f'Quote: "{self.quote_text}"\n'
            f"Speaker: {self.speaker} ({self.speaker_role})\n"
            f"Context: {self.context}\n"
            f"Sentiment: {self.sentiment_score:.2f} | Confidence: {self.confidence:.2f}\n"
            f"Themes: {themes}{margin_info}"
        )


@dataclass
class BottleneckAnalysis:
    """Bottleneck identification result with workstation utilization, wait times, and critical path."""

    bottleneck_name: str
    description: str
    severity: str  # "critical", "major", "minor"
    affected_components: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    recommendation: str = ""
    workstation_utilization: float = 0.0
    wait_times: Dict[str, Any] = field(default_factory=dict)
    critical_path: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bottleneck_name": self.bottleneck_name,
            "description": self.description,
            "severity": self.severity,
            "affected_components": self.affected_components,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
            "workstation_utilization": self.workstation_utilization,
            "wait_times": self.wait_times,
            "critical_path": self.critical_path,
        }

    def to_text(self) -> str:
        components = (
            ", ".join(self.affected_components)
            if self.affected_components
            else "Unknown"
        )
        evidence = "\n  - ".join(self.evidence) if self.evidence else "No evidence"
        util_info = (
            f"Utilization: {self.workstation_utilization:.1%}"
            if self.workstation_utilization
            else ""
        )
        wait_info = ""
        if self.wait_times and self.wait_times.get("has_wait_time"):
            wait_info = f"Wait: {self.wait_times.get('estimated_delay', 'N/A')} ({self.wait_times.get('severity', 'N/A')} severity)"
        return (
            f"Bottleneck: {self.bottleneck_name} [{self.severity.upper()}]\n"
            f"Description: {self.description}\n"
            f"Affected Components: {components}\n"
            f"Evidence:\n  - {evidence}\n"
            f"Recommendation: {self.recommendation}\n"
            f"{util_info} | {wait_info}".strip()
        )


@dataclass
class CollaborationAnalysis:
    """Collaboration pattern analysis result with consultation frequency and review effectiveness."""

    collaboration_type: str
    participants: List[str] = field(default_factory=list)
    description: str = ""
    effectiveness: str = "medium"  # "high", "medium", "low"
    examples: List[str] = field(default_factory=list)
    improvement_suggestions: List[str] = field(default_factory=list)
    consultation_frequency: Dict[str, Any] = field(default_factory=dict)
    review_effectiveness: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "collaboration_type": self.collaboration_type,
            "participants": self.participants,
            "description": self.description,
            "effectiveness": self.effectiveness,
            "examples": self.examples,
            "improvement_suggestions": self.improvement_suggestions,
            "consultation_frequency": self.consultation_frequency,
            "review_effectiveness": self.review_effectiveness,
        }

    def to_text(self) -> str:
        participants = ", ".join(self.participants) if self.participants else "Unknown"
        examples = "\n  - ".join(self.examples) if self.examples else "No examples"
        suggestions = (
            "\n  - ".join(self.improvement_suggestions)
            if self.improvement_suggestions
            else "None"
        )
        freq_label = (
            self.consultation_frequency.get("frequency_label", "unknown")
            if self.consultation_frequency
            else "unknown"
        )
        review_score = (
            self.review_effectiveness.get("effectiveness_score", 0.5)
            if self.review_effectiveness
            else 0.5
        )
        return (
            f"Collaboration Type: {self.collaboration_type} [Effectiveness: {self.effectiveness.upper()}]\n"
            f"Participants: {participants}\n"
            f"Description: {self.description}\n"
            f"Consultation Frequency: {freq_label} | Review Effectiveness: {review_score:.2f}\n"
            f"Examples:\n  - {examples}\n"
            f"Improvement Suggestions:\n  - {suggestions}"
        )


@dataclass
class DesignQualityResult:
    """Design quality assessment result with revision counts, manufacturability, and rework causes."""

    aspect: str
    rating: str  # "excellent", "good", "fair", "poor"
    findings: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    revision_counts: Dict[str, Any] = field(default_factory=dict)
    manufacturability_score: float = 0.0
    rework_causes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "aspect": self.aspect,
            "rating": self.rating,
            "findings": self.findings,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "metrics": self.metrics,
            "revision_counts": self.revision_counts,
            "manufacturability_score": self.manufacturability_score,
            "rework_causes": self.rework_causes,
        }

    def to_text(self) -> str:
        findings = "\n  - ".join(self.findings) if self.findings else "None"
        strengths = "\n  - ".join(self.strengths) if self.strengths else "None"
        weaknesses = "\n  - ".join(self.weaknesses) if self.weaknesses else "None"
        metrics = (
            ", ".join(f"{k}={v:.2f}" for k, v in self.metrics.items())
            if self.metrics
            else "None"
        )
        rework = ", ".join(self.rework_causes) if self.rework_causes else "None"
        return (
            f"Design Aspect: {self.aspect} [Rating: {self.rating.upper()}]\n"
            f"Findings:\n  - {findings}\n"
            f"Strengths:\n  - {strengths}\n"
            f"Weaknesses:\n  - {weaknesses}\n"
            f"Metrics: {metrics}\n"
            f"Revision Count: {self.revision_counts.get('revision_count', 0)} | Manufacturability: {self.manufacturability_score:.2f}\n"
            f"Rework Causes: {rework}"
        )


@dataclass
class RiskPrediction:
    """Risk prediction result with schedule confidence, budget at risk, and resource contention."""

    risk_name: str
    description: str
    likelihood: str  # "high", "medium", "low"
    impact: str  # "high", "medium", "low"
    risk_level: str = ""  # computed: "critical", "high", "medium", "low"
    indicators: List[str] = field(default_factory=list)
    mitigation_strategies: List[str] = field(default_factory=list)
    affected_stakeholders: List[str] = field(default_factory=list)
    schedule_confidence: Dict[str, Any] = field(default_factory=dict)
    budget_at_risk: Dict[str, Any] = field(default_factory=dict)
    resource_contention: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.risk_level:
            self.risk_level = self._compute_risk_level()

    def _compute_risk_level(self) -> str:
        likelihood_map = {"high": 3, "medium": 2, "low": 1}
        impact_map = {"high": 3, "medium": 2, "low": 1}
        score = likelihood_map.get(self.likelihood, 2) * impact_map.get(self.impact, 2)
        if score >= 6:
            return "critical"
        elif score >= 4:
            return "high"
        elif score >= 2:
            return "medium"
        return "low"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_name": self.risk_name,
            "description": self.description,
            "likelihood": self.likelihood,
            "impact": self.impact,
            "risk_level": self.risk_level,
            "indicators": self.indicators,
            "mitigation_strategies": self.mitigation_strategies,
            "affected_stakeholders": self.affected_stakeholders,
            "schedule_confidence": self.schedule_confidence,
            "budget_at_risk": self.budget_at_risk,
            "resource_contention": self.resource_contention,
        }

    def to_text(self) -> str:
        indicators = "\n  - ".join(self.indicators) if self.indicators else "None"
        strategies = (
            "\n  - ".join(self.mitigation_strategies)
            if self.mitigation_strategies
            else "None"
        )
        stakeholders = (
            ", ".join(self.affected_stakeholders)
            if self.affected_stakeholders
            else "Unknown"
        )
        sched_conf = (
            self.schedule_confidence.get("confidence_label", "unknown")
            if self.schedule_confidence
            else "unknown"
        )
        budget_risk = (
            self.budget_at_risk.get("amount_at_risk", "Minimal")
            if self.budget_at_risk
            else "Minimal"
        )
        return (
            f"Risk: {self.risk_name} [Level: {self.risk_level.upper()}]\n"
            f"Description: {self.description}\n"
            f"Likelihood: {self.likelihood.upper()} | Impact: {self.impact.upper()}\n"
            f"Affected Stakeholders: {stakeholders}\n"
            f"Schedule Confidence: {sched_conf} | Budget at Risk: {budget_risk}\n"
            f"Indicators:\n  - {indicators}\n"
            f"Mitigation Strategies:\n  - {strategies}"
        )


@dataclass
class TeamInterviewResult:
    """Team interview result simulating agent perspectives."""

    agent_name: str
    agent_role: str
    topics_discussed: List[str] = field(default_factory=list)
    key_responses: List[str] = field(default_factory=list)
    sentiment: float = 0.0
    confidence_score: float = 0.0
    alignment_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "agent_role": self.agent_role,
            "topics_discussed": self.topics_discussed,
            "key_responses": self.key_responses,
            "sentiment": self.sentiment,
            "confidence_score": self.confidence_score,
            "alignment_score": self.alignment_score,
        }

    def to_text(self) -> str:
        topics = ", ".join(self.topics_discussed) if self.topics_discussed else "None"
        responses = (
            "\n  - ".join(self.key_responses) if self.key_responses else "No responses"
        )
        return (
            f"Agent: {self.agent_name} ({self.agent_role})\n"
            f"Topics: {topics}\n"
            f"Sentiment: {self.sentiment:.2f} | Confidence: {self.confidence_score:.2f} | Alignment: {self.alignment_score:.2f}\n"
            f"Key Responses:\n  - {responses}"
        )


@dataclass
class ScenarioComparisonResult:
    """Scenario comparison result for comparing different outcomes."""

    scenario_name: str
    outcomes: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    comparison_with_baseline: Dict[str, Any] = field(default_factory=dict)
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "outcomes": self.outcomes,
            "metrics": self.metrics,
            "comparison_with_baseline": self.comparison_with_baseline,
            "recommendation": self.recommendation,
        }

    def to_text(self) -> str:
        outcomes = (
            "\n  - ".join(self.outcomes) if self.outcomes else "No outcomes recorded"
        )
        metrics_str = (
            ", ".join(f"{k}={v}" for k, v in self.metrics.items())
            if self.metrics
            else "None"
        )
        baseline = (
            self.comparison_with_baseline.get("status", "unknown")
            if self.comparison_with_baseline
            else "unknown"
        )
        return (
            f"Scenario: {self.scenario_name}\n"
            f"Baseline Comparison: {baseline}\n"
            f"Metrics: {metrics_str}\n"
            f"Outcomes:\n  - {outcomes}\n"
            f"Recommendation: {self.recommendation}"
        )


# ── Section & Report ───────────────────────────────────────────────────────────


@dataclass
class EngineeringSection:
    """Single section of an engineering report."""

    title: str
    content: str = ""
    analysis_type: str = (
        ""  # "quote", "bottleneck", "collaboration", "design_quality", "risk"
    )
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content,
            "analysis_type": self.analysis_type,
            "metadata": self.metadata,
        }

    def to_markdown(self, level: int = 2) -> str:
        md = f"{'#' * level} {self.title}\n\n"
        if self.content:
            md += f"{self.content}\n\n"
        return md


@dataclass
class EngineeringReport:
    """Complete engineering report."""

    report_id: str
    simulation_id: str
    graph_id: str
    title: str
    summary: str
    status: EngineeringReportStatus
    sections: List[EngineeringSection] = field(default_factory=list)
    markdown_content: str = ""
    created_at: str = ""
    completed_at: str = ""
    error: Optional[str] = None

    # Analysis results stored for structured access
    quote_analysis: List[QuoteAccuracyResult] = field(default_factory=list)
    bottleneck_analysis: List[BottleneckAnalysis] = field(default_factory=list)
    collaboration_analysis: List[CollaborationAnalysis] = field(default_factory=list)
    design_quality: List[DesignQualityResult] = field(default_factory=list)
    risk_analysis: List[RiskPrediction] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "simulation_id": self.simulation_id,
            "graph_id": self.graph_id,
            "title": self.title,
            "summary": self.summary,
            "status": self.status.value,
            "sections": [s.to_dict() for s in self.sections],
            "markdown_content": self.markdown_content,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "analysis_results": {
                "quotes": [q.to_dict() for q in self.quote_analysis],
                "bottlenecks": [b.to_dict() for b in self.bottleneck_analysis],
                "collaboration": [c.to_dict() for c in self.collaboration_analysis],
                "design_quality": [d.to_dict() for d in self.design_quality],
                "risks": [r.to_dict() for r in self.risk_analysis],
            },
        }

    def to_markdown(self) -> str:
        md = f"# {self.title}\n\n"
        md += f"> {self.summary}\n\n"
        md += f"---\n\n"
        for section in self.sections:
            md += section.to_markdown()
        return md

    def to_text(self) -> str:
        lines = [
            f"Engineering Report: {self.title}",
            f"Status: {self.status.value}",
            f"Simulation: {self.simulation_id}",
            f"Graph: {self.graph_id}",
            "",
            f"Summary: {self.summary}",
            "",
            "Sections:",
        ]
        for section in self.sections:
            lines.append(f"  [{section.analysis_type}] {section.title}")
            if section.content:
                lines.append(f"    {section.content[:200]}...")
        return "\n".join(lines)
