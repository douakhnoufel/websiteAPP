import cv2
import time
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from core.config import (
    STREAM_ALLOWED_HOSTS,
    STREAM_ALLOWED_SCHEMES,
    STREAM_INFERENCE_FPS,
    STREAM_JPEG_QUALITY,
)
from services.security import is_private_or_loopback_host
from services.model_manager import get_model_info
from services.inference import draw_inference, run_inference

router = APIRouter(prefix="/stream", tags=["stream"])


def _validate_stream_url(url: str) -> None:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()

    if scheme not in STREAM_ALLOWED_SCHEMES:
        raise HTTPException(400, f"Unsupported stream scheme: {scheme or 'missing'}")
    if not host:
        raise HTTPException(400, "Stream URL must include a host")
    if STREAM_ALLOWED_HOSTS:
        if host not in STREAM_ALLOWED_HOSTS:
            raise HTTPException(403, "Stream host is not in STREAM_ALLOWED_HOSTS")
        return
    if not is_private_or_loopback_host(host):
        raise HTTPException(
            403,
            "Stream host must be local/private or explicitly listed in STREAM_ALLOWED_HOSTS",
        )


def _probe_stream(url: str, timeout_sec: float = 5.0) -> dict:
    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        return {"ok": False, "error": "open_failed"}

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)

    deadline = time.time() + max(1.0, timeout_sec)
    readable = False
    while time.time() < deadline:
        ret, _ = cap.read()
        if ret:
            readable = True
            break
        time.sleep(0.05)

    cap.release()

    if not readable:
        return {
            "ok": False,
            "error": "no_frames",
            "width": width,
            "height": height,
            "fps": fps,
        }

    return {"ok": True, "width": width, "height": height, "fps": fps}


def _encode_mjpeg_frame(frame) -> bytes:
    ok, buffer = cv2.imencode(
        ".jpg",
        frame,
        [cv2.IMWRITE_JPEG_QUALITY, max(30, min(STREAM_JPEG_QUALITY, 95))],
    )
    if not ok:
        raise RuntimeError("Failed to encode JPEG frame")
    return (
        b"--frame\r\n"
        b"Content-Type: image/jpeg\r\n\r\n"
        + buffer.tobytes()
        + b"\r\n"
    )


def _read_latest_frame(cap: cv2.VideoCapture, max_reads: int = 6):
    latest = None
    for _ in range(max_reads):
        ret, frame = cap.read()
        if not ret:
            break
        latest = frame
    return latest


def _read_stream_frame(url: str):
    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        cap.release()
        raise HTTPException(502, "Cannot open RTMP/RTSP source")

    frame = _read_latest_frame(cap, max_reads=12)
    cap.release()
    if frame is None:
        raise HTTPException(502, "Stream opened but no frames were received")
    return frame


@router.get("/test")
async def test_stream(url: str = Query(...)):
    _validate_stream_url(url)
    result = _probe_stream(url)
    if result["ok"]:
        return {"ok": True, "url": url, "stream": result}

    hints = [
        "Confirm DJI Fly live stream is started and ingest URL/stream key are correct.",
        "Ensure RTMP server is reachable from this API host.",
        "If host is public, add it to STREAM_ALLOWED_HOSTS and restart the API.",
    ]
    return {"ok": False, "url": url, "stream": result, "hints": hints}


@router.get("/drone")
async def stream_drone(url: str = Query(...), model_id: str = Query("potato")):
    """
    Consumes an RTMP stream, processes it with YOLOv8, 
    and yields an MJPEG stream for the frontend.
    """
    _validate_stream_url(url)
    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        cap.release()
        raise HTTPException(502, "Cannot open RTMP/RTSP source")

    ret, first_frame = cap.read()
    if not ret:
        cap.release()
        raise HTTPException(502, "Stream opened but no frames were received")

    def _generate():
        info = get_model_info(model_id)
        min_interval = 0.0 if STREAM_INFERENCE_FPS <= 0 else 1.0 / STREAM_INFERENCE_FPS
        latest_annotated = draw_inference(
            first_frame,
            run_inference(first_frame, model_id, info=info),
            model_id,
        )
        last_inference_at = time.monotonic()
        yield _encode_mjpeg_frame(latest_annotated)

        while True:
            frame = _read_latest_frame(cap)
            if frame is None:
                break

            now = time.monotonic()
            if min_interval == 0.0 or (now - last_inference_at) >= min_interval:
                pred = run_inference(frame, model_id, info=info)
                latest_annotated = draw_inference(frame, pred, model_id)
                last_inference_at = now

            yield _encode_mjpeg_frame(latest_annotated)

        cap.release()

    return StreamingResponse(_generate(), media_type="multipart/x-mixed-replace; boundary=frame")


@router.get("/detect")
async def detect_stream(url: str = Query(...), model_id: str = Query("potato")):
    _validate_stream_url(url)
    frame = _read_stream_frame(url)
    info = get_model_info(model_id)
    pred = run_inference(frame, model_id, info=info)
    height, width = frame.shape[:2]
    return {
        "ok": True,
        "url": url,
        "model_id": model_id,
        "frame": {"width": width, "height": height},
        "prediction": pred,
        "detected": bool(pred.get("boxes")),
        "timestamp_ms": int(time.time() * 1000),
    }
