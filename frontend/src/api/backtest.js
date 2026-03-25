import service from './index'

// Start a backtest run
export const startBacktest = (numMarkets = 50, configOverrides = {}) => {
  return service.post('/api/backtest/run', { num_markets: numMarkets, config_overrides: configOverrides })
}

// Get a specific backtest run
export const getBacktestRun = (runId) => {
  return service.get(`/api/backtest/run/${runId}`)
}

// List all backtest runs
export const listBacktests = () => {
  return service.get('/api/backtest/runs')
}
