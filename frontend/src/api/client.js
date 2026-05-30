import axios from 'axios'

const BASE = '/api/v1'

const api = axios.create({ baseURL: BASE, timeout: 8000 })

export const submitOrder = (order) => api.post('/order', order).then((r) => r.data)

export const fetchTrades = (limit = 60) =>
  api.get('/trades', { params: { limit } }).then((r) => r.data)

export const fetchOrderBook = (depth = 15) =>
  api.get('/orderbook', { params: { depth } }).then((r) => r.data)

export const fetchMetrics = () => api.get('/metrics').then((r) => r.data)

export const fetchPrediction = () => api.get('/prediction').then((r) => r.data)

export const fetchInsights = () => api.get('/insights').then((r) => r.data)

export const chatWithAI = (message) =>
  api.post('/chat', { message }).then((r) => r.data)

export const startDemo  = () => api.post('/demo/start').then((r) => r.data)
export const stopDemo   = () => api.post('/demo/stop').then((r) => r.data)
export const demoStatus = () => api.get('/demo/status').then((r) => r.data)

export const startAIDemo  = () => api.post('/demo/ai/start').then((r) => r.data)
export const stopAIDemo   = () => api.post('/demo/ai/stop').then((r) => r.data)
export const aiDemoStatus = () => api.get('/demo/ai/status').then((r) => r.data)

export default api
