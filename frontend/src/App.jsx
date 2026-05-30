import { useState, useEffect, useCallback, useRef } from 'react'
import { motion } from 'framer-motion'

import Header         from './components/Header'
import OrderBook      from './components/OrderBook'
import TradeFeed      from './components/TradeFeed'
import PriceChart     from './components/PriceChart'
import PredictionWidget from './components/PredictionWidget'
import MetricsPanel   from './components/MetricsPanel'
import OrderForm      from './components/OrderForm'
import SparkMetrics   from './components/SparkMetrics'
import InsightsWidget from './components/InsightsWidget'
import ChatWidget     from './components/ChatWidget'

import { useWebSocket }  from './hooks/useWebSocket'
import { fetchTrades, startDemo, stopDemo, demoStatus, startAIDemo, stopAIDemo, aiDemoStatus }   from './api/client'

const MAX_TRADES = 120

export default function App() {
  const { connected, orderBook, metrics, lastTrade } = useWebSocket()
  const [trades, setTrades] = useState([])
  const [demoRunning,    setDemoRunning]    = useState(false)
  const [demoStatusData, setDemoStatusData] = useState(null)
  const [aiDemoRunning,  setAIDemoRunning]  = useState(false)
  const [aiDemoStatusData, setAIDemoStatusData] = useState(null)
  const [aiDemoError,    setAIDemoError]    = useState(null)

  // Poll rule-based demo status every 2s when running
  useEffect(() => {
    if (!demoRunning) return
    const id = setInterval(() => {
      demoStatus().then(setDemoStatusData).catch(() => {})
    }, 2000)
    return () => clearInterval(id)
  }, [demoRunning])

  // Poll AI demo status every 5s when running
  useEffect(() => {
    if (!aiDemoRunning) return
    const id = setInterval(() => {
      aiDemoStatus().then(setAIDemoStatusData).catch(() => {})
    }, 5000)
    return () => clearInterval(id)
  }, [aiDemoRunning])

  const handleDemoToggle = async () => {
    try {
      if (demoRunning) {
        await stopDemo()
        setDemoRunning(false)
        setDemoStatusData(null)
      } else {
        const data = await startDemo()
        setDemoRunning(true)
        setDemoStatusData(data)
      }
    } catch { /* server not up yet */ }
  }

  const handleAIDemoToggle = async () => {
    setAIDemoError(null)
    try {
      if (aiDemoRunning) {
        await stopAIDemo()
        setAIDemoRunning(false)
        setAIDemoStatusData(null)
      } else {
        const data = await startAIDemo()
        setAIDemoRunning(true)
        setAIDemoStatusData(data)
      }
    } catch (err) {
      const msg = err?.response?.data?.detail ?? 'AI Demo unavailable'
      setAIDemoError(msg)
      setTimeout(() => setAIDemoError(null), 5000)
    }
  }

  // Bootstrap recent trades from REST, then keep live via WS
  useEffect(() => {
    fetchTrades(60)
      .then((data) => setTrades(data))
      .catch(() => {})
  }, [])

  // Prepend new trade from WS broadcast
  useEffect(() => {
    if (!lastTrade?.trades?.length) return
    const newTrades = lastTrade.trades.map((t) => ({
      ...t,
      aggressor_side: t.aggressor_side ?? 'buy',
    }))
    setTrades((prev) => [...newTrades, ...prev].slice(0, MAX_TRADES))
  }, [lastTrade])

  // Derive last price + 24h change
  const lastPrice  = trades.length ? trades[0]?.price : null
  const firstPrice = trades.length ? trades[trades.length - 1]?.price : null
  const priceChange = lastPrice && firstPrice && firstPrice !== 0
    ? (lastPrice - firstPrice) / firstPrice
    : null

  return (
    <div className="min-h-screen bg-navy-950 bg-mesh flex flex-col">
      <Header
        connected={connected}
        lastPrice={lastPrice}
        priceChange={priceChange}
        metrics={metrics}
        demoRunning={demoRunning}
        demoStatus={demoStatusData}
        onDemoToggle={handleDemoToggle}
        aiDemoRunning={aiDemoRunning}
        aiDemoStatus={aiDemoStatusData}
        aiDemoError={aiDemoError}
        onAIDemoToggle={handleAIDemoToggle}
      />

      <main className="flex-1 max-w-screen-2xl mx-auto w-full px-4 py-4">
        {/* ── Desktop layout ─────────────────────────────────────────── */}
        <div className="hidden lg:grid gap-4" style={{ gridTemplateColumns: '260px 1fr 300px', gridTemplateRows: 'auto' }}>

          {/* LEFT COLUMN */}
          <div className="flex flex-col gap-4">
            <motion.div initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.05 }}>
              <OrderForm onOrderPlaced={() => fetchTrades(60).then(setTrades).catch(() => {})} />
            </motion.div>
            <motion.div initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 }} className="flex-1">
              <MetricsPanel metrics={metrics} />
            </motion.div>
            <motion.div initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.15 }}>
              <SparkMetrics />
            </motion.div>
          </div>

          {/* CENTER COLUMN */}
          <div className="flex flex-col gap-4">
            <motion.div
              initial={{ opacity: 0, y: -16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 }}
              style={{ height: '300px' }}
            >
              <PriceChart trades={trades} />
            </motion.div>
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              style={{ height: '380px' }}
            >
              <TradeFeed trades={trades} />
            </motion.div>
          </div>

          {/* RIGHT COLUMN — wider to hold Insights */}
          <div className="flex flex-col gap-4">
            <motion.div
              initial={{ opacity: 0, x: 16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.05 }}
              style={{ height: '340px' }}
            >
              <OrderBook orderBook={orderBook} />
            </motion.div>
            <motion.div
              initial={{ opacity: 0, x: 16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.1 }}
              style={{ height: '200px' }}
            >
              <PredictionWidget />
            </motion.div>
            <motion.div
              initial={{ opacity: 0, x: 16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.15 }}
              style={{ height: '500px' }}
            >
              <InsightsWidget />
            </motion.div>
          </div>

        </div>

        {/* ── Mobile layout ──────────────────────────────────────────── */}
        <div className="lg:hidden flex flex-col gap-4">
          <div style={{ height: '280px' }}><PriceChart trades={trades} /></div>
          <div className="grid grid-cols-2 gap-4">
            <div style={{ height: '220px' }}><PredictionWidget /></div>
            <MetricsPanel metrics={metrics} />
          </div>
          <OrderForm onOrderPlaced={() => fetchTrades(60).then(setTrades).catch(() => {})} />
          <div style={{ height: '340px' }}><OrderBook orderBook={orderBook} /></div>
          <div style={{ height: '300px' }}><TradeFeed trades={trades} /></div>
          <div style={{ height: '480px' }}><InsightsWidget /></div>
          <SparkMetrics />
        </div>

      </main>

      {/* Footer */}
      <footer className="border-t border-white/5 py-3 px-4 text-center text-xs text-slate-700 font-mono">
        FlashLedger v2.0 · Kafka + PySpark + LSTM + Groq · sub-millisecond matching engine
      </footer>

      {/* Floating AI Chat */}
      <ChatWidget />
    </div>
  )
}
