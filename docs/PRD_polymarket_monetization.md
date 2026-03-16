# PRD: MiroFish Polymarket Monetization Engine

## 1. Executive Summary

MiroFish is a multi-agent swarm intelligence engine that simulates public opinion to generate prediction market trading signals. The existing prototype fetches Polymarket markets, runs agent-based simulations, analyzes sentiment, and outputs BUY_YES / BUY_NO / HOLD signals — but cannot execute trades and lacks the infrastructure needed to monetize reliably.

This PRD defines everything required to turn MiroFish into a **fully autonomous Polymarket trading system** that generates revenue from prediction market alpha.

---

## 2. Current State (v0.2.0)

### What Works
| Component | Status | Notes |
|-----------|--------|-------|
| Polymarket market fetching | Working | Via Gamma API, binary markets only |
| Scenario generation | Working | LLM converts market question → balanced simulation scenario |
| Knowledge graph construction | Working | Neo4j CE, entity/relationship extraction |
| Agent persona generation | Working | 50 default agents with personality profiles |
| OASIS simulation (Reddit) | Working | 5 rounds default, CREATE_POST + CREATE_COMMENT |
| Sentiment analysis | Working | LLM classifies stance, computes weighted P(YES) |
| Signal generation | Working | Edge = simulated_prob - market_prob, 10% threshold |
| Frontend dashboard | Working | Market browser, run progress, signal display |

### What's Missing for Monetization
| Gap | Impact | Priority |
|-----|--------|----------|
| No trade execution | Cannot act on signals | P0 |
| No wallet / key management | Cannot interact with Polymarket contracts | P0 |
| No position tracking / P&L | Cannot measure performance | P0 |
| No backtesting framework | Cannot validate signal quality before risking capital | P0 |
| Single-platform simulation | Reddit-only limits signal diversity | P1 |
| No market filtering intelligence | Runs on any market, no selectivity | P1 |
| No confidence calibration | Raw confidence scores are uncalibrated | P1 |
| No risk management | No position sizing, stop-loss, or exposure limits | P1 |
| No scheduling / automation | Manual trigger only, no continuous scanning | P1 |
| Signal accuracy unknown | No historical performance data | P2 |
| No multi-market correlation | Treats each market independently | P2 |
| No real-time market price monitoring | Stale prices between runs | P2 |

---

## 3. Target Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    MiroFish Engine                       │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ Market    │→ │ Signal   │→ │ Risk     │              │
│  │ Scanner  │  │ Pipeline │  │ Manager  │              │
│  └──────────┘  └──────────┘  └──────────┘              │
│       │              │              │                    │
│       ▼              ▼              ▼                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ Market   │  │ Backtest │  │ Position │              │
│  │ Filter   │  │ Engine   │  │ Tracker  │              │
│  └──────────┘  └──────────┘  └──────────┘              │
│                      │              │                    │
│                      ▼              ▼                    │
│               ┌──────────┐  ┌──────────┐               │
│               │ Trade    │  │ P&L      │               │
│               │ Executor │  │ Dashboard│               │
│               └──────────┘  └──────────┘               │
│                      │                                   │
└──────────────────────│───────────────────────────────────┘
                       ▼
              Polymarket CLOB API
              (Polygon / USDC)
```

---

## 4. Feature Requirements

### 4.1 — Trade Execution (P0)

**Goal:** Execute trades on Polymarket based on generated signals.

#### 4.1.1 Polymarket CLOB Client
- Integrate with Polymarket's CLOB (Central Limit Order Book) API
- Support order types: market order, limit order (GTC, GTD)
- Handle Polygon network interactions (USDC approvals, CTF contract)
- API endpoint: `https://clob.polymarket.com`

#### 4.1.2 Wallet Management
- Secure private key storage (encrypted at rest, environment variable or keyfile)
- Polymarket API key + secret generation (derived from wallet signature)
- USDC balance checking on Polygon
- Support for Polymarket's proxy wallet system (allowances)
- Config additions to `.env`:
  ```
  POLYMARKET_PRIVATE_KEY=           # Polygon wallet private key (encrypted)
  POLYMARKET_API_KEY=               # CLOB API key
  POLYMARKET_API_SECRET=            # CLOB API secret
  POLYMARKET_API_PASSPHRASE=        # CLOB API passphrase
  POLYMARKET_CHAIN_ID=137           # Polygon mainnet
  POLYMARKET_FUNDER_ADDRESS=        # Proxy wallet address
  ```

#### 4.1.3 Order Lifecycle
- Create order from signal (direction → outcome token, edge → size)
- Monitor order fill status
- Cancel stale unfilled orders (configurable timeout)
- Persist order history (order_id, market, side, size, price, fill, timestamp)
- New model: `Order` dataclass in `models/prediction.py`

#### 4.1.4 New Files
- `backend/app/services/polymarket_trader.py` — CLOB client, order placement, fill monitoring
- `backend/app/services/wallet_manager.py` — Key management, balance queries, approvals

---

### 4.2 — Risk Management (P0)

**Goal:** Prevent catastrophic losses through position limits and sizing rules.

#### 4.2.1 Position Sizing
- Kelly criterion-based sizing: `f = edge / odds` (capped at half-Kelly)
- Maximum position size per market (configurable, default: $50 USDC)
- Maximum total exposure across all markets (configurable, default: $500 USDC)
- Minimum edge threshold before trade (configurable, default: 10%)
- Minimum confidence threshold (configurable, default: 0.4)

#### 4.2.2 Exposure Tracking
- Track all open positions with current market prices
- Real-time P&L calculation (unrealized + realized)
- Daily drawdown limit (configurable, default: 20% of bankroll)
- Auto-pause trading if drawdown limit hit

#### 4.2.3 Config Additions
```
RISK_MAX_POSITION_SIZE=50           # Max USDC per market
RISK_MAX_TOTAL_EXPOSURE=500         # Max USDC across all markets
RISK_MIN_EDGE=0.10                  # Minimum edge to trade
RISK_MIN_CONFIDENCE=0.40            # Minimum signal confidence
RISK_KELLY_FRACTION=0.5             # Half-Kelly
RISK_MAX_DAILY_DRAWDOWN=0.20        # 20% daily drawdown limit
RISK_COOLDOWN_MINUTES=60            # Cooldown after hitting drawdown limit
```

#### 4.2.4 New Files
- `backend/app/services/risk_manager.py` — Position sizing, exposure limits, drawdown tracking
- `backend/app/models/position.py` — Position, PortfolioState dataclasses

---

### 4.3 — Backtesting Engine (P0)

**Goal:** Validate signal quality on historical data before risking real capital.

#### 4.3.1 Historical Data Collection
- Fetch resolved Polymarket markets via Gamma API (`closed=true`)
- Store market snapshots: prices at discovery time, resolution outcome, resolution time
- Minimum dataset: 200+ resolved binary markets

#### 4.3.2 Backtest Pipeline
- For each historical market:
  1. Run prediction pipeline (scenario → simulation → sentiment → signal)
  2. Compare signal vs. actual resolution
  3. Record: predicted_prob, market_prob_at_time, actual_outcome, edge, would_have_traded
- Metrics: accuracy, Brier score, ROI (simulated), Sharpe ratio, max drawdown
- Output: backtest report (JSON + markdown summary)

#### 4.3.3 Calibration
- Plot calibration curve: predicted probability vs. actual frequency
- Apply Platt scaling or isotonic regression if miscalibrated
- Store calibration model for live signal adjustment

#### 4.3.4 New Files
- `backend/app/services/backtester.py` — Backtest orchestration, metrics computation
- `backend/app/services/calibrator.py` — Probability calibration
- `backend/app/api/backtest.py` — API endpoints for running/viewing backtests
- `backend/app/models/backtest.py` — BacktestRun, BacktestResult dataclasses

#### 4.3.5 API Endpoints
- `POST /api/backtest/run` — Start backtest on N historical markets
- `GET /api/backtest/run/<id>/status` — Poll progress
- `GET /api/backtest/run/<id>` — Get results with metrics
- `GET /api/backtest/runs` — List all backtests

---

### 4.4 — Market Scanner & Filtering (P1)

**Goal:** Automatically identify high-value trading opportunities.

#### 4.4.1 Market Selection Criteria
- Minimum volume: $50K (configurable)
- Minimum liquidity: $10K (configurable)
- Time to resolution: 1-30 days (avoid too short or too long)
- Binary markets only (YES/NO outcomes)
- Price range filter: 0.10 - 0.90 (avoid near-certain markets)
- Category filters: politics, crypto, sports, science, culture

#### 4.4.2 Continuous Scanning
- Scheduled market scan every N hours (configurable, default: 6 hours)
- New market detection: compare against previously seen condition_ids
- Re-scan existing positions: check for price movement > 5%
- Priority queue: score markets by (volume × liquidity × time_remaining)

#### 4.4.3 Config Additions
```
SCANNER_INTERVAL_HOURS=6
SCANNER_MIN_VOLUME=50000
SCANNER_MIN_LIQUIDITY=10000
SCANNER_MIN_DAYS_TO_RESOLUTION=1
SCANNER_MAX_DAYS_TO_RESOLUTION=30
SCANNER_PRICE_MIN=0.10
SCANNER_PRICE_MAX=0.90
SCANNER_MAX_CONCURRENT_RUNS=3
```

#### 4.4.4 New Files
- `backend/app/services/market_scanner.py` — Scheduled scanning, filtering, prioritization
- Modify `backend/app/services/polymarket_client.py` — Add category filters, pagination

---

### 4.5 — Dual-Platform Simulation (P1)

**Goal:** Run both Reddit and Twitter simulations for richer signal diversity.

#### 4.5.1 Changes
- Modify `PredictionManager.run_prediction()` to run both platforms in parallel
- Aggregate sentiment from both platforms (weighted average: 50/50 or configurable)
- Compare platform agreement as a confidence signal (high agreement → higher confidence)
- Track per-platform stance breakdown in `SentimentResult`

#### 4.5.2 Config Additions
```
PREDICTION_PLATFORMS=reddit,twitter   # Platforms to simulate
PREDICTION_PLATFORM_WEIGHTS=0.5,0.5   # Aggregation weights
PREDICTION_REQUIRE_AGREEMENT=false    # Only trade if platforms agree on direction
```

---

### 4.6 — Scheduling & Automation (P1)

**Goal:** Fully autonomous operation — scan, predict, trade, repeat.

#### 4.6.1 Scheduler
- Cron-based or interval-based job scheduler (APScheduler or Celery Beat)
- Jobs:
  - `scan_markets` — Every 6h: fetch new markets, filter, queue for prediction
  - `run_predictions` — Process queued markets (max 3 concurrent)
  - `execute_trades` — Convert completed signals to orders
  - `monitor_positions` — Every 1h: update P&L, check stop-loss
  - `cleanup` — Daily: archive old runs, purge expired market data

#### 4.6.2 Job Persistence
- Store job state in filesystem (consistent with existing pattern)
- Resume incomplete jobs on restart
- Dead-letter queue for failed runs (retry up to 3 times)

#### 4.6.3 New Files
- `backend/app/services/scheduler.py` — Job scheduling, queue management
- `backend/app/services/trade_executor.py` — Signal-to-order conversion with risk checks

---

### 4.7 — Portfolio Dashboard (P1)

**Goal:** Real-time visibility into positions, P&L, and signal performance.

#### 4.7.1 Backend API Endpoints
- `GET /api/portfolio/summary` — Total value, P&L, open positions count
- `GET /api/portfolio/positions` — All positions with current prices and unrealized P&L
- `GET /api/portfolio/history` — Trade history with realized P&L
- `GET /api/portfolio/metrics` — Win rate, avg edge, ROI, Sharpe, max drawdown
- `GET /api/portfolio/signals` — Signal performance log (signal vs. outcome)

#### 4.7.2 Frontend View
- New route: `/portfolio`
- Components:
  - Portfolio summary card (total value, daily P&L, win rate)
  - Open positions table (market, direction, entry price, current price, P&L)
  - Trade history table with filters
  - Performance chart (cumulative P&L over time)
  - Signal accuracy chart (calibration curve)
  - Risk gauge (current exposure vs. limits)

#### 4.7.3 New Files
- `backend/app/api/portfolio.py` — Portfolio API endpoints
- `backend/app/services/portfolio_tracker.py` — Position aggregation, P&L calculation
- `frontend/src/views/PortfolioView.vue` — Dashboard UI
- `frontend/src/api/portfolio.js` — API client

---

### 4.8 — Signal Quality Improvements (P2)

#### 4.8.1 Multi-Run Consensus
- Run N simulations per market (default: 3) with different random seeds
- Average the simulated probabilities across runs
- Standard deviation as uncertainty measure → feeds into confidence
- Only trade if all N runs agree on direction

#### 4.8.2 Web Research Augmentation
- Before simulation, fetch recent news articles related to the market question
- Inject news summaries into the context document alongside the LLM-generated scenario
- Sources: news APIs (NewsAPI, GDELT), Wikipedia current events
- Improves agent grounding in real-world facts

#### 4.8.3 Agent Diversity Tuning
- Vary agent expertise levels: 20% domain experts, 30% informed observers, 50% general public
- Add contrarian agents (10%) to stress-test consensus
- Scale agent count with market complexity (higher volume/liquidity → more agents)

#### 4.8.4 Temporal Weighting
- Weight later simulation rounds higher than earlier rounds (agents refine opinions over time)
- Detect opinion shift direction (converging or diverging) as meta-signal

---

### 4.9 — Monitoring & Alerting (P2)

#### 4.9.1 Alerts
- Telegram/Discord webhook for:
  - New signal generated (market, direction, edge, confidence)
  - Trade executed (market, side, size, price)
  - Position resolved (market, outcome, P&L)
  - Drawdown limit approaching (>15% of limit)
  - System errors (pipeline failure, API timeout)

#### 4.9.2 Health Checks
- `GET /api/status` — System health (Neo4j, Ollama, Polymarket API, wallet balance)
- Log aggregation with structured JSON logs
- Pipeline execution time tracking (per stage)

#### 4.9.3 Config Additions
```
ALERT_WEBHOOK_URL=                  # Telegram/Discord webhook
ALERT_ON_SIGNAL=true
ALERT_ON_TRADE=true
ALERT_ON_RESOLUTION=true
ALERT_ON_DRAWDOWN=true
```

---

## 5. Data Models (New & Modified)

### 5.1 New: `Order`
```python
@dataclass
class Order:
    order_id: str                   # Polymarket CLOB order ID
    run_id: str                     # Linked prediction run
    market_condition_id: str
    market_title: str
    side: str                       # BUY or SELL
    outcome: str                    # YES or NO
    size: float                     # USDC amount
    price: float                    # Limit price (0-1)
    status: str                     # PENDING, FILLED, PARTIAL, CANCELLED, FAILED
    filled_size: float
    avg_fill_price: float
    created_at: str
    updated_at: str
```

### 5.2 New: `Position`
```python
@dataclass
class Position:
    position_id: str
    market_condition_id: str
    market_title: str
    outcome: str                    # YES or NO
    entry_price: float
    current_price: float
    size: float                     # Number of outcome tokens
    cost_basis: float               # Total USDC spent
    unrealized_pnl: float
    status: str                     # OPEN, CLOSED, RESOLVED
    resolution: Optional[str]       # YES, NO (after market resolves)
    realized_pnl: Optional[float]   # Final P&L after resolution
    opened_at: str
    closed_at: Optional[str]
```

### 5.3 New: `PortfolioState`
```python
@dataclass
class PortfolioState:
    total_value: float              # Cash + unrealized position value
    cash_balance: float             # Available USDC
    total_exposure: float           # Sum of open position cost bases
    unrealized_pnl: float
    realized_pnl: float
    total_pnl: float
    win_rate: float                 # Resolved positions only
    total_trades: int
    open_positions: int
    daily_drawdown: float           # Current day's drawdown %
```

### 5.4 Modified: `PredictionRun`
Add fields:
```python
    order_id: Optional[str] = None          # Linked trade order
    position_id: Optional[str] = None       # Linked position
    calibrated_probability: Optional[float] = None  # Post-calibration probability
    consensus_runs: Optional[int] = None    # Number of consensus runs
    consensus_std: Optional[float] = None   # Cross-run standard deviation
```

---

## 6. API Endpoints (New)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/trade/execute` | Execute trade from signal |
| GET | `/api/trade/orders` | List all orders |
| GET | `/api/trade/orders/<id>` | Get order details |
| DELETE | `/api/trade/orders/<id>` | Cancel order |
| GET | `/api/portfolio/summary` | Portfolio overview |
| GET | `/api/portfolio/positions` | Open positions |
| GET | `/api/portfolio/history` | Trade history |
| GET | `/api/portfolio/metrics` | Performance metrics |
| POST | `/api/backtest/run` | Start backtest |
| GET | `/api/backtest/run/<id>` | Backtest results |
| GET | `/api/backtest/runs` | List backtests |
| POST | `/api/scanner/start` | Start market scanner |
| POST | `/api/scanner/stop` | Stop market scanner |
| GET | `/api/scanner/status` | Scanner state + queue |
| GET | `/api/status` | System health check |

---

## 7. Frontend Routes (New)

| Route | View | Description |
|-------|------|-------------|
| `/portfolio` | PortfolioView.vue | Positions, P&L, performance charts |
| `/backtest` | BacktestView.vue | Backtest runs, metrics, calibration |
| `/settings` | SettingsView.vue | Risk params, wallet, scanner config |

---

## 8. Implementation Phases

### Phase 1: Backtesting & Validation (2 weeks)
**Goal:** Prove signal quality before risking capital.
- [ ] Historical market data collector (resolved markets from Gamma API)
- [ ] Backtest pipeline (run prediction on historical markets, compare to resolution)
- [ ] Metrics computation (accuracy, Brier score, simulated ROI, calibration curve)
- [ ] Calibration service (Platt scaling on predicted probabilities)
- [ ] Backtest API endpoints + basic frontend view
- **Exit criteria:** 200+ markets backtested, documented accuracy & ROI

### Phase 2: Trade Execution & Risk (2 weeks)
**Goal:** Safely execute trades with guardrails.
- [ ] Polymarket CLOB client (py-clob-client integration)
- [ ] Wallet manager (key storage, balance queries, USDC approvals)
- [ ] Risk manager (position sizing, exposure limits, drawdown tracking)
- [ ] Order lifecycle (create, monitor fill, cancel stale)
- [ ] Position tracker (open/close positions, P&L computation)
- [ ] Trade execution API endpoints
- **Exit criteria:** Successfully place and fill a $1 test trade on Polymarket

### Phase 3: Automation & Monitoring (1 week)
**Goal:** Autonomous operation with visibility.
- [ ] Market scanner with filtering and priority queue
- [ ] Job scheduler (scan → predict → trade → monitor cycle)
- [ ] Portfolio dashboard (frontend view with positions, P&L, charts)
- [ ] Alert webhooks (Telegram/Discord notifications)
- [ ] Health check endpoint
- **Exit criteria:** System runs autonomously for 48h, placing trades and reporting results

### Phase 4: Signal Optimization (ongoing)
**Goal:** Improve edge over time.
- [ ] Multi-run consensus (3 runs per market, average probabilities)
- [ ] Dual-platform simulation (Reddit + Twitter)
- [ ] Web research augmentation (inject real news into scenario)
- [ ] Agent diversity tuning
- [ ] A/B test simulation parameters (rounds, agent count, platform weights)
- **Exit criteria:** Measurable improvement in backtest ROI vs. Phase 1 baseline

---

## 9. Configuration Summary

All new config via `.env` (following existing pattern):

```env
# === Trade Execution ===
POLYMARKET_PRIVATE_KEY=
POLYMARKET_API_KEY=
POLYMARKET_API_SECRET=
POLYMARKET_API_PASSPHRASE=
POLYMARKET_CHAIN_ID=137
POLYMARKET_FUNDER_ADDRESS=
PREDICTION_TRADE_ENABLED=false      # Master kill switch (already exists)

# === Risk Management ===
RISK_MAX_POSITION_SIZE=50
RISK_MAX_TOTAL_EXPOSURE=500
RISK_MIN_EDGE=0.10
RISK_MIN_CONFIDENCE=0.40
RISK_KELLY_FRACTION=0.5
RISK_MAX_DAILY_DRAWDOWN=0.20
RISK_COOLDOWN_MINUTES=60

# === Market Scanner ===
SCANNER_INTERVAL_HOURS=6
SCANNER_MIN_VOLUME=50000
SCANNER_MIN_LIQUIDITY=10000
SCANNER_MIN_DAYS_TO_RESOLUTION=1
SCANNER_MAX_DAYS_TO_RESOLUTION=30
SCANNER_PRICE_MIN=0.10
SCANNER_PRICE_MAX=0.90
SCANNER_MAX_CONCURRENT_RUNS=3

# === Signal Quality ===
PREDICTION_PLATFORMS=reddit,twitter
PREDICTION_PLATFORM_WEIGHTS=0.5,0.5
PREDICTION_CONSENSUS_RUNS=3
PREDICTION_REQUIRE_AGREEMENT=false

# === Alerts ===
ALERT_WEBHOOK_URL=
ALERT_ON_SIGNAL=true
ALERT_ON_TRADE=true
ALERT_ON_RESOLUTION=true
ALERT_ON_DRAWDOWN=true
```

---

## 10. Dependencies (New)

| Package | Purpose | Version |
|---------|---------|---------|
| `py-clob-client` | Polymarket CLOB API client | latest |
| `web3` | Polygon blockchain interaction | ^6.0 |
| `eth-account` | Wallet key management | ^0.11 |
| `apscheduler` | Job scheduling | ^3.10 |
| `scikit-learn` | Probability calibration (isotonic regression) | ^1.3 |
| `requests` | HTTP (already present) | existing |

---

## 11. Risk Considerations

### Financial Risk
- **Start small:** $1-5 trades during Phase 2 validation
- **Half-Kelly sizing** prevents ruin from miscalibrated signals
- **Drawdown circuit breaker** auto-pauses trading during bad streaks
- **PREDICTION_TRADE_ENABLED=false** by default — explicit opt-in required

### Technical Risk
- **LLM quality:** Signal quality is bottlenecked by local LLM (qwen2.5). Consider testing with stronger models via API (Claude, GPT-4) for higher-stakes markets
- **Simulation time:** Full pipeline takes 10-30 min per market. Scanner must prioritize
- **API rate limits:** Polymarket CLOB API has rate limits — implement backoff
- **Network reliability:** Polygon RPC can be flaky — use redundant RPC endpoints

### Regulatory Risk
- Polymarket operates under different regulatory frameworks by jurisdiction
- This system is for research and personal use
- Users are responsible for compliance with their local laws

---

## 12. Success Metrics

| Metric | Target (Phase 1) | Target (Phase 4) |
|--------|------------------|------------------|
| Backtest accuracy (binary) | >55% | >60% |
| Brier score | <0.25 | <0.22 |
| Simulated ROI (backtest) | >5% | >15% |
| Calibration RMSE | <0.15 | <0.10 |
| Avg edge on traded markets | >8% | >12% |
| Win rate (live trades) | N/A | >55% |
| Max drawdown | N/A | <25% |
| Markets scanned per day | N/A | 20+ |
| Avg pipeline time per market | <30min | <20min |

---

## 13. File Structure (New Files)

```
backend/app/
├── api/
│   ├── backtest.py          # Backtest API endpoints
│   ├── portfolio.py         # Portfolio/P&L API endpoints
│   └── trade.py             # Trade execution API endpoints
├── models/
│   ├── backtest.py          # BacktestRun, BacktestResult
│   └── position.py          # Order, Position, PortfolioState
├── services/
│   ├── backtester.py        # Backtest orchestration
│   ├── calibrator.py        # Probability calibration
│   ├── market_scanner.py    # Market filtering & scheduling
│   ├── polymarket_trader.py # CLOB order execution
│   ├── portfolio_tracker.py # Position & P&L tracking
│   ├── risk_manager.py      # Sizing, limits, drawdown
│   ├── scheduler.py         # Job scheduling
│   ├── trade_executor.py    # Signal → order pipeline
│   └── wallet_manager.py    # Key management, balances
frontend/src/
├── api/
│   ├── backtest.js          # Backtest API client
│   └── portfolio.js         # Portfolio API client
├── views/
│   ├── BacktestView.vue     # Backtest dashboard
│   ├── PortfolioView.vue    # Portfolio dashboard
│   └── SettingsView.vue     # Configuration UI
```
