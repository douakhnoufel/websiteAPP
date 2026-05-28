import cv2
import time
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from core.config import STREAM_ALLOWED_HOSTS, STREAM_ALLOWED_SCHEMES
from services.security import is_private_or_loopback_host
from services.model_manager import get_model_info
from services.inference import run_inference, draw_inference

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

        pred = run_inference(first_frame, model_id, info=info)
        annotated = draw_inference(first_frame, pred, model_id)
        _, buffer = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Process frame with YOLO
            pred = run_inference(frame, model_id, info=info)
            annotated = draw_inference(frame, pred, model_id)
            
            _, buffer = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        cap.release()

    return StreamingResponse(_generate(), media_type="multipart/x-mixed-replace; boundary=frame")
