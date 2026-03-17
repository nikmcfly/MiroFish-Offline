"""
Direct Debate Simulator — replaces OASIS multi-agent simulation with a single
LLM call that simulates a structured multi-perspective debate.

~30 seconds per market instead of ~30 minutes with OASIS.
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from ..models.prediction import PredictionMarket, SentimentResult
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger

logger = get_logger('mirofish.debate_simulator')

DEBATE_SYSTEM_PROMPT = """You are simulating a multi-perspective online debate about a prediction market question.

Generate a realistic Reddit-style discussion with 15-25 posts from diverse participants. Each post should represent a distinct perspective and argument.

CRITICAL RULES:
1. Include roughly equal representation of supporters (YES), opponents (NO), and neutral/analytical voices
2. Posts should contain substantive arguments, not just opinions
3. Include domain experts, general public, contrarians, and fence-sitters
4. Arguments should reference real-world evidence, data, historical precedents
5. Some posts should respond to or rebut other arguments
6. Do NOT let your own assessment bias the distribution — present the strongest case for BOTH sides

Output JSON with this exact structure:
{
    "posts": [
        {
            "author": "username",
            "author_type": "expert|general_public|stakeholder|analyst|contrarian",
            "stance": "for|against|neutral",
            "confidence": 0.8,
            "content": "The full post text with substantive argument...",
            "key_argument": "One-sentence summary of the core argument"
        }
    ],
    "debate_summary": "Brief summary of the overall debate dynamics",
    "strongest_for": "The single strongest argument for YES",
    "strongest_against": "The single strongest argument for NO"
}"""


class DebateSimulator:
    """Simulates multi-perspective debate via direct LLM call"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()

    def simulate_debate(
        self,
        market: PredictionMarket,
        context_document: str,
    ) -> SentimentResult:
        """
        Run a simulated debate and return sentiment analysis.

        Args:
            market: The prediction market question
            context_document: Background context from scenario generator

        Returns:
            SentimentResult with probability and breakdown
        """
        user_prompt = self._build_prompt(market, context_document)

        messages = [
            {"role": "system", "content": DEBATE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        logger.info(f"Running direct debate simulation for: {market.title}")

        result = self.llm_client.chat_json(
            messages=messages,
            temperature=0.6,
            max_tokens=8192,
        )

        posts = result.get("posts", [])
        logger.info(f"Debate generated {len(posts)} posts")

        return self._analyze_posts(
            posts,
            strongest_for=result.get("strongest_for", ""),
            strongest_against=result.get("strongest_against", ""),
        )

    def _build_prompt(self, market: PredictionMarket, context: str) -> str:
        parts = [
            "# Prediction Market Question",
            f"**Question:** {market.title}",
            f"**Current Market Prices:** YES {market.prices[0]:.0%} / NO {market.prices[1]:.0%}",
            f"**Trading Volume:** ${market.volume:,.0f}",
            f"**End Date:** {market.end_date}",
        ]

        if market.description:
            parts.append(f"\n**Market Description:**\n{market.description[:2000]}")

        if context:
            parts.append(f"\n**Background Context:**\n{context[:3000]}")

        parts.append(
            "\nSimulate a realistic Reddit debate thread about this question. "
            "Include 15-25 posts from diverse participants with substantive arguments."
        )

        return "\n".join(parts)

    def _analyze_posts(
        self,
        posts: List[Dict[str, Any]],
        strongest_for: str = "",
        strongest_against: str = "",
    ) -> SentimentResult:
        """Compute probability from debate posts"""
        stance_counts = {"for": 0, "against": 0, "neutral": 0}
        weighted_for = 0.0
        weighted_against = 0.0
        args_for = []
        args_against = []

        for post in posts:
            stance = post.get("stance", "neutral")
            confidence = float(post.get("confidence", 0.5))
            key_arg = post.get("key_argument", "")

            if stance in stance_counts:
                stance_counts[stance] += 1
            else:
                stance_counts["neutral"] += 1
                stance = "neutral"

            if stance == "for":
                weighted_for += confidence
                if key_arg:
                    args_for.append(key_arg)
            elif stance == "against":
                weighted_against += confidence
                if key_arg:
                    args_against.append(key_arg)

        # P(Yes) = weighted_for / (weighted_for + weighted_against)
        total_opinionated = weighted_for + weighted_against
        if total_opinionated > 0:
            sim_prob = weighted_for / total_opinionated
        else:
            sim_prob = 0.5

        # Confidence based on sample size and agreement
        total_classified = stance_counts["for"] + stance_counts["against"]
        if total_classified > 0:
            agreement = max(stance_counts["for"], stance_counts["against"]) / total_classified
            sample_factor = min(total_classified / 10, 1.0)
            result_confidence = agreement * sample_factor
        else:
            result_confidence = 0.0

        # Add strongest arguments at the top
        if strongest_for and strongest_for not in args_for:
            args_for.insert(0, strongest_for)
        if strongest_against and strongest_against not in args_against:
            args_against.insert(0, strongest_against)

        # Deduplicate
        args_for = list(dict.fromkeys(args_for))[:5]
        args_against = list(dict.fromkeys(args_against))[:5]

        return SentimentResult(
            simulated_probability=sim_prob,
            confidence=result_confidence,
            stance_counts=stance_counts,
            key_arguments_for=args_for,
            key_arguments_against=args_against,
            total_posts_analyzed=len(posts),
        )
