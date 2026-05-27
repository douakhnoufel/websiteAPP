import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

MODEL_DIR = Path(os.getenv("MODEL_DIR", BASE_DIR / "models"))
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", BASE_DIR / "uploads"))
OUTPUTS_DIR = Path(os.getenv("OUTPUTS_DIR", BASE_DIR / "outputs"))
STATIC_DIR = Path(os.getenv("STATIC_DIR", BASE_DIR / "static"))
TEMPLATE_PATH = Path(os.getenv("TEMPLATE_PATH", BASE_DIR / "templates" / "index.html"))
TEMPLATE_AUTO_RELOAD = os.getenv("TEMPLATE_AUTO_RELOAD", "0") == "1"

DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1"
MAX_IMAGE_MB = int(os.getenv("MAX_IMAGE_MB", "20"))
MAX_VIDEO_MB = int(os.getenv("MAX_VIDEO_MB", "100"))
VIDEO_SAMPLE_FPS = float(os.getenv("VIDEO_SAMPLE_FPS", "5"))
MODEL_CONF = float(os.getenv("MODEL_CONF", "0.25"))
MODEL_IMGSZ = int(os.getenv("MODEL_IMGSZ", "640"))
MODEL_DEVICE = os.getenv("MODEL_DEVICE", "").strip()
FRAME_MAX_EDGE = int(os.getenv("FRAME_MAX_EDGE", "640"))

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")
DJI_BRIDGE_LOCAL_ONLY = os.getenv("DJI_BRIDGE_LOCAL_ONLY", "1") == "1"
DJI_BRIDGE_TOKEN = os.getenv("DJI_BRIDGE_TOKEN", "").strip()
DJI_TELEMETRY_HZ = float(os.getenv("DJI_TELEMETRY_HZ", "2"))
DRONE_COMMAND_TTL_SEC = int(os.getenv("DRONE_COMMAND_TTL_SEC", "20"))

MODELS = [
    {
        "id": "potato",
        "name": "Potato Disease",
        "path": MODEL_DIR / "modelsigot" / "best.pt",
        "classes": ["early", "healthy", "late"],
        "labels": {"early": "Early blight", "healthy": "Healthy", "late": "Late blight"},
        "description": "YOLOv8n trained on 90 potato leaves",
    },
]

# Semantic colors: early (Orange), healthy (Green), late (Red)
PALETTE_BGR = [
    (0, 165, 255),  # Orange for early
    (0, 200, 80),   # Green for healthy
    (0, 60, 220),   # Red for late
    (200, 160, 0),
    (180, 0, 200), 
    (0, 200, 200), 
    (255, 80, 0), 
    (0, 80, 255), 
    (100, 200, 0),
]

# Ensure necessary directories exist
for d in [MODEL_DIR, UPLOADS_DIR, OUTPUTS_DIR, STATIC_DIR]:
    d.mkdir(parents=True, exist_ok=True)
