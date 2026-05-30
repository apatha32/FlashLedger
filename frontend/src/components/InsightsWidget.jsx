import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Lightbulb, RefreshCw, TrendingUp, TrendingDown, Minus, CheckCircle, Sparkles } from 'lucide-react'
import { fetchInsights } from '../api/client'

// ── Sub-components ─────────────────────────────────────────────────────────

const REGIME_META = {
  TRENDING_UP:    { label: 'Trending Up',    cls: 'badge-green'  },
  TRENDING_DOWN:  { label: 'Trending Down',  cls: 'badge-red'    },
  HIGH_VOLATILITY:{ label: 'High Volatility',cls: 'badge-yellow' },
  RANGING:        { label: 'Ranging',        cls: 'badge-blue'   },
}

function RegimeBadge({ regime }) {
  const meta = REGIME_META[regime] ?? { label: regime, cls: 'badge-blue' }
  return <span className={meta.cls}>{meta.label}</span>
}

function ActionDisplay({ action, confidence }) {
  const cfg = {
    BUY:  { color: 'text-bull',  bg: 'bg-bull/10',  border: 'border-bull/30',  Icon: TrendingUp  },
    SELL: { color: 'text-bear',  bg: 'bg-bear/10',  border: 'border-bear/30',  Icon: TrendingDown },
    HOLD: { color: 'text-slate-300', bg: 'bg-white/5', border: 'border-white/10', Icon: Minus     },
  }[action] ?? { color: 'text-slate-300', bg: 'bg-white/5', border: 'border-white/10', Icon: Minus }

  const { color, bg, border, Icon } = cfg

  return (
    <div className={`flex items-center justify-between rounded-xl px-4 py-3 border ${bg} ${border}`}>
      <div className="flex items-center gap-3">
        <Icon size={22} className={color} />
        <div>
          <div className={`text-xl font-bold font-mono tracking-widest ${color}`}>{action}</div>
          <div className="text-xs text-slate-500 mt-0.5">Recommendation</div>
        </div>
      </div>
      <div className="text-right">
        <div className={`text-lg font-bold font-mono ${color}`}>{Math.round(confidence * 100)}%</div>
        <div className="text-xs text-slate-500">confidence</div>
      </div>
    </div>
  )
}

function ProbBar({ sell, hold, buy }) {
  return (
    <div>
      <div className="flex justify-between text-xs font-mono text-slate-500 mb-1">
        <span>SELL {Math.round(sell * 100)}%</span>
        <span>HOLD {Math.round(hold * 100)}%</span>
        <span>BUY {Math.round(buy * 100)}%</span>
      </div>
      <div className="flex h-2 rounded-full overflow-hidden gap-px">
        <motion.div
          className="bg-bear rounded-l-full"
          animate={{ width: `${sell * 100}%` }}
          transition={{ duration: 0.6 }}
        />
        <motion.div
          className="bg-slate-600"
          animate={{ width: `${hold * 100}%` }}
          transition={{ duration: 0.6 }}
        />
        <motion.div
          className="bg-bull rounded-r-full"
          animate={{ width: `${buy * 100}%` }}
          transition={{ duration: 0.6 }}
        />
      </div>
    </div>
  )
}

function FeatureBar({ label, value, min = -5, max = 5, unit = '' }) {
  const pct = Math.min(Math.max(((value - min) / (max - min)) * 100, 0), 100)
  const isPositive = value >= 0

  return (
    <div className="flex items-center gap-2 text-xs font-mono">
      <span className="text-slate-500 w-24 shrink-0 truncate">{label}</span>
      <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
        <motion.div
          className={`h-full rounded-full ${isPositive ? 'bg-bull' : 'bg-bear'}`}
          style={{ marginLeft: isPositive ? '50%' : undefined, marginRight: !isPositive ? `${100 - pct}%` : undefined }}
          animate={{ width: `${Math.abs(pct - 50)}%` }}
          transition={{ duration: 0.5 }}
        />
      </div>
      <span className={`w-14 text-right ${isPositive ? 'text-bull' : 'text-bear'}`}>
        {value > 0 ? '+' : ''}{value}{unit}
      </span>
    </div>
  )
}

function SimilarCard({ rank, similarity, outcome }) {
  const color = { BUY: 'text-bull', SELL: 'text-bear', HOLD: 'text-slate-400' }[outcome]
  return (
    <div className="flex items-center justify-between text-xs font-mono py-1.5 border-b border-white/5 last:border-0">
      <span className="text-slate-600">#{rank}</span>
      <span className="text-slate-400 flex-1 text-center">{Math.round(similarity * 100)}% similar</span>
      <span className={`font-semibold ${color}`}>→ {outcome}</span>
    </div>
  )
}

// ── Main Component ─────────────────────────────────────────────────────────

export default function InsightsWidget() {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)
  const [age,     setAge]     = useState(0)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const resp = await fetchInsights()
      setData(resp)
      setAge(0)
    } catch {
      setError('Could not load insights')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const interval = setInterval(load, 20_000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    const t = setInterval(() => setAge((a) => a + 1), 1000)
    return () => clearInterval(t)
  }, [])

  const fv = data?.feature_values ?? {}

  return (
    <div className="panel flex flex-col h-full">
      <div className="panel-header">
        <div className="flex items-center gap-2">
          <Lightbulb size={14} className="text-gold" />
          <span className="panel-title">Market Insights</span>
        </div>
        <div className="flex items-center gap-2">
          {data && <RegimeBadge regime={data.regime} />}
          <button
            onClick={load}
            disabled={loading}
            className="text-slate-500 hover:text-slate-300 transition-colors disabled:opacity-40"
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-4">
        {error && (
          <div className="text-slate-500 text-sm text-center py-4">{error}</div>
        )}

        <AnimatePresence mode="wait">
          {data && (
            <motion.div
              key={data.action + data.confidence}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex flex-col gap-4"
            >
              {/* Action */}
              <ActionDisplay action={data.action} confidence={data.confidence} />

              {/* Probability bar */}
              <ProbBar {...data.probabilities} />

              {/* RSI */}
              <div className="flex justify-between items-center text-xs font-mono">
                <span className="text-slate-500">RSI(14)</span>
                <span className={`font-semibold ${
                  data.rsi > 70 ? 'text-bear' : data.rsi < 30 ? 'text-bull' : 'text-slate-300'
                }`}>{data.rsi}</span>
              </div>

              {/* Feature bars */}
              <div className="flex flex-col gap-1.5">
                <div className="text-xs text-slate-600 uppercase tracking-wider mb-1">Feature Analysis</div>
                <FeatureBar label="VWAP Δ"     value={fv.vwap_change ?? 0}     min={-2}  max={2}  unit="%" />
                <FeatureBar label="Vol Ratio"  value={fv.volume_ratio ?? 1}     min={0}   max={3}  unit="×" />
                <FeatureBar label="Imbalance"  value={fv.imbalance_norm ?? 0}   min={-2}  max={2}  unit="" />
                <FeatureBar label="Vel Δ"      value={fv.velocity_change ?? 0}  min={-50} max={50} unit="%" />
                <FeatureBar label="Volatility" value={fv.volatility ?? 0}       min={0}   max={3}  unit="%" />
              </div>

              {/* Insights */}
              {data.insights?.length > 0 && (
                <div className="flex flex-col gap-1.5">
                  <div className="text-xs text-slate-600 uppercase tracking-wider mb-1">Insights</div>
                  {data.insights.map((insight, i) => (
                    <div key={i} className="flex gap-2 text-xs text-slate-300 leading-relaxed">
                      <CheckCircle size={12} className="text-brand shrink-0 mt-0.5" />
                      <span>{insight}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Similar historical conditions */}
              {data.similar_conditions?.length > 0 && (
                <div>
                  <div className="text-xs text-slate-600 uppercase tracking-wider mb-2">
                    Similar Historical Patterns
                  </div>
                  {data.similar_conditions.map((sc) => (
                    <SimilarCard key={sc.rank} {...sc} />
                  ))}
                </div>
              )}

              {/* Groq AI Commentary */}
              {data.ai_commentary && (
                <div className="rounded-xl border border-brand/20 bg-brand/5 px-3 py-2.5">
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <Sparkles size={11} className="text-gold" />
                    <span className="text-[10px] uppercase tracking-wider text-gold/80 font-semibold">AI Analysis · Groq</span>
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed">{data.ai_commentary}</p>
                </div>
              )}

              <div className="text-xs text-slate-700 font-mono text-right">
                {data.probabilities.sell === 0.33 ? 'heuristic mode' : 'lightgbm'} · {age}s ago
              </div>
            </motion.div>
          )}

          {!data && !error && (
            <div className="text-slate-500 text-sm animate-pulse text-center py-8">
              Analysing market conditions…
            </div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
