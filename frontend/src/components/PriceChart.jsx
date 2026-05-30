import {
  ResponsiveContainer, ComposedChart, Line, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine,
} from 'recharts'
import { TrendingUp, TrendingDown } from 'lucide-react'

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const d = payload[0]?.payload
  return (
    <div className="bg-navy-800 border border-white/10 rounded-lg px-3 py-2 text-xs font-mono shadow-panel">
      <div className="text-slate-400">{d?.time}</div>
      <div className="text-white font-semibold">${d?.price?.toFixed(2)}</div>
      <div className="text-slate-400">Vol {d?.volume?.toFixed(2)}</div>
    </div>
  )
}

export default function PriceChart({ trades }) {
  // Build OHLCV-style buckets from raw trades (group by 2-second intervals)
  const data = (() => {
    if (!trades.length) return []
    const buckets = {}
    trades.forEach((t) => {
      const ts  = new Date(t.timestamp)
      const key = Math.floor(ts.getTime() / 2000) * 2000  // 2-second buckets
      if (!buckets[key]) buckets[key] = { prices: [], volume: 0, ts: key }
      buckets[key].prices.push(t.price)
      buckets[key].volume += t.quantity
    })
    return Object.values(buckets)
      .sort((a, b) => a.ts - b.ts)
      .slice(-60)
      .map((b) => ({
        time:   new Date(b.ts).toLocaleTimeString('en-US', { hour12: false }),
        price:  b.prices[b.prices.length - 1],
        volume: b.volume,
      }))
  })()

  const prices    = data.map((d) => d.price)
  const minP      = Math.min(...prices) * 0.9995
  const maxP      = Math.max(...prices) * 1.0005
  const trend     = prices.length >= 2 ? prices[prices.length - 1] - prices[0] : 0
  const trendPct  = prices[0] ? (trend / prices[0]) * 100 : 0

  return (
    <div className="panel flex flex-col h-full">
      <div className="panel-header">
        <span className="panel-title">Price Chart</span>
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-slate-500">2s candles</span>
          {trend !== 0 && (
            <span className={`flex items-center gap-1 text-xs font-mono font-semibold ${trend >= 0 ? 'text-bull' : 'text-bear'}`}>
              {trend >= 0 ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
              {trend >= 0 ? '+' : ''}{trendPct.toFixed(2)}%
            </span>
          )}
        </div>
      </div>

      {data.length < 2 ? (
        <div className="flex-1 flex items-center justify-center text-slate-600 text-sm">
          Waiting for trade data…
        </div>
      ) : (
        <div className="flex-1 px-2 py-3">
          <ResponsiveContainer width="100%" height="70%">
            <ComposedChart data={data} margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis
                dataKey="time"
                tick={{ fill: '#475569', fontSize: 10, fontFamily: 'JetBrains Mono' }}
                axisLine={false}
                tickLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                domain={[minP, maxP]}
                tick={{ fill: '#475569', fontSize: 10, fontFamily: 'JetBrains Mono' }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => `$${v.toFixed(0)}`}
                width={52}
              />
              <Tooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey="price"
                stroke={trend >= 0 ? '#22c55e' : '#ef4444'}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 3, fill: trend >= 0 ? '#22c55e' : '#ef4444' }}
                isAnimationActive={false}
              />
            </ComposedChart>
          </ResponsiveContainer>

          {/* Volume bars */}
          <ResponsiveContainer width="100%" height="28%">
            <ComposedChart data={data} margin={{ top: 0, right: 12, left: 0, bottom: 0 }}>
              <XAxis dataKey="time" hide />
              <YAxis hide />
              <Bar dataKey="volume" fill="rgba(59,130,246,0.3)" radius={[2, 2, 0, 0]} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
