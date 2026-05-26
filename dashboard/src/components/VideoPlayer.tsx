import { useRef, useEffect, useState, useCallback } from 'react'
import Hls from 'hls.js'
import type { DetectionResult, Detection } from '../types'

const API = `http://${window.location.hostname}:8000`

const PRESETS = [
  { label: '📁 Sample', url: `${API}/api/video/sample`, desc: 'Pedestrian footage — good for person detection' },
  { label: '🚗 City Traffic', url: `${API}/api/video/city`, desc: 'Aerial traffic scene — cars, trucks' },
  { label: '🔴 Marblehead Live', url: 'https://cs9.pixelcaster.com/live/lesi-lighthouse.stream/playlist.m3u8', desc: 'Marblehead Lighthouse webcam (Ohio, live HLS)' },
  { label: '🌐 Custom URL', url: '', desc: 'Paste any direct MP4 or HLS .m3u8 URL' },
]

const CLASS_COLORS: Record<string, string> = {
  person: '#f87171', car: '#60a5fa', bicycle: '#34d399',
  truck: '#fbbf24', motorcycle: '#fb923c', bus: '#a78bfa',
  dog: '#34d399', cat: '#fb923c',
}
const classColor = (cls: string) => CLASS_COLORS[cls] ?? '#94a3b8'

function drawBoxes(canvas: HTMLCanvasElement, detections: Detection[]) {
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  const { width, height } = canvas
  for (const det of detections) {
    const [x1, y1, x2, y2] = det.bbox
    const bx = x1 * width, by = y1 * height
    const bw = (x2 - x1) * width, bh = (y2 - y1) * height
    const color = classColor(det.cls)
    const label = `${det.cls} ${(det.confidence * 100).toFixed(0)}%`
    ctx.strokeStyle = color; ctx.lineWidth = 2.5
    ctx.strokeRect(bx, by, bw, bh)
    ctx.font = 'bold 12px monospace'
    const lw = ctx.measureText(label).width + 10
    const lh = 20, ly = by > lh + 2 ? by - lh : by + bh
    ctx.fillStyle = color
    ctx.beginPath(); ctx.roundRect(bx, ly, lw, lh, 3); ctx.fill()
    ctx.fillStyle = '#fff'; ctx.fillText(label, bx + 5, ly + 14)
  }
}

interface Props {
  result: DetectionResult | null
  onAutoDetect?: (r: DetectionResult) => void
}

export function VideoPlayer({ result, onAutoDetect }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const hlsRef = useRef<Hls | null>(null)

  const [presetIdx, setPresetIdx] = useState(0)
  const [customUrl, setCustomUrl] = useState('')
  const [uploadSrc, setUploadSrc] = useState<string | null>(null)
  const [useUpload, setUseUpload] = useState(false)

  const [detecting, setDetecting] = useState(false)
  const [detectErr, setDetectErr] = useState<string | null>(null)
  const [manualDets, setManualDets] = useState<Detection[] | null>(null)
  const [manualModel, setManualModel] = useState('')
  const [manualLatency, setManualLatency] = useState<number | null>(null)
  const [autoDetect, setAutoDetect] = useState(false)
  const clearTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const autoTimer = useRef<ReturnType<typeof setInterval> | undefined>(undefined)
  const autoRunning = useRef(false)  // guard against overlapping auto-detect calls

  const effectiveSrc = useCallback((): string => {
    if (useUpload && uploadSrc) return uploadSrc
    if (presetIdx === PRESETS.length - 1) return customUrl
    return PRESETS[presetIdx].url
  }, [useUpload, uploadSrc, presetIdx, customUrl])

  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    const src = effectiveSrc()

    if (hlsRef.current) { hlsRef.current.destroy(); hlsRef.current = null }

    if (!src) { video.src = ''; return }

    if (src.includes('.m3u8') && Hls.isSupported()) {
      const hls = new Hls({ enableWorker: false })
      hls.loadSource(src)
      hls.attachMedia(video)
      hlsRef.current = hls
    } else {
      video.src = src
      video.load()
      video.play().catch(() => {})
    }
  }, [effectiveSrc])

  useEffect(() => {
    const video = videoRef.current, canvas = canvasRef.current
    if (!video || !canvas) return
    const ro = new ResizeObserver(() => {
      canvas.width = video.clientWidth || 640
      canvas.height = video.clientHeight || 360
    })
    ro.observe(video)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current, video = videoRef.current
    if (!canvas) return
    canvas.width = video?.clientWidth || canvas.width
    canvas.height = video?.clientHeight || canvas.height
    const dets = manualDets ?? result?.detections ?? []
    drawBoxes(canvas, dets)
  }, [result, manualDets])

  // Shared frame-capture + detect logic
  const detectFrame = useCallback(async (): Promise<DetectionResult | null> => {
    const video = videoRef.current
    if (!video || video.readyState < 2) return null

    const tmp = document.createElement('canvas')
    tmp.width = video.videoWidth || 640
    tmp.height = video.videoHeight || 480
    const ctx = tmp.getContext('2d')!
    ctx.drawImage(video, 0, 0)

    const blob = await new Promise<Blob | null>((res) =>
      tmp.toBlob(res, 'image/jpeg', 0.85),
    )
    if (!blob) return null

    const fd = new FormData()
    fd.append('file', blob, 'frame.jpg')

    const res = await fetch(`${API}/api/detect`, { method: 'POST', body: fd })
    if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`)
    const data = await res.json()

    return {
      frame_id: crypto.randomUUID(),
      timestamp: Date.now() / 1000,
      model: data.model,
      latency_ms: data.latency_ms ?? 0,
      detections: data.detections,
    }
  }, [])

  // Auto-detect: captures a frame every second while ON
  useEffect(() => {
    if (!autoDetect) {
      clearInterval(autoTimer.current)
      autoTimer.current = undefined
      // Clear bboxes so WS stream overlay resumes
      setManualDets(null)
      setManualModel('')
      setManualLatency(null)
      return
    }

    autoTimer.current = setInterval(async () => {
      if (autoRunning.current) return
      autoRunning.current = true
      try {
        const dr = await detectFrame()
        if (dr) {
          setManualDets(dr.detections)
          setManualModel(dr.model)
          setManualLatency(dr.latency_ms)
          onAutoDetect?.(dr)
        }
      } catch {
        // silently ignore per-frame errors in auto mode
      } finally {
        autoRunning.current = false
      }
    }, 1000)

    return () => clearInterval(autoTimer.current)
  }, [autoDetect, detectFrame, onAutoDetect])

  const handleUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (uploadSrc) URL.revokeObjectURL(uploadSrc)
    setUploadSrc(URL.createObjectURL(file))
    setUseUpload(true)
    setManualDets(null)
  }

  const handleDetect = async () => {
    const video = videoRef.current
    if (!video) { setDetectErr('No video element'); return }
    if (video.readyState < 2) { setDetectErr('Video not ready — wait for it to load'); return }

    setDetecting(true)
    setDetectErr(null)

    try {
      const dr = await detectFrame()
      if (!dr) throw new Error('Frame capture returned null')

      setManualDets(dr.detections)
      setManualModel(dr.model)
      setManualLatency(dr.latency_ms)
      onAutoDetect?.(dr)

      clearTimeout(clearTimer.current)
      clearTimer.current = setTimeout(() => {
        setManualDets(null)
        setManualLatency(null)
      }, 4000)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setDetectErr(msg.includes('Tainted') || msg.includes('cross')
        ? 'Canvas blocked — video must load from same origin (use local presets, not Custom URL)'
        : msg)
    } finally {
      setDetecting(false)
    }
  }

  const src = effectiveSrc()
  const activeDets = manualDets ?? result?.detections ?? []
  const activeModel = manualDets ? manualModel : (result?.model ?? '')
  const activeLatency = manualDets ? manualLatency : (result?.latency_ms ?? null)

  return (
    <div className="flex flex-col gap-3">
      {/* Source tabs */}
      <div className="flex flex-wrap items-center gap-2">
        {PRESETS.map((p, i) => (
          <button key={i} onClick={() => { setUseUpload(false); setPresetIdx(i); setManualDets(null) }}
            title={p.desc}
            className={`px-3 py-1.5 rounded text-xs font-mono transition-colors ${
              !useUpload && presetIdx === i
                ? 'bg-violet-600 text-white'
                : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
            }`}>
            {p.label}
          </button>
        ))}
        <label title="Upload a local video file"
          className={`px-3 py-1.5 rounded text-xs font-mono cursor-pointer transition-colors ${
            useUpload ? 'bg-violet-600 text-white' : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
          }`}>
          📂 Upload
          <input type="file" accept="video/*" className="hidden" onChange={handleUpload} />
        </label>
      </div>

      {/* Custom URL input */}
      {!useUpload && presetIdx === PRESETS.length - 1 && (
        <input type="url" value={customUrl} onChange={(e) => setCustomUrl(e.target.value)}
          placeholder="Paste MP4 or HLS (.m3u8) URL"
          className="w-full px-3 py-1.5 rounded bg-gray-800 border border-gray-700 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-violet-500" />
      )}

      {/* Video + canvas overlay */}
      <div className="relative rounded-lg overflow-hidden bg-black border border-gray-800">
        <video ref={videoRef} autoPlay loop muted playsInline crossOrigin="anonymous"
          className="w-full block" />

        <canvas ref={canvasRef} className="absolute inset-0 pointer-events-none"
          style={{ width: '100%', height: '100%' }} />

        {!src && (
          <div className="absolute inset-0 flex items-center justify-center text-gray-600 text-sm">
            Select a video source above
          </div>
        )}

        {/* Auto-detect badge */}
        {autoDetect && (
          <div className="absolute top-3 left-3 bg-green-700/90 text-white text-xs font-mono px-2 py-1 rounded flex items-center gap-1.5">
            <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse inline-block" />
            Live detect
          </div>
        )}

        {/* Manual-detect badge (only shown when auto is off) */}
        {manualDets && !autoDetect && (
          <div className="absolute top-3 left-3 bg-violet-700/90 text-white text-xs font-mono px-2 py-1 rounded animate-pulse">
            📍 {manualDets.length} detection{manualDets.length !== 1 ? 's' : ''} · on-demand
          </div>
        )}

        {/* Footer */}
        {(activeDets.length > 0 || activeModel) && (
          <div className="absolute bottom-0 inset-x-0 bg-black/60 px-3 py-1 flex justify-between text-xs font-mono text-gray-300">
            <span>{activeDets.length} detection{activeDets.length !== 1 ? 's' : ''}</span>
            {activeLatency !== null && <span>{activeLatency.toFixed(1)} ms</span>}
            {activeModel && <span className="text-violet-400">{activeModel}</span>}
          </div>
        )}
      </div>

      {/* Controls row */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Manual detect button (hidden while auto-detect is on) */}
        {!autoDetect && (
          <button onClick={handleDetect} disabled={detecting || !src}
            className={`flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-semibold transition-all ${
              detecting
                ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
                : !src
                ? 'bg-gray-800 text-gray-600 cursor-not-allowed'
                : 'bg-violet-600 hover:bg-violet-500 active:scale-95 text-white shadow'
            }`}>
            {detecting
              ? <><span className="w-4 h-4 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" /> Detecting…</>
              : <><span>🔍</span> Detect frame</>}
          </button>
        )}

        {/* Auto-detect toggle */}
        <button onClick={() => setAutoDetect((v) => !v)} disabled={!src}
          className={`flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-semibold transition-all ${
            !src
              ? 'bg-gray-800 text-gray-600 cursor-not-allowed'
              : autoDetect
              ? 'bg-green-600 hover:bg-green-700 active:scale-95 text-white shadow'
              : 'bg-gray-700 hover:bg-gray-600 active:scale-95 text-gray-200'
          }`}>
          {autoDetect
            ? <><span className="w-2 h-2 bg-green-300 rounded-full animate-pulse inline-block" /> Auto ON</>
            : <>⚡ Auto-detect</>}
        </button>

        {detectErr && (
          <span className="text-xs text-red-400 max-w-xs">{detectErr}</span>
        )}
        {manualDets && !autoDetect && !detectErr && (
          <span className="text-xs text-violet-400">
            {manualDets.length} object{manualDets.length !== 1 ? 's' : ''} · clears in 4s
          </span>
        )}
        {autoDetect && (
          <span className="text-xs text-green-400">
            Detecting every ~1s · feeds charts
          </span>
        )}
      </div>

      <p className="text-xs text-gray-600">
        Auto-detect runs inference on each video frame ~1/s and updates charts in real time.
        Local presets and Marblehead Live support Detect. Custom URL videos may not (depends on CORS policy).
      </p>
    </div>
  )
}
