---
name: ship-pixelstream
description: Ships PixelStream to GitHub. Runs pre-ship checklist, commits all code, pushes to github.com/sabareeswarans11/PixelStream, and verifies the push. Use after QA pipeline and data checks pass.
---

# Ship PixelStream to GitHub

Commits and pushes PixelStream to `https://github.com/sabareeswarans11/PixelStream`.
GitHub auth is already configured via `gh` CLI.

## Pre-Ship Checklist (must all pass before commit)

### Code
- [ ] `uv run pytest tests/ -m "not integration" -v` — all pass
- [ ] `uv run ruff check src/` — zero errors
- [ ] `uv run mypy src/ --ignore-missing-imports` — zero errors
- [ ] `cd dashboard && npm run build` — build succeeds (no TS/lint errors)
- [ ] `/qa-pipeline` report: SHIP READY
- [ ] `/data-pipeline-check` report: DATA CLEAN

### Files
- [ ] `CLAUDE.md` — present and up to date
- [ ] `README.md` — present with setup instructions
- [ ] `pyproject.toml` — complete with all deps
- [ ] `docker-compose.yml` — Redpanda + Console
- [ ] `.env.template` — all vars with comments, no real values
- [ ] `.gitignore` — covers `.env`, `*.pt`, `data/detections/`, `node_modules/`
- [ ] `scripts/download_video.sh` + `scripts/run_demo.sh` — executable
- [ ] `data/sample.mp4` — NOT committed (in .gitignore)

### Security
- [ ] No API keys or secrets in any tracked file
- [ ] `.env` is gitignored
- [ ] No `*.pt` model files tracked
- [ ] No hardcoded paths (`/Users/sabareeswarans/...`) in source code

## Git Setup and Push

```bash
cd /Users/sabareeswarans/Projects_26/PixelStream

# Initialize if not already a repo
git init
git remote add origin https://github.com/sabareeswarans11/PixelStream.git 2>/dev/null || \
  git remote set-url origin https://github.com/sabareeswarans11/PixelStream.git

# Stage everything except gitignored files
git add .

# Verify what's staged (REVIEW before committing)
git status
git diff --cached --stat

# Commit
git commit -m "feat: PixelStream initial implementation

Real-time CV streaming pipeline: video file → Redpanda → Spark Structured
Streaming → YOLOv11n/RT-DETR-l (CPU, switchable) → Delta Lake → FastAPI
WebSocket → React + Visx dashboard.

Stack: Python 3.11, uv, PySpark 3.5, confluent-kafka, ultralytics,
FastAPI, React 18, Vite, Tailwind, Visx

Demo: Intel Mac 2019, CPU-only inference, single video file loop.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"

# Push
git branch -M main
git push -u origin main
```

## Post-Push Verification
```bash
# Verify push succeeded
gh repo view sabareeswarans11/PixelStream --json url,defaultBranchRef

# Check latest commit is there
gh api repos/sabareeswarans11/PixelStream/commits/main --jq '.sha[:7] + " " + .commit.message'
```

## GitHub Repo Setup (first push only)
```bash
# Create repo if it doesn't exist
gh repo create sabareeswarans11/PixelStream --public \
  --description "Real-time CV streaming: Kafka + Spark + YOLOv11 + React + Visx" \
  --homepage "" || echo "Repo already exists, skipping create"

# Set topics
gh api repos/sabareeswarans11/PixelStream -X PATCH \
  -f topics[]="kafka" -f topics[]="spark" -f topics[]="yolo" \
  -f topics[]="computer-vision" -f topics[]="real-time" \
  -f topics[]="python" -f topics[]="react" -f topics[]="delta-lake"
```

## After Push
- Open: `https://github.com/sabareeswarans11/PixelStream`
- Verify: README renders, file tree looks correct
- Share: the repo link is the demo artifact

## Rollback
If the push goes wrong:
```bash
git log --oneline -5          # see recent commits
git revert HEAD               # revert last commit
git push origin main          # push the revert
```
Never force-push to main without explicit confirmation.
