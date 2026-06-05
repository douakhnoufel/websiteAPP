import uuid
import time
import cv2
import numpy as np
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from core.config import (
    UPLOADS_DIR,
    OUTPUTS_DIR,
    MAX_IMAGE_MB,
    MAX_VIDEO_MB,
    VIDEO_SAMPLE_FPS,
    FRAME_MAX_EDGE,
    FRAME_MIN_CONF,
    FRAME_MIN_BOX_AREA_RATIO,
    DEMO_MODE,
    OUTPUT_TTL_SEC,
    DEFAULT_MODEL_ID,
)
from services.inference import NO_DETECTION_CLASS, run_inference, draw_inference, resize_max_edge
from services.file_handler import remove_file, remove_file_after
from services.model_manager import get_model_info, label_for

router = APIRouter(prefix="/predict", tags=["predict"])

CHUNK_SIZE = 1024 * 1024
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def _safe_suffix(file: UploadFile, allowed_exts: set[str], kind: str) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    if not suffix:
        raise HTTPException(400, f"{kind} file must have an extension (e.g. .jpg, .png)")
    if suffix not in allowed_exts:
        raise HTTPException(400, f"Unsupported {kind} file type: {suffix}")
    return suffix


async def _save_upload_limited(file: UploadFile, dest: Path, max_mb: int, kind: str) -> int:
    max_bytes = max_mb * 1024 * 1024
    total = 0
    try:
        with dest.open("wb") as out:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(413, f"{kind} exceeds {max_mb}MB limit")
                out.write(chunk)
            if total == 0:
                raise HTTPException(400, f"{kind} file is empty")
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    return total


async def _read_upload_limited(file: UploadFile, max_mb: int, kind: str) -> bytes:
    max_bytes = max_mb * 1024 * 1024
    chunks = []
    total = 0
    try:
        while True:
            chunk = await file.read(CHUNK_SIZE)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise HTTPException(413, f"{kind} exceeds {max_mb}MB limit")
            chunks.append(chunk)
        if total == 0:
            raise HTTPException(400, f"{kind} file is empty")
    finally:
        await file.close()
    return b"".join(chunks)


def _infer_image_file(img, model_id: str, out_path: Path) -> tuple[dict, int]:
    t0 = time.time()
    pred = run_inference(img, model_id)
    ms = int((time.time() - t0) * 1000)
    pred["inference_ms"] = ms
    ok = cv2.imwrite(str(out_path), draw_inference(img, pred, model_id))
    if not ok:
        raise HTTPException(500, "Cannot write annotated image")
    return pred, ms


def _open_video_writer(out_path: Path, fps: float, size: tuple[int, int]) -> tuple[cv2.VideoWriter, str]:
    for codec in ("avc1", "H264", "mp4v"):
        writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*codec), fps, size)
        if writer.isOpened():
            return writer, codec
        writer.release()
    raise HTTPException(500, "Cannot create annotated video")


def _process_video_file(img_path: Path, out_path: Path, model_id: str) -> dict:
    info = get_model_info(model_id)
    cap = cv2.VideoCapture(str(img_path))
    if not cap.isOpened():
        raise HTTPException(400, "Cannot open video")

    writer = None
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        width, height = int(cap.get(3)), int(cap.get(4))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if width <= 0 or height <= 0:
            raise HTTPException(400, "Video has invalid dimensions")

        writer, output_codec = _open_video_writer(out_path, fps, (width, height))

        preds, frame_index, t0 = [], 0, time.time()
        skip = max(1, int(round(fps / max(VIDEO_SAMPLE_FPS, 0.1))))

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_index % skip == 0:
                preds.append(run_inference(frame, model_id, info=info))
            writer.write(draw_inference(frame, preds[-1] if preds else {"boxes": []}, model_id))
            frame_index += 1
    finally:
        cap.release()
        if writer is not None:
            writer.release()

    ms = int((time.time() - t0) * 1000) if "t0" in locals() else 0
    votes = {}
    for pred in preds:
        cls = pred.get("class") or NO_DETECTION_CLASS
        votes[cls] = votes.get(cls, 0) + 1

    dom = max(votes, key=votes.get) if votes else NO_DETECTION_CLASS
    avg = round(sum(p.get("confidence", 0.0) for p in preds) / max(len(preds), 1), 3)
    classes = [*info["meta"]["classes"], NO_DETECTION_CLASS]
    dist = {c: round(votes.get(c, 0) / max(len(preds), 1) * 100, 1) for c in classes}

    return {
        "dominant_class": dom,
        "dominant_label": label_for(info, dom),
        "avg_confidence": avg,
        "class_distribution": dist,
        "frames_analyzed": len(preds),
        "detected_frames": sum(1 for p in preds if p.get("detected")),
        "total_frames": total,
        "inference_ms": ms,
        "output_video_codec": output_codec,
    }


@router.post("/image")
async def predict_image(bg: BackgroundTasks, file: UploadFile = File(...), model_id: str = Query(DEFAULT_MODEL_ID)):
    uid = uuid.uuid4().hex[:8]
    suffix = _safe_suffix(file, IMAGE_EXTS, "image")
    img_path = UPLOADS_DIR / f"{uid}{suffix}"
    out_path = OUTPUTS_DIR / f"{uid}_out.jpg"

    await _save_upload_limited(file, img_path, MAX_IMAGE_MB, "Image")

    img = await run_in_threadpool(cv2.imread, str(img_path))
    if img is None:
        bg.add_task(remove_file, str(img_path))
        raise HTTPException(400, "Cannot read image")

    try:
        pred, ms = await run_in_threadpool(_infer_image_file, img, model_id, out_path)
    except Exception:
        bg.add_task(remove_file, str(out_path))
        raise
    finally:
        bg.add_task(remove_file, str(img_path))

    if OUTPUT_TTL_SEC > 0:
        bg.add_task(remove_file_after, str(out_path), OUTPUT_TTL_SEC)

    return JSONResponse({"id": uid, "model_id": model_id, "demo": DEMO_MODE,
                         "prediction": pred, "inference_ms": ms,
                         "result_url": f"/outputs/{out_path.name}"})


@router.post("/video")
async def predict_video(bg: BackgroundTasks, file: UploadFile = File(...), model_id: str = Query(DEFAULT_MODEL_ID)):
    uid = uuid.uuid4().hex[:8]
    suffix = _safe_suffix(file, VIDEO_EXTS, "video")
    img_path = UPLOADS_DIR / f"{uid}{suffix}"
    out_path = OUTPUTS_DIR / f"{uid}_out.mp4"

    await _save_upload_limited(file, img_path, MAX_VIDEO_MB, "Video")

    try:
        summary = await run_in_threadpool(_process_video_file, img_path, out_path, model_id)
    except Exception:
        bg.add_task(remove_file, str(out_path))
        raise
    finally:
        bg.add_task(remove_file, str(img_path))

    if OUTPUT_TTL_SEC > 0:
        bg.add_task(remove_file_after, str(out_path), OUTPUT_TTL_SEC)

    return JSONResponse({"id": uid, "model_id": model_id, "demo": DEMO_MODE,
                         **summary, "result_url": f"/outputs/{out_path.name}"})


@router.post("/frame")
async def predict_frame(file: UploadFile = File(...), model_id: str = Query(DEFAULT_MODEL_ID)):
    data = await _read_upload_limited(file, MAX_IMAGE_MB, "Frame")
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(400, "Cannot decode frame")

    img = resize_max_edge(img, FRAME_MAX_EDGE)
    t0 = time.time()
    pred = await run_in_threadpool(run_inference, img, model_id)

    h, w = img.shape[:2]
    frame_area = max(float(h * w), 1.0)
    strong_boxes = []
    for box in pred.get("boxes", []):
        x1, y1, x2, y2 = box.get("bbox", [0, 0, 0, 0])
        bw = max(0.0, float(x2 - x1))
        bh = max(0.0, float(y2 - y1))
        area_ratio = (bw * bh) / frame_area
        if float(box.get("confidence", 0.0)) >= FRAME_MIN_CONF and area_ratio >= FRAME_MIN_BOX_AREA_RATIO:
            strong_boxes.append(box)

    if not strong_boxes:
        info = get_model_info(model_id)
        pred["class"] = NO_DETECTION_CLASS
        pred["label"] = label_for(info, NO_DETECTION_CLASS)
        pred["confidence"] = 0.0
        pred["detected"] = False
        pred["boxes"] = []
    else:
        pred["boxes"] = strong_boxes
        best_box = max(strong_boxes, key=lambda b: float(b.get("confidence", 0.0)))
        pred["class"] = best_box.get("class", pred.get("class", NO_DETECTION_CLASS))
        pred["label"] = label_for(get_model_info(model_id), pred["class"])
        pred["confidence"] = round(float(best_box.get("confidence", pred.get("confidence", 0.0))), 3)
        pred["detected"] = True

    pred["inference_ms"] = int((time.time() - t0) * 1000)
    pred["demo"] = DEMO_MODE
    return JSONResponse(pred)
