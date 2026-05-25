#!/usr/bin/env bash
# Starts the full PixelStream demo stack.
# Requires: Docker, uv, Node.js 18+
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== PixelStream Demo ==="
echo ""

# 1. Infrastructure
echo "→ Starting Redpanda..."
docker-compose up -d
sleep 4

# 2. Create topics (idempotent)
echo "→ Creating Kafka topics..."
docker exec "$(docker-compose ps -q redpanda)" \
  rpk topic create ps.frames ps.detections --brokers localhost:9092 2>/dev/null || true

# 3. Dependencies
echo "→ Checking Python deps..."
uv sync --quiet

# 4. Sample video
echo "→ Checking sample video..."
bash scripts/download_video.sh

# 5. Models
echo "→ Checking models..."
uv run python scripts/download_models.py

echo ""
echo "Starting pipeline components..."
echo ""

# 6. Spark consumer (background)
uv run pixelstream-spark &
SPARK_PID=$!
echo "  ✓ Spark consumer PID=$SPARK_PID (waiting 15s for JVM init...)"
sleep 15

# 7. Frame producer (background)
uv run pixelstream-producer &
PROD_PID=$!
echo "  ✓ Frame producer PID=$PROD_PID"

# 8. Dashboard API (background)
uv run pixelstream-api &
API_PID=$!
echo "  ✓ Dashboard API PID=$API_PID"
sleep 2

# 9. React dev server (background)
if [ -d "dashboard/node_modules" ]; then
  cd dashboard && npm run dev &
  DASH_PID=$!
  cd "$ROOT"
  echo "  ✓ React dashboard PID=$DASH_PID"
else
  echo "  ⚠ dashboard/node_modules missing — run: cd dashboard && npm install"
  DASH_PID=0
fi

echo ""
echo "=== PixelStream running ==="
echo "  Dashboard:        http://localhost:5173"
echo "  API stats:        http://localhost:8000/api/stats"
echo "  Redpanda Console: http://localhost:8080"
echo "  Spark UI:         http://localhost:4040"
echo ""
echo "Press Ctrl+C to stop all components."

cleanup() {
  echo ""
  echo "Stopping..."
  [ $SPARK_PID -ne 0 ] && kill "$SPARK_PID" 2>/dev/null || true
  [ $PROD_PID -ne 0 ] && kill "$PROD_PID" 2>/dev/null || true
  [ $API_PID -ne 0 ] && kill "$API_PID" 2>/dev/null || true
  [ "${DASH_PID:-0}" -ne 0 ] && kill "$DASH_PID" 2>/dev/null || true
  docker-compose down
  echo "Done."
}
trap cleanup EXIT INT TERM

wait
