import { useEffect, useState } from 'react'
import type { Stats } from '../types'

const API = `http://${window.location.hostname}:8000`

export function useStats() {
  const [stats, setStats] = useState<Stats | null>(null)

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch(`${API}/api/stats`)
        if (res.ok) setStats(await res.json())
      } catch {
        // API not ready yet
      }
    }
    poll()
    const id = setInterval(poll, 5000)
    return () => clearInterval(id)
  }, [])

  return stats
}
