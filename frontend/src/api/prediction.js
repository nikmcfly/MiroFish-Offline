import service, { requestWithRetry } from './index'

// Fetch active markets from Polymarket
export const fetchMarkets = (params = {}) => {
  return service.get('/api/prediction/markets', { params })
}

// Start a prediction run
export const startPredictionRun = (market) => {
  return requestWithRetry(
    () => service.post('/api/prediction/run', { market }),
    3,
    1000
  )
}

// Get prediction run status
export const getRunStatus = (runId) => {
  return service.get(`/api/prediction/run/${runId}/status`)
}

// Get full prediction run details
export const getRun = (runId) => {
  return service.get(`/api/prediction/run/${runId}`)
}

// List all prediction runs
export const listRuns = (limit = 50) => {
  return service.get('/api/prediction/runs', { params: { limit } })
}

// Delete a prediction run
export const deleteRun = (runId) => {
  return service.delete(`/api/prediction/run/${runId}`)
}
