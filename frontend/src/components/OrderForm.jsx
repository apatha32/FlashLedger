import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { submitOrder } from '../api/client'

export default function OrderForm({ onOrderPlaced }) {
  const [side,     setSide]     = useState('buy')
  const [price,    setPrice]    = useState('')
  const [quantity, setQuantity] = useState('')
  const [userId,   setUserId]   = useState('trader-1')
  const [loading,  setLoading]  = useState(false)
  const [result,   setResult]   = useState(null)
  const [error,    setError]    = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setResult(null)
    setError(null)
    try {
      const data = await submitOrder({
        user_id:  userId,
        side,
        price:    parseFloat(price),
        quantity: parseFloat(quantity),
      })
      setResult(data)
      onOrderPlaced?.(data)
      setPrice('')
      setQuantity('')
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  const isBuy = side === 'buy'

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Place Order</span>
      </div>

      <form onSubmit={handleSubmit} className="p-4 flex flex-col gap-3">
        {/* Buy / Sell toggle */}
        <div className="grid grid-cols-2 gap-1.5 p-1 bg-navy-950 rounded-lg">
          {['buy', 'sell'].map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setSide(s)}
              className={`py-2 rounded-md text-sm font-semibold transition-all duration-200 ${
                side === s
                  ? s === 'buy'
                    ? 'bg-bull text-white shadow'
                    : 'bg-bear text-white shadow'
                  : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              {s.toUpperCase()}
            </button>
          ))}
        </div>

        {/* User ID */}
        <div>
          <label className="block text-xs text-slate-500 mb-1 font-mono">USER ID</label>
          <input
            className="input-field"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            placeholder="trader-1"
            required
          />
        </div>

        {/* Price */}
        <div>
          <label className="block text-xs text-slate-500 mb-1 font-mono">LIMIT PRICE</label>
          <input
            type="number"
            step="0.01"
            min="0.01"
            className="input-field"
            placeholder="100.00"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            required
          />
        </div>

        {/* Quantity */}
        <div>
          <label className="block text-xs text-slate-500 mb-1 font-mono">QUANTITY</label>
          <input
            type="number"
            step="0.0001"
            min="0.0001"
            className="input-field"
            placeholder="1.0000"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            required
          />
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={loading}
          className={`py-2.5 rounded-lg font-semibold text-sm transition-all duration-200 active:scale-[0.98] disabled:opacity-40 ${
            isBuy
              ? 'bg-bull hover:brightness-110 text-white'
              : 'bg-bear hover:brightness-110 text-white'
          }`}
        >
          {loading ? 'Placing…' : `${isBuy ? 'BUY' : 'SELL'} ${quantity || '—'} @ ${price || '—'}`}
        </button>

        {/* Feedback */}
        <AnimatePresence>
          {result && (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="rounded-lg border border-bull/30 bg-bull/10 px-3 py-2 text-xs font-mono text-bull"
            >
              <div className="font-semibold">{result.order_status.toUpperCase()}</div>
              <div className="text-slate-400 mt-0.5">
                {result.trades?.length ?? 0} trade(s) · {result.latency_ms?.toFixed(2)}ms latency
              </div>
            </motion.div>
          )}
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="rounded-lg border border-bear/30 bg-bear/10 px-3 py-2 text-xs font-mono text-bear"
            >
              {error}
            </motion.div>
          )}
        </AnimatePresence>
      </form>
    </div>
  )
}
