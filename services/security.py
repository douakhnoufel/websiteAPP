import ipaddress
import secrets

from fastapi import Header, HTTPException, Request, status

from core.config import DJI_BRIDGE_LOCAL_ONLY, DJI_BRIDGE_TOKEN


LOCAL_HOSTNAMES = {"localhost", "testclient"}


def is_private_or_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    normalized = host.strip().strip("[]").lower()
    if normalized in LOCAL_HOSTNAMES or normalized.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


def drone_auth_status() -> str:
    return "enabled" if DJI_BRIDGE_TOKEN else "disabled"


def _token_from_headers(
    authorization: str | None,
    x_dji_bridge_token: str | None,
) -> str:
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer" and value:
            return value.strip()
    return (x_dji_bridge_token or "").strip()


async def require_drone_access(
    request: Request,
    authorization: str | None = Header(default=None),
    x_dji_bridge_token: str | None = Header(default=None, alias="X-DJI-Bridge-Token"),
) -> None:
    client_host = request.client.host if request.client else None
    if DJI_BRIDGE_LOCAL_ONLY and not is_private_or_loopback_host(client_host):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Drone bridge access is restricted to local/private network clients",
        )

    if not DJI_BRIDGE_TOKEN:
        return

    supplied = _token_from_headers(authorization, x_dji_bridge_token)
    if not secrets.compare_digest(supplied, DJI_BRIDGE_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing drone bridge token",
            headers={"WWW-Authenticate": "Bearer"},
        )
