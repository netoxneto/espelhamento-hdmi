"""Sessão de vídeo com troca segura de captura Windows Graphics Capture."""
from __future__ import annotations

from enum import Enum, auto
import logging
import threading

import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QCursor
from PySide6.QtWidgets import QApplication, QWidget


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
    """Janela de saída dedicada; o frame é desenhado diretamente pelo Qt."""

    def __init__(self, monitor, fps=30):
        super().__init__()
        self.monitor = monitor
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        if hasattr(self, "setAttribute"):
            self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
            self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        if hasattr(self, "setCursor"):
            self.setCursor(QCursor(Qt.CursorShape.BlankCursor))
        self._source_hwnd = None
        self._frame = None
        self._image = QImage()
        self._lock = threading.Lock()
        self._frame_count = 0
        self._last_shape = None
        self.setStyleSheet("background: black;")
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(max(1, int(1000 / fps)))
        self._apply_monitor_geometry()

    def _find_target_screen(self):
        screens_fn = getattr(QApplication, "screens", None)
        if not callable(screens_fn):
            return None
        screens = screens_fn()
        target_name = self.monitor.get("name")
        if target_name:
            for screen in screens:
                if screen.name() == target_name:
                    return screen

        target_rect = (
            int(self.monitor["left"]), int(self.monitor["top"]),
            int(self.monitor["width"]), int(self.monitor["height"]),
        )
        for screen in screens:
            g = screen.geometry()
            if (g.x(), g.y(), g.width(), g.height()) == target_rect:
                return screen
        return None

    def _apply_monitor_geometry(self):
        screen = self._find_target_screen()
        if screen is not None:
            g = screen.geometry()
            self.setGeometry(g)
        else:
            self.setGeometry(
                int(self.monitor["left"]), int(self.monitor["top"]),
                int(self.monitor["width"]), int(self.monitor["height"]),
            )

    def set_source_window(self, selected):
        self._source_hwnd = int(selected.get("hwnd")) if selected and selected.get("hwnd") else None

    def set_frame(self, frame):
        with self._lock:
            self._frame = frame.copy()
            self._frame_count += 1
            self._last_shape = tuple(self._frame.shape)

    @property
    def frame_count(self):
        with self._lock:
            return self._frame_count

    @property
    def last_shape(self):
        with self._lock:
            return self._last_shape

    def clear(self):
        with self._lock:
            self._frame = None
            self._image = QImage()
        self.update()

    def show_output(self):
        screen = self._find_target_screen()
        # O QWindow precisa existir para setScreen(); mostrar como janela normal
        # primeiro garante que o native window seja criado no Windows.
        if not self.isVisible():
            self.show()
        handle = self.windowHandle()
        if handle is not None and screen is not None:
            handle.setScreen(screen)
            g = screen.geometry()
            self.setGeometry(g)
        else:
            self._apply_monitor_geometry()
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self.update()

    def hide_output(self):
        self.hide()

    def refresh(self):
        with self._lock:
            frame = None if self._frame is None else self._frame.copy()
        if frame is None:
            return

        h, w = frame.shape[:2]
        if frame.ndim != 3 or frame.shape[2] not in (3, 4):
            return

        # windows-capture entrega BGRA/BGR. A saída é armazenada como RGB sem
        # alpha para que nenhuma composição/transparência do Qt possa apagar o frame.
        if frame.shape[2] == 4:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
        else:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = QImage(
            rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888
        ).copy()
        with self._lock:
            self._image = image
        self.update()

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)
        with self._lock:
            image = self._image.copy() if not self._image.isNull() else QImage()
        if not image.isNull():
            scaled = image.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawImage(x, y, scaled)
        self._paint_source_cursor(painter, image, scaled, x, y)
        painter.end()

    def _paint_source_cursor(self, painter, image, scaled, x, y):
        """Desenha um cursor somente quando o mouse está sobre a janela capturada.

        O cursor não é mais embutido pelo Windows Graphics Capture. Assim,
        mover o mouse pelo desktop/GUI não faz o ponteiro aparecer na TV.
        """
        hwnd = self._source_hwnd
        if not hwnd:
            return
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32

            class POINT(ctypes.Structure):
                _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]
            class RECT(ctypes.Structure):
                _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                            ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

            pt = POINT()
            rect = RECT()

            # A posição do mouse sozinha não determina se ele pertence à
            # janela transmitida. Ex.: o Word continua sendo capturado
            # enquanto o usuário opera o Chrome. Nesse caso o ponteiro do
            # Chrome NÃO deve ser desenhado sobre o frame do Word.
            foreground = user32.GetForegroundWindow()
            if not foreground:
                return

            # Normaliza para a janela raiz para funcionar também quando o
            # foco estiver em um controle/filho dentro do aplicativo.
            GA_ROOT = 2
            foreground_root = user32.GetAncestor(foreground, GA_ROOT)
            source_root = user32.GetAncestor(hwnd, GA_ROOT)
            if foreground_root and source_root and foreground_root != source_root:
                return

            if not user32.GetCursorPos(ctypes.byref(pt)):
                return
            if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return

            ww = rect.right - rect.left
            wh = rect.bottom - rect.top
            if ww <= 0 or wh <= 0:
                return
            if not (rect.left <= pt.x < rect.right and rect.top <= pt.y < rect.bottom):
                return

            # A imagem mantém a proporção da captura. Mapeamos a posição do
            # cursor da janela-fonte para o retângulo efetivamente desenhado.
            sx = (pt.x - rect.left) / ww
            sy = (pt.y - rect.top) / wh
            cx = x + sx * scaled.width()
            cy = y + sy * scaled.height()

            from PySide6.QtCore import QPointF
            from PySide6.QtGui import QPolygonF, QPen, QBrush
            points = [
                QPointF(cx, cy),
                QPointF(cx, cy + 24),
                QPointF(cx + 6, cy + 18),
                QPointF(cx + 12, cy + 30),
                QPointF(cx + 17, cy + 28),
                QPointF(cx + 11, cy + 16),
                QPointF(cx + 20, cy + 16),
            ]
            painter.setPen(QPen(Qt.GlobalColor.black, 2))
            painter.setBrush(QBrush(Qt.GlobalColor.white))
            painter.drawPolygon(QPolygonF(points))
        except Exception:
            # Cursor é apenas um complemento visual; falhar aqui nunca pode
            # interromper a apresentação dos frames.
            return


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
            # O cursor é desenhado pela FullscreenOutput somente quando o
            # ponteiro está dentro da janela capturada. Isso evita que o
            # ponteiro do desktop apareça na TV quando o usuário estiver
            # operando fora da janela transmitida.
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
        self.output.set_source_window(selected)

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

    def set_monitor(self, monitor):
        """Move the output window to a new monitor while stopped."""
        with self._operation_lock:
            with self._state_lock:
                if self._closed:
                    raise RuntimeError("A sessão já foi encerrada.")
                if self._state not in (CaptureState.STOPPED, CaptureState.FAILED):
                    raise RuntimeError("Pare a transmissão antes de trocar o monitor de saída.")
                self.monitor = monitor
                old_output = self.output
                self.output = FullscreenOutput(monitor, fps=self.fps)
            try:
                old_output.close()
            except Exception:
                pass

    def stop_capture(self):
        """Para a captura atual, mas mantém a sessão disponível para novo start."""
        with self._operation_lock:
            with self._state_lock:
                if self._closed:
                    return
                self._generation += 1
                self._state = CaptureState.STOPPING
                capture = self.capture
                control = self.capture_control
                self.capture = None
                self.capture_control = None
                self.selected = None

            self._stop_capture(capture, control)
            self.output.clear()
            self.output.hide_output()
            with self._state_lock:
                if not self._closed:
                    self._state = CaptureState.STOPPED

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
        self.output.show_output()
        if self.mouse_lock:
            self.mouse_lock.activate()
        self.app.exec()
        self.stop()
