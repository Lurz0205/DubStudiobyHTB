"""dubstudio package root."""
import sys
from dubstudio.packaging import ensure_runtime_paths

ensure_runtime_paths()

# Windows asyncio Proactor WinError 10054 Suppression
if sys.platform == "win32":
    import asyncio
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass
    try:
        from asyncio.proactor_events import _ProactorBasePipeTransport
        _orig_call_connection_lost = _ProactorBasePipeTransport._call_connection_lost
        def _safe_call_connection_lost(self, exc):
            try:
                _orig_call_connection_lost(self, exc)
            except (ConnectionResetError, OSError) as e:
                if getattr(e, "winerror", None) != 10054 and not isinstance(e, ConnectionResetError):
                    raise
        _ProactorBasePipeTransport._call_connection_lost = _safe_call_connection_lost
    except Exception:
        pass

