import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Brain, TrendingUp, TrendingDown, RefreshCw } from 'lucide-react'
import { fetchPrediction } from '../api/client'

export default function PredictionWidget() {
  const [pred,    setPred]    = useState(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)
  const [age,     setAge]     = useState(0)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchPrediction()
      setPred(data)
      setAge(0)
    } catch (e) {
      setError('Model unavailable')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const interval = setInterval(load, 15_000)   // refresh every 15 s
    return () => clearInterval(interval)
  }, [])

  // Age counter
  useEffect(() => {
    const t = setInterval(() => setAge((a) => a + 1), 1000)
    return () => clearInterval(t)
  }, [])

  const isUp   = pred?.direction === 'up'
  const conf   = pred?.confidence ?? 0
  const pct    = Math.round(conf * 100)

  // SVG circle progress
  const RADIUS = 36
  const CIRCUMFERENCE = 2 * Math.PI * RADIUS
  const dashOffset = CIRCUMFERENCE * (1 - conf)

  return (
    <div className={`panel flex flex-col h-full relative overflow-hidden transition-shadow duration-500 ${
      pred ? (isUp ? 'glow-ring-green' : 'glow-ring-red') : ''
    }`}>
      <div className="panel-header">
        <div className="flex items-center gap-2">
          <Brain size={14} className="text-gold" />
          <span className="panel-title">LSTM Prediction</span>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="text-slate-500 hover:text-slate-300 transition-colors disabled:opacity-40"
        >
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center gap-4 px-4 py-4">
        {error ? (
          <div className="text-slate-500 text-sm text-center">{error}<br />
            <span className="text-xs text-slate-600">Run ml/train.py to enable</span>
          </div>
        ) : (
          <AnimatePresence mode="wait">
            {pred && (
              <motion.div
                key={pred.direction + pct}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className="flex flex-col items-center gap-3 w-full"
              >
                {/* Circular confidence meter */}
                <div className="relative">
                  <svg width="96" height="96" className="-rotate-90">
                    <circle cx="48" cy="48" r={RADIUS} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="6" />
                    <motion.circle
                      cx="48" cy="48" r={RADIUS}
                      fill="none"
                      stroke={isUp ? '#22c55e' : '#ef4444'}
                      strokeWidth="6"
                      strokeLinecap="round"
                      strokeDasharray={CIRCUMFERENCE}
                      initial={{ strokeDashoffset: CIRCUMFERENCE }}
                      animate={{ strokeDashoffset: dashOffset }}
                      transition={{ duration: 0.8, ease: 'easeOut' }}
                    />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    {isUp
                      ? <TrendingUp  size={28} className="text-bull" />
                      : <TrendingDown size={28} className="text-bear" />
                    }
                  </div>
                </div>

                {/* Direction + confidence */}
                <div className="text-center">
                  <div className={`text-2xl font-bold font-mono tracking-widest ${isUp ? 'text-bull' : 'text-bear'}`}>
                    {isUp ? '▲ UP' : '▼ DOWN'}
                  </div>
                  <div className="text-slate-400 text-xs mt-1">
                    {pct}% confidence
                  </div>
                </div>

                {/* Model info */}
                <div className="w-full flex justify-between text-xs text-slate-600 font-mono border-t border-white/5 pt-3">
                  <span>{pred.model === 'lstm' ? '2-Layer LSTM' : 'Heuristic'}</span>
                  <span>{pred.window_rows} rows</span>
                  <span>{age}s ago</span>
                </div>
              </motion.div>
            )}

            {!pred && !error && (
              <div className="text-slate-500 text-sm animate-pulse">Fetching prediction…</div>
            )}
          </AnimatePresence>
        )}
      </div>
    </div>
  )
}
