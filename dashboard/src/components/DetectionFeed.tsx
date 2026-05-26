import type { DetectionResult } from '../types'

interface Props {
  history: DetectionResult[]
}

const CLASS_COLORS: Record<string, string> = {
  person: 'bg-red-900/50 text-red-300',
  car: 'bg-blue-900/50 text-blue-300',
  bicycle: 'bg-emerald-900/50 text-emerald-300',
  truck: 'bg-amber-900/50 text-amber-300',
  dog: 'bg-violet-900/50 text-violet-300',
  cat: 'bg-orange-900/50 text-orange-300',
}

function badge(cls: string) {
  return CLASS_COLORS[cls] ?? 'bg-gray-800 text-gray-300'
}

export function DetectionFeed({ history }: Props) {
  const recent = [...history].reverse().slice(0, 8)

  return (
    <div className="flex flex-col gap-2">
      <span className="text-xs text-gray-500 uppercase tracking-wider">Recent Detections</span>
      <div className="flex flex-col gap-1 max-h-48 overflow-y-auto">
        {recent.length === 0 && (
          <span className="text-gray-600 text-sm">No detections yet</span>
        )}
        {recent.map((r) => (
          <div
            key={r.frame_id}
            className="flex items-center gap-2 px-3 py-1.5 bg-gray-900 rounded border border-gray-800 text-xs"
          >
            <span className="text-gray-600 font-mono w-20 shrink-0 truncate">{r.frame_id.slice(0, 8)}</span>
            <div className="flex flex-wrap gap-1 flex-1">
              {r.detections.map((d, i) => (
                <span key={i} className={`px-1.5 py-0.5 rounded text-xs font-mono ${badge(d.cls)}`}>
                  {d.cls} {(d.confidence * 100).toFixed(0)}%
                </span>
              ))}
              {r.detections.length === 0 && (
                <span className="text-gray-700">no detections</span>
              )}
            </div>
            <span className="text-gray-600 shrink-0">{r.latency_ms.toFixed(0)}ms</span>
          </div>
        ))}
      </div>
    </div>
  )
}
