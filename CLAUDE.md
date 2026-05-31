# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Role

Act as a professional web developer, YOLO/computer-vision specialist, and drone systems engineer. Prioritize real-time performance, low-latency inference, and reliable drone telemetry pipelines.

## Commands

```bash
# Install
pip install -r requirements.txt

# Run (HTTP)
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run (HTTPS, Windows)
start.bat

# Docker
docker compose up --build

# Validate model accuracy
python validate.py --data <dataset_path> --model models/potato.pt
```

## Architecture

**FastAPI** app (`main.py`) with 4 routers mounted under `/`:

| Router | Prefix | Purpose |
|--------|--------|---------|
| `routers/health.py` | `/` | Health check, model listing, root UI |
| `routers/predict.py` | `/predict` | Image/video/frame YOLO inference |
| `routers/stream.py` | `/stream` | RTMP/RTSP → MJPEG real-time inference |
| `routers/drone.py` | `/drone` | DJI bridge telemetry & command queue |

**Services:**
- `services/model_manager.py` — thread-safe YOLO model loading, metadata, label lookup
- `services/inference.py` — core prediction pipeline: resize → infer → draw boxes
- `services/drone_manager.py` — stateful drone FSM (IDLE/AUTO_SCAN/HOLD/RTH/EMERGENCY_STOP), command queue (max 200, TTL-based), telemetry aggregation
- `services/security.py` — drone auth (Bearer token + local-only IP whitelist), stream host validation
- `services/file_handler.py` — async file cleanup with TTL

**Core config** (`core/config.py`): all tunable parameters (confidence, imgsz, FPS sampling, upload limits, CORS, drone TTL) are resolved from env vars. The model registry defines `potato.pt` with 3 classes: `early`, `healthy`, `late`.

## Key Design Constraints

- **Real-time stream**: `/stream/drone` is MJPEG (`multipart/x-mixed-replace`). Frame loop must be non-blocking; inference runs per-frame. Latency budget: keep under 100ms/frame at 640px.
- **Drone command queue**: commands expire (TTL). The DJI bridge polls `/drone/bridge/commands` and pushes telemetry to `/drone/bridge/telemetry`. Never block the queue; use async throughout.
- **Security**: drone endpoints check `DJI_BRIDGE_TOKEN` header AND (when `DJI_BRIDGE_LOCAL_ONLY=1`) verify the caller IP is loopback/private. Stream URLs are validated for allowed schemes and private/loopback hosts only.
- **Demo mode**: if ultralytics is absent, `model_manager` returns random predictions — do not remove this fallback.
- **Output cleanup**: uploaded and result files are deleted after `OUTPUT_TTL_SEC` via background tasks.

## Environment Variables

Copy `.env.example` to `.env`. Key vars:

```
MODEL_CONF=0.25          # YOLO confidence threshold
MODEL_IMGSZ=640          # Inference image size
VIDEO_SAMPLE_FPS=5       # Frame sampling for video prediction
MAX_IMAGE_MB=20
MAX_VIDEO_MB=100
DJI_BRIDGE_LOCAL_ONLY=1  # Restrict drone bridge to localhost
DJI_BRIDGE_TOKEN=        # Bearer token for drone endpoints
STREAM_ALLOWED_SCHEMES=rtmp,rtsp,http,https
ALLOWED_ORIGINS=*
```
