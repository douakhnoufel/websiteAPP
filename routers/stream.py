import cv2
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from services.model_manager import get_model_info
from services.inference import run_inference, draw_inference

router = APIRouter(prefix="/stream", tags=["stream"])

@router.get("/drone")
async def stream_drone(url: str = Query(...), model_id: str = Query("potato")):
    """
    Consumes an RTMP stream, processes it with YOLOv8, 
    and yields an MJPEG stream for the frontend.
    """
    def _generate():
        cap = cv2.VideoCapture(url)
        if not cap.isOpened():
            print(f"Failed to open RTMP stream: {url}")
            return
        
        info = get_model_info(model_id)
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
