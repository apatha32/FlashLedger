import { useEffect, useRef, useState, useCallback } from 'react'

const WS_URL =
  typeof window !== 'undefined'
    ? `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api/v1/ws`
    : 'ws://localhost:8000/api/v1/ws'

export function useWebSocket() {
  const wsRef    = useRef(null)
  const [connected, setConnected] = useState(false)
  const [orderBook, setOrderBook] = useState({ bids: [], asks: [], symbol: 'FLASH' })
  const [metrics,   setMetrics]   = useState(null)
  const [lastTrade, setLastTrade] = useState(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
    }

    ws.onmessage = (event) => {
      try {
        if (event.data === 'pong') return
        const msg = JSON.parse(event.data)

        if (msg.type === 'orderbook_update') setOrderBook(msg.data)
        if (msg.type === 'metrics_update')   setMetrics(msg.data)
        if (msg.type === 'trade_executed')   setLastTrade(msg.data)
      } catch (_) {}
    }

    ws.onclose = () => {
      setConnected(false)
      // Reconnect after 3 s
      setTimeout(connect, 3000)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [])

  useEffect(() => {
    connect()
    // Heartbeat ping every 25 s
    const ping = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send('ping')
      }
    }, 25_000)
    return () => {
      clearInterval(ping)
      wsRef.current?.close()
    }
  }, [connect])

  return { connected, orderBook, metrics, lastTrade }
}
