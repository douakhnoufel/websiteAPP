from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.config import DJI_BRIDGE_LOCAL_ONLY, DJI_TELEMETRY_HZ
from services.security import drone_auth_status, require_drone_access
from services.drone_manager import (
    acknowledge_command,
    get_command_status,
    get_drone_state,
    get_drone_telemetry,
    ingest_telemetry,
    poll_commands,
    queue_command,
)

router = APIRouter(prefix="/drone", tags=["drone"])


class DroneCommand(BaseModel):
    command: str


class DroneTelemetryIn(BaseModel):
    mode: str | None = None
    mission: str | None = None
    status: str | None = None
    battery_pct: float | None = Field(default=None, ge=0, le=100)
    altitude_m: float | None = None
    link_quality_pct: float | None = Field(default=None, ge=0, le=100)
    ground_speed_mps: float | None = None
    gps_lat: float | None = Field(default=None, ge=-90, le=90)
    gps_lon: float | None = Field(default=None, ge=-180, le=180)
    failsafe: str | None = None
    armed: bool | None = None
    bridge_time_ms: int | None = Field(default=None, ge=0, le=60000)


class CommandAckIn(BaseModel):
    id: str
    success: bool = True
    detail: str | None = None


@router.get("/telemetry")
async def telemetry():
    return {
        "ok": True,
        "telemetry": get_drone_telemetry(),
        "bridge": {
            "local_only": DJI_BRIDGE_LOCAL_ONLY,
            "auth": drone_auth_status(),
            "telemetry_hz_target": DJI_TELEMETRY_HZ,
        },
    }


@router.get("/state")
async def state():
    return {
        "ok": True,
        "state": get_drone_state(),
        "bridge": {
            "local_only": DJI_BRIDGE_LOCAL_ONLY,
            "auth": drone_auth_status(),
            "telemetry_hz_target": DJI_TELEMETRY_HZ,
        },
    }


@router.post("/command")
async def command(payload: DroneCommand, _: None = Depends(require_drone_access)):
    try:
        queued = queue_command(payload.command)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "queued": queued, "state": get_drone_state()}


@router.get("/command/{command_id}")
async def command_status(command_id: str, _: None = Depends(require_drone_access)):
    try:
        status = get_command_status(command_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "command": status}


@router.post("/bridge/telemetry")
async def bridge_telemetry(payload: DroneTelemetryIn, _: None = Depends(require_drone_access)):
    return {"ok": True, "telemetry": ingest_telemetry(payload.model_dump(exclude_none=True))}


@router.get("/bridge/commands")
async def bridge_commands(limit: int = Query(10, ge=1, le=100), _: None = Depends(require_drone_access)):
    return {"ok": True, "commands": poll_commands(limit=limit)}


@router.post("/bridge/ack")
async def bridge_ack(payload: CommandAckIn, _: None = Depends(require_drone_access)):
    try:
        ack = acknowledge_command(payload.id, payload.success, payload.detail)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "ack": ack}
