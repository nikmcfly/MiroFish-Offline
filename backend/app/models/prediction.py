"""
Prediction Market data models and persistence
"""

import os
import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass, field

from ..config import Config


class PredictionRunStatus(str, Enum):
    FETCHING_MARKET = "fetching_market"
    GENERATING_SCENARIO = "generating_scenario"
    RUNNING_SIMULATION = "running_simulation"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PredictionMarket:
    """Polymarket market data"""
    condition_id: str
    title: str
    slug: str
    description: str
    outcomes: List[str]
    prices: List[float]
    volume: float
    liquidity: float
    end_date: str
    active: bool = True
    actual_outcome: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "condition_id": self.condition_id,
            "title": self.title,
            "slug": self.slug,
            "description": self.description,
            "outcomes": self.outcomes,
            "prices": self.prices,
            "volume": self.volume,
            "liquidity": self.liquidity,
            "end_date": self.end_date,
            "active": self.active,
        }
        if self.actual_outcome is not None:
            d["actual_outcome"] = self.actual_outcome
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PredictionMarket':
        return cls(
            condition_id=data.get('condition_id', ''),
            title=data.get('title', ''),
            slug=data.get('slug', ''),
            description=data.get('description', ''),
            outcomes=data.get('outcomes', []),
            prices=data.get('prices', []),
            volume=data.get('volume', 0),
            liquidity=data.get('liquidity', 0),
            end_date=data.get('end_date', ''),
            active=data.get('active', True),
            actual_outcome=data.get('actual_outcome'),
        )


@dataclass
class TradingSignal:
    """Trading signal from prediction analysis"""
    direction: str  # BUY_YES, BUY_NO, HOLD
    edge: float  # simulated_prob - market_prob (signed)
    confidence: float  # 0-1
    reasoning: str
    simulated_probability: float
    market_probability: float
    category: Optional[str] = None
    confidence_tier: Optional[str] = None  # HIGH, MEDIUM, LOW

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "direction": self.direction,
            "edge": round(self.edge, 4),
            "confidence": round(self.confidence, 4),
            "reasoning": self.reasoning,
            "simulated_probability": round(self.simulated_probability, 4),
            "market_probability": round(self.market_probability, 4),
        }
        if self.category is not None:
            d["category"] = self.category
        if self.confidence_tier is not None:
            d["confidence_tier"] = self.confidence_tier
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TradingSignal':
        return cls(
            direction=data['direction'],
            edge=data['edge'],
            confidence=data['confidence'],
            reasoning=data['reasoning'],
            simulated_probability=data['simulated_probability'],
            market_probability=data['market_probability'],
            category=data.get('category'),
            confidence_tier=data.get('confidence_tier'),
        )


@dataclass
class SentimentResult:
    """Result from sentiment analysis of simulation"""
    simulated_probability: float
    confidence: float
    stance_counts: Dict[str, int]  # {for: N, against: N, neutral: N}
    key_arguments_for: List[str]
    key_arguments_against: List[str]
    total_posts_analyzed: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulated_probability": round(self.simulated_probability, 4),
            "confidence": round(self.confidence, 4),
            "stance_counts": self.stance_counts,
            "key_arguments_for": self.key_arguments_for,
            "key_arguments_against": self.key_arguments_against,
            "total_posts_analyzed": self.total_posts_analyzed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SentimentResult':
        return cls(
            simulated_probability=data['simulated_probability'],
            confidence=data['confidence'],
            stance_counts=data['stance_counts'],
            key_arguments_for=data['key_arguments_for'],
            key_arguments_against=data['key_arguments_against'],
            total_posts_analyzed=data['total_posts_analyzed'],
        )


@dataclass
class PredictionRun:
    """Full prediction run state"""
    run_id: str
    status: PredictionRunStatus
    created_at: str
    updated_at: str

    # Market info
    market: Optional[Dict[str, Any]] = None

    # Pipeline IDs
    project_id: Optional[str] = None
    graph_id: Optional[str] = None
    simulation_id: Optional[str] = None

    # Scenario
    scenario: Optional[Dict[str, Any]] = None

    # Results
    sentiment: Optional[Dict[str, Any]] = None
    signal: Optional[Dict[str, Any]] = None

    # Error
    error: Optional[str] = None
    progress_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status.value if isinstance(self.status, PredictionRunStatus) else self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "market": self.market,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "simulation_id": self.simulation_id,
            "scenario": self.scenario,
            "sentiment": self.sentiment,
            "signal": self.signal,
            "error": self.error,
            "progress_message": self.progress_message,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PredictionRun':
        status = data.get('status', 'fetching_market')
        if isinstance(status, str):
            status = PredictionRunStatus(status)
        return cls(
            run_id=data['run_id'],
            status=status,
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
            market=data.get('market'),
            project_id=data.get('project_id'),
            graph_id=data.get('graph_id'),
            simulation_id=data.get('simulation_id'),
            scenario=data.get('scenario'),
            sentiment=data.get('sentiment'),
            signal=data.get('signal'),
            error=data.get('error'),
            progress_message=data.get('progress_message', ''),
        )


class PredictionRunManager:
    """Manages prediction run persistence — follows ProjectManager pattern"""

    PREDICTIONS_DIR = Config.PREDICTION_DATA_DIR

    @classmethod
    def _ensure_dir(cls):
        os.makedirs(cls.PREDICTIONS_DIR, exist_ok=True)

    @classmethod
    def _get_run_dir(cls, run_id: str) -> str:
        return os.path.join(cls.PREDICTIONS_DIR, run_id)

    @classmethod
    def _get_run_path(cls, run_id: str) -> str:
        return os.path.join(cls._get_run_dir(run_id), 'run.json')

    @classmethod
    def create_run(cls) -> PredictionRun:
        cls._ensure_dir()
        run_id = f"pred_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        run = PredictionRun(
            run_id=run_id,
            status=PredictionRunStatus.FETCHING_MARKET,
            created_at=now,
            updated_at=now,
        )
        run_dir = cls._get_run_dir(run_id)
        os.makedirs(run_dir, exist_ok=True)
        cls.save_run(run)
        return run

    @classmethod
    def save_run(cls, run: PredictionRun) -> None:
        run.updated_at = datetime.now().isoformat()
        run_path = cls._get_run_path(run.run_id)
        os.makedirs(os.path.dirname(run_path), exist_ok=True)
        with open(run_path, 'w', encoding='utf-8') as f:
            json.dump(run.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def get_run(cls, run_id: str) -> Optional[PredictionRun]:
        run_path = cls._get_run_path(run_id)
        if not os.path.exists(run_path):
            return None
        with open(run_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return PredictionRun.from_dict(data)

    @classmethod
    def list_runs(cls, limit: int = 50) -> List[PredictionRun]:
        cls._ensure_dir()
        runs = []
        for name in os.listdir(cls.PREDICTIONS_DIR):
            run = cls.get_run(name)
            if run:
                runs.append(run)
        runs.sort(key=lambda r: r.created_at, reverse=True)
        return runs[:limit]

    @classmethod
    def delete_run(cls, run_id: str) -> bool:
        import shutil
        run_dir = cls._get_run_dir(run_id)
        if not os.path.exists(run_dir):
            return False
        shutil.rmtree(run_dir)
        return True
