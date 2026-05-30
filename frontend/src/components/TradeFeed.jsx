import { useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

function TradeRow({ trade, isNew }) {
  const isBuy  = trade.aggressor_side === 'buy'
  const ts     = new Date(trade.timestamp)
  const time   = ts.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })

  return (
    <motion.div
      initial={isNew ? { opacity: 0, x: 20, backgroundColor: isBuy ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)' } : false}
      animate={{ opacity: 1, x: 0, backgroundColor: 'transparent' }}
      transition={{ duration: 0.4 }}
      className="grid grid-cols-4 text-xs font-mono px-3 py-1 hover:bg-white/[0.03] rounded"
    >
      <span className="text-slate-500">{time}</span>
      <span className={isBuy ? 'text-bull text-right' : 'text-bear text-right'}>
        ${trade.price?.toFixed(2)}
      </span>
      <span className="text-slate-300 text-right">{trade.quantity?.toFixed(4)}</span>
      <span className={`text-right font-medium ${isBuy ? 'text-bull' : 'text-bear'}`}>
        {isBuy ? 'BUY' : 'SELL'}
      </span>
    </motion.div>
  )
}

export default function TradeFeed({ trades }) {
  const listRef = useRef(null)

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = 0
    }
  }, [trades.length])

  return (
    <div className="panel flex flex-col h-full">
      <div className="panel-header">
        <span className="panel-title">Trade Feed</span>
        <span className="badge badge-blue">{trades.length} recent</span>
      </div>

      {/* Column headers */}
      <div className="grid grid-cols-4 text-xs font-mono text-slate-600 px-3 py-1.5 border-b border-white/5">
        <span>TIME</span>
        <span className="text-right">PRICE</span>
        <span className="text-right">QTY</span>
        <span className="text-right">SIDE</span>
      </div>

      <div
        ref={listRef}
        className="flex-1 overflow-y-auto py-1 flex flex-col gap-0"
      >
        <AnimatePresence initial={false}>
          {trades.map((t, i) => (
            <TradeRow key={t.trade_id} trade={t} isNew={i === 0} />
          ))}
        </AnimatePresence>

        {trades.length === 0 && (
          <div className="flex-1 flex items-center justify-center text-slate-600 text-sm">
            Awaiting trades…
          </div>
        )}
      </div>
    </div>
  )
}
