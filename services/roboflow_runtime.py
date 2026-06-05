import os
import tempfile
from dataclasses import dataclass

import cv2


@dataclass
class RoboflowWorkflowRuntime:
    client: object
    workspace_name: str
    workflow_id: str
    parameters: dict
    model_id: str | None = None


def load_roboflow_workflow(meta):
    api_key = os.getenv("ROBOFLOW_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Set ROBOFLOW_API_KEY to enable Roboflow workflow inference")

    try:
        from inference_sdk import InferenceHTTPClient
    except ImportError as exc:
        raise RuntimeError("inference-sdk is not installed") from exc

    client = InferenceHTTPClient(
        api_url=meta.get("api_url", "https://serverless.roboflow.com"),
        api_key=api_key,
    )
    return RoboflowWorkflowRuntime(
        client=client,
        workspace_name=meta.get("workspace_name", ""),
        workflow_id=meta.get("workflow_id", ""),
        parameters=meta.get("parameters", {}),
        model_id=meta.get("model_id"),
    )


def run_roboflow_workflow(img, info):
    runtime = info.get("roboflow")
    if runtime is None:
        from services.classifier_runtime import demo_classifier_result

        return {
            **demo_classifier_result(info["meta"]["classes"], info),
            "boxes": [],
            "task": "remote_detection",
        }

    fd, img_path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    try:
        if not cv2.imwrite(img_path, img):
            raise RuntimeError("Could not prepare image for Roboflow")
        if runtime.model_id:
            result = runtime.client.infer(img_path, model_id=runtime.model_id)
        else:
            result = runtime.client.run_workflow(
                workspace_name=runtime.workspace_name,
                workflow_id=runtime.workflow_id,
                images={"image": img_path},
                parameters=runtime.parameters,
                use_cache=True,
            )
    finally:
        try:
            os.remove(img_path)
        except OSError:
            pass

    return _normalize_roboflow_result(result, info, img.shape[:2])


def _normalize_roboflow_result(result, info, img_shape):
    predictions = _find_predictions(result)
    classes = info["meta"]["classes"]
    boxes = []
    scores = {c: 0.0 for c in classes}
    h, w = img_shape

    for pred in predictions:
        cls = str(pred.get("class") or pred.get("class_name") or pred.get("label") or "unknown")
        conf = float(pred.get("confidence") or pred.get("score") or 0.0)
        scores[cls] = max(scores.get(cls, 0.0), round(conf, 3))
        bbox = _prediction_bbox(pred, w, h)
        if bbox:
            boxes.append({"class": cls, "confidence": round(conf, 3), "bbox": bbox})

    if boxes:
        top = max(boxes, key=lambda box: float(box.get("confidence", 0.0)))
        top_cls = top["class"]
        top_conf = float(top["confidence"])
    elif predictions:
        top_pred = max(predictions, key=lambda pred: float(pred.get("confidence") or pred.get("score") or 0.0))
        top_cls = str(top_pred.get("class") or top_pred.get("class_name") or top_pred.get("label") or "unknown")
        top_conf = float(top_pred.get("confidence") or top_pred.get("score") or 0.0)
    else:
        top_cls = "no_detection"
        top_conf = 0.0

    return {
        "class": top_cls,
        "label": info["meta"].get("labels", {}).get(top_cls, top_cls.replace("_", " ").title()),
        "confidence": round(top_conf, 3),
        "detected": bool(predictions),
        "boxes": boxes,
        "scores": {k: round(v, 3) for k, v in scores.items()},
        "task": "remote_detection",
    }


def _find_predictions(value):
    if isinstance(value, list):
        if value and all(isinstance(item, dict) for item in value):
            if any(("confidence" in item or "score" in item) for item in value):
                return value
        for item in value:
            found = _find_predictions(item)
            if found:
                return found
    if isinstance(value, dict):
        for key in ("predictions", "detections", "objects"):
            found = _find_predictions(value.get(key))
            if found:
                return found
        for item in value.values():
            found = _find_predictions(item)
            if found:
                return found
    return []


def _prediction_bbox(pred, width, height):
    if all(k in pred for k in ("x", "y", "width", "height")):
        cx, cy = float(pred["x"]), float(pred["y"])
        bw, bh = float(pred["width"]), float(pred["height"])
        x1, y1 = int(cx - bw / 2), int(cy - bh / 2)
        x2, y2 = int(cx + bw / 2), int(cy + bh / 2)
    elif "bbox" in pred and isinstance(pred["bbox"], (list, tuple)) and len(pred["bbox"]) == 4:
        x1, y1, x2, y2 = map(int, pred["bbox"])
    else:
        return None

    x1 = max(0, min(width - 1, x1))
    y1 = max(0, min(height - 1, y1))
    x2 = max(0, min(width, x2))
    y2 = max(0, min(height, y2))
    if x2 <= x1 or y2 <= y1:
        return None
    return [x1, y1, x2, y2]
