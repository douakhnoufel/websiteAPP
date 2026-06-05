from pathlib import Path
from threading import Lock

from fastapi import HTTPException

from core.config import MODELS, DEMO_MODE, PALETTE_BGR
from services.classifier_runtime import load_onnx_classifier
from services.roboflow_runtime import load_roboflow_workflow

_yolo_ok = False
_yolo_import_error = None
_YOLO = None
if not DEMO_MODE:
    try:
        from ultralytics import YOLO as _YOLO
        _yolo_ok = True
    except ImportError as exc:
        _yolo_import_error = str(exc)
        print("ultralytics not installed - set DEMO_MODE=1 to allow demo mode")

_loaded = {}

def label_for(info, cls):
    labels = info["meta"].get("labels") or {}
    return labels.get(cls, cls.replace("_", " ").title())

def _names_from_yolo(yolo):
    names = getattr(yolo, "names", None)
    if isinstance(names, dict):
        return [names[i] for i in sorted(names) if isinstance(i, int)]
    if isinstance(names, (list, tuple)):
        return [str(name) for name in names]
    return []

def load_models(strict=True):
    _loaded.clear()
    errors = []
    needs_yolo = any(entry.get("runtime", "ultralytics") == "ultralytics" for entry in MODELS)
    if needs_yolo and not _yolo_ok and not DEMO_MODE:
        msg = f"ultralytics import failed: {_yolo_import_error or 'unknown error'}"
        if strict:
            errors.append(msg)
        print(f"  [ERROR] {msg}")
        
    for entry in MODELS:
        mid = entry["id"]
        path = Path(entry["path"]) if entry.get("path") else None
        yolo = None
        classifier = None
        roboflow = None
        error = None
        runtime = entry.get("runtime", "ultralytics")
        required = bool(entry.get("required", True))
        
        if runtime == "ultralytics" and _yolo_ok:
            if path and path.exists():
                try:
                    yolo = _YOLO(str(path))
                    detected_classes = _names_from_yolo(yolo)
                    if detected_classes:
                        entry["classes"] = detected_classes
                except Exception as exc:
                    error = f"Failed to load {path.name}: {exc}"
            else:
                error = f"Model file not found: {path}"
        elif runtime == "onnx_classifier":
            if path and path.exists():
                try:
                    classifier = load_onnx_classifier(path, entry)
                except Exception as exc:
                    error = f"Failed to load {path.name}: {exc}"
            else:
                error = f"Model file not found: {path}"
        elif runtime == "external_artifact":
            error = "Export or copy the model artifact before server inference"
        elif runtime == "roboflow_workflow":
            try:
                roboflow = load_roboflow_workflow(entry)
            except Exception as exc:
                error = str(exc)
        elif runtime != "ultralytics":
            error = f"Unsupported runtime: {runtime}"
                
        loaded = yolo is not None or classifier is not None or roboflow is not None
        status = "loaded" if loaded else ("demo" if DEMO_MODE else ("optional" if not required else "error"))
        print(f"  [{status}] {mid}")
        
        _loaded[mid] = {
            "yolo": yolo,
            "classifier": classifier,
            "roboflow": roboflow,
            "meta": entry,
            "error": error,
            "loaded": loaded,
            "available": loaded or DEMO_MODE,
            "lock": Lock(),
            "colors": {cls: PALETTE_BGR[i % len(PALETTE_BGR)]
                       for i, cls in enumerate(entry["classes"])},
        }
        
        if error and strict and required:
            errors.append(error)
            
    if errors and strict:
        raise RuntimeError("; ".join(errors))

def get_model_info(model_id):
    info = _loaded.get(model_id)
    if not info:
        raise HTTPException(404, f"Unknown model_id: {model_id}")
    if not info.get("loaded") and not DEMO_MODE:
        err = info.get("error") or "Model not loaded"
        raise HTTPException(503, err)
    return info

def get_loaded_models():
    return _loaded
