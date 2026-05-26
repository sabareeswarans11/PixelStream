import type { Stats } from '../types'

interface Props {
  stats: Stats | null
  connected: boolean
}

export function StatusBar({ stats, connected }: Props) {
  return (
    <div className="flex items-center gap-6 px-4 py-2 bg-gray-900 border-b border-gray-800 text-sm">
      <span className="font-semibold text-violet-400 tracking-wide">PixelStream</span>
      <span className={`flex items-center gap-1.5 ${connected ? 'text-green-400' : 'text-red-400'}`}>
        <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400 animate-pulse' : 'bg-red-500'}`} />
        {connected ? 'Live' : 'Reconnecting…'}
      </span>
      {stats && (
        <>
          <Stat label="FPS" value={stats.fps.toFixed(1)} />
          <Stat label="Frames" value={stats.total_frames.toLocaleString()} />
          <Stat label="Detections" value={stats.total_detections.toLocaleString()} />
          <Stat label="Uptime" value={`${stats.uptime_seconds}s`} />
          <span className="ml-auto text-gray-500">
            model: <span className="text-violet-300">{stats.active_model}</span>
          </span>
        </>
      )}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <span className="text-gray-400">
      {label}: <span className="text-white font-mono">{value}</span>
    </span>
  )
}
