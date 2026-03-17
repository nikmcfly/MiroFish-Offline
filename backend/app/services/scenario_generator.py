"""
Scenario Generator — converts a prediction market question into a simulation scenario
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass

from ..models.prediction import PredictionMarket
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger

logger = get_logger('mirofish.scenario_generator')


@dataclass
class ScenarioConfig:
    """Generated simulation scenario from a market question"""
    simulation_requirement: str
    context_document: str
    suggested_agent_count: int
    stance_distribution: Dict[str, float]  # {supportive: 0.4, opposing: 0.4, neutral: 0.2}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_requirement": self.simulation_requirement,
            "context_document": self.context_document,
            "suggested_agent_count": self.suggested_agent_count,
            "stance_distribution": self.stance_distribution,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScenarioConfig':
        return cls(
            simulation_requirement=data['simulation_requirement'],
            context_document=data['context_document'],
            suggested_agent_count=data.get('suggested_agent_count', 50),
            stance_distribution=data.get('stance_distribution', {
                "supportive": 0.4, "opposing": 0.4, "neutral": 0.2
            }),
        )


SCENARIO_SYSTEM_PROMPT = """You are a research analyst preparing a factual briefing for prediction market analysis.

Given a prediction market question, create a comprehensive factual context document. Your goal is ACCURACY, not balance — if the evidence overwhelmingly favors one outcome, say so clearly.

CRITICAL RULES:
1. The context document must be FACTUAL and evidence-based — include real data, precedents, and structural constraints
2. Clearly state which outcome the evidence favors and why
3. Include the strongest arguments for BOTH sides, but weight them by evidence quality
4. Note base rates, historical precedents, and known constraints that affect probability
5. Identify what would need to happen for the less likely outcome to occur

Output JSON with these fields:
{
    "simulation_requirement": "A clear framing of the question with key factors to consider.",
    "context_document": "A 500-1000 word factual briefing covering: current situation, key evidence for and against, base rates, historical precedents, structural constraints, stakeholder positions, and what would need to change for each outcome. Be honest about which side the evidence favors.",
    "suggested_agent_count": 20,
    "stance_distribution": {
        "supportive": 0.3,
        "opposing": 0.4,
        "neutral": 0.3
    }
}"""


class ScenarioGenerator:
    """Converts a prediction market question into a simulation scenario"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()

    def generate_scenario(self, market: PredictionMarket) -> ScenarioConfig:
        """
        Generate a balanced simulation scenario from a market question.

        Args:
            market: PredictionMarket with question and context

        Returns:
            ScenarioConfig ready for the simulation pipeline
        """
        user_message = self._build_prompt(market)

        messages = [
            {"role": "system", "content": SCENARIO_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        logger.info(f"Generating scenario for market: {market.title}")

        result = self.llm_client.chat_json(
            messages=messages,
            temperature=0.4,
            max_tokens=4096,
        )

        scenario = ScenarioConfig(
            simulation_requirement=result.get('simulation_requirement', ''),
            context_document=result.get('context_document', ''),
            suggested_agent_count=result.get('suggested_agent_count', 50),
            stance_distribution=result.get('stance_distribution', {
                "supportive": 0.35, "opposing": 0.35, "neutral": 0.30
            }),
        )

        logger.info(f"Scenario generated: {len(scenario.context_document)} chars context")
        return scenario

    def _build_prompt(self, market: PredictionMarket) -> str:
        """Build the user prompt from market data"""
        parts = [
            f"# Prediction Market Question",
            f"**Question:** {market.title}",
            f"**Outcomes:** {', '.join(market.outcomes)}",
            f"**Current Prices:** {', '.join(f'{o}: ${p:.2f}' for o, p in zip(market.outcomes, market.prices))}",
            f"**Trading Volume:** ${market.volume:,.0f}",
            f"**End Date:** {market.end_date}",
        ]

        if market.description:
            # Truncate very long descriptions
            desc = market.description[:3000]
            parts.append(f"\n**Market Description:**\n{desc}")

        parts.append(
            "\nCreate a balanced simulation scenario for this market. "
            "The simulation should produce organic discourse that reveals "
            "the collective intelligence of diverse agents debating this question."
        )

        return '\n'.join(parts)
