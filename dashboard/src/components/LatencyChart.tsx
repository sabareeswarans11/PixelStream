import { useMemo } from 'react'
import { ParentSize } from '@visx/responsive'
import { scaleLinear, scaleTime } from '@visx/scale'
import { LinePath, Area } from '@visx/shape'
import { AxisBottom, AxisLeft } from '@visx/axis'
import { GridRows } from '@visx/grid'
import { curveMonotoneX } from 'd3-shape'
import type { DetectionResult } from '../types'

interface Props {
  history: DetectionResult[]
}

interface ChartInnerProps extends Props {
  width: number
  height: number
}

const MARGIN = { top: 10, right: 16, bottom: 30, left: 48 }

function ChartInner({ history, width, height }: ChartInnerProps) {
  const innerW = width - MARGIN.left - MARGIN.right
  const innerH = height - MARGIN.top - MARGIN.bottom

  const data = useMemo(
    () => history.map((r) => ({ t: new Date(r.timestamp * 1000), ms: r.latency_ms })),
    [history],
  )

  const xScale = useMemo(() => {
    if (data.length < 2) return null
    return scaleTime({
      domain: [data[0].t, data[data.length - 1].t],
      range: [0, innerW],
    })
  }, [data, innerW])

  const yMax = useMemo(() => Math.max(...data.map((d) => d.ms), 100), [data])
  const yScale = useMemo(
    () => scaleLinear({ domain: [0, yMax * 1.1], range: [innerH, 0] }),
    [yMax, innerH],
  )

  if (!xScale || data.length < 2) {
    return (
      <svg width={width} height={height}>
        <text x={width / 2} y={height / 2} textAnchor="middle" fill="#4b5563" fontSize={12}>
          Waiting for data…
        </text>
      </svg>
    )
  }

  return (
    <svg width={width} height={height}>
      <defs>
        <linearGradient id="latency-gradient" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.4} />
          <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0} />
        </linearGradient>
      </defs>
      <g transform={`translate(${MARGIN.left},${MARGIN.top})`}>
        <GridRows
          scale={yScale}
          width={innerW}
          stroke="#1f2937"
          numTicks={4}
        />
        <Area
          data={data}
          x={(d) => xScale(d.t) ?? 0}
          y0={innerH}
          y1={(d) => yScale(d.ms)}
          fill="url(#latency-gradient)"
          curve={curveMonotoneX}
        />
        <LinePath
          data={data}
          x={(d) => xScale(d.t) ?? 0}
          y={(d) => yScale(d.ms)}
          stroke="#8b5cf6"
          strokeWidth={2}
          curve={curveMonotoneX}
        />
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
          numTicks={5}
          stroke="#374151"
          tickStroke="#374151"
          tickLabelProps={{ fill: '#6b7280', fontSize: 10, textAnchor: 'middle', dy: 4 }}
          tickFormat={(d) => {
            const date = d instanceof Date ? d : new Date(d as number)
            return `${date.getHours()}:${String(date.getMinutes()).padStart(2, '0')}:${String(date.getSeconds()).padStart(2, '0')}`
          }}
        />
      </g>
    </svg>
  )
}

export function LatencyChart({ history }: Props) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-xs text-gray-500 uppercase tracking-wider">Inference Latency (ms)</span>
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
