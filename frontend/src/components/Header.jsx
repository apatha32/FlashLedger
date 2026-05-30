import { Zap, Activity, Wifi, WifiOff, Play, Square, Bot } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

const REGIME_COLORS = {
  ranging:     'text-slate-400 bg-white/5 border-white/10',
  bull:        'text-bull bg-bull/10 border-bull/20',
  bear:        'text-bear bg-bear/10 border-bear/20',
  high_vol:    'text-gold bg-gold/10 border-gold/20',
  flash_crash: 'text-bear bg-bear/20 border-bear/40 animate-pulse',
}

const REGIME_LABELS = {
  ranging: 'RANGING', bull: 'BULL RUN', bear: 'BEAR DUMP',
  high_vol: 'HIGH VOL', flash_crash: '⚡ FLASH CRASH',
}

export default function Header({ connected, lastPrice, priceChange, metrics,
  demoRunning, demoStatus, onDemoToggle,
  aiDemoRunning, aiDemoStatus, aiDemoError, onAIDemoToggle,
}) {
  const changePositive = priceChange >= 0
  const regimeCls   = REGIME_COLORS[demoStatus?.regime] ?? REGIME_COLORS.ranging
  const regimeLabel = REGIME_LABELS[demoStatus?.regime]  ?? 'RANGING'

  return (
    <header className="bg-navy-900/80 backdrop-blur-sm border-b border-white/5 sticky top-0 z-50">
      <div className="max-w-screen-2xl mx-auto px-4 h-14 flex items-center gap-6">

        {/* Brand */}
        <div className="flex items-center gap-2 select-none shrink-0">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-brand to-indigo-600 flex items-center justify-center shadow-glow">
            <Zap size={15} className="text-white" fill="currentColor" />
          </div>
          <span className="font-semibold text-sm tracking-wide text-slate-100">
            Flash<span className="text-brand">Ledger</span>
          </span>
        </div>

        <div className="w-px h-6 bg-white/10" />

        {/* Symbol + live price */}
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono font-semibold text-slate-300 tracking-widest">
            FLASH / USD
          </span>
          {lastPrice !== null && (
            <AnimatePresence mode="wait">
              <motion.span
                key={lastPrice}
                initial={{ opacity: 0.4, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className={`font-mono font-bold text-base ${changePositive ? 'text-bull' : 'text-bear'}`}
              >
                ${lastPrice?.toFixed(2)}
              </motion.span>
            </AnimatePresence>
          )}
          {priceChange !== null && (
            <span className={`text-xs font-mono ${changePositive ? 'text-bull' : 'text-bear'}`}>
              {changePositive ? '+' : ''}{(priceChange * 100).toFixed(2)}%
            </span>
          )}
        </div>

        <div className="flex-1" />

        {/* Metrics chips */}
        {metrics && (
          <div className="hidden md:flex items-center gap-4 text-xs font-mono text-slate-400">
            <span>
              <span className="text-slate-600 mr-1">ORDERS</span>
              {metrics.orders_processed.toLocaleString()}
            </span>
            <span>
              <span className="text-slate-600 mr-1">TRADES</span>
              {metrics.trades_executed.toLocaleString()}
            </span>
            <span>
              <span className="text-slate-600 mr-1">LAT</span>
              {metrics.avg_latency_ms.toFixed(2)}ms
            </span>
            {metrics.spread != null && (
              <span>
                <span className="text-slate-600 mr-1">SPREAD</span>
                {metrics.spread.toFixed(2)}
              </span>
            )}
          </div>
        )}

        <div className="w-px h-6 bg-white/10" />

        {/* Demo mode controls */}
        <div className="flex items-center gap-2">

          {/* ── Rule-based demo (PRIMARY) ── */}
          <button
            onClick={onDemoToggle}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
              demoRunning
                ? 'bg-bear/15 border-bear/30 text-bear hover:bg-bear/25'
                : 'bg-brand/15 border-brand/30 text-brand hover:bg-brand/25'
            }`}
            title="Rule-based market simulation — market makers, trend followers, regime changes"
          >
            {demoRunning
              ? <><Square size={11} fill="currentColor" /> STOP</>
              : <><Play   size={11} fill="currentColor" /> DEMO</>
            }
          </button>

          {/* Regime badge */}
          <AnimatePresence>
            {demoRunning && demoStatus?.regime && (
              <motion.span
                key={demoStatus.regime}
                initial={{ opacity: 0, scale: 0.85 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{    opacity: 0, scale: 0.85 }}
                className={`text-[10px] font-bold font-mono px-2 py-0.5 rounded-md border ${regimeCls}`}
              >
                {regimeLabel}
              </motion.span>
            )}
          </AnimatePresence>

          <div className="w-px h-4 bg-white/10" />

          {/* ── AI demo (ADDITIONAL) ── */}
          <button
            onClick={onAIDemoToggle}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
              aiDemoRunning
                ? 'bg-bear/15 border-bear/30 text-bear hover:bg-bear/25'
                : 'bg-gold/10 border-gold/20 text-gold hover:bg-gold/20'
            }`}
            title="Groq AI agent — Llama 3.3 generates orders from live market context"
          >
            <Bot size={11} />
            {aiDemoRunning ? 'STOP AI' : 'AI DEMO'}
          </button>

          {/* AI active pulse */}
          <AnimatePresence>
            {aiDemoRunning && (
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex items-center gap-1 text-[10px] font-mono text-gold"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-gold animate-pulse inline-block" />
                groq
              </motion.span>
            )}
          </AnimatePresence>

          {/* AI error toast */}
          <AnimatePresence>
            {aiDemoError && (
              <motion.span
                initial={{ opacity: 0, x: 8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0 }}
                className="text-[10px] text-bear font-mono max-w-[180px] truncate"
                title={aiDemoError}
              >
                {aiDemoError}
              </motion.span>
            )}
          </AnimatePresence>
        </div>

        <div className="w-px h-6 bg-white/10" />

        {/* Connection status */}
        <div className="flex items-center gap-2">
          <Activity size={14} className="text-slate-500" />
          <span className="text-xs text-slate-500 hidden sm:inline">KAFKA</span>
          <span className="w-1.5 h-1.5 rounded-full bg-bull animate-pulse" title="Kafka connected" />
        </div>

        <div className="flex items-center gap-2">
          {connected ? (
            <>
              <Wifi size={14} className="text-bull" />
              <span className="text-xs text-bull font-medium hidden sm:inline">LIVE</span>
            </>
          ) : (
            <>
              <WifiOff size={14} className="text-slate-500" />
              <span className="text-xs text-slate-500 hidden sm:inline">RECONNECTING</span>
            </>
          )}
        </div>

      </div>
    </header>
  )
}
