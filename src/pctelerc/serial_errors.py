"""Actionable USB failures without echoing driver buffers or credentials."""
from __future__ import annotations

import re


class RadioConnectionError(ValueError):
    """Application-owned radio setup explanation, safe for display."""


def describe_serial_error(exc: BaseException, port: str, operation: str = "open") -> str:
    selected = port.strip().upper()
    label = selected if re.fullmatch(r"COM[1-9][0-9]{0,4}", selected) else "selected port"
    action = operation if operation in ("open", "read", "write", "communicate") else "communicate"
    windows, posix, kinds, fragments = set(), set(), set(), []
    pending, seen = [exc], set()
    while pending and len(seen) < 8:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        kinds.add(type(item).__name__)
        for attr, codes in (("winerror", windows), ("errno", posix)):
            value = getattr(item, attr, None)
            if isinstance(value, int):
                codes.add(value)
        for related in (item.__cause__, item.__context__, *item.args):
            if isinstance(related, BaseException):
                pending.append(related)
            elif isinstance(related, str):
                fragments.append(related[:512].lower())
    # pyserial sometimes wraps the Windows exception as text. Match only known
    # categories; never include that text in the returned message or logs.
    wrapped = " ".join(fragments)
    prefix = f"USB {label}: could not {action}. "
    if windows & {5, 32, 33} or posix & {13, 16} or "PermissionError" in kinds or any(
        token in wrapped for token in ("access is denied", "permission denied", "permissionerror(", "resource busy")
    ):
        return prefix + "Access denied or port busy. Close Arduino Serial Monitor, Mission Planner and other serial applications, then reconnect."
    if windows & {2, 3} or posix & {2} or "FileNotFoundError" in kinds or any(
        token in wrapped for token in ("filenotfounderror(", "cannot find the file", "no such file")
    ):
        return prefix + "Port not found. Replug BASE, refresh ports and select the COM number that appears in Device Manager."
    if windows & {21, 31, 121, 995, 1167} or posix & {5, 6, 19}:
        return prefix + "Device unavailable. Check the data cable, USB connection and serial driver, then reconnect manually."
    if "SerialTimeoutException" in kinds:
        return prefix + "USB operation timed out. Check the board and data cable, then reconnect manually."
    # Preserve only fixed application-owned fault descriptions, never arbitrary
    # exception strings. These explain deliberate queue/backlog safety stops.
    for text, message in (
        ("receive backlog", "USB receive backlog; reduce vehicle telemetry and reconnect manually."),
        ("backed up", "USB output is backed up; control is disabled. Reconnect manually."),
        ("incomplete", "Incomplete USB send; control is disabled. Reconnect manually."),
    ):
        if text in wrapped:
            return prefix + message
    return prefix + "Check the native USB COM port, close other serial applications and reconnect. Reconnect manually."
