"""
Database Integration for Digital Twin

Connects the Digital Twin to live PostgreSQL databases:
- ERP database (machines, operators, jobs, materials)
- Sensor database (real-time machine data)
- Digital Twin database (config, snapshots, predictions)

This module provides adapters that can be configured to match your schema.
"""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Iterator
import json
import logging

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from ..scheduling.models import (
    Machine,
    MachineType,
    MachineStatus,
    Operator,
    LaborSkill,
    Job,
    JobPriority,
    Operation,
)
from ..utils.logger import get_logger

logger = get_logger("mirofish.digital_twin.db_integration")


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class DatabaseConfig:
    """Database connection configuration"""

    name: str  # "erp", "sensor", "dt"
    host: str
    port: int
    database: str
    username: str
    password: str
    schema: str = "public"
    pool_size: int = 10
    max_overflow: int = 20

    @property
    def connection_string(self) -> str:
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class TableMapping:
    """Maps your table/column names to Digital Twin expected fields"""

    # Machines table
    machines_table: str = "machines"
    machine_id_column: str = "machine_id"
    machine_name_column: str = "name"
    machine_type_column: str = "machine_type"
    machine_status_column: str = "status"
    machine_capacity_column: str = "capacity"
    machine_efficiency_column: str = "efficiency"
    machine_location_column: str = "location"

    # Operators table
    operators_table: str = "employees"
    operator_id_column: str = "employee_id"
    operator_name_column: str = "name"
    operator_skills_column: str = "skills"  # Can be JSON array or comma-separated
    operator_shift_start_column: str = "shift_start"
    operator_shift_end_column: str = "shift_end"
    operator_status_column: str = "status"

    # Jobs table
    jobs_table: str = "work_orders"
    job_id_column: str = "work_order_id"
    job_name_column: str = "name"
    job_priority_column: str = "priority"
    job_status_column: str = "status"
    job_due_date_column: str = "due_date"

    # Sensor data table
    sensor_table: str = "machine_sensor_data"
    sensor_machine_id_column: str = "machine_id"
    sensor_timestamp_column: str = "timestamp"
    sensor_metric_column: str = "metric_type"
    sensor_value_column: str = "value"

    def get_column_mapping(self, table: str) -> Dict[str, str]:
        """Get column mapping for a specific table"""
        mappings = {
            self.machines_table: {
                "machine_id": self.machine_id_column,
                "name": self.machine_name_column,
                "machine_type": self.machine_type_column,
                "status": self.machine_status_column,
                "capacity": self.machine_capacity_column,
                "efficiency": self.machine_efficiency_column,
                "location": self.machine_location_column,
            },
            self.operators_table: {
                "operator_id": self.operator_id_column,
                "name": self.operator_name_column,
                "skills": self.operator_skills_column,
                "shift_start": self.operator_shift_start_column,
                "shift_end": self.operator_shift_end_column,
                "status": self.operator_status_column,
            },
            self.jobs_table: {
                "job_id": self.job_id_column,
                "name": self.job_name_column,
                "priority": self.job_priority_column,
                "status": self.job_status_column,
                "due_date": self.job_due_date_column,
            },
            self.sensor_table: {
                "machine_id": self.sensor_machine_id_column,
                "timestamp": self.sensor_timestamp_column,
                "metric_type": self.sensor_metric_column,
                "value": self.sensor_value_column,
            },
        }
        return mappings.get(table, {})


# =============================================================================
# Connection Manager
# =============================================================================


class DatabaseConnectionManager:
    """
    Manages connections to multiple PostgreSQL databases.

    Supports:
    - ERP database (machines, operators, jobs)
    - Sensor database (real-time data)
    - Digital Twin database (snapshots, predictions)
    """

    def __init__(self):
        self._engines: Dict[str, Engine] = {}
        self._session_factories: Dict[str, sessionmaker] = {}

    def register_database(self, config: DatabaseConfig) -> None:
        """Register a database connection"""
        engine = create_engine(
            config.connection_string,
            poolclass=QueuePool,
            pool_size=config.pool_size,
            max_overflow=config.max_overflow,
            pool_pre_ping=True,  # Health check connections
            pool_recycle=3600,  # Recycle connections after 1 hour
        )

        self._engines[config.name] = engine
        self._session_factories[config.name] = sessionmaker(bind=engine)

        logger.info(f"Registered database: {config.name} ({config.database})")

    @contextmanager
    def get_session(self, db_name: str) -> Iterator[Session]:
        """Get a database session (context manager)"""
        if db_name not in self._session_factories:
            raise ValueError(f"Database not registered: {db_name}")

        session = self._session_factories[db_name]()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_engine(self, db_name: str) -> Engine:
        """Get SQLAlchemy engine for raw queries"""
        if db_name not in self._engines:
            raise ValueError(f"Database not registered: {db_name}")
        return self._engines[db_name]

    def execute_query(
        self, db_name: str, query: str, params: Optional[Dict] = None
    ) -> List[Dict]:
        """Execute a raw SQL query and return results as dicts"""
        engine = self.get_engine(db_name)

        with engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            return [dict(row._mapping) for row in result]

    def test_connection(self, db_name: str) -> bool:
        """Test database connectivity"""
        try:
            engine = self.get_engine(db_name)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database connection failed ({db_name}): {e}")
            return False

    def get_table_names(self, db_name: str, schema: str = "public") -> List[str]:
        """Get list of tables in database (for discovery)"""
        engine = self.get_engine(db_name)
        inspector = inspect(engine)
        return inspector.get_table_names(schema=schema)


# =============================================================================
# ERP Adapter
# =============================================================================


class ERPAdapter:
    """
    Adapter for ERP database.

    Reads machines, operators, jobs, materials from your ERP system.

    Example usage:
        adapter = ERPAdapter(connection_manager, table_mapping)
        machines = adapter.get_machines()
        jobs = adapter.get_active_jobs()
    """

    def __init__(
        self,
        db_manager: DatabaseConnectionManager,
        table_mapping: TableMapping,
        db_name: str = "erp",
    ):
        self.db = db_manager
        self.mapping = table_mapping
        self.db_name = db_name

    def get_machines(self, active_only: bool = True) -> List[Machine]:
        """
        Fetch machines from ERP.

        Customize the query to match your schema:
        - Add/remove columns
        - Add filters (department, location, etc.)
        - Join with additional tables
        """
        m = self.mapping

        query = f"""
            SELECT 
                {m.machine_id_column} as machine_id,
                {m.machine_name_column} as name,
                {m.machine_type_column} as machine_type,
                {m.machine_status_column} as status,
                COALESCE({m.machine_capacity_column}, 10.0) as capacity,
                COALESCE({m.machine_efficiency_column}, 0.9) as efficiency,
                {m.machine_location_column} as location
            FROM {m.machines_table}
            WHERE 1=1
            {"AND " + m.machine_status_column + " = 'ACTIVE'" if active_only else ""}
            ORDER BY {m.machine_name_column}
        """

        rows = self.db.execute_query(self.db_name, query)

        machines = []
        for row in rows:
            try:
                machine = Machine(
                    machine_id=str(row["machine_id"]),
                    name=row["name"],
                    machine_type=self._parse_machine_type(row.get("machine_type")),
                    capacity=float(row.get("capacity", 10.0)),
                    historical_efficiency=float(row.get("efficiency", 0.9)),
                    historical_uptime=0.95,  # Default or from another table
                    status=self._parse_machine_status(row.get("status")),
                )
                machines.append(machine)
            except Exception as e:
                logger.warning(f"Failed to parse machine row: {row}, error: {e}")

        logger.info(f"Fetched {len(machines)} machines from ERP")
        return machines

    def get_operators(self, active_only: bool = True) -> List[Operator]:
        """Fetch operators/employees from ERP"""
        m = self.mapping

        query = f"""
            SELECT 
                {m.operator_id_column} as operator_id,
                {m.operator_name_column} as name,
                {m.operator_skills_column} as skills,
                {m.operator_shift_start_column} as shift_start,
                {m.operator_shift_end_column} as shift_end,
                {m.operator_status_column} as status
            FROM {m.operators_table}
            WHERE 1=1
            {"AND " + m.operator_status_column + " = 'ACTIVE'" if active_only else ""}
            ORDER BY {m.operator_name_column}
        """

        rows = self.db.execute_query(self.db_name, query)

        operators = []
        for row in rows:
            try:
                operator = Operator(
                    operator_id=str(row["operator_id"]),
                    name=row["name"],
                    skills=self._parse_skills(row.get("skills")),
                    skill_levels={},  # Populate from skills table if available
                    shift_start=int(row.get("shift_start", 7)),
                    shift_end=int(row.get("shift_end", 15)),
                    hourly_rate=25.0,  # From compensation table
                    efficiency_factor=1.0,
                )
                operators.append(operator)
            except Exception as e:
                logger.warning(f"Failed to parse operator row: {row}, error: {e}")

        logger.info(f"Fetched {len(operators)} operators from ERP")
        return operators

    def get_jobs(
        self,
        status_filter: Optional[List[str]] = None,
        date_range: Optional[tuple] = None,
    ) -> List[Job]:
        """
        Fetch jobs/work orders from ERP.

        Args:
            status_filter: Only get jobs with these statuses
            date_range: (start_date, end_date) tuple
        """
        m = self.mapping

        status_clause = ""
        if status_filter:
            statuses = ", ".join([f"'{s}'" for s in status_filter])
            status_clause = f"AND {m.job_status_column} IN ({statuses})"

        date_clause = ""
        if date_range:
            start, end = date_range
            date_clause = f"AND {m.job_due_date_column} BETWEEN '{start}' AND '{end}'"

        query = f"""
            SELECT 
                {m.job_id_column} as job_id,
                {m.job_name_column} as name,
                {m.job_priority_column} as priority,
                {m.job_status_column} as status,
                {m.job_due_date_column} as due_date
            FROM {m.jobs_table}
            WHERE 1=1
            {status_clause}
            {date_clause}
            ORDER BY {m.job_due_date_column}
        """

        rows = self.db.execute_query(self.db_name, query)

        jobs = []
        for row in rows:
            try:
                job = Job(
                    job_id=str(row["job_id"]),
                    name=row["name"],
                    priority=self._parse_job_priority(row.get("priority")),
                    due_date=row.get("due_date"),
                    release_date=datetime.now(),
                    operations=[],  # Fetch separately via get_operations_for_job
                )
                jobs.append(job)
            except Exception as e:
                logger.warning(f"Failed to parse job row: {row}, error: {e}")

        logger.info(f"Fetched {len(jobs)} jobs from ERP")
        return jobs

    def get_operations_for_job(self, job_id: str) -> List[Operation]:
        """
        Fetch operations for a specific job.

        Customize based on your operations/routing table structure.
        """
        # Example query - customize to your schema
        query = f"""
            SELECT 
                operation_id,
                operation_name,
                machine_type_required,
                setup_time,
                run_time,
                sequence
            FROM job_operations
            WHERE job_id = :job_id
            ORDER BY sequence
        """

        rows = self.db.execute_query(self.db_name, query, {"job_id": job_id})

        operations = []
        for row in rows:
            try:
                op = Operation(
                    operation_id=str(row["operation_id"]),
                    name=row["operation_name"],
                    machine_type=self._parse_machine_type(
                        row.get("machine_type_required")
                    ),
                    duration=int(row.get("run_time", 60)),
                    setup_time=int(row.get("setup_time", 0)),
                )
                operations.append(op)
            except Exception as e:
                logger.warning(f"Failed to parse operation: {e}")

        return operations

    # Helper methods for parsing
    def _parse_machine_type(self, value: Optional[str]) -> MachineType:
        """Map your machine type values to MachineType enum"""
        if not value:
            return MachineType.ASSEMBLY

        mapping = {
            "laser": MachineType.LASER,
            "press": MachineType.PRESSBRAKE,
            "pressbrake": MachineType.PRESSBRAKE,
            "weld": MachineType.WELDING,
            "welding": MachineType.WELDING,
            "polish": MachineType.POLISHING,
            "assembly": MachineType.ASSEMBLY,
            "ship": MachineType.SHIPPING,
        }

        return mapping.get(value.lower(), MachineType.ASSEMBLY)

    def _parse_machine_status(self, value: Optional[str]) -> MachineStatus:
        """Map your status values to MachineStatus enum"""
        if not value:
            return MachineStatus.AVAILABLE

        mapping = {
            "active": MachineStatus.AVAILABLE,
            "available": MachineStatus.AVAILABLE,
            "running": MachineStatus.RUNNING,
            "busy": MachineStatus.RUNNING,
            "maintenance": MachineStatus.MAINTENANCE,
            "down": MachineStatus.DOWN,
            "offline": MachineStatus.OFFLINE,
        }

        return mapping.get(value.lower(), MachineStatus.AVAILABLE)

    def _parse_job_priority(self, value: Optional[str]) -> JobPriority:
        """Map your priority values to JobPriority enum"""
        if not value:
            return JobPriority.NORMAL

        mapping = {
            "low": JobPriority.LOW,
            "normal": JobPriority.NORMAL,
            "high": JobPriority.HIGH,
            "rush": JobPriority.RUSH,
            "critical": JobPriority.CRITICAL,
            "urgent": JobPriority.CRITICAL,
        }

        return mapping.get(value.lower(), JobPriority.NORMAL)

    def _parse_skills(self, value: Any) -> List[str]:
        """Parse skills from various formats (JSON array, comma-separated, etc.)"""
        if not value:
            return []

        if isinstance(value, list):
            return value

        if isinstance(value, str):
            # Try JSON first
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except:
                pass

            # Fall back to comma-separated
            return [s.strip() for s in value.split(",")]

        return []


# =============================================================================
# Sensor Data Adapter
# =============================================================================


class SensorDataAdapter:
    """
    Adapter for real-time sensor data.

    Reads machine metrics, status changes, operator check-ins.
    Writes state snapshots and events.
    """

    def __init__(
        self,
        db_manager: DatabaseConnectionManager,
        table_mapping: TableMapping,
        db_name: str = "sensor",
    ):
        self.db = db_manager
        self.mapping = table_mapping
        self.db_name = db_name

    def get_latest_machine_status(self, machine_id: str) -> Optional[Dict]:
        """Get most recent status for a machine"""
        m = self.mapping

        query = f"""
            SELECT 
                {m.sensor_machine_id_column} as machine_id,
                {m.sensor_timestamp_column} as timestamp,
                {m.sensor_metric_column} as metric_type,
                {m.sensor_value_column} as value
            FROM {m.sensor_table}
            WHERE {m.sensor_machine_id_column} = :machine_id
            AND {m.sensor_timestamp_column} >= NOW() - INTERVAL '1 hour'
            ORDER BY {m.sensor_timestamp_column} DESC
            LIMIT 1
        """

        rows = self.db.execute_query(self.db_name, query, {"machine_id": machine_id})
        return rows[0] if rows else None

    def get_machine_metrics(
        self,
        machine_id: str,
        metric_types: Optional[List[str]] = None,
        time_range: Optional[tuple] = None,
    ) -> List[Dict]:
        """
        Get historical metrics for a machine.

        Args:
            metric_types: ['temperature', 'vibration', 'oee', 'availability']
            time_range: (start_time, end_time) as datetime objects
        """
        m = self.mapping

        metric_clause = ""
        if metric_types:
            metrics = ", ".join([f"'{mt}'" for mt in metric_types])
            metric_clause = f"AND {m.sensor_metric_column} IN ({metrics})"

        time_clause = ""
        if time_range:
            start, end = time_range
            time_clause = (
                f"AND {m.sensor_timestamp_column} BETWEEN '{start}' AND '{end}'"
            )

        query = f"""
            SELECT 
                {m.sensor_timestamp_column} as timestamp,
                {m.sensor_metric_column} as metric_type,
                {m.sensor_value_column} as value
            FROM {m.sensor_table}
            WHERE {m.sensor_machine_id_column} = :machine_id
            {metric_clause}
            {time_clause}
            ORDER BY {m.sensor_timestamp_column} DESC
            LIMIT 1000
        """

        return self.db.execute_query(self.db_name, query, {"machine_id": machine_id})

    def get_current_oee(self, machine_id: str) -> Dict[str, float]:
        """Calculate current OEE from sensor data"""
        # Get latest metrics
        metrics = self.get_machine_metrics(
            machine_id,
            metric_types=["availability", "performance", "quality"],
            time_range=(datetime.now() - timedelta(hours=1), datetime.now()),
        )

        # Calculate OEE = Availability × Performance × Quality
        result = {"availability": 1.0, "performance": 1.0, "quality": 1.0, "oee": 1.0}

        for metric in metrics:
            metric_type = metric.get("metric_type", "").lower()
            value = float(metric.get("value", 1.0))

            if "availability" in metric_type:
                result["availability"] = value
            elif "performance" in metric_type:
                result["performance"] = value
            elif "quality" in metric_type:
                result["quality"] = value

        result["oee"] = (
            result["availability"] * result["performance"] * result["quality"]
        )
        return result

    def write_sensor_reading(
        self,
        machine_id: str,
        metric_type: str,
        value: float,
        timestamp: Optional[datetime] = None,
    ) -> bool:
        """Write a sensor reading to the database"""
        m = self.mapping
        ts = timestamp or datetime.now()

        query = f"""
            INSERT INTO {m.sensor_table} 
            ({m.sensor_machine_id_column}, {m.sensor_timestamp_column}, 
             {m.sensor_metric_column}, {m.sensor_value_column})
            VALUES (:machine_id, :timestamp, :metric_type, :value)
        """

        try:
            self.db.execute_query(
                self.db_name,
                query,
                {
                    "machine_id": machine_id,
                    "timestamp": ts,
                    "metric_type": metric_type,
                    "value": value,
                },
            )
            return True
        except Exception as e:
            logger.error(f"Failed to write sensor reading: {e}")
            return False

    def get_operator_check_in_status(
        self,
        operator_id: str,
        date: Optional[datetime] = None,
    ) -> Optional[str]:
        """Get operator's check-in status for a date"""
        # Customize based on your attendance table
        date = date or datetime.now()

        query = """
            SELECT status
            FROM operator_attendance
            WHERE operator_id = :operator_id
            AND DATE(check_time) = DATE(:date)
            ORDER BY check_time DESC
            LIMIT 1
        """

        rows = self.db.execute_query(
            self.db_name,
            query,
            {
                "operator_id": operator_id,
                "date": date,
            },
        )

        return rows[0]["status"] if rows else None


# =============================================================================
# Digital Twin Repository
# =============================================================================


class DigitalTwinRepository:
    """
    Repository for Digital Twin data.

    Stores:
    - Configuration settings
    - Factory state snapshots
    - Disruption predictions
    - Schedule history
    - State change events
    """

    def __init__(
        self,
        db_manager: DatabaseConnectionManager,
        db_name: str = "dt",
    ):
        self.db = db_manager
        self.db_name = db_name

    # Configuration
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        query = """
            SELECT value, value_type
            FROM digital_twin_config
            WHERE config_key = :key
            ORDER BY updated_at DESC
            LIMIT 1
        """

        rows = self.db.execute_query(self.db_name, query, {"key": key})

        if not rows:
            return default

        row = rows[0]
        value = row["value"]
        value_type = row.get("value_type", "string")

        # Parse based on type
        if value_type == "json":
            return json.loads(value)
        elif value_type == "int":
            return int(value)
        elif value_type == "float":
            return float(value)
        elif value_type == "bool":
            return value.lower() == "true"

        return value

    def set_config(
        self, key: str, value: Any, value_type: Optional[str] = None
    ) -> None:
        """Set configuration value"""
        if value_type is None:
            # Auto-detect type
            if isinstance(value, dict) or isinstance(value, list):
                value_type = "json"
                value = json.dumps(value)
            elif isinstance(value, bool):
                value_type = "bool"
                value = str(value)
            elif isinstance(value, int):
                value_type = "int"
            elif isinstance(value, float):
                value_type = "float"
            else:
                value_type = "string"

        query = """
            INSERT INTO digital_twin_config 
            (config_key, value, value_type, updated_at)
            VALUES (:key, :value, :value_type, NOW())
            ON CONFLICT (config_key) DO UPDATE SET
                value = EXCLUDED.value,
                value_type = EXCLUDED.value_type,
                updated_at = EXCLUDED.updated_at
        """

        self.db.execute_query(
            self.db_name,
            query,
            {
                "key": key,
                "value": str(value),
                "value_type": value_type,
            },
        )

    # Snapshots
    def save_snapshot(self, snapshot_data: Dict) -> str:
        """Save a factory state snapshot"""
        query = """
            INSERT INTO factory_snapshots 
            (snapshot_id, timestamp, snapshot_data, metrics)
            VALUES (gen_random_uuid(), NOW(), :data, :metrics)
            RETURNING snapshot_id
        """

        rows = self.db.execute_query(
            self.db_name,
            query,
            {
                "data": json.dumps(snapshot_data),
                "metrics": json.dumps(snapshot_data.get("metrics", {})),
            },
        )

        return rows[0]["snapshot_id"] if rows else None

    def get_latest_snapshot(self) -> Optional[Dict]:
        """Get most recent factory snapshot"""
        query = """
            SELECT snapshot_id, timestamp, snapshot_data, metrics
            FROM factory_snapshots
            ORDER BY timestamp DESC
            LIMIT 1
        """

        rows = self.db.execute_query(self.db_name, query)

        if rows:
            return {
                "snapshot_id": rows[0]["snapshot_id"],
                "timestamp": rows[0]["timestamp"],
                "data": json.loads(rows[0]["snapshot_data"]),
                "metrics": json.loads(rows[0]["metrics"]),
            }
        return None

    # Predictions
    def save_prediction(self, prediction_data: Dict) -> str:
        """Save a disruption prediction"""
        query = """
            INSERT INTO disruption_predictions 
            (prediction_id, timestamp, disruption_type, entity_id, 
             entity_type, probability, predicted_time, metadata)
            VALUES (gen_random_uuid(), NOW(), :type, :entity_id,
                    :entity_type, :probability, :predicted_time, :metadata)
            RETURNING prediction_id
        """

        pred = prediction_data
        rows = self.db.execute_query(
            self.db_name,
            query,
            {
                "type": pred.get("disruption_type"),
                "entity_id": pred.get("entity_id"),
                "entity_type": pred.get("entity_type"),
                "probability": pred.get("probability"),
                "predicted_time": pred.get("predicted_time"),
                "metadata": json.dumps(pred.get("metadata", {})),
            },
        )

        return rows[0]["prediction_id"] if rows else None

    def get_predictions(
        self,
        time_range: Optional[tuple] = None,
        entity_type: Optional[str] = None,
        min_probability: float = 0.0,
    ) -> List[Dict]:
        """Get disruption predictions with filters"""
        conditions = ["probability >= :min_prob"]
        params = {"min_prob": min_probability}

        if time_range:
            start, end = time_range
            conditions.append("predicted_time BETWEEN :start AND :end")
            params["start"] = start
            params["end"] = end

        if entity_type:
            conditions.append("entity_type = :entity_type")
            params["entity_type"] = entity_type

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT prediction_id, timestamp, disruption_type, entity_id,
                   entity_type, probability, predicted_time, metadata
            FROM disruption_predictions
            WHERE {where_clause}
            ORDER BY probability DESC, predicted_time ASC
        """

        return self.db.execute_query(self.db_name, query, params)

    # State change events
    def log_state_change(self, event_data: Dict) -> None:
        """Log a state change event"""
        query = """
            INSERT INTO state_change_events
            (event_id, timestamp, event_type, entity_id, entity_type,
             old_value, new_value, metadata)
            VALUES (gen_random_uuid(), NOW(), :event_type, :entity_id,
                    :entity_type, :old_value, :new_value, :metadata)
        """

        self.db.execute_query(
            self.db_name,
            query,
            {
                "event_type": event_data.get("event_type"),
                "entity_id": event_data.get("entity_id"),
                "entity_type": event_data.get("entity_type"),
                "old_value": json.dumps(event_data.get("old_value")),
                "new_value": json.dumps(event_data.get("new_value")),
                "metadata": json.dumps(event_data.get("metadata", {})),
            },
        )

    def get_state_history(
        self,
        entity_id: Optional[str] = None,
        time_range: Optional[tuple] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """Get state change history"""
        conditions = ["1=1"]
        params = {}

        if entity_id:
            conditions.append("entity_id = :entity_id")
            params["entity_id"] = entity_id

        if time_range:
            start, end = time_range
            conditions.append("timestamp BETWEEN :start AND :end")
            params["start"] = start
            params["end"] = end

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT timestamp, event_type, entity_id, entity_type,
                   old_value, new_value, metadata
            FROM state_change_events
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT :limit
        """
        params["limit"] = limit

        return self.db.execute_query(self.db_name, query, params)


# =============================================================================
# Factory Functions
# =============================================================================


def create_db_manager(
    erp_config: Optional[DatabaseConfig] = None,
    sensor_config: Optional[DatabaseConfig] = None,
    dt_config: Optional[DatabaseConfig] = None,
) -> DatabaseConnectionManager:
    """
    Create a database manager with all connections.

    Example:
        manager = create_db_manager(
            erp_config=DatabaseConfig(
                name="erp",
                host="erp-db.company.com",
                port=5432,
                database="erp_production",
                username="mirofish_reader",
                password="...",
            ),
            sensor_config=DatabaseConfig(...),
            dt_config=DatabaseConfig(...),
        )
    """
    manager = DatabaseConnectionManager()

    if erp_config:
        manager.register_database(erp_config)
    if sensor_config:
        manager.register_database(sensor_config)
    if dt_config:
        manager.register_database(dt_config)

    return manager
