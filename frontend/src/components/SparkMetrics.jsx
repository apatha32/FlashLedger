import { Layers, Cpu } from 'lucide-react'

function Row({ label, value, color = 'text-slate-200' }) {
  return (
    <div className="flex justify-between items-center text-xs font-mono py-1.5 border-b border-white/5 last:border-0">
      <span className="text-slate-500">{label}</span>
      <span className={color}>{value}</span>
    </div>
  )
}

export default function SparkMetrics() {
  // In production these would come from a /api/v1/spark-status endpoint.
  // For now we display the pipeline topology as static documentation.
  return (
    <div className="panel">
      <div className="panel-header">
        <div className="flex items-center gap-2">
          <Layers size={13} className="text-indigo-400" />
          <span className="panel-title">Spark Pipeline</span>
        </div>
        <span className="badge badge-yellow">10s windows</span>
      </div>

      <div className="px-4 py-3">
        <Row label="Source"          value="Kafka → trades"    color="text-brand-light" />
        <Row label="Engine"          value="PySpark 3.5"        color="text-slate-300" />
        <Row label="Window"          value="10 s / watermark 30 s" />
        <Row label="Features"        value="vol · vwap · imbalance · velocity" />
        <Row label="Sink"            value="PostgreSQL market_features" color="text-bull" />
        <Row label="Checkpoint"      value="/tmp/flashledger-checkpoints" />
      </div>

      <div className="px-4 pb-3">
        <div className="rounded-lg bg-navy-950 p-3 text-xs font-mono text-slate-500 leading-5">
          <div className="flex items-center gap-2 mb-2 text-indigo-400">
            <Cpu size={12} /> <span className="font-semibold">ML Pipeline</span>
          </div>
          <div>model    <span className="text-slate-300">2-Layer LSTM (PyTorch)</span></div>
          <div>input    <span className="text-slate-300">20-step sliding window</span></div>
          <div>output   <span className="text-slate-300">up / down + confidence</span></div>
          <div>retrain  <span className="text-slate-300">python -m ml.train</span></div>
        </div>
      </div>
    </div>
  )
}
