from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from core.config import ALLOWED_ORIGINS, STATIC_DIR, OUTPUTS_DIR
from routers import health, predict, stream, drone

app = FastAPI(title="PotatoScan API", version="3.0 - Enterprise")

origins = ["*"] if ALLOWED_ORIGINS.strip() == "*" else [o.strip() for o in ALLOWED_ORIGINS.split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")

app.include_router(health.router)
app.include_router(predict.router)
app.include_router(stream.router)
app.include_router(drone.router)

@app.on_event("startup")
async def on_startup():
    health.load_template()
