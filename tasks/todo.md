# Phase 1: Backtesting + Paper Trading + SQLite

## Implementation Steps

- [x] Step 1: Dead code cleanup + comment translation
- [x] Step 2: Extract calibration constants to Config
- [x] Step 3: Tighten exception handling + wire retry
- [x] Step 4: SQLite storage layer (SQLAlchemy Core)
- [x] Step 5: Backtest data models
- [x] Step 6: Extend PolymarketClient for resolved markets
- [x] Step 7: DI storage backend on PredictionManager
- [x] Step 8: Backtesting engine
- [x] Step 9: Calibration service
- [x] Step 10: Paper trading service
- [x] Step 11: Backtest API endpoints
- [x] Step 12: DESIGN.md
- [x] Step 13: BacktestView frontend
- [x] Step 14: Test suite

## Post-Review Fixes
- [x] HMAC-signed pickle blobs in calibrator (security hardening)
- [x] Input validation on num_markets (max 500)
- [x] Frontend field name mismatches (id/metrics/started_at)
- [x] outline: none → outline: revert (accessibility)
- [x] Backtest API returns run_id synchronously (pre-create run before thread)
- [x] .gitignore: exclude backend/data/ (SQLite files)
- [x] Frontend build verified (vite build passes)

## Verification
- [x] 59 tests pass (2.08s)
- [x] Backend starts without import errors
- [x] All API endpoints respond correctly (/health, /api/backtest/runs, /api/backtest/run/:id)
- [x] Frontend builds cleanly (vite build — 0 errors)
- [x] PAPER badge added to PredictionView nav
- [x] BacktestView renders with warm empty state
