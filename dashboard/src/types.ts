export interface Detection {
  cls: string
  confidence: number
  bbox: [number, number, number, number] // x1,y1,x2,y2 normalized [0,1]
}

export interface DetectionResult {
  frame_id: string
  timestamp: number
  model: string
  latency_ms: number
  detections: Detection[]
  thumbnail_b64?: string // 320×240 JPEG base64
}

export interface Stats {
  total_frames: number
  total_detections: number
  active_model: string
  fps: number
  uptime_seconds: number
}
