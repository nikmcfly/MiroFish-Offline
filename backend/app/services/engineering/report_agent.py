"""
Engineering Report Agent

Generates engineering-focused reports using ReACT pattern.
Specialized for technical analysis: quotes, bottlenecks, collaboration, design quality, and risks.

Report sections (EXACT names):
- Executive Summary
- Quote Analysis
- Process Performance
- Design Quality Assessment
- Risk Assessment
- Recommendations

This is distinct from the general ReportAgent which focuses on
future-prediction simulation reports. EngineeringReportAgent focuses
on extracting and analyzing technical engineering patterns.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime

from ...config import Config
from ...utils.llm_client import LLMClient
from ...utils.logger import get_logger
from ..graph_tools import GraphToolsService
from .report_models import (
    EngineeringReport,
    EngineeringSection,
    EngineeringReportStatus,
    QuoteAccuracyResult,
    BottleneckAnalysis,
    CollaborationAnalysis,
    DesignQualityResult,
    RiskPrediction,
)
from .tools import EngineeringToolsService

logger = get_logger("mirofish.engineering_report_agent")


class EngineeringReportAgent:
    """
    Engineering Report Agent

    Uses specialized tools to analyze simulation data for engineering insights:
    - Quote accuracy analysis (quoted vs actual, margin, confidence)
    - Process bottleneck identification (utilization, wait times, critical path)
    - Collaboration effectiveness evaluation (consultation frequency, review effectiveness)
    - Design quality assessment (revision counts, manufacturability, rework causes)
    - Risk prediction (schedule confidence, budget at risk, resource contention)
    - Team interviews (agent perspectives and alignment)
    - Scenario comparison (outcome analysis)

    ReACT-compatible tool usage with existing graph tools and new engineering tools.
    """

    def __init__(
        self,
        graph_id: str,
        simulation_id: str,
        llm_client: Optional[LLMClient] = None,
        engineering_tools: Optional[EngineeringToolsService] = None,
        storage: Optional[Any] = None,
    ):
        """
        Initialize Engineering Report Agent.

        Args:
            graph_id: Graph ID
            simulation_id: Simulation ID
            llm_client: LLM client (optional)
            engineering_tools: Engineering tools service (optional)
            storage: GraphStorage instance (optional, used if tools not provided)
        """
        self.graph_id = graph_id
        self.simulation_id = simulation_id

        self.llm = llm_client or LLMClient()

        if engineering_tools is not None:
            self.tools = engineering_tools
        elif storage is not None:
            self.tools = EngineeringToolsService(storage=storage)
        else:
            raise ValueError("Either engineering_tools or storage must be provided")

        self.graph_tools = GraphToolsService(
            storage=self.tools.storage, llm_client=self.llm
        )

        logger.info(
            f"EngineeringReportAgent initialized: graph_id={graph_id}, simulation_id={simulation_id}"
        )

    def generate_report(
        self,
        progress_callback: Optional[Callable] = None,
        report_id: Optional[str] = None,
    ) -> EngineeringReport:
        """
        Generate a complete engineering report.

        Args:
            progress_callback: Optional progress callback(stage, progress, message)
            report_id: Optional report ID (generated if not provided)

        Returns:
            EngineeringReport with all sections and analysis results
        """
        report_id = report_id or f"eng_report_{uuid.uuid4().hex[:12]}"

        report = EngineeringReport(
            report_id=report_id,
            simulation_id=self.simulation_id,
            graph_id=self.graph_id,
            title="Engineering Analysis Report",
            summary="Technical engineering analysis based on simulation data",
            status=EngineeringReportStatus.PENDING,
            created_at=datetime.now().isoformat(),
        )

        try:
            if progress_callback:
                progress_callback("analyzing", 10, "Analyzing quote accuracy...")

            # Phase 1: Quote Accuracy Analysis
            quotes = self.tools.analyze_quote_accuracy(graph_id=self.graph_id, limit=20)
            report.quote_analysis = quotes

            if progress_callback:
                progress_callback("analyzing", 25, "Identifying process bottlenecks...")

            # Phase 2: Bottleneck Analysis
            bottlenecks = self.tools.identify_process_bottlenecks(
                graph_id=self.graph_id, limit=10
            )
            report.bottleneck_analysis = bottlenecks

            if progress_callback:
                progress_callback(
                    "analyzing", 40, "Evaluating collaboration effectiveness..."
                )

            # Phase 3: Collaboration Effectiveness
            collaborations = self.tools.evaluate_collaboration_effectiveness(
                graph_id=self.graph_id, limit=10
            )
            report.collaboration_analysis = collaborations

            if progress_callback:
                progress_callback("analyzing", 55, "Analyzing design quality...")

            # Phase 4: Design Quality Assessment
            design_quality = self.tools.analyze_design_quality(
                graph_id=self.graph_id, limit=10
            )
            report.design_quality = design_quality

            if progress_callback:
                progress_callback("analyzing", 70, "Predicting risk exposure...")

            # Phase 5: Risk Prediction
            risks = self.tools.predict_risk_exposure(graph_id=self.graph_id, limit=10)
            report.risk_analysis = risks

            if progress_callback:
                progress_callback("analyzing", 80, "Interviewing project team...")

            # Phase 6: Team Interviews (stored but not as separate section)
            team_interviews = self.tools.interview_project_team(
                graph_id=self.graph_id, limit=10
            )

            if progress_callback:
                progress_callback("analyzing", 85, "Comparing scenario outcomes...")

            # Phase 7: Scenario Comparison (stored but not as separate section)
            scenario_comparisons = self.tools.compare_scenario_outcomes(
                graph_id=self.graph_id, limit=5
            )

            if progress_callback:
                progress_callback("generating", 90, "Building report sections...")

            # Build sections from analysis results using EXACT section names
            report.sections = self._build_sections(report)

            # Generate executive summary
            report.summary = self._generate_executive_summary(report)

            # Generate markdown content
            report.markdown_content = self._generate_markdown(report)
            report.status = EngineeringReportStatus.COMPLETED
            report.completed_at = datetime.now().isoformat()

            if progress_callback:
                progress_callback("completed", 100, "Report generation complete")

            logger.info(f"Engineering report generated: {report_id}")
            return report

        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            report.status = EngineeringReportStatus.FAILED
            report.error = str(e)
            return report

    def _build_sections(self, report: EngineeringReport) -> List[EngineeringSection]:
        """Build report sections from analysis results with EXACT section names."""
        sections = []

        # 1. Quote Analysis (EXACT name)
        if report.quote_analysis:
            quotes_content = self._summarize_quotes(report.quote_analysis)
            sections.append(
                EngineeringSection(
                    title="Quote Analysis",
                    content=quotes_content,
                    analysis_type="quote_accuracy",
                    metadata={"count": len(report.quote_analysis)},
                )
            )

        if report.bottleneck_analysis:
            bottlenecks_content = self._summarize_bottlenecks(
                report.bottleneck_analysis
            )
            if report.collaboration_analysis:
                bottlenecks_content += "\n\n### Collaboration Effectiveness\n\n"
                bottlenecks_content += self._summarize_collaborations(
                    report.collaboration_analysis
                )
            sections.append(
                EngineeringSection(
                    title="Process Performance",
                    content=bottlenecks_content,
                    analysis_type="bottleneck",
                    metadata={
                        "count": len(report.bottleneck_analysis),
                        "critical": sum(
                            1
                            for b in report.bottleneck_analysis
                            if b.severity == "critical"
                        ),
                        "collaboration_patterns": len(report.collaboration_analysis),
                    },
                )
            )

        if report.design_quality:
            quality_content = self._summarize_design_quality(report.design_quality)
            sections.append(
                EngineeringSection(
                    title="Design Quality Assessment",
                    content=quality_content,
                    analysis_type="design_quality",
                    metadata={
                        "count": len(report.design_quality),
                        "good_rating": sum(
                            1
                            for d in report.design_quality
                            if d.rating in ["good", "excellent"]
                        ),
                    },
                )
            )

        if report.risk_analysis:
            risks_content = self._summarize_risks(report.risk_analysis)
            sections.append(
                EngineeringSection(
                    title="Risk Assessment",
                    content=risks_content,
                    analysis_type="risk",
                    metadata={
                        "count": len(report.risk_analysis),
                        "critical_risks": sum(
                            1
                            for r in report.risk_analysis
                            if r.risk_level == "critical"
                        ),
                    },
                )
            )

        recommendations_content = self._generate_recommendations(report)
        sections.append(
            EngineeringSection(
                title="Recommendations",
                content=recommendations_content,
                analysis_type="recommendations",
                metadata={},
            )
        )

        return sections

    def _generate_executive_summary(self, report: EngineeringReport) -> str:
        """Generate executive summary content."""
        lines = [
            "## Executive Summary",
            "",
            f"This engineering analysis report examines technical performance, collaboration patterns, and risk factors based on simulation data.",
            "",
        ]

        # Quote analysis summary
        if report.quote_analysis:
            lines.append(
                f"**Quote Analysis**: Analyzed {len(report.quote_analysis)} quotes for accuracy and sentiment."
            )

        # Bottleneck summary
        if report.bottleneck_analysis:
            critical_count = sum(
                1 for b in report.bottleneck_analysis if b.severity == "critical"
            )
            major_count = sum(
                1 for b in report.bottleneck_analysis if b.severity == "major"
            )
            lines.append(
                f"**Process Performance**: Identified {len(report.bottleneck_analysis)} bottlenecks ({critical_count} critical, {major_count} major)."
            )

        # Collaboration summary
        if report.collaboration_analysis:
            high_eff = sum(
                1 for c in report.collaboration_analysis if c.effectiveness == "high"
            )
            lines.append(
                f"**Collaboration**: Evaluated {len(report.collaboration_analysis)} collaboration patterns ({high_eff} high effectiveness)."
            )

        # Design quality summary
        if report.design_quality:
            good_rating = sum(
                1 for d in report.design_quality if d.rating in ["good", "excellent"]
            )
            lines.append(
                f"**Design Quality**: Assessed {len(report.design_quality)} design aspects ({good_rating} rated good or excellent)."
            )

        # Risk summary
        if report.risk_analysis:
            critical_risks = sum(
                1 for r in report.risk_analysis if r.risk_level == "critical"
            )
            high_risks = sum(1 for r in report.risk_analysis if r.risk_level == "high")
            lines.append(
                f"**Risk Assessment**: Identified {len(report.risk_analysis)} risks ({critical_risks} critical, {high_risks} high)."
            )

        return "\n".join(lines)

    def _summarize_quotes(self, quotes: List[QuoteAccuracyResult]) -> str:
        """Generate summary text for quotes."""
        if not quotes:
            return "No quotes extracted from the simulation data."

        lines = [f"Analyzed {len(quotes)} quotes for accuracy and sentiment.\n"]

        # Group by speaker
        by_speaker: Dict[str, List[QuoteAccuracyResult]] = {}
        for q in quotes:
            by_speaker.setdefault(q.speaker, []).append(q)

        for speaker, speaker_quotes in list(by_speaker.items())[:5]:
            lines.append(f"**{speaker}** ({speaker_quotes[0].speaker_role}):")
            for q in speaker_quotes[:2]:
                sentiment_indicator = (
                    "positive"
                    if q.sentiment_score > 0.3
                    else "negative"
                    if q.sentiment_score < -0.3
                    else "neutral"
                )
                lines.append(
                    f'  > "{q.quote_text[:80]}{"..." if len(q.quote_text) > 80 else ""}" [{sentiment_indicator}]'
                )
                if q.margin_analysis and q.margin_analysis.get("has_comparison"):
                    lines.append(f"    Margin: {q.margin_analysis.get('analysis', '')}")
            lines.append("")

        # Theme summary
        all_themes = set()
        for q in quotes:
            all_themes.update(q.key_themes)
        if all_themes:
            lines.append(f"**Key Themes**: {', '.join(sorted(all_themes))}")

        return "\n".join(lines)

    def _summarize_bottlenecks(self, bottlenecks: List[BottleneckAnalysis]) -> str:
        """Generate summary text for bottlenecks (Process Performance)."""
        if not bottlenecks:
            return "No bottlenecks identified in the simulation data."

        lines = [f"Identified {len(bottlenecks)} process bottlenecks.\n"]

        # Sort by severity
        severity_order = {"critical": 0, "major": 1, "minor": 2}
        sorted_bottlenecks = sorted(
            bottlenecks, key=lambda b: severity_order.get(b.severity, 3)
        )

        for b in sorted_bottlenecks:
            components = (
                ", ".join(b.affected_components[:2])
                if b.affected_components
                else "Unknown"
            )
            lines.append(f"**{b.bottleneck_name}** [{b.severity.upper()}]")
            lines.append(
                f"  Description: {b.description[:100]}{'...' if len(b.description) > 100 else ''}"
            )
            lines.append(f"  Affected: {components}")
            if b.workstation_utilization:
                lines.append(f"  Utilization: {b.workstation_utilization:.1%}")
            if b.wait_times and b.wait_times.get("has_wait_time"):
                lines.append(
                    f"  Wait Time: {b.wait_times.get('estimated_delay', 'N/A')} ({b.wait_times.get('severity', 'N/A')})"
                )
            if b.critical_path and b.critical_path.get("on_critical_path"):
                lines.append(f"  Critical Path: Yes (system-wide impact)")
            if b.recommendation:
                lines.append(
                    f"  Recommendation: {b.recommendation[:80]}{'...' if len(b.recommendation) > 80 else ''}"
                )
            lines.append("")

        return "\n".join(lines)

    def _summarize_collaborations(
        self, collaborations: List[CollaborationAnalysis]
    ) -> str:
        """Generate summary text for collaboration patterns."""
        if not collaborations:
            return "No collaboration patterns identified."

        lines = [f"Found {len(collaborations)} collaboration patterns.\n"]

        # Group by effectiveness
        by_effectiveness: Dict[str, List[CollaborationAnalysis]] = {}
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
                freq = (
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
                    f"    Consultation: {freq} | Review Effectiveness: {review_score:.2f}"
                )
            lines.append("")

        return "\n".join(lines)

    def _summarize_design_quality(self, assessments: List[DesignQualityResult]) -> str:
        """Generate summary text for design quality."""
        if not assessments:
            return "No design quality assessments available."

        lines = [f"Assessed {len(assessments)} design aspects.\n"]

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

        return "\n".join(lines)

    def _summarize_risks(self, risks: List[RiskPrediction]) -> str:
        """Generate summary text for risks (Risk Assessment)."""
        if not risks:
            return "No risks identified."

        lines = [f"Identified {len(risks)} risks.\n"]

        # Sort by risk level
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_risks = sorted(risks, key=lambda r: severity_order.get(r.risk_level, 4))

        for r in sorted_risks:
            stakeholders = (
                ", ".join(r.affected_stakeholders[:2])
                if r.affected_stakeholders
                else "Unknown"
            )
            lines.append(f"**{r.risk_name}** [{r.risk_level.upper()}]")
            lines.append(
                f"  Likelihood: {r.likelihood.upper()} | Impact: {r.impact.upper()}"
            )
            lines.append(f"  Stakeholders: {stakeholders}")
            if r.schedule_confidence:
                sched = r.schedule_confidence.get("confidence_label", "unknown")
                lines.append(f"  Schedule Confidence: {sched}")
            if r.budget_at_risk and r.budget_at_risk.get("has_budget_risk"):
                lines.append(
                    f"  Budget at Risk: {r.budget_at_risk.get('amount_at_risk', 'N/A')}"
                )
            if r.mitigation_strategies:
                lines.append(
                    f"  Mitigation: {r.mitigation_strategies[0][:60]}{'...' if len(r.mitigation_strategies[0]) > 60 else ''}"
                )
            lines.append("")

        return "\n".join(lines)

    def _generate_recommendations(self, report: EngineeringReport) -> str:
        """Generate recommendations based on all analysis."""
        lines = [
            "Based on the analysis above, the following recommendations are provided:\n",
        ]

        # Priority 1: Critical bottlenecks
        critical_bottlenecks = [
            b for b in report.bottleneck_analysis if b.severity == "critical"
        ]
        if critical_bottlenecks:
            lines.append("**Immediate Actions (Critical Bottlenecks):**")
            for b in critical_bottlenecks[:3]:
                lines.append(f"- Address {b.bottleneck_name}: {b.recommendation[:100]}")
            lines.append("")

        # Priority 2: High-severity risks
        high_risks = [
            r for r in report.risk_analysis if r.risk_level in ("high", "critical")
        ]
        if high_risks:
            lines.append("**Risk Mitigation:**")
            for r in high_risks[:3]:
                if r.mitigation_strategies:
                    lines.append(f"- {r.risk_name}: {r.mitigation_strategies[0][:100]}")
            lines.append("")

        # Priority 3: Collaboration improvements
        low_collaboration = [
            c for c in report.collaboration_analysis if c.effectiveness == "low"
        ]
        if low_collaboration:
            lines.append("**Collaboration Improvements:**")
            for c in low_collaboration[:2]:
                if c.improvement_suggestions:
                    lines.append(
                        f"- {c.collaboration_type}: {c.improvement_suggestions[0][:100]}"
                    )
            lines.append("")

        # Priority 4: Design quality improvements
        poor_quality = [
            d for d in report.design_quality if d.rating in ("poor", "fair")
        ]
        if poor_quality:
            lines.append("**Design Quality Improvements:**")
            for d in poor_quality[:3]:
                if d.weaknesses:
                    lines.append(
                        f"- {d.aspect}: Address {d.weaknesses[0][:80] if d.weaknesses else 'issues'}"
                    )
            lines.append("")

        # Default recommendation if nothing specific
        if len(lines) == 1:
            lines.append(
                "- Continue monitoring process performance and collaboration patterns."
            )
            lines.append("- Regular reviews recommended to maintain quality standards.")

        return "\n".join(lines)

    def _generate_markdown(self, report: EngineeringReport) -> str:
        """Generate full markdown content for the report."""
        md = f"# {report.title}\n\n"
        md += f"> {report.summary}\n\n"
        md += f"---\n\n"
        md += f"**Report ID:** {report.report_id}\n"
        md += f"**Simulation:** {self.simulation_id}\n"
        md += f"**Graph:** {self.graph_id}\n"
        md += f"**Generated:** {report.created_at}\n\n"

        # Executive Summary section (always first)
        md += "---\n\n"
        md += "## Executive Summary\n\n"

        # Add summary content
        exec_summary = self._generate_executive_summary(report)
        # Remove the "## Executive Summary" line we added
        exec_summary_lines = exec_summary.split("\n")
        exec_summary_lines = [l for l in exec_summary_lines if not l.startswith("## ")]
        md += "\n".join(exec_summary_lines) + "\n\n"

        # Process remaining sections
        for section in report.sections:
            md += "---\n\n"
            md += f"## {section.title}\n\n"
            if section.content:
                md += f"{section.content}\n\n"

        # Add analysis results appendix
        md += "---\n\n"
        md += "## Appendix: Detailed Analysis Results\n\n"

        if report.quote_analysis:
            md += "### Quote Analysis Details\n\n"
            for q in report.quote_analysis:
                md += f"```\n{q.to_text()}\n```\n\n"

        if report.bottleneck_analysis:
            md += "### Process Performance Details\n\n"
            for b in report.bottleneck_analysis:
                md += f"```\n{b.to_text()}\n```\n\n"

        if report.collaboration_analysis:
            md += "### Collaboration Analysis Details\n\n"
            for c in report.collaboration_analysis:
                md += f"```\n{c.to_text()}\n```\n\n"

        if report.design_quality:
            md += "### Design Quality Assessment Details\n\n"
            for d in report.design_quality:
                md += f"```\n{d.to_text()}\n```\n\n"

        if report.risk_analysis:
            md += "### Risk Assessment Details\n\n"
            for r in report.risk_analysis:
                md += f"```\n{r.to_text()}\n```\n\n"

        return md

    def get_available_tools(self) -> List[str]:
        return [
            "insight_forge",
            "panorama_search",
            "quick_search",
            "interview_agents",
            "analyze_quote_accuracy",
            "identify_process_bottlenecks",
            "evaluate_collaboration_effectiveness",
            "analyze_design_quality",
            "predict_risk_exposure",
            "interview_project_team",
            "compare_scenario_outcomes",
        ]

    def execute_tool(
        self, tool_name: str, parameters: Optional[Dict[str, Any]] = None
    ) -> str:
        params = parameters or {}
        if tool_name == "insight_forge":
            return self.graph_tools.insight_forge(
                graph_id=self.graph_id,
                query=params.get("query", "engineering context"),
                simulation_requirement=params.get(
                    "simulation_requirement", "engineering report"
                ),
            ).to_text()
        if tool_name == "panorama_search":
            return self.graph_tools.panorama_search(
                graph_id=self.graph_id,
                query=params.get("query", "engineering context"),
            ).to_text()
        if tool_name == "quick_search":
            return self.graph_tools.quick_search(
                graph_id=self.graph_id,
                query=params.get("query", "engineering context"),
                limit=int(params.get("limit", 20)),
            ).to_text()
        if tool_name == "interview_agents":
            return self.graph_tools.interview_agents(
                simulation_id=self.simulation_id,
                interview_requirement=params.get(
                    "question", "What are the engineering concerns?"
                ),
                simulation_requirement=params.get(
                    "simulation_requirement", "engineering report"
                ),
                max_agents=int(params.get("max_agents", 5)),
            ).to_text()

        if tool_name == "analyze_quote_accuracy":
            return "\n\n".join(
                item.to_text()
                for item in self.tools.analyze_quote_accuracy(
                    self.graph_id, params.get("query", ""), int(params.get("limit", 20))
                )
            )
        if tool_name == "identify_process_bottlenecks":
            return "\n\n".join(
                item.to_text()
                for item in self.tools.identify_process_bottlenecks(
                    self.graph_id, params.get("query", ""), int(params.get("limit", 10))
                )
            )
        if tool_name == "evaluate_collaboration_effectiveness":
            return "\n\n".join(
                item.to_text()
                for item in self.tools.evaluate_collaboration_effectiveness(
                    self.graph_id, params.get("query", ""), int(params.get("limit", 10))
                )
            )
        if tool_name == "analyze_design_quality":
            return "\n\n".join(
                item.to_text()
                for item in self.tools.analyze_design_quality(
                    self.graph_id, params.get("query", ""), int(params.get("limit", 10))
                )
            )
        if tool_name == "predict_risk_exposure":
            return "\n\n".join(
                item.to_text()
                for item in self.tools.predict_risk_exposure(
                    self.graph_id, params.get("query", ""), int(params.get("limit", 10))
                )
            )
        if tool_name == "interview_project_team":
            return "\n\n".join(
                item.to_text()
                for item in self.tools.interview_project_team(
                    self.graph_id, params.get("topics", []), int(params.get("limit", 5))
                )
            )
        if tool_name == "compare_scenario_outcomes":
            return "\n\n".join(
                item.to_text()
                for item in self.tools.compare_scenario_outcomes(
                    self.graph_id,
                    params.get("scenario_names", []),
                    int(params.get("limit", 5)),
                )
            )

        return f"Unknown tool: {tool_name}"
