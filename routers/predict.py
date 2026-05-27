import uuid
import time
import shutil
import cv2
import numpy as np
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse

from core.config import UPLOADS_DIR, OUTPUTS_DIR, MAX_IMAGE_MB, MAX_VIDEO_MB, VIDEO_SAMPLE_FPS, FRAME_MAX_EDGE
from services.inference import run_inference, draw_inference, resize_max_edge
from services.file_handler import remove_file
from services.model_manager import get_model_info, label_for

router = APIRouter(prefix="/predict", tags=["predict"])

@router.post("/image")
async def predict_image(bg: BackgroundTasks, file: UploadFile = File(...), model_id: str = Query("potato")):
    uid = uuid.uuid4().hex[:8]
    img_path = UPLOADS_DIR / f"{uid}{Path(file.filename).suffix}"
    out_path = OUTPUTS_DIR / f"{uid}_out.jpg"
    
    with open(img_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
        
    if img_path.stat().st_size > MAX_IMAGE_MB * 1024 * 1024:
        bg.add_task(remove_file, str(img_path))
        raise HTTPException(413, f"Image exceeds {MAX_IMAGE_MB}MB limit")
        
    img = cv2.imread(str(img_path))
    if img is None:
        bg.add_task(remove_file, str(img_path))
        raise HTTPException(400, "Cannot read image")
        
    t0 = time.time()
    pred = run_inference(img, model_id)
    ms = int((time.time() - t0) * 1000)
    pred["inference_ms"] = ms
    
    cv2.imwrite(str(out_path), draw_inference(img, pred, model_id))
    bg.add_task(remove_file, str(img_path))
    
    return JSONResponse({"id": uid, "model_id": model_id, "prediction": pred,
                         "inference_ms": ms, "result_url": f"/outputs/{out_path.name}"})

@router.post("/video")
async def predict_video(bg: BackgroundTasks, file: UploadFile = File(...), model_id: str = Query("potato")):
    uid = uuid.uuid4().hex[:8]
    img_path = UPLOADS_DIR / f"{uid}{Path(file.filename).suffix}"
    out_path = OUTPUTS_DIR / f"{uid}_out.mp4"
    
    with open(img_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
        
    if img_path.stat().st_size > MAX_VIDEO_MB * 1024 * 1024:
        bg.add_task(remove_file, str(img_path))
        raise HTTPException(413, f"Video exceeds {MAX_VIDEO_MB}MB limit")
        
    cap = cv2.VideoCapture(str(img_path))
    if not cap.isOpened():
        bg.add_task(remove_file, str(img_path))
        raise HTTPException(400, "Cannot open video")
        
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    W, H = int(cap.get(3)), int(cap.get(4))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    
    preds, fi, t0 = [], 0, time.time()
    skip = max(1, int(round(fps / max(VIDEO_SAMPLE_FPS, 0.1))))
    info = get_model_info(model_id)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if fi % skip == 0:
            p = run_inference(frame, model_id, info=info)
            preds.append(p)
        writer.write(draw_inference(frame, preds[-1] if preds else {"boxes": []}, model_id))
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
    dom_label = label_for(info, dom)
    
    bg.add_task(remove_file, str(img_path))
    
    return JSONResponse({"id": uid, "model_id": model_id, "dominant_class": dom,
                         "dominant_label": dom_label, "avg_confidence": avg, "class_distribution": dist,
                         "frames_analyzed": len(preds), "total_frames": total,
                         "inference_ms": ms, "result_url": f"/outputs/{out_path.name}"})

@router.post("/frame")
async def predict_frame(file: UploadFile = File(...), model_id: str = Query("potato")):
    data = await file.read()
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(400, "Cannot decode frame")
        
    img = resize_max_edge(img, FRAME_MAX_EDGE)
    t0 = time.time()
    pred = run_inference(img, model_id)
    pred["inference_ms"] = int((time.time() - t0) * 1000)
    return JSONResponse(pred)
