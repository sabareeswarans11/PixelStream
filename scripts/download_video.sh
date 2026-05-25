#!/usr/bin/env bash
# Downloads a royalty-free pedestrian/traffic clip for the PixelStream demo.
# Source: Pixabay (CC0) via direct MP4 link.
set -euo pipefail

DEST="data/sample.mp4"
mkdir -p data

if [ -f "$DEST" ]; then
  echo "✓ $DEST already exists ($(du -h "$DEST" | cut -f1))"
  exit 0
fi

echo "→ Downloading sample video..."

# Pixabay CC0 clip: short traffic / pedestrian scene ~10s 720p
VIDEO_URL="https://cdn.pixabay.com/video/2016/01/14/1892-152055375_large.mp4"

if command -v wget &>/dev/null; then
  wget -q --show-progress -O "$DEST" "$VIDEO_URL"
elif command -v curl &>/dev/null; then
  curl -L --progress-bar -o "$DEST" "$VIDEO_URL"
else
  echo "Error: neither wget nor curl found" >&2
  exit 1
fi

SIZE=$(du -h "$DEST" | cut -f1)
echo "✓ Downloaded $DEST ($SIZE)"
