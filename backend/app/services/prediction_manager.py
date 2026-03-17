"""
Prediction Manager — orchestrates the full prediction pipeline:
market → scenario → project → graph → simulation → analysis → signal
"""

import time
from typing import Optional, Callable

from flask import current_app

from ..config import Config
from ..models.prediction import (
    PredictionMarket, PredictionRun, PredictionRunStatus,
    PredictionRunManager, TradingSignal, SentimentResult,
)
from ..models.project import ProjectManager
from ..services.polymarket_client import PolymarketClient
from ..services.scenario_generator import ScenarioGenerator
from ..services.sentiment_analyzer import SentimentAnalyzer
from ..services.ontology_generator import OntologyGenerator
from ..services.graph_builder import GraphBuilderService
from ..services.simulation_manager import SimulationManager, SimulationStatus
from ..services.simulation_runner import SimulationRunner, RunnerStatus
from ..models.task import TaskManager, TaskStatus
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger

logger = get_logger('mirofish.prediction_manager')


class PredictionManager:
    """Orchestrates the full prediction pipeline"""

    def __init__(self, storage=None):
        """
        Args:
            storage: Neo4jStorage instance (from app.extensions)
        """
        self.storage = storage
        self.llm_client = LLMClient()
        self.polymarket = PolymarketClient()
        self.scenario_gen = ScenarioGenerator(self.llm_client)
        self.sentiment_analyzer = SentimentAnalyzer(self.llm_client)
        self.ontology_gen = OntologyGenerator(self.llm_client)
        self.sim_manager = SimulationManager()

    def run_prediction(
        self,
        market: PredictionMarket,
        run: PredictionRun,
        progress_callback: Optional[Callable] = None,
    ) -> PredictionRun:
        """
        Execute the full prediction pipeline.

        This runs synchronously (called from a background thread).

        Args:
            market: The market to predict
            run: PredictionRun to update with progress
            progress_callback: Optional (stage, progress, message) callback
        """
        try:
            run.market = market.to_dict()
            self._update(run, PredictionRunStatus.FETCHING_MARKET, "Market data loaded", progress_callback)

            # Step 1: Generate scenario
            self._update(run, PredictionRunStatus.GENERATING_SCENARIO, "Generating simulation scenario...", progress_callback)
            scenario = self.scenario_gen.generate_scenario(market)
            run.scenario = scenario.to_dict()
            PredictionRunManager.save_run(run)

            # Step 2: Create project with synthetic document
            self._update(run, PredictionRunStatus.CREATING_PROJECT, "Creating project...", progress_callback)
            project = ProjectManager.create_project(name=f"Prediction: {market.title[:80]}")
            run.project_id = project.project_id

            # Save context document as extracted text
            ProjectManager.save_extracted_text(project.project_id, scenario.context_document)
            project.total_text_length = len(scenario.context_document)
            project.simulation_requirement = scenario.simulation_requirement
            ProjectManager.save_project(project)
            PredictionRunManager.save_run(run)

            # Step 3: Generate ontology
            self._update(run, PredictionRunStatus.BUILDING_GRAPH, "Generating ontology...", progress_callback)
            ontology = self.ontology_gen.generate(
                document_texts=[scenario.context_document],
                simulation_requirement=scenario.simulation_requirement,
            )
            project.ontology = ontology
            project.analysis_summary = ontology.get('analysis_summary', '')
            ProjectManager.save_project(project)

            # Step 4: Build graph (synchronous — wait for completion)
            self._update(run, PredictionRunStatus.BUILDING_GRAPH, "Building knowledge graph...", progress_callback)
            graph_builder = GraphBuilderService(self.storage)
            task_id = graph_builder.build_graph_async(
                text=scenario.context_document,
                ontology=ontology,
                graph_name=f"pred_{run.run_id}",
                chunk_size=Config.DEFAULT_CHUNK_SIZE,
                chunk_overlap=Config.DEFAULT_CHUNK_OVERLAP,
            )

            # Poll for graph build completion
            task_manager = TaskManager()
            graph_id = self._wait_for_task(task_manager, task_id, "graph build", progress_callback, run)

            if not graph_id:
                raise RuntimeError("Graph build failed or timed out")

            run.graph_id = graph_id
            project.graph_id = graph_id
            ProjectManager.save_project(project)
            PredictionRunManager.save_run(run)

            # Step 5: Create and prepare simulation
            self._update(run, PredictionRunStatus.PREPARING_SIMULATION, "Preparing simulation...", progress_callback)
            sim_state = self.sim_manager.create_simulation(
                project_id=project.project_id,
                graph_id=graph_id,
                enable_twitter=False,  # Reddit-only for richer discourse
                enable_reddit=True,
            )
            run.simulation_id = sim_state.simulation_id
            PredictionRunManager.save_run(run)

            # Get entity types from ontology
            entity_types = [et['name'] for et in ontology.get('entity_types', [])]

            self.sim_manager.prepare_simulation(
                simulation_id=sim_state.simulation_id,
                simulation_requirement=scenario.simulation_requirement,
                document_text=scenario.context_document,
                defined_entity_types=entity_types,
                use_llm_for_profiles=True,
                parallel_profile_count=3,
                storage=self.storage,
            )

            # Step 6: Run simulation
            self._update(run, PredictionRunStatus.RUNNING_SIMULATION, "Running simulation...", progress_callback)
            max_rounds = Config.PREDICTION_DEFAULT_ROUNDS
            SimulationRunner.start_simulation(
                simulation_id=sim_state.simulation_id,
                platform="reddit",
                max_rounds=max_rounds,
                enable_graph_memory_update=False,
            )

            # Poll for simulation completion
            self._wait_for_simulation(sim_state.simulation_id, progress_callback, run)

            # Step 7: Analyze sentiment
            self._update(run, PredictionRunStatus.ANALYZING, "Analyzing simulation output...", progress_callback)
            sentiment = self.sentiment_analyzer.analyze(
                simulation_id=sim_state.simulation_id,
                market_question=market.title,
                platform="reddit",
            )
            run.sentiment = sentiment.to_dict()
            PredictionRunManager.save_run(run)

            # Step 8: Generate trading signal
            signal = self._generate_signal(market, sentiment)
            run.signal = signal.to_dict()

            self._update(run, PredictionRunStatus.COMPLETED, "Prediction complete", progress_callback)
            return run

        except Exception as e:
            logger.error(f"Prediction pipeline failed: {e}", exc_info=True)
            run.status = PredictionRunStatus.FAILED
            run.error = str(e)
            run.progress_message = f"Failed: {str(e)}"
            PredictionRunManager.save_run(run)
            return run

    def _update(self, run: PredictionRun, status: PredictionRunStatus, message: str, callback=None):
        """Update run status and notify"""
        run.status = status
        run.progress_message = message
        PredictionRunManager.save_run(run)
        if callback:
            callback(status.value, message)
        logger.info(f"[{run.run_id}] {status.value}: {message}")

    def _wait_for_task(self, task_manager, task_id, task_name, callback, run, timeout=600):
        """Poll TaskManager until task completes. Returns result graph_id or None."""
        start = time.time()
        while time.time() - start < timeout:
            task = task_manager.get_task(task_id)
            if not task:
                time.sleep(2)
                continue

            if task.status == TaskStatus.COMPLETED:
                result = task.result or {}
                return result.get('graph_id')

            if task.status == TaskStatus.FAILED:
                raise RuntimeError(f"{task_name} failed: {task.error}")

            # Update progress message
            if task.message:
                run.progress_message = f"Building graph: {task.message}"
                PredictionRunManager.save_run(run)

            time.sleep(3)

        raise RuntimeError(f"{task_name} timed out after {timeout}s")

    def _wait_for_simulation(self, simulation_id, callback, run, timeout=7200):
        """Poll simulation runner until it completes"""
        start = time.time()
        while time.time() - start < timeout:
            run_state = SimulationRunner.get_run_state(simulation_id)

            if run_state is None:
                time.sleep(3)
                continue

            status = run_state.runner_status

            if status in (RunnerStatus.COMPLETED, RunnerStatus.STOPPED):
                logger.info(f"Simulation {simulation_id} completed")
                return

            if status == RunnerStatus.FAILED:
                raise RuntimeError(f"Simulation failed: {run_state.error}")

            # Update progress
            if run_state.current_round > 0:
                msg = f"Simulation round {run_state.current_round}/{run_state.total_rounds}"
                run.progress_message = msg
                PredictionRunManager.save_run(run)

            time.sleep(5)

        raise RuntimeError(f"Simulation timed out after {timeout}s")

    def _generate_signal(self, market: PredictionMarket, sentiment: SentimentResult) -> TradingSignal:
        """Compare simulated probability vs market price to generate trading signal"""
        # Market YES price
        market_prob = market.prices[0] if market.prices else 0.5
        sim_prob = sentiment.simulated_probability

        edge = sim_prob - market_prob
        threshold = Config.PREDICTION_SIGNAL_THRESHOLD

        if edge > threshold:
            direction = "BUY_YES"
            reasoning = (
                f"Simulated probability ({sim_prob:.1%}) is {edge:.1%} higher than "
                f"market price ({market_prob:.1%}). Agents lean toward YES."
            )
        elif edge < -threshold:
            direction = "BUY_NO"
            reasoning = (
                f"Simulated probability ({sim_prob:.1%}) is {abs(edge):.1%} lower than "
                f"market price ({market_prob:.1%}). Agents lean toward NO."
            )
        else:
            direction = "HOLD"
            reasoning = (
                f"Simulated probability ({sim_prob:.1%}) is within threshold of "
                f"market price ({market_prob:.1%}). No clear edge."
            )

        return TradingSignal(
            direction=direction,
            edge=edge,
            confidence=sentiment.confidence,
            reasoning=reasoning,
            simulated_probability=sim_prob,
            market_probability=market_prob,
        )
