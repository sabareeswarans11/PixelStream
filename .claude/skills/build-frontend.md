---
name: build-frontend
description: Builds the PixelStream React dashboard. Use when scaffolding or extending the React Vite app, Visx charts, WebSocket live feed, model selector, or stats panel. Produces demo-quality UI — not AI-generic styling.
---

# Build Frontend — PixelStream React Dashboard

Build the React + Vite + Tailwind + Visx dashboard that connects to the FastAPI backend via
WebSocket and REST. The UI should look like a real-time CV monitoring tool — dark theme,
data-dense, not a generic SaaS landing page.

## Stack
- React 18, Vite, Tailwind CSS
- `@visx/xychart`, `@visx/area`, `@visx/bar` for charts
- `@visx/responsive` for responsive containers
- No additional state management (useState + useRef is enough)
- WebSocket via native browser API (wrapped in a custom hook)

## Setup
```bash
cd dashboard
npm create vite@latest . -- --template react
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
npm install @visx/xychart @visx/area @visx/bar @visx/responsive @visx/scale @visx/group
npm run dev   # verify blank React app runs at localhost:5173
```

Vite proxy in `vite.config.js` — proxy API and WS to FastAPI:
```js
export default {
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true }
    }
  }
}
```

## Component Build Order
1. `useWebSocket.js` hook
2. `StatsPanel.jsx`
3. `ModelSelector.jsx`
4. `DetectionChart.jsx`
5. `LiveFeed.jsx`
6. Wire in `App.jsx`

## 1. useWebSocket.js
```js
export function useWebSocket(url) {
  const [lastMessage, setLastMessage] = useState(null)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)

  useEffect(() => {
    function connect() {
      const ws = new WebSocket(url)
      wsRef.current = ws
      ws.onopen = () => setConnected(true)
      ws.onmessage = (e) => setLastMessage(JSON.parse(e.data))
      ws.onclose = () => { setConnected(false); setTimeout(connect, 2000) }
    }
    connect()
    return () => wsRef.current?.close()
  }, [url])

  return { lastMessage, connected }
}
```

## 2. StatsPanel.jsx
Polls `/api/stats` every 2s. Shows: FPS, avg latency (ms), total detections, active model, uptime.
Dark bg panel, monospace numbers, green/red indicator for connection.

## 3. ModelSelector.jsx
```jsx
const MODELS = ['yolov11n', 'rtdetr-l']
// POST /api/model { model: name } on click
// Disable button for 1s after click (debounce)
// Show active model with a highlighted border
```
- YOLOv11n label: "YOLOv11n — fast (~15 FPS)"
- RT-DETR-l label: "RT-DETR-l — accurate (~3 FPS)"

## 4. DetectionChart.jsx
Visx AreaStack. Rolling 60-second window of detection counts per class.
```jsx
// Data shape: [{ time, person: 3, car: 1, bicycle: 0 }, ...]
// Update on each WS message — push new point, shift off points > 60s old
// Colors: person=#6366f1, car=#f59e0b, bicycle=#10b981, (other classes auto-colored)
```
Use `@visx/responsive`'s `ParentSize` wrapper.

## 5. LiveFeed.jsx
```jsx
// Canvas 320×240 (thumbnail size — never full frame over WS)
// On each WS message:
//   1. If message includes frame_b64: draw thumbnail on canvas
//   2. Draw bbox overlays: semi-transparent colored rect per detection
//   3. Draw label above each bbox: "person 0.91"
// Color coding: same palette as DetectionChart
```

## Design Constraints (avoid AI aesthetic)
| Avoid | Use instead |
|---|---|
| Purple gradient hero | Dark `#0f172a` background (slate-900) |
| Rounded-2xl everything | `rounded` (4px) consistent |
| Oversized padding | Tight `p-3` panels |
| Equal card grid | Left: feed + stats (1/3), Right: chart (2/3) |
| White background | Dark theme throughout |
| Generic icons | Text labels only |

## Layout
```
┌──────────────────────────────────────────────────────┐
│  PixelStream          [connected ●]     [YOLOv11n|RT-DETR-l]  │ ← header
├──────────────────────┬───────────────────────────────┤
│  Live Feed (canvas)  │  Detection Chart (Visx Area)  │
│  320×240             │  Last 60 seconds              │
├──────────────────────┤                               │
│  Stats Panel         │                               │
│  FPS / latency / cnt │                               │
└──────────────────────┴───────────────────────────────┘
```

## Verification
```bash
cd dashboard && npm run dev
# Open http://localhost:5173
# Start backend stack → verify WS connects (● green indicator)
# Watch detection chart populate
# Click model toggle → confirm POST /api/model fires
# Check browser console: zero errors
```

## Red Flags
- Canvas not clearing between frames (call `ctx.clearRect` first)
- WS reconnect loop spamming console (add backoff)
- Chart re-rendering entire DOM on each message (use refs for data buffer)
- Tailwind classes not applying (check `content` in tailwind.config.js)
