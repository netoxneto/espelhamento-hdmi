"""Interface gráfica principal do Espelhamento HDMI."""
from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QObject, Signal, Qt, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.input.mouse_lock import MouseLock
from app.video.session import CaptureSession, CaptureState
from app.windows.monitor_manager import list_monitors
from app.windows.window_manager import list_windows

logger = logging.getLogger(__name__)


class GuiSignals(QObject):
    operation_started = Signal(str)
    operation_finished = Signal(bool, str)
    refresh_finished = Signal()


class MainWindow(QMainWindow):
    """Janela de configuração e controle da transmissão."""

    def __init__(self, session: CaptureSession, mouse_lock: MouseLock):
        super().__init__()
        self.session = session
        self.mouse_lock = mouse_lock
        self.signals = GuiSignals()
        self._busy = False
        self._closing = False
        self._monitors = []
        self._windows = []

        self.setWindowTitle("Espelhamento HDMI")
        self.setMinimumSize(620, 500)
        self.resize(700, 560)
        self._build_ui()
        self._connect_signals()
        self._diagnostic_timer = QTimer(self)
        self._diagnostic_timer.timeout.connect(self._update_diagnostics)
        self._diagnostic_timer.start(500)
        self.refresh_all()

    def _build_ui(self):
        root = QWidget(self)
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(18)

        title = QLabel("ESPELHAMENTO HDMI")
        title.setObjectName("title")
        subtitle = QLabel("Transmita uma janela específica para sua TV ou segundo monitor.")
        subtitle.setObjectName("subtitle")
        outer.addWidget(title)
        outer.addWidget(subtitle)

        form_card = QFrame()
        form_card.setObjectName("card")
        form = QFormLayout(form_card)
        form.setContentsMargins(20, 20, 20, 20)
        form.setVerticalSpacing(14)

        self.monitor_combo = QComboBox()
        self.monitor_combo.setPlaceholderText("Nenhum monitor detectado")
        self.window_combo = QComboBox()
        self.window_combo.setPlaceholderText("Nenhuma janela detectada")
        form.addRow("Monitor de saída", self.monitor_combo)
        form.addRow("Janela para transmitir", self.window_combo)
        outer.addWidget(form_card)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.transmit_button = QPushButton("▶  Transmitir")
        self.transmit_button.setObjectName("primary")
        self.stop_button = QPushButton("■  Parar")
        self.refresh_button = QPushButton("↻  Atualizar")
        actions.addWidget(self.transmit_button, 2)
        actions.addWidget(self.stop_button, 1)
        actions.addWidget(self.refresh_button, 1)
        outer.addLayout(actions)

        status_card = QFrame()
        status_card.setObjectName("card")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(20, 18, 20, 18)
        status_layout.setSpacing(9)

        status_title = QLabel("Status")
        status_title.setObjectName("section")
        self.status_label = QLabel("PARADO")
        self.status_label.setObjectName("status")
        self.selected_label = QLabel("Janela: —")
        self.output_label = QLabel("Saída: —")
        self.frame_label = QLabel("Frames recebidos: 0")
        self.frame_label.setObjectName("diagnostic")
        status_layout.addWidget(status_title)
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.selected_label)
        status_layout.addWidget(self.output_label)
        status_layout.addWidget(self.frame_label)
        outer.addWidget(status_card)

        mouse_row = QHBoxLayout()
        self.mouse_status = QLabel("Mouse: bloqueado no monitor principal")
        self.mouse_button = QPushButton("Liberar mouse")
        mouse_row.addWidget(self.mouse_status, 1)
        mouse_row.addWidget(self.mouse_button)
        outer.addLayout(mouse_row)

        hint = QLabel("Atalho global: Ctrl + Alt + F12 alterna o bloqueio do mouse.")
        hint.setObjectName("hint")
        outer.addWidget(hint)
        outer.addStretch(1)

        self.stop_button.setEnabled(False)
        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet(
            """
            QMainWindow { background: #f4f6f8; }
            QLabel#title { font-size: 25px; font-weight: 700; color: #17202a; }
            QLabel#subtitle { font-size: 13px; color: #65717d; }
            QFrame#card { background: white; border: 1px solid #dfe4e8; border-radius: 12px; }
            QLabel#section { font-size: 12px; font-weight: 700; color: #65717d; }
            QLabel#status { font-size: 18px; font-weight: 700; color: #16803c; }
            QLabel#hint { color: #7a858e; font-size: 12px; }
            QLabel#diagnostic { color: #4d5963; font-size: 12px; }
            QComboBox { min-height: 38px; padding: 0 10px; border: 1px solid #cbd3da; border-radius: 7px; background: white; color: #17202a; }
            QComboBox::drop-down { border: none; width: 28px; }
            QComboBox QAbstractItemView { background-color: #ffffff; color: #17202a; }
            QComboBox QAbstractItemView { background: white; color: #17202a; selection-background-color: #dce9fb; selection-color: #17202a; }
            QPushButton { min-height: 38px; padding: 0 16px; border: 1px solid #cbd3da; border-radius: 7px; background: #ffffff; color: #17202a; }
            QPushButton:hover { background: #eef2f5; }
            QPushButton#primary { background: #1769e0; color: white; border: none; font-weight: 700; }
            QPushButton#primary:hover { background: #0f5dcc; }
            QPushButton:disabled { color: #9aa3aa; background: #eef0f2; }
            """
        )

    def _connect_signals(self):
        self.transmit_button.clicked.connect(self.start_transmission)
        self.stop_button.clicked.connect(self.stop_transmission)
        self.refresh_button.clicked.connect(self.refresh_all)
        self.mouse_button.clicked.connect(self.toggle_mouse)
        self.signals.operation_started.connect(self._on_operation_started)
        self.signals.operation_finished.connect(self._on_operation_finished)
        self.signals.refresh_finished.connect(self._on_refresh_finished)

    def refresh_all(self):
        if self._busy:
            return
        try:
            monitors = list_monitors()
            windows = list_windows()
        except Exception as exc:
            logger.exception("Falha ao enumerar monitores/janelas")
            self._monitors = []
            self._windows = []
            self.monitor_combo.clear()
            self.window_combo.clear()
            self.status_label.setText("ERRO AO ENUMERAR WINDOWS")
            QMessageBox.critical(
                self,
                "Espelhamento HDMI",
                "Não foi possível obter os monitores e aplicativos do Windows.\n\n"
                f"Detalhes: {exc}",
            )
            return

        self._monitors = monitors
        self._windows = windows

        current_monitor = self.monitor_combo.currentData()
        current_hwnd = current_monitor.get("name") if isinstance(current_monitor, dict) else None
        self.monitor_combo.clear()
        for monitor in self._monitors:
            label = f"{monitor['name']} — {monitor['width']}x{monitor['height']}"
            if monitor["primary"]:
                label += " (principal)"
            self.monitor_combo.addItem(label, monitor)
        if current_hwnd:
            for i, monitor in enumerate(self._monitors):
                if monitor.get("name") == current_hwnd:
                    self.monitor_combo.setCurrentIndex(i)
                    break

        current_window = self.window_combo.currentData()
        current_title = current_window.get("title") if isinstance(current_window, dict) else None
        self.window_combo.clear()
        for window in self._windows:
            self.window_combo.addItem(
                f"{window['title']}  (PID {window['pid']})", window
            )
        if current_title:
            for i, window in enumerate(self._windows):
                if window.get("hwnd") == current_window.get("hwnd"):
                    self.window_combo.setCurrentIndex(i)
                    break

        self.monitor_combo.setPlaceholderText("Nenhum monitor detectado" if not self._monitors else "Selecione o monitor")
        self.window_combo.setPlaceholderText("Nenhuma janela detectada" if not self._windows else "Selecione a janela")
        self.signals.refresh_finished.emit()

    def _on_refresh_finished(self):
        if not self._monitors:
            self.status_label.setText("NENHUM MONITOR ENCONTRADO")
            self.output_label.setText("Saída: o Windows não retornou nenhum monitor")
        elif not self._windows:
            self.status_label.setText("NENHUMA JANELA ENCONTRADA")
            self.selected_label.setText("Janela: o Windows não retornou nenhuma janela visível")
        elif self.session.state in (CaptureState.STOPPED, CaptureState.FAILED):
            self.status_label.setText("PARADO")

    def _selected_monitor(self):
        return self.monitor_combo.currentData()

    def _selected_window(self):
        return self.window_combo.currentData()

    def start_transmission(self):
        monitor = self._selected_monitor()
        window = self._selected_window()
        if not monitor or not window:
            QMessageBox.warning(self, "Seleção incompleta", "Selecione o monitor e a janela.")
            return

        if self.session.state in (CaptureState.RUNNING, CaptureState.STARTING, CaptureState.SWITCHING, CaptureState.STOPPING):
            self._run_operation("switch", window)
            return

        try:
            self.session.set_monitor(monitor)
        except Exception as exc:
            QMessageBox.critical(self, "Monitor de saída", str(exc))
            return
        self._run_operation("start", window)

    def stop_transmission(self):
        if self.session.state == CaptureState.CLOSED:
            return
        self._run_operation("stop_capture", None)

    def toggle_mouse(self):
        if self.mouse_lock.locked:
            self.mouse_lock.unlock()
        else:
            self.mouse_lock.lock()
        self._update_mouse_ui()

    def _run_operation(self, operation: str, selected):
        """Executa a operação nativa no thread principal do Qt.

        O windows-capture cria sua própria thread em start_free_threaded().
        Manter a criação de WindowsCapture no thread principal restaura o mesmo
        contexto de inicialização usado pela versão que funcionava antes da GUI.
        """
        if self._busy:
            return
        self._busy = True
        self.signals.operation_started.emit(operation)
        try:
            if operation == "start":
                self.session.start(selected)
            elif operation == "switch":
                self.session.switch_window(selected)
            elif operation == "stop_capture":
                self.session.stop_capture()
            self.signals.operation_finished.emit(True, "")
        except Exception as exc:
            logger.exception("Operação %s falhou", operation)
            self.signals.operation_finished.emit(False, str(exc))

    def _on_operation_started(self, operation: str):
        self.status_label.setText({
            "start": "INICIANDO...",
            "switch": "TROCANDO JANELA...",
            "stop_capture": "ENCERRANDO...",
        }.get(operation, "PROCESSANDO..."))
        self.transmit_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.monitor_combo.setEnabled(False)
        self.window_combo.setEnabled(False)

    def _on_operation_finished(self, ok: bool, message: str):
        self._busy = False
        self.monitor_combo.setEnabled(self.session.state != CaptureState.RUNNING)
        self.window_combo.setEnabled(True)
        self.refresh_button.setEnabled(True)

        state = self.session.state
        running = state == CaptureState.RUNNING
        self.transmit_button.setEnabled(True)
        self.stop_button.setEnabled(running)

        if ok and running:
            # Só mostra a saída depois que start_free_threaded() foi concluído.
            # Assim a TV não aparece como uma tela preta durante a inicialização.
            if not self.session.output.isVisible():
                self.session.output.show_output()
            selected = self.session.selected or self._selected_window()
            monitor = self.session.monitor
            self.status_label.setText("TRANSMITINDO")
            self.selected_label.setText(f"Janela: {selected['title'] if selected else '—'}")
            self.output_label.setText(
                f"Saída: {monitor['name']} — {monitor['width']}x{monitor['height']}"
            )
        elif ok:
            self.status_label.setText("PARADO")
            self.selected_label.setText("Janela: —")
            self.output_label.setText("Saída: —")
        else:
            self.status_label.setText("ERRO")
            QMessageBox.critical(self, "Erro", message or "A operação não foi concluída.")

        self._update_mouse_ui()

    def _update_mouse_ui(self):
        if self.mouse_lock.locked:
            self.mouse_status.setText("Mouse: bloqueado no monitor principal")
            self.mouse_button.setText("Liberar mouse")
        else:
            self.mouse_status.setText("Mouse: liberado")
            self.mouse_button.setText("Bloquear mouse")

    def _update_diagnostics(self):
        count = self.session.output.frame_count
        shape = self.session.output.last_shape
        if shape:
            self.frame_label.setText(f"Frames recebidos: {count}  |  Formato: {shape[1]}x{shape[0]}x{shape[2]}")
        else:
            self.frame_label.setText("Frames recebidos: 0  |  aguardando primeiro frame")

    def closeEvent(self, event: QCloseEvent):
        if self._closing:
            event.accept()
            return
        self._closing = True
        self.transmit_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        try:
            self.session.stop()
        except Exception:
            logger.exception("Erro ao encerrar a sessão")
        try:
            self.mouse_lock.release()
        finally:
            event.accept()


def create_gui(session: CaptureSession, mouse_lock: MouseLock) -> MainWindow:
    window = MainWindow(session, mouse_lock)
    window.show()
    return window
