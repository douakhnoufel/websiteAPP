import time
import uuid
from threading import Lock

from core.config import DRONE_COMMAND_TTL_SEC


SUPPORTED_COMMANDS = {
    "start_scan",
    "return_to_home",
    "hold_position",
    "emergency_stop",
}
KNOWN_MODES = {"IDLE", "AUTO_SCAN", "HOLD", "RTH", "EMERGENCY_STOP"}
KNOWN_STATUS = {
    "waiting_bridge",
    "connected",
    "ready",
    "command_queued",
    "command_delivered",
    "command_failed",
}
BRIDGE_CONNECTED_SEC = 3.0
BRIDGE_STALE_SEC = 8.0
COMMAND_TTL_SEC = float(DRONE_COMMAND_TTL_SEC)

_LOCK = Lock()
_STATE = {
    "mode": "IDLE",
    "mission": "Unassigned",
    "status": "waiting_bridge",
    "battery_pct": None,
    "altitude_m": None,
    "link_quality_pct": None,
    "ground_speed_mps": None,
    "gps_lat": None,
    "gps_lon": None,
    "failsafe": "Unknown",
    "armed": False,
    "last_command": None,
    "last_telemetry_at": None,
    "last_bridge_time_ms": None,
    "last_received_at": None,
    "updated_at": time.time(),
}
_COMMAND_QUEUE = []
COMMAND_QUEUE_MAX = 200  # hard cap; pruned after each expire pass


def _now() -> float:
    return time.time()


def _state_snapshot_locked() -> dict:
    bridge_health = "disconnected"
    if _STATE["last_telemetry_at"] is not None:
        age = _now() - _STATE["last_telemetry_at"]
        if age <= BRIDGE_CONNECTED_SEC:
            bridge_health = "connected"
        elif age <= BRIDGE_STALE_SEC:
            bridge_health = "stale"
    return {
        "mode": _STATE["mode"],
        "mission": _STATE["mission"],
        "status": _STATE["status"],
        "armed": _STATE["armed"],
        "last_command": _STATE["last_command"],
        "failsafe": _STATE["failsafe"],
        "last_telemetry_at": _STATE["last_telemetry_at"],
        "updated_at": _STATE["updated_at"],
        "bridge_connected": bridge_health == "connected",
        "bridge_health": bridge_health,
        "last_bridge_time_ms": _STATE["last_bridge_time_ms"],
        "last_received_at": _STATE["last_received_at"],
    }


def _telemetry_snapshot_locked() -> dict:
    return {
        "battery_pct": _STATE["battery_pct"],
        "altitude_m": _STATE["altitude_m"],
        "link_quality_pct": _STATE["link_quality_pct"],
        "ground_speed_mps": _STATE["ground_speed_mps"],
        "gps_lat": _STATE["gps_lat"],
        "gps_lon": _STATE["gps_lon"],
        "mode": _STATE["mode"],
        "mission": _STATE["mission"],
        "failsafe": _STATE["failsafe"],
        "status": _STATE["status"],
        "last_telemetry_at": _STATE["last_telemetry_at"],
        "bridge_time_ms": _STATE["last_bridge_time_ms"],
        "received_at": _STATE["last_received_at"],
        "updated_at": _STATE["updated_at"],
    }


def get_drone_state() -> dict:
    with _LOCK:
        return _state_snapshot_locked()


def get_drone_telemetry() -> dict:
    with _LOCK:
        return _telemetry_snapshot_locked()


def queue_command(command: str) -> dict:
    cmd = command.strip().lower()
    if cmd not in SUPPORTED_COMMANDS:
        raise ValueError(f"Unsupported command: {command}")

    with _LOCK:
        command_id = uuid.uuid4().hex
        _COMMAND_QUEUE.append(
            {
                "id": command_id,
                "command": cmd,
                "queued_at": _now(),
                "status": "queued",
                "expires_at": _now() + COMMAND_TTL_SEC,
            }
        )
        _STATE["last_command"] = cmd
        _STATE["status"] = "command_queued"
        _STATE["updated_at"] = _now()
        return {
            "id": command_id,
            "command": cmd,
            "status": "queued",
            "queued_at": _COMMAND_QUEUE[-1]["queued_at"],
            "expires_at": _COMMAND_QUEUE[-1]["expires_at"],
        }


def _normalize_mode(value: str | None) -> str | None:
    if value is None:
        return None
    upper = value.strip().upper()
    return upper if upper in KNOWN_MODES else "UNKNOWN"


def _normalize_status(value: str | None) -> str | None:
    if value is None:
        return None
    lower = value.strip().lower()
    return lower if lower in KNOWN_STATUS else "unknown"


_TERMINAL_STATUSES = {"expired", "ack_success", "ack_failed"}


def _expire_commands_locked() -> None:
    now = _now()
    for command in _COMMAND_QUEUE:
        if command["status"] in {"queued", "delivered"} and now > command["expires_at"]:
            command["status"] = "expired"
            command["expired_at"] = now
    # Prune terminal entries once we exceed the cap, keeping the most recent ones
    terminal = [c for c in _COMMAND_QUEUE if c["status"] in _TERMINAL_STATUSES]
    if len(_COMMAND_QUEUE) > COMMAND_QUEUE_MAX and terminal:
        remove = set(id(c) for c in terminal[: len(_COMMAND_QUEUE) - COMMAND_QUEUE_MAX])
        _COMMAND_QUEUE[:] = [c for c in _COMMAND_QUEUE if id(c) not in remove]


def ingest_telemetry(payload: dict) -> dict:
    with _LOCK:
        _expire_commands_locked()
        mode = _normalize_mode(payload.get("mode"))
        status = _normalize_status(payload.get("status"))
        if mode is not None:
            _STATE["mode"] = mode
        if "mission" in payload:
            _STATE["mission"] = payload["mission"]
        if status is not None:
            _STATE["status"] = status
        for key in ("battery_pct", "altitude_m", "link_quality_pct", "ground_speed_mps", "gps_lat", "gps_lon", "failsafe", "armed"):
            if key in payload:
                _STATE[key] = payload[key]
        if "bridge_time_ms" in payload:
            _STATE["last_bridge_time_ms"] = payload["bridge_time_ms"]
        _STATE["last_received_at"] = _now()
        _STATE["last_telemetry_at"] = _now()
        _STATE["updated_at"] = _now()
        if _STATE["status"] in (None, "", "waiting_bridge"):
            _STATE["status"] = "connected"
        return _telemetry_snapshot_locked()


def poll_commands(limit: int = 10) -> list:
    with _LOCK:
        _expire_commands_locked()
        queued = [c for c in _COMMAND_QUEUE if c["status"] == "queued"]
        take = queued[: max(1, min(limit, 100))]
        now = _now()
        for command in take:
            command["status"] = "delivered"
            command["delivered_at"] = now
        if take:
            _STATE["status"] = "command_delivered"
            _STATE["updated_at"] = now
        return take


def acknowledge_command(command_id: str, success: bool, detail: str | None = None) -> dict:
    with _LOCK:
        _expire_commands_locked()
        for command in _COMMAND_QUEUE:
            if command["id"] == command_id:
                if command["status"] == "expired":
                    raise ValueError(f"Command expired: {command_id}")
                command["status"] = "ack_success" if success else "ack_failed"
                command["ack_at"] = _now()
                command["detail"] = detail
                _STATE["status"] = "ready" if success else "command_failed"
                _STATE["updated_at"] = _now()
                return command
    raise ValueError(f"Unknown command id: {command_id}")


def get_command_status(command_id: str) -> dict:
    with _LOCK:
        _expire_commands_locked()
        for command in _COMMAND_QUEUE:
            if command["id"] == command_id:
                return command
    raise ValueError(f"Unknown command id: {command_id}")
