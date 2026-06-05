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
DEFAULT_MODEL_ID = os.getenv("DEFAULT_MODEL_ID", "potato").strip() or "potato"
FRAME_MAX_EDGE = int(os.getenv("FRAME_MAX_EDGE", "640"))
FRAME_MIN_CONF = float(os.getenv("FRAME_MIN_CONF", "0.55"))
FRAME_MIN_BOX_AREA_RATIO = float(os.getenv("FRAME_MIN_BOX_AREA_RATIO", "0.02"))
# How long (seconds) annotated output files are kept before background deletion (0 = keep forever)
OUTPUT_TTL_SEC = int(os.getenv("OUTPUT_TTL_SEC", "3600"))

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")
DJI_BRIDGE_LOCAL_ONLY = os.getenv("DJI_BRIDGE_LOCAL_ONLY", "1") == "1"
DJI_BRIDGE_TOKEN = os.getenv("DJI_BRIDGE_TOKEN", "").strip()
DJI_TELEMETRY_HZ = float(os.getenv("DJI_TELEMETRY_HZ", "2"))
DRONE_COMMAND_TTL_SEC = int(os.getenv("DRONE_COMMAND_TTL_SEC", "20"))
STREAM_ALLOWED_SCHEMES = {
    s.strip().lower()
    for s in os.getenv("STREAM_ALLOWED_SCHEMES", "rtmp,rtsp,http,https").split(",")
    if s.strip()
}
STREAM_ALLOWED_HOSTS = {
    h.strip().lower()
    for h in os.getenv("STREAM_ALLOWED_HOSTS", "").split(",")
    if h.strip()
}

MODELS = [
    {
        "id": "potato",
        "name": "Potato Disease",
        "family": "PotatoScan",
        "runtime": "ultralytics",
        "task": "detection",
        "required": True,
        "path": MODEL_DIR / "potato.pt",
        "classes": ["early", "healthy", "late"],
        "labels": {
            "early": "Early blight",
            "healthy": "Healthy",
            "late": "Late blight",
            "no_detection": "No detection",
            "unknown": "Unknown",
        },
        "description": "YOLOv8n trained on 90 potato leaves",
        "source_url": "https://www.kaggle.com/datasets/aarishasifkhan/plantvillage-potato-disease-dataset/data",
        "input": "image, video, webcam, drone",
    },
    {
        "id": "plant_disease_detection",
        "name": "Plant Disease Detection",
        "family": "Multi-plant detector",
        "runtime": "ultralytics",
        "task": "detection",
        "required": False,
        "path": MODEL_DIR / "plant_disease_detection.pt",
        "classes": ["plant_disease"],
        "labels": {
            "plant_disease": "Plant disease",
            "no_detection": "No detection",
            "unknown": "Unknown",
        },
        "description": "Large Ultralytics detector copied from Downloads/PlantDiseaseDetection.pt",
        "source_url": "",
        "input": "image, video, webcam, drone",
    },
    {
        "id": "tomato_leaf",
        "name": "Tomato Leaf Disease",
        "family": "TomatoScan",
        "runtime": "ultralytics",
        "task": "detection",
        "required": False,
        "path": MODEL_DIR / "tomato_leaf.pt",
        "classes": [
            "Tomato Bacterial Spot",
            "Tomato Early blight",
            "Tomato Late blight",
            "Tomato Leaf Mold",
            "Tomato Septoria leaf spot",
            "Tomato Spider mites Two-spotted spider mite",
            "Tomato Target Spot",
            "Tomato Yellow Leaf Curl Virus",
            "Tomato healthy",
            "Tomato mosaic virus",
        ],
        "labels": {
            "Tomato Bacterial Spot": "Tomato bacterial spot",
            "Tomato Early blight": "Tomato early blight",
            "Tomato Late blight": "Tomato late blight",
            "Tomato Leaf Mold": "Tomato leaf mold",
            "Tomato Septoria leaf spot": "Tomato septoria leaf spot",
            "Tomato Spider mites Two-spotted spider mite": "Tomato spider mites / two-spotted spider mite",
            "Tomato Target Spot": "Tomato target spot",
            "Tomato Yellow Leaf Curl Virus": "Tomato yellow leaf curl virus",
            "Tomato healthy": "Healthy tomato leaf",
            "Tomato mosaic virus": "Tomato mosaic virus",
            "no_detection": "No detection",
            "unknown": "Unknown",
        },
        "description": "Ultralytics YOLO tomato leaf disease model copied from Downloads/best_tomato_leaf_model.pt",
        "source_url": "",
        "input": "image, video, webcam, drone",
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
