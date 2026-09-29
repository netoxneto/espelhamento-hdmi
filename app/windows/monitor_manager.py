"""Enumeração de monitores físicos/lógicos do Windows via pywin32."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def list_monitors():
    """Retorna os monitores disponíveis no Windows.

    Cada item contém coordenadas virtuais, resolução, dispositivo e indicação
    de monitor principal. Usa pywin32 porque ele já faz parte das dependências
    do projeto e evita diferenças de assinatura ctypes entre versões do Windows.
    """
    try:
        import win32api
    except ImportError as exc:
        raise RuntimeError(
            "pywin32 não está instalado. Execute install.bat novamente."
        ) from exc

    found = []
    for handle, _hdc, _rect in win32api.EnumDisplayMonitors():
        info = win32api.GetMonitorInfo(handle)
        left, top, right, bottom = info["Monitor"]
        flags = int(info.get("Flags", 0))
        found.append(
            {
                "name": info.get("Device") or f"MONITOR_{len(found) + 1}",
                "left": int(left),
                "top": int(top),
                "width": int(right - left),
                "height": int(bottom - top),
                "primary": bool(flags & 1),
            }
        )

    found.sort(key=lambda m: (not m["primary"], m["left"], m["top"], m["name"]))
    logger.info("Monitores encontrados: %d", len(found))
    for monitor in found:
        logger.info("Monitor: %s %sx%s primary=%s", monitor["name"], monitor["width"], monitor["height"], monitor["primary"])
    return found
