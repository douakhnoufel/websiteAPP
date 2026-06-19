# PotatoScan

FastAPI-based potato disease detection service backed by Ultralytics YOLO.

## Paper Figures

The paper-ready diagram sources are in:

- [`docs/paper_figures.md`](docs/paper_figures.md)

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
