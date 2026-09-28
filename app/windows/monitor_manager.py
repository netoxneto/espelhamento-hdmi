"""Enumeração de monitores Win32; não altera a configuração do Windows."""
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32

class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT),
                ("rcWork", RECT), ("dwFlags", wintypes.DWORD),
                ("szDevice", wintypes.WCHAR * 32)]

MONITORINFOF_PRIMARY = 1

def list_monitors():
    found = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR,
                                        wintypes.HDC, ctypes.POINTER(RECT), wintypes.LPARAM)
    def callback(handle, _hdc, _rect, _data):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(info)
        if user32.GetMonitorInfoW(handle, ctypes.byref(info)):
            r = info.rcMonitor
            found.append({
                "name": info.szDevice,
                "left": r.left, "top": r.top,
                "width": r.right-r.left, "height": r.bottom-r.top,
                "primary": bool(info.dwFlags & MONITORINFOF_PRIMARY)
            })
        return True
    user32.EnumDisplayMonitors(0, 0, callback_type(callback), 0)
    return found
