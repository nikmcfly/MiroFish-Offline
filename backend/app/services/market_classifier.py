"""
Market classifier — assigns a category to each market via LLM.
Results are cached in SQLite to avoid re-classifying the same market.
"""

from typing import Dict, List, Optional

from ..models.prediction import PredictionMarket
from ..storage.sqlite_store import SQLiteStore
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger

logger = get_logger('mirofish.market_classifier')

CATEGORIES = [
    "politics", "sports", "crypto", "economics",
    "science", "entertainment", "other",
]

CLASSIFY_SYSTEM_PROMPT = f"""You are a market classifier. Given a prediction market title and description,
classify it into exactly ONE of these categories: {', '.join(CATEGORIES)}.

Respond with JSON: {{"category": "<category>"}}

Rules:
- "politics" = elections, legislation, government policy, geopolitics
- "sports" = athletic competitions, tournaments, player performance
- "crypto" = cryptocurrency prices, blockchain events, DeFi
- "economics" = economic indicators, interest rates, stock market, commodities
- "science" = scientific discoveries, space, climate, health/medicine
- "entertainment" = movies, music, awards, celebrity events, TV, gaming
- "other" = anything that doesn't clearly fit above"""

# Confidence tier thresholds based on absolute edge size
TIER_THRESHOLD_HIGH = 0.15   # |edge| >= 15%
TIER_THRESHOLD_MEDIUM = 0.08  # |edge| >= 8%


def compute_confidence_tier(edge: float) -> str:
    """Assign HIGH/MEDIUM/LOW tier based on absolute edge magnitude."""
    abs_edge = abs(edge)
    if abs_edge >= TIER_THRESHOLD_HIGH:
        return "HIGH"
    elif abs_edge >= TIER_THRESHOLD_MEDIUM:
        return "MEDIUM"
    return "LOW"


class MarketClassifier:
    """Classifies prediction markets into categories using LLM with SQLite caching."""

    def __init__(self, store: SQLiteStore, llm_client: Optional[LLMClient] = None):
        self.store = store
        self.llm_client = llm_client or LLMClient()

    def classify(self, market_id: str, title: str, description: str = "") -> str:
        """Classify a single market. Returns cached result if available."""
        cached = self.store.get_market_category(market_id)
        if cached:
            return cached

        category = self._llm_classify(title, description)
        self.store.save_market_category(market_id, category)
        logger.info(f"Classified market '{title[:50]}' as '{category}'")
        return category

    def classify_batch(self, markets: List[PredictionMarket]) -> Dict[str, str]:
        """Classify a batch of markets. Only LLM-calls uncached ones."""
        results = {}
        for market in markets:
            results[market.condition_id] = self.classify(
                market.condition_id, market.title, market.description or ""
            )
        return results

    def _llm_classify(self, title: str, description: str) -> str:
        """Call LLM to classify a market."""
        user_msg = f"Title: {title}"
        if description:
            user_msg += f"\nDescription: {description[:500]}"

        try:
            result = self.llm_client.chat_json(
                messages=[
                    {"role": "system", "content": CLASSIFY_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.1,
            )
            category = result.get("category", "other").lower().strip()
            if category not in CATEGORIES:
                logger.warning(f"LLM returned unknown category '{category}', defaulting to 'other'")
                return "other"
            return category
        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            return "other"
