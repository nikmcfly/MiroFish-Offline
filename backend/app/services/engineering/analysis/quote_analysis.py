"""
Quote Analysis Module

Analyzes quotes from agent interactions in simulations.
Extracts speakers, sentiments, themes, and context.
Includes quote accuracy metrics: quoted vs actual, margin analysis, confidence calibration.
"""

from __future__ import annotations

import logging
import re as re_module
from typing import Any, Dict, List, Optional

from ....storage import GraphStorage
from ....utils.llm_client import LLMClient
from ....utils.logger import get_logger
from ..report_models import QuoteAccuracyResult

logger = get_logger("mirofish.quote_analysis")


class QuoteAnalysis:
    """
    Quote Analysis

    Provides specialized quote extraction and analysis for engineering reports.
    Analyzes speaker, sentiment, themes, and context.
    Includes quote accuracy analysis with quoted vs actual values, margin analysis,
    and confidence calibration.
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
        self, graph_id: str, query: str = "", limit: int = 20
    ) -> List[QuoteAccuracyResult]:
        """
        Analyze quotes from graph with accuracy metrics.

        Args:
            graph_id: Graph ID
            query: Optional query to focus analysis
            limit: Maximum quotes to analyze

        Returns:
            List of QuoteAccuracyResult with to_dict() and to_text() methods
        """
        logger.info(f"QuoteAnalysis.analyze: graph_id={graph_id}, limit={limit}")

        try:
            search_results = self.storage.search(
                graph_id=graph_id,
                query=query
                or "quote statement response opinion feedback estimate projection",
                limit=limit * 2,
                scope="edges",
            )

            quotes: List[QuoteAccuracyResult] = []
            seen_texts: set = set()

            edge_list = self._get_edges(search_results)

            for edge in edge_list:
                fact = self._get_fact(edge)
                if not fact or len(fact) < 15:
                    continue

                if self._looks_like_quote(fact):
                    quote_text = self._clean_text(fact)
                    if quote_text in seen_texts or len(quote_text) < 10:
                        continue
                    seen_texts.add(quote_text)

                    speaker, role = self._extract_speaker(edge)
                    sentiment = self._score_sentiment(quote_text)
                    themes = self._detect_themes(quote_text)

                    # Extract quote accuracy metrics
                    quoted_value, actual_value = self._extract_quote_values(quote_text)
                    margin_analysis = self._compute_margin_analysis(
                        quoted_value, actual_value
                    )
                    confidence = self._compute_confidence_calibration(fact, sentiment)

                    quotes.append(
                        QuoteAccuracyResult(
                            quote_text=quote_text,
                            speaker=speaker,
                            speaker_role=role,
                            context=self._build_context(edge),
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

            logger.info(f"QuoteAnalysis: analyzed {len(quotes)} quotes for accuracy")
            return quotes

        except Exception as e:
            logger.error(f"QuoteAnalysis.analyze failed: {e}")
            return []

    def summarize_quotes(
        self, quotes: List[QuoteAccuracyResult], focus: str = ""
    ) -> str:
        """
        Generate a text summary of quotes.

        Args:
            quotes: List of QuoteAccuracyResult
            focus: Optional focus area

        Returns:
            Summary string
        """
        if not quotes:
            return "No quotes found for analysis."

        lines = [
            f"Quote Analysis Summary (n={len(quotes)})",
            "",
        ]

        # Group by speaker
        by_speaker: Dict[str, List[QuoteAccuracyResult]] = {}
        for q in quotes:
            by_speaker.setdefault(q.speaker, []).append(q)

        for speaker, speaker_quotes in by_speaker.items():
            lines.append(f"**{speaker}** ({speaker_quotes[0].speaker_role}):")
            for q in speaker_quotes[:3]:
                truncated = (
                    q.quote_text[:100] + "..."
                    if len(q.quote_text) > 100
                    else q.quote_text
                )
                lines.append(f'  > "{truncated}"')
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

    def _looks_like_quote(self, text: str) -> bool:
        quote_chars = ['"', '"', '"', """, """, "「", "」", "『", "』"]
        text_stripped = text.strip()
        if text_stripped.startswith(tuple(quote_chars)):
            return True
        if text_stripped.endswith(tuple(quote_chars)):
            return True
        # Simple check for quote-like pattern: starts with quote char after whitespace
        return len(text_stripped) > 10 and text_stripped[0] in '"' + "'"

    def _clean_text(self, text: str) -> str:
        text = text.strip()
        quote_chars = ['"', '"', '"', """, """, "「", "」", "『", "』"]
        for ch in quote_chars:
            if text.startswith(ch):
                text = text[1:]
            if text.endswith(ch):
                text = text[:-1]
        # Remove leading/trailing quotes and whitespace
        text = re_module.sub(r'^["\']?\s*', "", text)
        text = re_module.sub(r'\s*["\']?\s*$', "", text)
        return text.strip()

    def _extract_speaker(self, edge: Dict[str, Any]) -> tuple:
        source = ""
        target = ""
        if isinstance(edge, dict):
            source = edge.get("source_node_name", "")
            target = edge.get("target_node_name", "")
        speaker = source or target or "Unknown Agent"
        role = self._infer_role(speaker)
        return speaker, role

    def _infer_role(self, name: str) -> str:
        name_lower = name.lower()
        roles = {
            "engineer": ["engineer", "dev", "tech"],
            "manager": ["manager", "lead", "director", "head"],
            "designer": ["designer", "ux", "ui"],
            "analyst": ["analyst", "data", "qa"],
            "executive": ["ceo", "cto", "cfo", "vp", "chief"],
        }
        for role, keywords in roles.items():
            if any(kw in name_lower for kw in keywords):
                return role
        return "Agent"

    def _score_sentiment(self, text: str) -> float:
        positive = [
            "good",
            "great",
            "excellent",
            "success",
            "improve",
            "benefit",
            "positive",
            "achieve",
            "effective",
        ]
        negative = [
            "bad",
            "poor",
            "fail",
            "problem",
            "issue",
            "risk",
            "negative",
            "concern",
            "bottleneck",
            "delay",
        ]
        text_lower = text.lower()
        pos = sum(1 for w in positive if w in text_lower)
        neg = sum(1 for w in negative if w in text_lower)
        total = pos + neg
        if total == 0:
            return 0.0
        return (pos - neg) / total

    def _detect_themes(self, text: str) -> List[str]:
        themes_map = {
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
        found = []
        for theme, keywords in themes_map.items():
            if any(kw in text_lower for kw in keywords):
                found.append(theme)
        return found[:3]

    def _build_context(self, edge: Dict[str, Any]) -> str:
        if isinstance(edge, dict):
            rel = edge.get("name", "")
            fact = edge.get("fact", "")[:50]
            if rel and rel != fact:
                return f"Related via: {rel}"
        return ""

    def _extract_quote_values(self, text: str) -> tuple:
        """Extract quoted and actual values from quote text."""
        # Look for numeric patterns like "$100" or "100 units"
        numbers = re_module.findall(
            r"[\$€£]?\d+(?:\.\d+)?%?(?:\s*(?:units?|hours?|days?|weeks?|months?|estimates?|projections?|quotes?|actuals?)?)?",
            text.lower(),
        )
        if len(numbers) >= 2:
            try:
                quoted = float(re_module.sub(r"[^\d.]", "", numbers[0]))
                actual = float(re_module.sub(r"[^\d.]", "", numbers[1]))
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
        if re_module.search(r"\d+", fact):
            confidence += 0.1

        # Adjust based on sentiment extremity
        if abs(sentiment) > 0.5:
            confidence -= 0.1

        return max(0.1, min(0.95, confidence))
