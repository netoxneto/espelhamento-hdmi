"""Enumeração das janelas de aplicativo disponíveis para captura."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def list_windows():
    """Retorna janelas visíveis com título e HWND válido."""
    try:
        import win32gui
        import win32process
    except ImportError as exc:
        raise RuntimeError(
            "pywin32 não está instalado. Execute install.bat novamente."
        ) from exc

    results = []

    def callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True

        title = win32gui.GetWindowText(hwnd).strip()
        if not title:
            return True

        # Janelas minimizadas continuam sendo selecionáveis; janelas de
        # ferramenta sem título não entram por causa do filtro acima.
        _thread_id, pid = win32process.GetWindowThreadProcessId(hwnd)
        results.append(
            {
                "hwnd": int(hwnd),
                "title": title,
                "pid": int(pid),
            }
        )
        return True

    win32gui.EnumWindows(callback, None)
    results.sort(key=lambda item: item["title"].casefold())
    logger.info("Janelas visíveis encontradas: %d", len(results))
    return results
