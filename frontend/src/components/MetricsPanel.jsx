import { motion } from 'framer-motion'
import { Activity, Zap, BarChart2, GitMerge } from 'lucide-react'

function StatCard({ icon: Icon, label, value, unit, color = 'text-brand-light' }) {
  return (
    <motion.div
      layout
      className="stat-card"
    >
      <div className="flex items-center gap-2 text-slate-500">
        <Icon size={13} />
        <span className="stat-label">{label}</span>
      </div>
      <div className={`stat-value ${color}`}>
        {value ?? '—'}
        {unit && <span className="text-xs text-slate-500 ml-1">{unit}</span>}
      </div>
    </motion.div>
  )
}

export default function MetricsPanel({ metrics }) {
  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Engine Metrics</span>
        <span className="w-1.5 h-1.5 rounded-full bg-bull animate-pulse-slow" />
      </div>

      <div className="p-3 grid grid-cols-2 gap-2">
        <StatCard
          icon={GitMerge}
          label="Orders"
          value={metrics?.orders_processed?.toLocaleString() ?? '0'}
          color="text-brand-light"
        />
        <StatCard
          icon={Activity}
          label="Trades"
          value={metrics?.trades_executed?.toLocaleString() ?? '0'}
          color="text-bull"
        />
        <StatCard
          icon={Zap}
          label="Avg Latency"
          value={metrics?.avg_latency_ms?.toFixed(3) ?? '—'}
          unit="ms"
          color="text-gold"
        />
        <StatCard
          icon={BarChart2}
          label="Spread"
          value={metrics?.spread != null ? metrics.spread.toFixed(2) : '—'}
          color="text-slate-300"
        />
      </div>
    </div>
  )
}
