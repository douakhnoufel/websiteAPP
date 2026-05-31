# Repository Guidelines

## Project Structure & Module Organization

This repository contains a FastAPI-based potato disease detection service backed by Ultralytics YOLO models.

- `main.py`: API entry point, model loading, prediction endpoints, video/frame processing, and static UI serving.
- `validate.py`: CLI utility for checking YOLO model accuracy against class-labeled image folders.
- `templates/index.html`: browser UI served from `/`.
- `static/`: frontend static assets.
- `models/`: model weights and exported ML artifacts. The default runtime model is `models/potato.pt`.
- `uploads/` and `outputs/`: runtime-generated files. Do not treat generated images or videos as source changes.
- `Dockerfile` and `docker-compose.yml`: containerized deployment configuration.

## Build, Test, and Development Commands

- `python -m pip install -r requirements.txt`: install FastAPI, Uvicorn, Ultralytics, OpenCV, NumPy, Pillow, and certificate helpers.
- `python -m uvicorn main:app --reload`: run the API locally on `http://127.0.0.1:8000`.
- `start.bat`: run the service with HTTPS using `cert.pem` and `key.pem`.
- `docker compose up --build`: build and run the containerized service on port `8000`.
- `python validate.py --data path\to\data --model models\potato.pt`: validate model accuracy using class subfolders such as `early`, `healthy`, and `late`.

## Coding Style & Naming Conventions

Use Python 3.11-compatible code. Follow PEP 8 with 4-space indentation, clear function names, and short helper functions for image/model operations. Keep environment-backed settings near the top of `main.py` and prefer `Path` objects for filesystem paths. Use lowercase snake_case for variables, functions, and endpoint helpers. Keep YOLO class IDs, labels, and model metadata explicit in `MODELS`.

## Testing Guidelines

There is no formal pytest suite yet. For API changes, manually verify:

- `GET /health`
- `GET /models`
- `POST /predict/image`
- `POST /predict/frame`

For ML changes, run `validate.py` against a labeled dataset and record per-class and overall accuracy. Add future tests under `tests/` with names like `test_health.py` or `test_predict_image.py`.

## Commit & Pull Request Guidelines

The current history uses concise, descriptive commits, for example: `Initial commit: Production-ready PotatoScan app with Docker, UI redesign, and deployment configs`. Use imperative summaries that describe the user-visible change.

Pull requests should include a short description, affected endpoints or UI areas, validation steps, and screenshots or sample outputs when frontend or prediction rendering changes.

## Security & Configuration Tips

Do not commit private certificates, secrets, or large generated outputs. Prefer `.env.example` for documented settings. Review `ALLOWED_ORIGINS`, model paths, upload limits, and `DEMO_MODE` before deployment.

## Agent-Specific Instructions

When contributing as an automation agent, treat this as a Flutter-adjacent ML/YOLO backend: preserve API contracts expected by clients, keep model behavior measurable, and avoid unrelated UI or model refactors.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, invoke the `skill` tool with `skill: "graphify"` before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
