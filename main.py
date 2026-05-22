import os, uuid, time, shutil, cv2, numpy as np
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = Path(os.getenv("MODEL_DIR", BASE_DIR / "models"))
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", BASE_DIR / "uploads"))
OUTPUTS_DIR = Path(os.getenv("OUTPUTS_DIR", BASE_DIR / "outputs"))
STATIC_DIR = Path(os.getenv("STATIC_DIR", BASE_DIR / "static"))
TEMPLATE_PATH = Path(os.getenv("TEMPLATE_PATH", BASE_DIR / "templates" / "index.html"))

DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1"
MAX_IMAGE_MB = int(os.getenv("MAX_IMAGE_MB", "20"))
MAX_VIDEO_MB = int(os.getenv("MAX_VIDEO_MB", "100"))
VIDEO_SAMPLE_FPS = float(os.getenv("VIDEO_SAMPLE_FPS", "5"))
MODEL_CONF = float(os.getenv("MODEL_CONF", "0.25"))
MODEL_IMGSZ = int(os.getenv("MODEL_IMGSZ", "640"))
MODEL_DEVICE = os.getenv("MODEL_DEVICE", "").strip()
FRAME_MAX_EDGE = int(os.getenv("FRAME_MAX_EDGE", "640"))

MODELS = [
    {
        "id": "potato",
        "name": "Potato Disease",
        "path": MODEL_DIR / "potato.pt",
        "classes": ["early", "healthy", "late"],
        "labels": {"early": "Early blight", "healthy": "Healthy", "late": "Late blight"},
        "description": "YOLOv8n trained on PlantVillage potato leaves",
    },
]

_PALETTE_BGR = [
    (0,200,80),(0,130,255),(0,60,220),(200,160,0),
    (180,0,200),(0,200,200),(255,80,0),(0,80,255),(100,200,0),
]

for d in [MODEL_DIR, UPLOADS_DIR, OUTPUTS_DIR, STATIC_DIR]:
    d.mkdir(parents=True, exist_ok=True)

_yolo_ok = False
_yolo_import_error = None
try:
    from ultralytics import YOLO as _YOLO
    _yolo_ok = True
except ImportError as exc:
    _yolo_import_error = str(exc)
    if not DEMO_MODE:
        print("ultralytics not installed — set DEMO_MODE=1 to allow demo mode")

_loaded = {}

def _label_for(info, cls):
    labels = info["meta"].get("labels") or {}
    return labels.get(cls, cls.replace("_", " ").title())

def _resize_max_edge(img, max_edge):
    if max_edge <= 0:
        return img
    h, w = img.shape[:2]
    if max(h, w) <= max_edge:
        return img
    scale = max_edge / max(h, w)
    return cv2.resize(img, (int(w * scale), int(h * scale)))

def _load_models(strict=True):
    _loaded.clear()
    errors = []
    if not _yolo_ok:
        msg = f"ultralytics import failed: {_yolo_import_error or 'unknown error'}"
        if strict:
            errors.append(msg)
        print(f"  [ERROR] {msg}")
    for entry in MODELS:
        mid, path = entry["id"], Path(entry["path"])
        yolo = None
        error = None
        if _yolo_ok:
            if path.exists():
                try:
                    yolo = _YOLO(str(path))
                except Exception as exc:
                    error = f"Failed to load {path.name}: {exc}"
            else:
                error = f"Model file not found: {path}"
        status = "loaded" if yolo else ("demo" if DEMO_MODE else "error")
        print(f"  [{status}] {mid}")
        _loaded[mid] = {
            "yolo": yolo,
            "meta": entry,
            "error": error,
            "colors": {cls: _PALETTE_BGR[i % len(_PALETTE_BGR)]
                       for i, cls in enumerate(entry["classes"])},
        }
        if error and strict:
            errors.append(error)
    if errors and strict:
        raise RuntimeError("; ".join(errors))

def _get_model_info(model_id):
    info = _loaded.get(model_id)
    if not info:
        raise HTTPException(404, f"Unknown model_id: {model_id}")
    if info["yolo"] is None and not DEMO_MODE:
        err = info.get("error") or "Model not loaded"
        raise HTTPException(503, err)
    return info

def _run(img, model_id, info=None):
    info = info or _get_model_info(model_id)
    yolo = info["yolo"]
    classes = info["meta"]["classes"]
    if yolo is None:
        import random
        cls = random.choice(classes)
        conf = round(random.uniform(0.70, 0.97), 3)
        h, w = img.shape[:2]
        return {
            "class": cls,
            "label": _label_for(info, cls),
            "confidence": conf,
            "boxes": [{"class": cls, "confidence": conf, "bbox": [int(w*0.1), int(h*0.1), int(w*0.9), int(h*0.9)]}],
            "scores": {c: round(1.0 / len(classes), 3) for c in classes}
        }
    predict_kwargs = {"conf": MODEL_CONF, "verbose": False, "imgsz": MODEL_IMGSZ}
    if MODEL_DEVICE:
        predict_kwargs["device"] = MODEL_DEVICE
    results = yolo.predict(img, **predict_kwargs)[0]
    boxes_out = []
    class_votes = {}
    for box in results.boxes:
        cls_id = int(box.cls[0])
        cls = classes[cls_id] if cls_id < len(classes) else "unknown"
        conf = float(box.conf[0])
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        boxes_out.append({"class": cls, "confidence": round(conf, 3), "bbox": [x1, y1, x2, y2]})
        class_votes[cls] = max(class_votes.get(cls, 0), conf)
    if not boxes_out:
        top_cls, top_conf = classes[0] if classes else "unknown", 0.0
    else:
        top_cls = max(class_votes, key=class_votes.get)
        top_conf = class_votes[top_cls]
    scores = {c: round(class_votes.get(c, 0.0), 3) for c in classes}
    return {
        "class": top_cls,
        "label": _label_for(info, top_cls),
        "confidence": round(top_conf, 3),
        "boxes": boxes_out,
        "scores": scores
    }

def _draw(img, pred, model_id):
    out = img.copy()
    info = _loaded.get(model_id)
    if not info:
        return out
    colors = info["colors"]
    for box in pred.get("boxes", []):
        x1, y1, x2, y2 = box["bbox"]
        cls, conf = box["class"], box["confidence"]
        color = colors.get(cls, (200, 200, 200))
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        (tw, th), _ = cv2.getTextSize(f"{cls} {conf:.0%}", cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(out, (x1, y1 - th - 8), (x1 + tw + 8, y1), color, -1)
        cv2.putText(out, f"{cls} {conf:.0%}", (x1 + 4, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return out

def _remove(path):
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        pass

app = FastAPI(title="Potato Disease Detection API", version="2.0")
origins_env = os.getenv("ALLOWED_ORIGINS", "*")
origins = ["*"] if origins_env.strip() == "*" else [o.strip() for o in origins_env.split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")

_INDEX_HTML = None

@app.on_event("startup")
async def _load_template():
    global _INDEX_HTML
    path = TEMPLATE_PATH
    if not path.exists():
        print("WARNING: templates/index.html not found")
    else:
        _INDEX_HTML = path.read_text(encoding="utf-8")
        print(f"  [OK] loaded template ({len(_INDEX_HTML)} chars)")
    _load_models(strict=not DEMO_MODE)

@app.get("/", response_class=HTMLResponse)
async def root():
    if _INDEX_HTML is None:
        raise HTTPException(503, "Template not loaded")
    return HTMLResponse(_INDEX_HTML)

@app.get("/health")
async def health():
    return {"status": "ok", "models": {
        mid: {"loaded": s["yolo"] is not None, "classes": s["meta"]["classes"], "error": s.get("error")}
        for mid, s in _loaded.items()
    }}

@app.get("/models")
async def list_models():
    return [{"id": mid, "name": s["meta"]["name"], "description": s["meta"]["description"],
             "classes": s["meta"]["classes"], "loaded": s["yolo"] is not None, "error": s.get("error")}
            for mid, s in _loaded.items()]

@app.post("/predict/image")
async def predict_image(bg: BackgroundTasks, file: UploadFile = File(...),
                        model_id: str = Query("potato")):
    uid = uuid.uuid4().hex[:8]
    img_path = UPLOADS_DIR / f"{uid}{Path(file.filename).suffix}"
    out_path = OUTPUTS_DIR / f"{uid}_out.jpg"
    with open(img_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    if img_path.stat().st_size > MAX_IMAGE_MB * 1024 * 1024:
        bg.add_task(_remove, str(img_path))
        raise HTTPException(413, f"Image exceeds {MAX_IMAGE_MB}MB limit")
    img = cv2.imread(str(img_path))
    if img is None:
        raise HTTPException(400, "Cannot read image")
    t0 = time.time()
    pred = _run(img, model_id)
    ms = int((time.time() - t0) * 1000)
    pred["inference_ms"] = ms
    cv2.imwrite(str(out_path), _draw(img, pred, model_id))
    bg.add_task(_remove, str(img_path))
    return JSONResponse({"id": uid, "model_id": model_id, "prediction": pred,
                         "inference_ms": ms, "result_url": f"/outputs/{out_path.name}"})

@app.post("/predict/video")
async def predict_video(bg: BackgroundTasks, file: UploadFile = File(...),
                        model_id: str = Query("potato")):
    uid = uuid.uuid4().hex[:8]
    img_path = UPLOADS_DIR / f"{uid}{Path(file.filename).suffix}"
    out_path = OUTPUTS_DIR / f"{uid}_out.mp4"
    with open(img_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    if img_path.stat().st_size > MAX_VIDEO_MB * 1024 * 1024:
        bg.add_task(_remove, str(img_path))
        raise HTTPException(413, f"Video exceeds {MAX_VIDEO_MB}MB limit")
    cap = cv2.VideoCapture(str(img_path))
    if not cap.isOpened():
        raise HTTPException(400, "Cannot open video")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    W, H = int(cap.get(3)), int(cap.get(4))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    preds, fi, t0 = [], 0, time.time()
    skip = max(1, int(round(fps / max(VIDEO_SAMPLE_FPS, 0.1))))
    info = _get_model_info(model_id)
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if fi % skip == 0:
            p = _run(frame, model_id, info=info)
            preds.append(p)
        writer.write(_draw(frame, preds[-1] if preds else {"boxes": []}, model_id))
        fi += 1
    cap.release()
    writer.release()
    ms = int((time.time() - t0) * 1000)
    votes = {}
    for p in preds:
        votes[p["class"]] = votes.get(p["class"], 0) + 1
    dom = max(votes, key=votes.get) if votes else "unknown"
    avg = round(sum(p["confidence"] for p in preds) / max(len(preds), 1), 3)
    classes = info["meta"]["classes"]
    dist = {c: round(votes.get(c, 0) / max(len(preds), 1) * 100, 1) for c in classes}
    dom_label = _label_for(info, dom)
    bg.add_task(_remove, str(img_path))
    return JSONResponse({"id": uid, "model_id": model_id, "dominant_class": dom,
                         "dominant_label": dom_label, "avg_confidence": avg, "class_distribution": dist,
                         "frames_analyzed": len(preds), "total_frames": total,
                         "inference_ms": ms, "result_url": f"/outputs/{out_path.name}"})

@app.post("/predict/frame")
async def predict_frame(file: UploadFile = File(...), model_id: str = Query("potato")):
    data = await file.read()
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(400, "Cannot decode frame")
    img = _resize_max_edge(img, FRAME_MAX_EDGE)
    t0 = time.time()
    pred = _run(img, model_id)
    pred["inference_ms"] = int((time.time() - t0) * 1000)
    return JSONResponse(pred)
