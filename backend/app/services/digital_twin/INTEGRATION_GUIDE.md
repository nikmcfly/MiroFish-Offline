# Digital Twin Shop System Integration Guide

Complete API specification for integrating the MiroFish Digital Twin with your shop system (ERP/MES).

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         YOUR SHOP SYSTEM                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │   ERP       │  │   MES       │  │   SCADA     │  │  Database   │   │
│  │  Module     │  │  Module     │  │   System    │  │  (PostgreSQL)│   │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘   │
└─────────┼────────────────┼────────────────┼────────────────┼─────────────┘
          │                │                │                │
          └────────────────┴────────────────┴────────────────┘
                              │
                              ▼ REST API Calls
┌─────────────────────────────────────────────────────────────────────────┐
│                    MIROFISH DIGITAL TWIN SERVICE                        │
│                        (Running on Port 5001)                         │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ API Layer (backend/app/api/digital_twin.py)                      │   │
│  │  • POST /api/twin/data/*    - Receive live data                 │   │
│  │  • POST /api/twin/simulate  - Run simulations                   │   │
│  │  • GET  /api/twin/predictions - Get disruption forecasts        │   │
│  │  • POST /api/twin/simulate/schedule - Full pipeline             │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Digital Twin Core                                               │   │
│  │  • State Manager - Tracks live factory state                    │   │
│  │  • Disruption Engine - Simulates future disruptions             │   │
│  │  • Prediction Bridge - Feeds results to scheduler             │   │
│  │  • OR-Tools Solver - Generates optimized schedules              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Base URL

```
http://mirofish-server:5001/api/twin
```

## Authentication

Currently uses IP-based access control. For production, add API key authentication:

```python
headers = {
    "X-API-Key": "your-api-key",
    "Content-Type": "application/json"
}
```

## API Endpoints

### 1. Service Initialization

#### `POST /initialize`
Initialize the Digital Twin with database connections and table mappings.

**When to call:** Once at startup, or when reconfiguring database connections.

**Request:**
```json
{
  "databases": {
    "erp": {
      "host": "erp-db.company.com",
      "port": 5432,
      "database": "erp_production",
      "username": "mirofish_reader",
      "password": "secret",
      "schema": "public"
    },
    "sensor": {
      "host": "scada-db.company.com",
      "port": 5432,
      "database": "sensor_data",
      "username": "mirofish_reader",
      "password": "secret"
    },
    "dt": {
      "host": "localhost",
      "port": 5432,
      "database": "digital_twin",
      "username": "mirofish",
      "password": "secret"
    }
  },
  "table_mapping": {
    "machines_table": "equipment",
    "machine_id_column": "asset_id",
    "machine_name_column": "asset_name",
    "machine_type_column": "equipment_type",
    "machine_status_column": "operational_status",
    "operators_table": "employees",
    "operator_id_column": "emp_id",
    "jobs_table": "work_orders",
    "sensor_table": "machine_telemetry"
  }
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "initialized": true,
    "machines_tracked": 25,
    "operators_tracked": 40,
    "jobs_tracked": 15
  }
}
```

---

### 2. Live Data Ingestion

#### `POST /data/machines`
Push real-time machine data (status, metrics, OEE).

**When to call:** Continuously (every 30-60 seconds) or on status changes.

**Request:**
```json
{
  "machines": [
    {
      "machine_id": "LASER_001",
      "status": "RUNNING",
      "oee": 0.85,
      "temperature": 75.5,
      "vibration": 2.1,
      "power_consumption": 45.2,
      "cycle_count": 15420,
      "current_job_id": "WO_2024_001",
      "timestamp": "2024-01-15T10:30:00Z",
      "metadata": {
        "shift": "morning",
        "operator_id": "OP_123"
      }
    },
    {
      "machine_id": "PRESS_002",
      "status": "DOWN",
      "oee": 0.0,
      "timestamp": "2024-01-15T10:30:00Z",
      "metadata": {
        "reason": "maintenance_scheduled",
        "expected_back_online": "2024-01-15T12:00:00Z"
      }
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "updated": 2
  }
}
```

---

#### `POST /data/operators`
Push operator attendance and assignment data.

**When to call:** On check-in/check-out events, or assignment changes.

**Request:**
```json
{
  "operators": [
    {
      "operator_id": "EMP_001",
      "event": "check_in",
      "timestamp": "2024-01-15T07:00:00Z"
    },
    {
      "operator_id": "EMP_002",
      "event": "assignment",
      "current_assignment": "LASER_001",
      "timestamp": "2024-01-15T08:15:00Z"
    },
    {
      "operator_id": "EMP_003",
      "event": "check_out",
      "timestamp": "2024-01-15T15:00:00Z"
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "processed": 3
  }
}
```

---

#### `POST /data/jobs`
Push job progress updates.

**When to call:** When operations start/complete, or job status changes.

**Request:**
```json
{
  "jobs": [
    {
      "job_id": "WO_2024_001",
      "status": "in_progress",
      "current_operation_idx": 2,
      "percent_complete": 45.5,
      "assigned_machine_id": "LASER_001",
      "assigned_operator_id": "EMP_001",
      "timestamp": "2024-01-15T10:30:00Z"
    },
    {
      "job_id": "WO_2024_002",
      "operation_completed": true,
      "timestamp": "2024-01-15T10:30:00Z"
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "processed": 2
  }
}
```

---

### 3. Simulation Execution

#### `POST /simulate`
Run disruption simulation and get predictions.

**When to call:** Periodically (every 5-15 minutes) or before major scheduling decisions.

**Synchronous Request:**
```json
{
  "scenario": "high_stress",
  "simulation_hours": 24
}
```

**Asynchronous Request (with callback):**
```json
{
  "scenario": "default",
  "callback_url": "https://your-shop-system.com/webhooks/simulation-results"
}
```

**Response (sync):**
```json
{
  "success": true,
  "data": {
    "simulation_id": "sim_abc123",
    "status": "completed",
    "predictions": [
      {
        "disruption_type": "MACHINE_BREAKDOWN",
        "entity_id": "LASER_001",
        "entity_type": "machine",
        "probability": 0.75,
        "predicted_time": "2024-01-15T14:30:00Z",
        "confidence": 0.8,
        "affected_jobs": ["WO_2024_001", "WO_2024_003"],
        "estimated_delay_minutes": 120,
        "estimated_cost_impact": 2400.00,
        "recommended_action": "Prepare backup machine",
        "alternative_resources": ["LASER_002", "LASER_003"]
      },
      {
        "disruption_type": "OPERATOR_ABSENCE",
        "entity_id": "EMP_001",
        "entity_type": "operator",
        "probability": 0.15,
        "predicted_time": "2024-01-16T08:00:00Z",
        "estimated_delay_minutes": 30,
        "alternative_resources": ["EMP_004", "EMP_005"]
      }
    ]
  }
}
```

**Callback Payload (async):**
```json
{
  "simulation_id": "sim_abc123",
  "status": "completed",
  "predictions": [...]
}
```

---

#### `POST /simulate/schedule`
**Full Pipeline:** Run simulation → Get predictions → Optimize schedule.

**When to call:** When you need an optimized schedule that accounts for predicted disruptions.

**Request:**
```json
{
  "scenario": "default",
  "reschedule_strategy": "adaptive",
  "current_problem": {
    // Optional - uses current factory state if not provided
  }
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "predictions": [...],
    "reschedule_triggered": true,
    "reschedule_reason": "High disruption probability: 75%",
    "new_makespan": 1200,
    "schedule": {
      "makespan": 1200,
      "total_cost": 4500.00,
      "utilization": 0.85,
      "entries": [
        {
          "job_id": "WO_2024_001",
          "operation_id": "OP_001",
          "machine_id": "LASER_002",
          "operator_id": "EMP_001",
          "start_time": "2024-01-15T11:00:00Z",
          "end_time": "2024-01-15T12:30:00Z",
          "duration": 90
        }
      ]
    },
    "recommendations": [
      {
        "type": "machine_reassignment",
        "job_id": "WO_2024_001",
        "from_machine": "LASER_001",
        "to_machine": "LASER_002",
        "reason": "Predicted breakdown on LASER_001"
      }
    ]
  }
}
```

---

### 4. Query Endpoints

#### `GET /state`
Get current factory state snapshot.

**When to call:** To get the complete current state for UI display or external systems.

**Response:**
```json
{
  "success": true,
  "data": {
    "timestamp": "2024-01-15T10:30:00Z",
    "machines": {
      "LASER_001": {
        "machine_id": "LASER_001",
        "name": "Laser Cutter 1",
        "status": "RUNNING",
        "current_job_id": "WO_2024_001",
        "oee": 0.85,
        "temperature": 75.5,
        "availability": 0.95
      }
    },
    "operators": {...},
    "jobs": {...},
    "metrics": {
      "total_machine_utilization": 0.78,
      "total_operator_utilization": 0.82,
      "jobs_in_queue": 5,
      "jobs_in_progress": 12
    }
  }
}
```

---

#### `GET /predictions`
Get recent high-risk predictions.

**Query Parameters:**
- `min_probability` (float, default 0.0) - Filter by minimum probability
- `hours_ahead` (int, default 24) - Look ahead window

**Request:**
```
GET /api/twin/predictions?min_probability=0.5&hours_ahead=12
```

**Response:**
```json
{
  "success": true,
  "data": {
    "count": 3,
    "predictions": [...]
  }
}
```

---

#### `GET /stats`
Get service statistics.

**Response:**
```json
{
  "success": true,
  "data": {
    "state_manager": {
      "updates_received": 15420,
      "events_published": 8760
    },
    "prediction_bridge": {
      "predictions_received": 145,
      "feedbacks_applied": 142,
      "reschedules_triggered": 23
    },
    "disruption_engine": {
      "total_predictions": 145,
      "by_type": {
        "MACHINE_BREAKDOWN": {"count": 89, "avg_probability": 0.42},
        "OPERATOR_ABSENCE": {"count": 34, "avg_probability": 0.18}
      }
    }
  }
}
```

---

#### `GET /health`
Health check for monitoring.

**Response:**
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "timestamp": "2024-01-15T10:30:00Z",
    "initialized": true,
    "databases": {
      "erp": "connected",
      "sensor": "connected",
      "dt": "connected"
    }
  }
}
```

---

## Integration Patterns

### Pattern 1: Push-Based Data Flow

Your shop system pushes data to the Digital Twin continuously:

```python
import requests
import schedule
import time

API_BASE = "http://mirofish-server:5001/api/twin"

# Push machine data every 60 seconds
def push_machine_data():
    machines = get_machine_data_from_scada()
    requests.post(f"{API_BASE}/data/machines", json={"machines": machines})

# Push operator data on events
def on_operator_check_in(operator_id):
    requests.post(f"{API_BASE}/data/operators", json={
        "operators": [{"operator_id": operator_id, "event": "check_in"}]
    })

# Push job data on progress
def on_operation_complete(job_id):
    requests.post(f"{API_BASE}/data/jobs", json={
        "jobs": [{"job_id": job_id, "operation_completed": True}]
    })

# Schedule continuous updates
schedule.every(60).seconds.do(push_machine_data)

while True:
    schedule.run_pending()
    time.sleep(1)
```

---

### Pattern 2: Periodic Simulation

Run simulations periodically and act on predictions:

```python
def run_periodic_simulation():
    # Run simulation
    response = requests.post(f"{API_BASE}/simulate", json={
        "scenario": "default"
    })
    
    predictions = response.json()["data"]["predictions"]
    
    # Act on high-risk predictions
    for pred in predictions:
        if pred["probability"] > 0.7:
            if pred["disruption_type"] == "MACHINE_BREAKDOWN":
                # Alert maintenance team
                alert_maintenance(pred["entity_id"], pred["recommended_action"])
                
            elif pred["disruption_type"] == "RUSH_ORDER_ARRIVAL":
                # Prepare flexible capacity
                reserve_capacity(pred["predicted_time"])

# Run every 10 minutes
schedule.every(10).minutes.do(run_periodic_simulation)
```

---

### Pattern 3: Preemptive Scheduling

Get an optimized schedule that accounts for predicted disruptions:

```python
def get_optimized_schedule():
    # Get schedule that accounts for disruptions
    response = requests.post(f"{API_BASE}/simulate/schedule", json={
        "scenario": "high_stress",
        "reschedule_strategy": "adaptive"
    })
    
    result = response.json()["data"]
    
    if result["reschedule_triggered"]:
        new_schedule = result["schedule"]
        
        # Display recommendations to planner
        for rec in result["recommendations"]:
            print(f"Recommendation: {rec['type']} - {rec['reason']}")
        
        # Apply schedule (with user confirmation)
        if confirm_schedule_change(new_schedule):
            apply_schedule_to_mes(new_schedule)

# Run before each shift change
schedule.every().day.at("06:30").do(get_optimized_schedule)
schedule.every().day.at("14:30").do(get_optimized_schedule)
```

---

### Pattern 4: Event-Driven Architecture

Use webhooks for real-time updates:

```python
from flask import Flask, request

app = Flask(__name__)

@app.route('/webhooks/simulation-results', methods=['POST'])
def handle_simulation_results():
    data = request.json
    
    for pred in data["predictions"]:
        if pred["probability"] > 0.8:
            # High urgency - notify immediately
            send_urgent_alert(pred)
        else:
            # Log for review
            log_prediction(pred)
    
    return "OK"

# Request simulation with callback
requests.post(f"{API_BASE}/simulate", json={
    "scenario": "default",
    "callback_url": "https://your-system.com/webhooks/simulation-results"
})
```

---

## Error Handling

All endpoints return consistent error format:

```json
{
  "success": false,
  "error": "Descriptive error message",
  "code": "ERROR_CODE",  // optional
  "details": {}  // additional context
}
```

**Common Error Codes:**
- `400` - Bad Request (invalid JSON, missing fields)
- `500` - Server Error (simulation failed, database error)

**Retry Strategy:**
```python
from tenacity import retry, wait_exponential

@retry(wait=wait_exponential(multiplier=1, min=4, max=10))
def call_digital_twin_api(endpoint, data):
    response = requests.post(f"{API_BASE}{endpoint}", json=data)
    response.raise_for_status()
    return response.json()
```

---

## Performance Expectations

| Endpoint | Latency | Throughput |
|----------|---------|------------|
| `/data/machines` | < 50ms | 1000 req/s |
| `/data/operators` | < 50ms | 1000 req/s |
| `/data/jobs` | < 50ms | 1000 req/s |
| `/simulate` | 50-200ms | 10 req/s |
| `/simulate/schedule` | 1s - 5min | 1 req/s |
| `/state` | < 100ms | 100 req/s |
| `/predictions` | < 50ms | 100 req/s |

---

## Deployment

### Docker Compose

```yaml
version: '3.8'
services:
  mirofish-digital-twin:
    image: mirofish-digital-twin:latest
    ports:
      - "5001:5001"
    environment:
      - DATABASE_URL=postgresql://mirofish:secret@dt-db:5432/digital_twin
      - LOG_LEVEL=INFO
    networks:
      - shop-network
    restart: unless-stopped
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mirofish-digital-twin
spec:
  replicas: 2
  selector:
    matchLabels:
      app: mirofish-digital-twin
  template:
    metadata:
      labels:
        app: mirofish-digital-twin
    spec:
      containers:
      - name: api
        image: mirofish-digital-twin:latest
        ports:
        - containerPort: 5001
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: url
```

---

## Next Steps

1. **Set up the service** - Deploy MiroFish Digital Twin on your infrastructure
2. **Configure table mappings** - Map your schema to the expected format
3. **Start data ingestion** - Begin pushing live data
4. **Run first simulation** - Verify predictions are meaningful
5. **Integrate with scheduler** - Connect optimized schedules to your MES
6. **Monitor and tune** - Adjust thresholds based on real-world performance

---

## Support

For issues or questions:
- Check logs: `docker logs mirofish-digital-twin`
- Health endpoint: `GET /api/twin/health`
- Stats endpoint: `GET /api/twin/stats`
