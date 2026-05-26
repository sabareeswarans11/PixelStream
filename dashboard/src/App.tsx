import { useDetections } from './hooks/useDetections'
import { useStats } from './hooks/useStats'
import { StatusBar } from './components/StatusBar'
import { ModelSwitch } from './components/ModelSwitch'
import { VideoPlayer } from './components/VideoPlayer'
import { LatencyChart } from './components/LatencyChart'
import { ClassBarChart } from './components/ClassBarChart'
import { DetectionFeed } from './components/DetectionFeed'
import './index.css'

export default function App() {
  const { latest, history, connected, pushResult } = useDetections()
  const stats = useStats()

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">
      <StatusBar stats={stats} connected={connected} />

      <div className="flex-1 p-4 grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left column: video player with bbox overlay + model switch */}
        <div className="lg:col-span-2 flex flex-col gap-4">
          <VideoPlayer result={latest} onAutoDetect={pushResult} />
          <div className="flex items-center justify-between px-1">
            <ModelSwitch activeModel={stats?.active_model ?? 'yolov11n'} />
            {latest && (
              <span className="text-xs text-gray-500 font-mono">
                frame {latest.frame_id.slice(0, 8)}…
              </span>
            )}
          </div>
        </div>

        {/* Right column: charts + feed */}
        <div className="flex flex-col gap-4">
          <LatencyChart history={history} />
          <ClassBarChart history={history} />
          <DetectionFeed history={history} />
        </div>
      </div>
    </div>
  )
}
