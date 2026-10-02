from __future__ import annotations


def socket_error_code(exc: BaseException) -> int | None:
    code = getattr(exc, "winerror", None)
    if code is None:
        code = getattr(exc, "errno", None)
    try:
        return int(code) if code is not None else None
    except (TypeError, ValueError):
        return None


def describe_mavlink_start_error(exc: BaseException, listen_port: int) -> str:
    code = socket_error_code(exc)

    if code == 10048:
        return (
            f"UDP {listen_port} is already in use. Close Mission Planner, another "
            "PC TeleRC instance, MAVProxy/QGroundControl, or another MAVLink listener, "
            "then click Apply & Reconnect."
        )
    if code == 10013:
        return (
            f"Windows denied access to UDP {listen_port}. Check Windows excluded UDP "
            "port ranges, security/network software, or choose a matching free port "
            "on both PC TeleRC and the ESP32 bridge."
        )

    return f"MAVLink worker stopped: {exc}"
