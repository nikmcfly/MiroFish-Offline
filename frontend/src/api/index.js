import axios from 'axios'

// Create axios instance
const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:5001',
  timeout: 300000, // 5 minute timeout (ontology generation may require longer time)
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor
service.interceptors.request.use(
  config => {
    return config
  },
  error => {
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

// Response interceptor (fault-tolerant retry mechanism)
service.interceptors.response.use(
  response => {
    const res = response.data

    // If the returned status code is not success, throw error
    if (!res.success && res.success !== undefined) {
      console.error('API Error:', res.error || res.message || 'Unknown error')
      return Promise.reject(new Error(res.error || res.message || 'Error'))
    }

    return res
  },
  async error => {
    console.error('Response error:', error)

    const config = error.config

    // Handle timeout
    if (error.code === 'ECONNABORTED' && error.message.includes('timeout')) {
      console.error('Request timeout')
    }

    // Handle network error
    if (error.message === 'Network Error') {
      console.error('Network error - please check your connection')
    }

    // Retry logic for transient failures (network errors, timeouts, 5xx server errors)
    if (config) {
      config.__retryCount = config.__retryCount || 0
      const maxRetries = config.__maxRetries !== undefined ? config.__maxRetries : 3
      const retryDelay = config.__retryDelay || 1000

      const isTimeout = error.code === 'ECONNABORTED' && error.message.includes('timeout')
      const isNetworkError = error.message === 'Network Error'
      const isServerError = error.response && error.response.status >= 500

      if ((isTimeout || isNetworkError || isServerError) && config.__retryCount < maxRetries) {
        config.__retryCount += 1
        const delay = retryDelay * Math.pow(2, config.__retryCount - 1)
        console.warn(`Request failed, retrying (${config.__retryCount}/${maxRetries}) after ${delay}ms...`)
        await new Promise(resolve => setTimeout(resolve, delay))
        return service(config)
      }
    }

    return Promise.reject(error)
  }
)

// Request function with retry
export const requestWithRetry = async (requestFn, maxRetries = 3, delay = 1000) => {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await requestFn()
    } catch (error) {
      if (i === maxRetries - 1) throw error

      console.warn(`Request failed, retrying (${i + 1}/${maxRetries})...`)
      await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, i)))
    }
  }
}

export default service
