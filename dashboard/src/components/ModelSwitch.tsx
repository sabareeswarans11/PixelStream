import { useState } from 'react'

const MODELS = ['yolov11n', 'rtdetr-l'] as const
type Model = (typeof MODELS)[number]

const API = `http://${window.location.hostname}:8000`

interface Props {
  activeModel: string
}

export function ModelSwitch({ activeModel }: Props) {
  const [switching, setSwitching] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const switchModel = async (model: Model) => {
    if (model === activeModel || switching) return
    setSwitching(true)
    setError(null)
    try {
      const res = await fetch(`${API}/api/model`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        setError(data.detail ?? 'Switch failed')
      }
    } catch {
      setError('Network error')
    } finally {
      setSwitching(false)
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs text-gray-500 uppercase tracking-wider">Model</span>
      <div className="flex gap-2">
        {MODELS.map((m) => (
          <button
            key={m}
            onClick={() => switchModel(m)}
            disabled={switching}
            className={`px-3 py-1.5 rounded text-sm font-mono transition-colors ${
              m === activeModel
                ? 'bg-violet-600 text-white'
                : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
            } disabled:opacity-50`}
          >
            {m === 'yolov11n' ? '⚡ YOLOv11n' : '🎯 RT-DETR-l'}
          </button>
        ))}
      </div>
      {error && <span className="text-xs text-red-400">{error}</span>}
    </div>
  )
}
