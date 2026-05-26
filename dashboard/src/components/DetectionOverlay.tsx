import type { DetectionResult } from '../types'

const CLASS_COLORS: Record<string, string> = {
  person: '#f87171',
  car: '#60a5fa',
  bicycle: '#34d399',
  truck: '#fbbf24',
  dog: '#a78bfa',
  cat: '#fb923c',
}

function classColor(cls: string): string {
  return CLASS_COLORS[cls] ?? '#94a3b8'
}

interface Props {
  result: DetectionResult | null
}

export function DetectionOverlay({ result }: Props) {
  if (!result) {
    return (
      <div className="relative w-full aspect-[4/3] bg-gray-900 rounded-lg flex items-center justify-center border border-gray-800">
        <span className="text-gray-600 text-sm">Waiting for frames…</span>
      </div>
    )
  }

  return (
    <div className="relative w-full aspect-[4/3] bg-gray-900 rounded-lg overflow-hidden border border-gray-800">
      {/* Video thumbnail */}
      {result.thumbnail_b64 && (
        <img
          src={`data:image/jpeg;base64,${result.thumbnail_b64}`}
          className="absolute inset-0 w-full h-full object-cover"
          alt="frame"
        />
      )}

      {/* SVG bounding box overlay — normalized coordinates match aspect ratio */}
      <svg
        className="absolute inset-0 w-full h-full"
        viewBox="0 0 1 1"
        preserveAspectRatio="none"
      >
        {result.detections.map((det, i) => {
          const [x1, y1, x2, y2] = det.bbox
          const color = classColor(det.cls)
          const labelY = Math.max(0.04, y1)
          return (
            <g key={i}>
              <rect
                x={x1}
                y={y1}
                width={x2 - x1}
                height={y2 - y1}
                fill="none"
                stroke={color}
                strokeWidth="0.004"
                opacity={0.9}
              />
              <rect
                x={x1}
                y={labelY - 0.038}
                width={Math.min(0.18, 1 - x1)}
                height={0.038}
                fill={color}
                opacity={0.85}
              />
              <text
                x={x1 + 0.006}
                y={labelY - 0.008}
                fontSize="0.028"
                fill="white"
                fontFamily="monospace"
                fontWeight="bold"
              >
                {det.cls} {(det.confidence * 100).toFixed(0)}%
              </text>
            </g>
          )
        })}
      </svg>

      {/* Metadata footer */}
      <div className="absolute bottom-0 inset-x-0 bg-black/60 px-3 py-1 flex justify-between text-xs font-mono text-gray-300">
        <span>{result.detections.length} detection{result.detections.length !== 1 ? 's' : ''}</span>
        <span>{result.latency_ms.toFixed(1)} ms</span>
        <span className="text-violet-400">{result.model}</span>
      </div>
    </div>
  )
}
