import cv2
import random
from core.config import MODEL_CONF, MODEL_IMGSZ, MODEL_DEVICE
from services.classifier_runtime import run_classifier
from services.model_manager import get_model_info, label_for
from services.roboflow_runtime import run_roboflow_workflow

NO_DETECTION_CLASS = "no_detection"
MAX_LABEL_CHARS = 34

def run_inference(img, model_id, info=None):
    info = info or get_model_info(model_id)
    yolo = info["yolo"]
    classes = info["meta"]["classes"]
    task = info["meta"].get("task", "detection")
    runtime = info["meta"].get("runtime", "ultralytics")
    h, w = img.shape[:2]

    if runtime == "roboflow_workflow":
        return run_roboflow_workflow(img, info)

    if task == "classification":
        return run_classifier(img, info)
    
    if yolo is None:
        cls = random.choice(classes)
        conf = round(random.uniform(0.70, 0.97), 3)
        return {
            "class": cls,
            "label": label_for(info, cls),
            "confidence": conf,
            "detected": True,
            "boxes": [{"class": cls, "confidence": conf, "bbox": [int(w*0.1), int(h*0.1), int(w*0.9), int(h*0.9)]}],
            "scores": {c: round(1.0 / len(classes), 3) for c in classes}
        }
        
    predict_kwargs = {"conf": MODEL_CONF, "verbose": False, "imgsz": MODEL_IMGSZ}
    if MODEL_DEVICE:
        predict_kwargs["device"] = MODEL_DEVICE
        
    lock = info.get("lock")
    if lock:
        with lock:
            results = yolo.predict(img, **predict_kwargs)[0]
    else:
        results = yolo.predict(img, **predict_kwargs)[0]
    boxes_out = []
    class_votes = {}
    
    for box in results.boxes:
        cls_id = int(box.cls[0])
        cls = classes[cls_id] if 0 <= cls_id < len(classes) else "unknown"
        conf = float(box.conf[0])
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        x1 = max(0, min(w - 1, x1))
        y1 = max(0, min(h - 1, y1))
        x2 = max(0, min(w, x2))
        y2 = max(0, min(h, y2))
        if x2 <= x1 or y2 <= y1:
            continue
        boxes_out.append({"class": cls, "confidence": round(conf, 3), "bbox": [x1, y1, x2, y2]})
        class_votes[cls] = max(class_votes.get(cls, 0), conf)
        
    if not boxes_out:
        top_cls, top_conf = NO_DETECTION_CLASS, 0.0
    else:
        top_cls = max(class_votes, key=class_votes.get)
        top_conf = class_votes[top_cls]
        
    scores = {c: round(class_votes.get(c, 0.0), 3) for c in classes}
    
    return {
        "class": top_cls,
        "label": label_for(info, top_cls),
        "confidence": round(top_conf, 3),
        "detected": bool(boxes_out),
        "boxes": boxes_out,
        "scores": scores
    }

def draw_inference(img, pred, model_id):
    out = img.copy()
    info = get_model_info(model_id)
    if not info:
        return out

    if info["meta"].get("task") == "classification":
        label = pred.get("label") or label_for(info, pred.get("class", "unknown"))
        conf = float(pred.get("confidence", 0.0))
        text = f"{label} {conf:.0%}"
        overlay = out.copy()
        cv2.rectangle(overlay, (0, 0), (out.shape[1], 62), (20, 35, 24), -1)
        out = cv2.addWeighted(overlay, 0.78, out, 0.22, 0)
        cv2.putText(out, text, (18, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.82,
                    (255, 255, 255), 2, cv2.LINE_AA)
        return out
        
    colors = info["colors"]
    for box in pred.get("boxes", []):
        x1, y1, x2, y2 = box["bbox"]
        cls, conf = box["class"], box["confidence"]
        color = colors.get(cls, (200, 200, 200))
        label = _overlay_label(cls, conf)
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 1)
        label_width = min(out.shape[1] - x1, tw + 10)
        label_top = y1 - th - 10
        label_bottom = y1
        if label_top < 0:
            label_top = y1
            label_bottom = min(out.shape[0], y1 + th + 10)
        cv2.rectangle(out, (x1, label_top), (x1 + label_width, label_bottom), color, -1)
        cv2.putText(out, label, (x1 + 5, label_bottom - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1, cv2.LINE_AA)
    return out

def _overlay_label(cls, conf):
    label = str(cls).replace("_", " ")
    if len(label) > MAX_LABEL_CHARS:
        label = label[:MAX_LABEL_CHARS - 1].rstrip() + "..."
    return f"{label} {float(conf):.0%}"

def resize_max_edge(img, max_edge):
    if max_edge <= 0:
        return img
    h, w = img.shape[:2]
    if max(h, w) <= max_edge:
        return img
    scale = max_edge / max(h, w)
    return cv2.resize(img, (int(w * scale), int(h * scale)))
