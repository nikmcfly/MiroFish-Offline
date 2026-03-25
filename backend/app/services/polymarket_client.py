"""
Polymarket client — fetches markets from the Gamma API
"""

import time
import requests
from typing import List, Optional, Dict, Any

from ..config import Config
from ..models.prediction import PredictionMarket
from ..utils.logger import get_logger
from ..utils.retry import retry_with_backoff

logger = get_logger('mirofish.polymarket')


class PolymarketClient:
    """Fetches prediction market data from Polymarket's Gamma API"""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or Config.POLYMARKET_GAMMA_URL

    @retry_with_backoff(max_retries=3, exceptions=(requests.RequestException,))
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

    @retry_with_backoff(max_retries=3, exceptions=(requests.RequestException,))
    def get_market(self, condition_id: str) -> Optional[PredictionMarket]:
        """Fetch a single market by condition_id"""
        url = f"{self.base_url}/markets/{condition_id}"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return self._parse_market(data)

    def fetch_resolved_markets(self, limit: int = 200) -> List[PredictionMarket]:
        """
        Fetch resolved (closed) markets from Polymarket.

        Args:
            limit: Max markets to return

        Returns:
            List of PredictionMarket objects with actual_outcome set
        """
        markets = []
        offset = 0
        page_size = min(limit, 100)

        while len(markets) < limit:
            try:
                params: Dict[str, Any] = {
                    "limit": page_size,
                    "closed": True,
                    "order": "volume",
                    "ascending": False,
                    "offset": offset,
                }

                url = f"{self.base_url}/markets"
                logger.info(f"Fetching resolved markets (offset={offset})")

                resp = requests.get(url, params=params, timeout=30)
                resp.raise_for_status()
                raw_markets = resp.json()

                if not isinstance(raw_markets, list) or len(raw_markets) == 0:
                    break

                for item in raw_markets:
                    market = self._parse_resolved_market(item)
                    if market is not None:
                        markets.append(market)
                        if len(markets) >= limit:
                            break

                offset += page_size

                # Courtesy delay between paginated fetches
                if len(markets) < limit and len(raw_markets) == page_size:
                    time.sleep(1.0)
                else:
                    break

            except requests.RequestException as e:
                logger.error(f"Failed to fetch resolved markets at offset {offset}: {e}")
                break

        logger.info(f"Fetched {len(markets)} resolved markets")
        return markets

    def _parse_resolved_market(self, data: Dict[str, Any]) -> Optional[PredictionMarket]:
        """Parse a resolved market, extracting actual outcome from resolution data."""
        market = self._parse_market(data)
        if market is None:
            return None

        # Determine actual outcome from tokens or resolution data
        tokens = data.get('tokens', [])
        actual_outcome = None

        if tokens:
            for token in tokens:
                winner = token.get('winner', False)
                if winner:
                    actual_outcome = token.get('outcome', '').upper()
                    break

        # If no winner token, check resolved status
        if actual_outcome is None:
            resolved = data.get('resolved', False)
            resolution = data.get('resolution', '')
            if resolved and resolution:
                actual_outcome = resolution.upper()

        if actual_outcome is None:
            logger.debug(f"Skipping unresolved market: {market.title}")
            return None

        market.active = False
        market.actual_outcome = actual_outcome
        return market

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
            logger.warning(f"Failed to parse market data: {e} — raw keys: {list(data.keys())}")
            return None
