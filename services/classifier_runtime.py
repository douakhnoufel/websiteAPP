import random
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class ClassifierRuntime:
    session: object
    input_name: str
    output_name: str | None
    input_size: tuple[int, int]
    layout: str
    mean: tuple[float, float, float]
    std: tuple[float, float, float]


def load_onnx_classifier(path, meta):
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise RuntimeError("onnxruntime is not installed") from exc

    providers = ["CPUExecutionProvider"]
    session = ort.InferenceSession(str(path), providers=providers)
    input_meta = session.get_inputs()[0]
    output_meta = session.get_outputs()[0] if session.get_outputs() else None
    shape = list(input_meta.shape or [])
    layout = meta.get("layout", "nchw").lower()
    input_size = _resolve_input_size(shape, layout, int(meta.get("input_size", 224)))
    return ClassifierRuntime(
        session=session,
        input_name=input_meta.name,
        output_name=output_meta.name if output_meta else None,
        input_size=input_size,
        layout=layout,
        mean=tuple(meta.get("mean", (0.485, 0.456, 0.406))),
        std=tuple(meta.get("std", (0.229, 0.224, 0.225))),
    )


def run_classifier(img, info):
    runtime = info.get("classifier")
    classes = info["meta"]["classes"]
    if runtime is None:
        return demo_classifier_result(classes, info)

    tensor = _preprocess(img, runtime)
    outputs = runtime.session.run(
        [runtime.output_name] if runtime.output_name else None,
        {runtime.input_name: tensor},
    )
    logits = np.asarray(outputs[0]).reshape(-1).astype(np.float32)
    if logits.size != len(classes):
        limit = min(logits.size, len(classes))
        logits = logits[:limit]
        classes = classes[:limit]
    probs = _softmax(logits)
    top_idx = int(np.argmax(probs)) if probs.size else 0
    cls = classes[top_idx] if classes else "unknown"
    scores = {c: round(float(probs[i]), 3) for i, c in enumerate(classes)}
    return {
        "class": cls,
        "label": info["meta"].get("labels", {}).get(cls, cls.replace("_", " ").title()),
        "confidence": round(float(probs[top_idx]), 3) if probs.size else 0.0,
        "detected": True,
        "boxes": [],
        "scores": scores,
        "task": "classification",
    }


def demo_classifier_result(classes, info):
    cls = random.choice(classes)
    conf = round(random.uniform(0.72, 0.96), 3)
    base = max(round((1.0 - conf) / max(len(classes) - 1, 1), 3), 0.0)
    scores = {c: base for c in classes}
    scores[cls] = conf
    return {
        "class": cls,
        "label": info["meta"].get("labels", {}).get(cls, cls.replace("_", " ").title()),
        "confidence": conf,
        "detected": True,
        "boxes": [],
        "scores": scores,
        "task": "classification",
    }


def _resolve_input_size(shape, layout, fallback):
    dims = [d if isinstance(d, int) and d > 0 else None for d in shape]
    if layout == "nhwc" and len(dims) >= 4:
        h, w = dims[1] or fallback, dims[2] or fallback
        return int(w), int(h)
    if len(dims) >= 4:
        h, w = dims[2] or fallback, dims[3] or fallback
        return int(w), int(h)
    return fallback, fallback


def _preprocess(img, runtime):
    resized = cv2.resize(img, runtime.input_size, interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    mean = np.asarray(runtime.mean, dtype=np.float32)
    std = np.asarray(runtime.std, dtype=np.float32)
    rgb = (rgb - mean) / std
    if runtime.layout == "nhwc":
        return rgb[np.newaxis, :, :, :].astype(np.float32)
    return np.transpose(rgb, (2, 0, 1))[np.newaxis, :, :, :].astype(np.float32)


def _softmax(values):
    values = values - np.max(values)
    exp = np.exp(values)
    total = np.sum(exp)
    if not np.isfinite(total) or total <= 0:
        return np.zeros_like(values, dtype=np.float32)
    return exp / total
