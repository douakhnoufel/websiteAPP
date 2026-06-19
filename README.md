# PotatoScan

**PotatoScan** is a real-time plant disease detection platform powered by YOLO computer vision. Point a camera or drone feed at your crops and get instant disease diagnosis with confidence scores.

## Features

- **Live Disease Detection** — real-time YOLO inference on live video streams (drone or webcam)
- **Multi-Model Workbench** — compare predictions across multiple detection models side by side
- **Interactive Disease Graph** — visual knowledge graph linking diseases, symptoms, crops, and treatments
- **Android App** — native mobile app for on-field scanning, available directly from the dashboard
- **Drone Integration** — RTMP/WebRTC live feed ingestion from drone cameras via MediaMTX
- **REST API** — FastAPI backend with `/predict` endpoint for programmatic access

## Stack

- **Backend**: FastAPI + Uvicorn (Python)
- **Inference**: YOLOv8 / Ultralytics
- **Streaming**: MediaMTX (RTMP, HLS, WebRTC)
- **Frontend**: HTML/CSS/JS dashboard
- **Deployment**: Docker Compose on DigitalOcean

## Getting Started

```bash
docker compose up -d
```

The dashboard runs at `http://localhost:8000`. Publish a live feed to `rtmp://<host>:1935/live/drone` to start detection.

## Mobile App

Download the Android APK directly from the dashboard homepage. The app connects to the same backend for on-device scanning and live results.

## API

```
POST /predict
Content-Type: multipart/form-data

file: <image>
```

Returns detected diseases, bounding boxes, and confidence scores.

## Paper Figures

The paper-ready diagram sources are in:

- [`docs/paper_figures.md`](docs/paper_figures.md)
- [`docs/uml/use_case.puml`](docs/uml/use_case.puml)
- [`docs/uml/sequence_prediction.puml`](docs/uml/sequence_prediction.puml)
- [`docs/uml/deployment.puml`](docs/uml/deployment.puml)
- [`docs/uml/component.puml`](docs/uml/component.puml)

It includes:

- system architecture
- inference workflow
- deployment topology

## Project Structure

- `main.py` entry point
- `routers/` request handlers
- `services/` model, inference, security, and drone logic
- `templates/index.html` browser UI
- `models/` YOLO weights
- `docker-compose.yml` deployment stack
