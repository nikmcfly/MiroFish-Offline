"""
Polymarket client — fetches active markets from the Gamma API
"""

import requests
from typing import List, Optional, Dict, Any

from ..config import Config
from ..models.prediction import PredictionMarket
from ..utils.logger import get_logger

logger = get_logger('mirofish.polymarket')


class PolymarketClient:
    """Fetches prediction market data from Polymarket's Gamma API"""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or Config.POLYMARKET_GAMMA_URL

    def fetch_active_markets(
        self,
        min_volume: float = 10000,
        limit: int = 50,
        search: Optional[str] = None,
    ) -> List[PredictionMarket]:
        """
        Fetch active binary markets from Polymarket.

        Args:
            min_volume: Minimum trading volume filter
            limit: Max markets to return
            search: Optional search query

        Returns:
            List of PredictionMarket objects
        """
        try:
            params: Dict[str, Any] = {
                "limit": min(limit, 100),
                "active": True,
                "closed": False,
                "order": "volume",
                "ascending": False,
            }

            url = f"{self.base_url}/markets"
            logger.info(f"Fetching markets from {url}")

            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            raw_markets = resp.json()

            if not isinstance(raw_markets, list):
                logger.warning(f"Unexpected response format: {type(raw_markets)}")
                return []

            markets = []
            for item in raw_markets:
                market = self._parse_market(item)
                if market is None:
                    continue
                if market.volume < min_volume:
                    continue
                if search and search.lower() not in market.title.lower():
                    continue
                markets.append(market)
                if len(markets) >= limit:
                    break

            logger.info(f"Fetched {len(markets)} markets (filtered from {len(raw_markets)})")
            return markets

        except requests.RequestException as e:
            logger.error(f"Failed to fetch markets: {e}")
            raise

    def get_market(self, condition_id: str) -> Optional[PredictionMarket]:
        """Fetch a single market by condition_id"""
        try:
            url = f"{self.base_url}/markets/{condition_id}"
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return self._parse_market(data)
        except requests.RequestException as e:
            logger.error(f"Failed to fetch market {condition_id}: {e}")
            return None

    def _parse_market(self, data: Dict[str, Any]) -> Optional[PredictionMarket]:
        """Parse raw Gamma API response into PredictionMarket"""
        try:
            import json as _json

            # Gamma API returns tokens with prices for each outcome
            tokens = data.get('tokens', [])
            outcomes = []
            prices = []

            if tokens:
                for token in tokens:
                    outcomes.append(token.get('outcome', 'Unknown'))
                    prices.append(float(token.get('price', 0)))
            else:
                # Gamma API returns outcomes/outcomePrices as JSON strings
                raw_outcomes = data.get('outcomes', '["Yes", "No"]')
                raw_prices = data.get('outcomePrices', '["0.5", "0.5"]')

                # Parse if string, use directly if already list
                if isinstance(raw_outcomes, str):
                    outcomes = _json.loads(raw_outcomes)
                else:
                    outcomes = raw_outcomes or ['Yes', 'No']

                if isinstance(raw_prices, str):
                    prices = [float(p) for p in _json.loads(raw_prices)]
                elif isinstance(raw_prices, list):
                    prices = [float(p) for p in raw_prices]
                else:
                    prices = [0.5, 0.5]

            return PredictionMarket(
                condition_id=data.get('conditionId', data.get('condition_id', '')),
                title=data.get('question', data.get('title', 'Unknown')),
                slug=data.get('slug', ''),
                description=data.get('description', ''),
                outcomes=outcomes,
                prices=prices,
                volume=float(data.get('volume', 0) or 0),
                liquidity=float(data.get('liquidity', 0) or 0),
                end_date=data.get('endDate', data.get('end_date', '')),
                active=data.get('active', True),
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Failed to parse market: {e}")
            return None
