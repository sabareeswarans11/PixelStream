import { useMemo } from 'react'
import { ParentSize } from '@visx/responsive'
import { scaleBand, scaleLinear } from '@visx/scale'
import { Bar } from '@visx/shape'
import { AxisBottom, AxisLeft } from '@visx/axis'
import type { DetectionResult } from '../types'

interface Props {
  history: DetectionResult[]
}

const COLORS = ['#8b5cf6', '#60a5fa', '#34d399', '#f87171', '#fbbf24', '#fb923c', '#a78bfa']
const MARGIN = { top: 10, right: 16, bottom: 40, left: 48 }

function ChartInner({ history, width, height }: Props & { width: number; height: number }) {
  const innerW = width - MARGIN.left - MARGIN.right
  const innerH = height - MARGIN.top - MARGIN.bottom

  const counts = useMemo(() => {
    const map: Record<string, number> = {}
    for (const r of history) {
      for (const d of r.detections) {
        map[d.cls] = (map[d.cls] ?? 0) + 1
      }
    }
    return Object.entries(map)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
  }, [history])

  const xScale = scaleBand({
    domain: counts.map(([cls]) => cls),
    range: [0, innerW],
    padding: 0.3,
  })

  const yMax = Math.max(...counts.map(([, c]) => c), 1)
  const yScale = scaleLinear({ domain: [0, yMax], range: [innerH, 0] })

  if (counts.length === 0) {
    return (
      <svg width={width} height={height}>
        <text x={width / 2} y={height / 2} textAnchor="middle" fill="#4b5563" fontSize={12}>
          No detections yet
        </text>
      </svg>
    )
  }

  return (
    <svg width={width} height={height}>
      <g transform={`translate(${MARGIN.left},${MARGIN.top})`}>
        {counts.map(([cls, count], i) => {
          const bw = xScale.bandwidth()
          const bx = xScale(cls) ?? 0
          const by = yScale(count)
          const bh = innerH - by
          return (
            <Bar
              key={cls}
              x={bx}
              y={by}
              width={bw}
              height={bh}
              fill={COLORS[i % COLORS.length]}
              opacity={0.85}
              rx={2}
            />
          )
        })}
        <AxisLeft
          scale={yScale}
          numTicks={4}
          stroke="#374151"
          tickStroke="#374151"
          tickLabelProps={{ fill: '#6b7280', fontSize: 10, textAnchor: 'end', dx: -4 }}
        />
        <AxisBottom
          scale={xScale}
          top={innerH}
          stroke="#374151"
          tickStroke="#374151"
          tickLabelProps={{ fill: '#9ca3af', fontSize: 11, textAnchor: 'middle', dy: 4 }}
        />
      </g>
    </svg>
  )
}

export function ClassBarChart({ history }: Props) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-xs text-gray-500 uppercase tracking-wider">Detections by Class</span>
      <div className="h-40 bg-gray-900 rounded-lg border border-gray-800 overflow-hidden">
        <ParentSize>
          {({ width, height }) => (
            <ChartInner history={history} width={width} height={height} />
          )}
        </ParentSize>
      </div>
    </div>
  )
}
