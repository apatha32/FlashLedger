import { useMemo } from 'react'
import { motion } from 'framer-motion'

function DepthRow({ price, quantity, cumulative, maxCumulative, side }) {
  const pct = maxCumulative > 0 ? (cumulative / maxCumulative) * 100 : 0
  const isBuy = side === 'bid'

  return (
    <div className="relative flex items-center h-6 text-xs font-mono group">
      {/* Depth bar */}
      <motion.div
        className={`absolute right-0 top-0 h-full opacity-15 ${isBuy ? 'bg-bull' : 'bg-bear'}`}
        style={{ width: `${pct}%` }}
        layout
        transition={{ duration: 0.25 }}
      />
      <span className="relative z-10 w-1/2 text-right pr-4 text-slate-300 group-hover:text-white">
        {price.toFixed(2)}
      </span>
      <span className={`relative z-10 w-1/2 text-right pr-3 ${isBuy ? 'text-bull' : 'text-bear'}`}>
        {quantity.toFixed(4)}
      </span>
    </div>
  )
}

export default function OrderBook({ orderBook }) {
  const { bids = [], asks = [] } = orderBook

  const maxCumBid = useMemo(() => {
    let cum = 0
    return bids.reduce((acc, b) => { cum += b.quantity; return Math.max(acc, cum) }, 0)
  }, [bids])

  const maxCumAsk = useMemo(() => {
    let cum = 0
    return asks.reduce((acc, a) => { cum += a.quantity; return Math.max(acc, cum) }, 0)
  }, [asks])

  const spread = useMemo(() => {
    if (!bids.length || !asks.length) return null
    return (asks[0].price - bids[0].price).toFixed(2)
  }, [bids, asks])

  // Cumulative quantities
  const bidsWithCum = useMemo(() => {
    let cum = 0
    return bids.map((b) => ({ ...b, cumulative: (cum += b.quantity) }))
  }, [bids])

  const asksWithCum = useMemo(() => {
    let cum = 0
    return asks.map((a) => ({ ...a, cumulative: (cum += a.quantity) }))
  }, [asks])

  return (
    <div className="panel flex flex-col h-full">
      <div className="panel-header">
        <span className="panel-title">Order Book</span>
        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="text-slate-500">SPREAD</span>
          <span className="text-gold">{spread ?? '—'}</span>
        </div>
      </div>

      {/* Column headers */}
      <div className="flex text-xs font-mono text-slate-600 px-3 py-1.5 border-b border-white/5">
        <span className="w-1/2 text-right pr-4">PRICE</span>
        <span className="w-1/2 text-right pr-3">QTY</span>
      </div>

      {/* Asks — ascending, so reverse display */}
      <div className="flex-1 overflow-hidden flex flex-col-reverse px-3 py-1 gap-0.5">
        {asksWithCum.slice(0, 12).reverse().map((a) => (
          <DepthRow key={a.price} {...a} maxCumulative={maxCumAsk} side="ask" />
        ))}
      </div>

      {/* Mid price */}
      <div className="px-3 py-1.5 flex items-center justify-center border-y border-white/5">
        {bids.length && asks.length ? (
          <span className="font-mono font-bold text-sm text-white">
            ${((bids[0].price + asks[0].price) / 2).toFixed(2)}
          </span>
        ) : (
          <span className="text-slate-600 text-xs">no market</span>
        )}
      </div>

      {/* Bids */}
      <div className="flex-1 overflow-hidden px-3 py-1 flex flex-col gap-0.5">
        {bidsWithCum.slice(0, 12).map((b) => (
          <DepthRow key={b.price} {...b} maxCumulative={maxCumBid} side="bid" />
        ))}
      </div>
    </div>
  )
}
