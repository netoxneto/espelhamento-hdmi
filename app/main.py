from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from app.gui.main_window import MainWindow
from app.input.mouse_lock import MouseLock
from app.video.session import CaptureSession
from app.windows.monitor_manager import list_monitors


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


def main():
    if sys.platform != "win32":
        print("Este aplicativo foi desenvolvido exclusivamente para Windows 11.")
        return 2

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Espelhamento HDMI")
    app.setOrganizationName("Espelhamento HDMI")

    monitors = list_monitors()
    if not monitors:
        QMessageBox.critical(None, "Espelhamento HDMI", "Nenhum monitor foi encontrado pelo Windows.")
        return 1

    # A sessão inicia no monitor principal como fallback; a GUI pode mover
    # a saída para o monitor escolhido antes da primeira transmissão.
    selected_monitor = next((m for m in monitors if m["primary"]), monitors[0])
    mouse_lock = MouseLock(enabled=True)
    session = CaptureSession(selected_monitor, mouse_lock=mouse_lock, fps=30)

    # A saída fullscreen já é criada pela sessão para preservar a arquitetura
    # existente. Ela fica preta até a primeira transmissão.
    window = MainWindow(session, mouse_lock)
    window.show()

    try:
        return app.exec()
    finally:
        try:
            session.stop()
        finally:
            mouse_lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
