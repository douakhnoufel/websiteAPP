from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from core.config import TEMPLATE_PATH, DEMO_MODE, TEMPLATE_AUTO_RELOAD
from services.model_manager import get_loaded_models, load_models

router = APIRouter()

_INDEX_HTML = None
_INDEX_MTIME = None


def _refresh_template_if_changed():
    global _INDEX_HTML, _INDEX_MTIME
    if not TEMPLATE_PATH.exists():
        return
    if TEMPLATE_AUTO_RELOAD:
        _INDEX_HTML = TEMPLATE_PATH.read_text(encoding="utf-8")
        _INDEX_MTIME = TEMPLATE_PATH.stat().st_mtime
        return
    mtime = TEMPLATE_PATH.stat().st_mtime
    if _INDEX_HTML is None or _INDEX_MTIME != mtime:
        _INDEX_HTML = TEMPLATE_PATH.read_text(encoding="utf-8")
        _INDEX_MTIME = mtime

def load_template():
    global _INDEX_HTML, _INDEX_MTIME
    if not TEMPLATE_PATH.exists():
        print("WARNING: templates/index.html not found")
    else:
        _INDEX_HTML = TEMPLATE_PATH.read_text(encoding="utf-8")
        _INDEX_MTIME = TEMPLATE_PATH.stat().st_mtime
        print(f"  [OK] loaded template ({len(_INDEX_HTML)} chars)")
    load_models(strict=not DEMO_MODE)

@router.get("/", response_class=HTMLResponse)
async def root():
    _refresh_template_if_changed()
    if _INDEX_HTML is None:
        raise HTTPException(503, "Template not loaded")
    return HTMLResponse(
        _INDEX_HTML,
        headers={"Cache-Control": "no-store, max-age=0"},
    )

@router.get("/health")
async def health():
    _loaded = get_loaded_models()
    return {"status": "ok", "models": {
        mid: {"loaded": s["yolo"] is not None, "classes": s["meta"]["classes"], "error": s.get("error")}
        for mid, s in _loaded.items()
    }}

@router.get("/models")
async def list_models():
    _loaded = get_loaded_models()
    return [{"id": mid, "name": s["meta"]["name"], "description": s["meta"]["description"],
             "classes": s["meta"]["classes"], "loaded": s["yolo"] is not None, "error": s.get("error")}
            for mid, s in _loaded.items()]
