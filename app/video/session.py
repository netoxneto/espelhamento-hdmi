"""Sessão de vídeo com troca segura de captura Windows Graphics Capture."""
from __future__ import annotations

from enum import Enum, auto
import logging
import threading

import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap, QCursor
from PySide6.QtWidgets import QApplication, QLabel, QWidget


logger = logging.getLogger(__name__)


class CaptureState(Enum):
    STOPPED = auto()
    STARTING = auto()
    RUNNING = auto()
    SWITCHING = auto()
    STOPPING = auto()
    FAILED = auto()
    CLOSED = auto()


class FullscreenOutput(QWidget):
    def __init__(self, monitor, fps=30):
        super().__init__()
        self.monitor = monitor
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("background: black;")
        self.label.setCursor(QCursor(Qt.CursorShape.BlankCursor))
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setGeometry(monitor["left"], monitor["top"], monitor["width"], monitor["height"])
        self.label.setGeometry(0, 0, monitor["width"], monitor["height"])
        self.setStyleSheet("background: black;")
        self.showFullScreen()
        self._frame = None
        self._lock = threading.Lock()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(max(1, int(1000 / fps)))

    def set_frame(self, frame):
        with self._lock:
            self._frame = frame.copy()

    def clear(self):
        with self._lock:
            self._frame = None
        self.label.clear()

    def refresh(self):
        with self._lock:
            frame = None if self._frame is None else self._frame.copy()
        if frame is None:
            return
        h, w = frame.shape[:2]
        if frame.shape[2] == 4:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGBA)
            fmt = QImage.Format.Format_RGBA8888
        else:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            fmt = QImage.Format.Format_RGB888
        image = QImage(rgb.data, w, h, rgb.strides[0], fmt).copy()
        pix = QPixmap.fromImage(image).scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.label.setPixmap(pix)


class CaptureSession:
    """Mantém a saída Qt e serializa toda a vida útil da captura nativa."""

    def __init__(self, monitor, mouse_lock=None, fps=30):
        self.monitor = monitor
        self.mouse_lock = mouse_lock
        self.fps = fps
        self.app = QApplication.instance() or QApplication([])
        self.output = FullscreenOutput(monitor, fps=fps)

        self.capture = None
        self.capture_control = None
        self.selected = None

        # _state_lock protege somente o estado compartilhado. Nunca fazemos
        # stop()/wait()/start_free_threaded() enquanto ele estiver adquirido.
        self._state_lock = threading.RLock()
        # Uma única operação nativa por vez: start, switch e stop são serializados.
        self._operation_lock = threading.Lock()

        self._state = CaptureState.STOPPED
        self._closed = False
        self._generation = 0

    @property
    def state(self):
        with self._state_lock:
            return self._state

    @property
    def generation(self):
        with self._state_lock:
            return self._generation

    def _make_capture(self, selected, generation):
        try:
            from windows_capture import WindowsCapture
        except ImportError as exc:
            raise RuntimeError("Biblioteca windows-capture ausente. Execute install.bat.") from exc

        kwargs = {
            "cursor_capture": False,
            "draw_border": False,
        }
        if selected.get("hwnd"):
            kwargs["window_hwnd"] = int(selected["hwnd"])
        else:
            kwargs["window_name"] = selected["title"]

        capture = WindowsCapture(**kwargs)

        @capture.event
        def on_frame_arrived(frame, capture_control):
            # O callback pode ocorrer imediatamente dentro de
            # start_free_threaded(). Por isso a captura já foi registrada em
            # self.capture antes do start ser chamado.
            try:
                with self._state_lock:
                    current = (
                        not self._closed
                        and self.capture is capture
                        and self._generation == generation
                        and self._state in (CaptureState.STARTING, CaptureState.RUNNING)
                    )
                if not current:
                    # Callback atrasado de uma geração antiga. Não toca no
                    # estado, no frame nem no controle da sessão atual.
                    return

                data = getattr(frame, "frame_buffer", None)
                if data is None:
                    raise RuntimeError(
                        "A versão instalada de windows-capture não expõe frame.frame_buffer."
                    )
                arr = np.asarray(data)
                if arr.ndim != 3 or arr.shape[2] not in (3, 4):
                    raise RuntimeError(f"Formato de frame não suportado: {arr.shape}")

                with self._state_lock:
                    still_current = (
                        not self._closed
                        and self.capture is capture
                        and self._generation == generation
                        and self._state in (CaptureState.STARTING, CaptureState.RUNNING)
                    )
                    if still_current:
                        self.output.set_frame(arr)
            except Exception as exc:
                with self._state_lock:
                    current = (
                        not self._closed
                        and self.capture is capture
                        and self._generation == generation
                        and self._state in (CaptureState.STARTING, CaptureState.RUNNING)
                    )
                if not current:
                    return
                logger.error("Erro na captura de %r: %s", selected["title"], exc)
                with self._state_lock:
                    if self.capture is capture and self._generation == generation:
                        self._generation += 1
                        self.capture = None
                        self.capture_control = None
                        self.selected = None
                        self._state = CaptureState.FAILED
                # O stop é feito fora do lock para não bloquear callbacks.
                try:
                    capture_control.stop()
                except Exception:
                    pass

        @capture.event
        def on_closed():
            with self._state_lock:
                current = (
                    self.capture is capture
                    and self._generation == generation
                    and not self._closed
                )
                if not current:
                    return

                self.capture = None
                self.capture_control = None
                self.selected = None
                self._state = CaptureState.FAILED

            logger.warning("A janela selecionada foi encerrada: %s", selected["title"])

        return capture

    def _stop_capture(self, capture, control):
        """Stop idempotente; nenhuma chamada é feita sob _state_lock."""
        if control is not None:
            try:
                control.stop()
            except Exception as exc:
                logger.warning("Aviso ao parar captura: %s", exc)
            try:
                control.wait()
            except Exception:
                pass
            return

        if capture is not None:
            # Compatibilidade somente com versões antigas da biblioteca.
            stop = getattr(capture, "stop", None)
            if callable(stop):
                try:
                    stop()
                except Exception as exc:
                    logger.warning("Aviso ao parar captura: %s", exc)

    def _rollback_failed_start(self, capture, generation, previous_selected, previous_state):
        # Invalidamos esta geração antes de limpar recursos. Um callback tardio
        # não poderá alterar a sessão nem parar uma captura posterior.
        with self._state_lock:
            if self.capture is capture and self._generation == generation:
                self._generation += 1
                self.capture = None
                self.capture_control = None
                self.selected = None
                self._state = CaptureState.FAILED if previous_state != CaptureState.STOPPED else CaptureState.STOPPED

        stop = getattr(capture, "stop", None)
        if callable(stop):
            try:
                stop()
            except Exception:
                pass

        # Melhor esforço para restaurar a seleção anterior quando havia uma.
        # A seleção é recolocada antes do helper para que o rollback também
        # passe pelo mesmo caminho serializado, sem uma segunda implementação.
        if previous_selected is not None:
            try:
                with self._state_lock:
                    if self._closed:
                        return
                    self.selected = previous_selected
                    self._state = CaptureState.FAILED
                logger.warning("A nova captura falhou; tentando restaurar a janela anterior...")
                self._start_selected_serialized(previous_selected)
                return
            except Exception as rollback_exc:
                logger.error("Falha ao restaurar a janela anterior: %s", rollback_exc)

    def _start_selected_serialized(self, selected):
        previous_selected = None
        previous_state = CaptureState.STOPPED

        with self._state_lock:
            if self._closed:
                raise RuntimeError("A sessão já foi encerrada.")
            previous_selected = self.selected
            previous_state = self._state
            old_capture = self.capture
            old_control = self.capture_control

            # Invalida imediatamente callbacks da captura antiga.
            self._generation += 1
            self._state = CaptureState.SWITCHING if old_capture is not None else CaptureState.STOPPED
            if old_capture is not None:
                # STOPPING é um estado transitório interno da operação de troca.
                self._state = CaptureState.STOPPING
            self.capture = None
            self.capture_control = None
            self.selected = None

        # Nenhum lock de estado é mantido durante stop/wait.
        self._stop_capture(old_capture, old_control)

        # Registra a nova captura antes do start, eliminando a race do callback.
        with self._state_lock:
            if self._closed:
                self._state = CaptureState.CLOSED
                raise RuntimeError("A sessão foi encerrada durante a troca.")
            self._generation += 1
            generation = self._generation
            self._state = CaptureState.STARTING

        new_capture = self._make_capture(selected, generation)
        with self._state_lock:
            if self._closed or generation != self._generation:
                raise RuntimeError("A sessão mudou durante a preparação da captura.")
            self.capture = new_capture
            self.capture_control = None
            self.selected = selected

        try:
            new_control = new_capture.start_free_threaded()
        except Exception as exc:
            self._rollback_failed_start(
                new_capture,
                generation,
                previous_selected,
                previous_state,
            )
            raise RuntimeError(f"Falha ao iniciar captura de '{selected['title']}': {exc}") from exc

        with self._state_lock:
            # Um shutdown/troca não pode ser sobrescrito pelo retorno tardio.
            if self._closed or self.capture is not new_capture or self._generation != generation:
                stale = True
            else:
                stale = False
                self.capture_control = new_control
                self._state = CaptureState.RUNNING

        if stale:
            self._stop_capture(new_capture, new_control)
            return

        print(f"\nTransmitindo agora: {selected['title']} (PID {selected['pid']})")

    def start(self, selected):
        if not selected:
            return
        with self._operation_lock:
            self._start_selected_serialized(selected)

    def switch_window(self, selected):
        """Troca centralizada e serializada da janela transmitida."""
        if not selected:
            return
        with self._operation_lock:
            with self._state_lock:
                if self._closed:
                    raise RuntimeError("A sessão já foi encerrada.")
                current = self.selected
            if current and current.get("hwnd") == selected.get("hwnd"):
                return
            print(f"\nTrocando para: {selected['title']}...")
            self._start_selected_serialized(selected)
            print("Troca concluída.")

    def switch(self, selected):
        try:
            self.switch_window(selected)
        except Exception as exc:
            print(f"\nNão foi possível trocar a janela: {exc}")

    def stop(self):
        # Shutdown também participa da mesma serialização para nunca competir
        # com start/switch.
        with self._operation_lock:
            with self._state_lock:
                if self._closed:
                    self.output.close()
                    return
                self._closed = True
                self._generation += 1
                self._state = CaptureState.STOPPING
                capture = self.capture
                control = self.capture_control
                self.capture = None
                self.capture_control = None
                self.selected = None

            self._stop_capture(capture, control)

            with self._state_lock:
                self._state = CaptureState.CLOSED
            self.output.close()

    def run(self):
        if self.mouse_lock:
            self.mouse_lock.activate()
        self.app.exec()
        self.stop()
