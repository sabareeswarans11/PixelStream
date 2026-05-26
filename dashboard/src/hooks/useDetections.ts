import { useEffect, useRef, useState, useCallback } from 'react'
import type { DetectionResult } from '../types'

const WS_URL = `ws://${window.location.hostname}:8000/ws/detections`
const MAX_HISTORY = 60

export function useDetections() {
  const [latest, setLatest] = useState<DetectionResult | null>(null)
  const [history, setHistory] = useState<DetectionResult[]>([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)

    ws.onmessage = (e) => {
      try {
        const msg: DetectionResult = JSON.parse(e.data)
        setLatest(msg)
        setHistory((prev) => {
          const next = [...prev, msg]
          return next.length > MAX_HISTORY ? next.slice(-MAX_HISTORY) : next
        })
      } catch {
        // ignore malformed messages
      }
    }

    ws.onclose = () => {
      setConnected(false)
      reconnectRef.current = setTimeout(connect, 2000)
    }

    ws.onerror = () => ws.close()
  }, [])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectRef.current) clearTimeout(reconnectRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  const pushResult = useCallback((r: DetectionResult) => {
    setLatest(r)
    setHistory((prev) => {
      const next = [...prev, r]
      return next.length > MAX_HISTORY ? next.slice(-MAX_HISTORY) : next
    })
  }, [])

  return { latest, history, connected, pushResult }
}
