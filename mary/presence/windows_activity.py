"""Best-effort Windows foreground-window observation. No screenshots."""
from __future__ import annotations
import sys
from typing import Any

def foreground_window() -> dict[str, Any]:
    if sys.platform != "win32": return {"available": False, "title": "", "platform": sys.platform}
    try:
        import ctypes
        user32=ctypes.windll.user32
        hwnd=user32.GetForegroundWindow()
        length=user32.GetWindowTextLengthW(hwnd)
        buffer=ctypes.create_unicode_buffer(length+1)
        user32.GetWindowTextW(hwnd,buffer,length+1)
        return {"available": bool(hwnd), "title": str(buffer.value)[:500], "platform": "win32"}
    except Exception as exc:
        return {"available": False, "title": "", "platform": "win32", "error": f"{type(exc).__name__}: {exc}"}
