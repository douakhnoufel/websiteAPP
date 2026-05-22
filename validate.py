import argparse
from collections import Counter
from pathlib import Path

import cv2
from ultralytics import YOLO

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

def iter_images(root):
    for p in root.rglob("*"):
        if p.suffix.lower() in IMAGE_EXTS:
            yield p

def predict_class(model, img, conf, imgsz, device):
    kwargs = {"conf": conf, "imgsz": imgsz, "verbose": False}
    if device:
        kwargs["device"] = device
    res = model.predict(img, **kwargs)[0]
    if not res.boxes:
        return None
    cls_id = int(res.boxes[0].cls[0])
    return res.names.get(cls_id, str(cls_id))

def main():
    ap = argparse.ArgumentParser(description="Validate YOLO model accuracy on a folder of labeled images.")
    ap.add_argument("--data", required=True, help="Root folder with class subfolders (e.g., data/early, data/healthy)")
    ap.add_argument("--model", default="models/potato.pt", help="Path to YOLO model")
    ap.add_argument("--classes", default="early,healthy,late", help="Comma-separated class folder names")
    ap.add_argument("--conf", type=float, default=0.25, help="Confidence threshold")
    ap.add_argument("--imgsz", type=int, default=640, help="Image size")
    ap.add_argument("--device", default="", help="Device string, e.g. 'cpu' or '0'")
    args = ap.parse_args()

    root = Path(args.data)
    if not root.exists():
        raise SystemExit(f"Data folder not found: {root}")

    model = YOLO(args.model)
    classes = [c.strip() for c in args.classes.split(",") if c.strip()]
    totals = Counter()
    correct = Counter()

    for cls in classes:
        cls_dir = root / cls
        if not cls_dir.exists():
            print(f"[WARN] Missing class folder: {cls_dir}")
            continue
        for img_path in iter_images(cls_dir):
            img = cv2.imread(str(img_path))
            if img is None:
                continue
            pred = predict_class(model, img, args.conf, args.imgsz, args.device.strip())
            totals[cls] += 1
            if pred == cls:
                correct[cls] += 1

    total = sum(totals.values())
    correct_total = sum(correct.values())
    print("Per-class accuracy:")
    for cls in classes:
        t = totals[cls]
        acc = (correct[cls] / t * 100) if t else 0.0
        print(f"  {cls:10s} {acc:6.2f}%  ({correct[cls]}/{t})")
    overall = (correct_total / total * 100) if total else 0.0
    print(f"Overall: {overall:.2f}% ({correct_total}/{total})")

if __name__ == "__main__":
    main()
