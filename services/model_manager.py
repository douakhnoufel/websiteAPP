from pathlib import Path
from threading import Lock

from fastapi import HTTPException

from core.config import MODELS, DEMO_MODE, PALETTE_BGR

_yolo_ok = False
_yolo_import_error = None
try:
    from ultralytics import YOLO as _YOLO
    _yolo_ok = True
except ImportError as exc:
    _yolo_import_error = str(exc)
    if not DEMO_MODE:
        print("ultralytics not installed \u2014 set DEMO_MODE=1 to allow demo mode")

_loaded = {}

def label_for(info, cls):
    labels = info["meta"].get("labels") or {}
    return labels.get(cls, cls.replace("_", " ").title())

def load_models(strict=True):
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
            "lock": Lock(),
            "colors": {cls: PALETTE_BGR[i % len(PALETTE_BGR)]
                       for i, cls in enumerate(entry["classes"])},
        }
        
        if error and strict:
            errors.append(error)
            
    if errors and strict:
        raise RuntimeError("; ".join(errors))

def get_model_info(model_id):
    info = _loaded.get(model_id)
    if not info:
        raise HTTPException(404, f"Unknown model_id: {model_id}")
    if info["yolo"] is None and not DEMO_MODE:
        err = info.get("error") or "Model not loaded"
        raise HTTPException(503, err)
    return info

def get_loaded_models():
    return _loaded
