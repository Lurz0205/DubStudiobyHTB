"""Structured JSON-lines event streaming for UI and CLI progress reporting."""
import json
import sys
from typing import Any, Dict, Optional


_listeners = []


def add_event_listener(listener) -> None:
    """Register an in-process listener callback for emitted events."""
    if listener not in _listeners:
        _listeners.append(listener)


def remove_event_listener(listener) -> None:
    """Unregister an in-process listener callback."""
    if listener in _listeners:
        _listeners.remove(listener)


def emit_event(
    stage: str,
    pct: float,
    msg: str,
    level: str = "info",
    extra: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> None:
    """Emit a JSON-lines formatted progress event to stdout and in-process listeners."""
    event_data = {
        "stage": stage,
        "pct": round(pct, 2),
        "msg": msg,
        "level": level,
    }
    if extra:
        event_data.update(extra)
    if data:
        event_data["data"] = data
    if kwargs:
        event_data.update(kwargs)

    # Use sys.stdout directly with flush for real-time consumption
    payload = json.dumps(event_data, ensure_ascii=False) + "\n"
    try:
        sys.stdout.write(payload)
        sys.stdout.flush()
    except (UnicodeEncodeError, UnicodeError):
        try:
            if hasattr(sys.stdout, "buffer"):
                sys.stdout.buffer.write(payload.encode("utf-8", errors="replace"))
                sys.stdout.buffer.flush()
            else:
                sys.stdout.write(json.dumps(event_data, ensure_ascii=True) + "\n")
                sys.stdout.flush()
        except Exception:
            pass
    except Exception:
        pass

    for listener in list(_listeners):
        try:
            listener(event_data)
        except Exception:
            pass

