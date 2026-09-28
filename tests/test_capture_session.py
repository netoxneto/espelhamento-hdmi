import sys
import threading
import time
import types
import unittest
from unittest.mock import patch

import numpy as np


# PySide6 não está instalado no ambiente de validação. Estes stubs permitem
# exercitar a máquina de estados/callbacks sem alterar o código de produção.
class _FakeSignal:
    def connect(self, fn):
        self.fn = fn


class _FakeTimer:
    def __init__(self, parent=None):
        self.timeout = _FakeSignal()

    def start(self, _ms):
        pass


class _FakeQt:
    class AlignmentFlag:
        AlignCenter = 1

    class WindowType:
        FramelessWindowHint = 1
        WindowStaysOnTopHint = 2

    class CursorShape:
        BlankCursor = 1

    class AspectRatioMode:
        KeepAspectRatio = 1

    class TransformationMode:
        SmoothTransformation = 1


class _FakeQImage:
    Format = types.SimpleNamespace(Format_RGBA8888=1, Format_RGB888=2)

    def __init__(self, *args):
        pass

    def copy(self):
        return self


class _FakeQPixmap:
    @classmethod
    def fromImage(cls, image):
        return cls()

    def scaled(self, *args):
        return self


class _FakeCursor:
    def __init__(self, *args):
        pass


class _FakeQApplication:
    _instance = None

    def __init__(self, args=None):
        type(self)._instance = self

    @classmethod
    def instance(cls):
        return cls._instance

    def exec(self):
        return 0

    def quit(self):
        pass


class _FakeWidget:
    def __init__(self, *args, **kwargs):
        pass

    def setWindowFlags(self, *args):
        pass

    def setGeometry(self, *args):
        pass

    def setStyleSheet(self, *args):
        pass

    def showFullScreen(self):
        pass

    def close(self):
        pass

    def size(self):
        return (1920, 1080)


class _FakeLabel(_FakeWidget):
    def setAlignment(self, *args):
        pass

    def setCursor(self, *args):
        pass

    def clear(self):
        pass

    def setPixmap(self, *args):
        pass


qtcore = types.ModuleType("PySide6.QtCore")
qtcore.Qt = _FakeQt
qtcore.QTimer = _FakeTimer
qtgui = types.ModuleType("PySide6.QtGui")
qtgui.QImage = _FakeQImage
qtgui.QPixmap = _FakeQPixmap
qtgui.QCursor = _FakeCursor
qtwidgets = types.ModuleType("PySide6.QtWidgets")
qtwidgets.QApplication = _FakeQApplication
qtwidgets.QLabel = _FakeLabel
qtwidgets.QWidget = _FakeWidget
pyside = types.ModuleType("PySide6")
pyside.QtCore = qtcore
pyside.QtGui = qtgui
pyside.QtWidgets = qtwidgets
sys.modules.setdefault("PySide6", pyside)
sys.modules.setdefault("PySide6.QtCore", qtcore)
sys.modules.setdefault("PySide6.QtGui", qtgui)
sys.modules.setdefault("PySide6.QtWidgets", qtwidgets)


class FakeControl:
    def __init__(self, owner):
        self.owner = owner
        self.stopped = False
        self.waited = False

    def stop(self):
        if not self.stopped:
            self.stopped = True
            self.owner.active = False
            FakeCapture.active_count -= 1
            self.owner.on_closed()

    def wait(self):
        self.waited = True


class FakeCapture:
    instances = []
    active_count = 0
    max_active = 0
    factory = None
    start_hook = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.handlers = {}
        self.active = False
        self.control = None
        self.on_closed = lambda: None
        FakeCapture.instances.append(self)

    def event(self, fn):
        self.handlers[fn.__name__] = fn
        if fn.__name__ == "on_closed":
            self.on_closed = fn
        return fn

    def start_free_threaded(self):
        if FakeCapture.factory is not None:
            FakeCapture.factory(self)
        if FakeCapture.start_hook is not None:
            FakeCapture.start_hook(self)
        self.active = True
        FakeCapture.active_count += 1
        FakeCapture.max_active = max(FakeCapture.max_active, FakeCapture.active_count)
        self.control = FakeControl(self)
        if getattr(self, "emit_immediate_frame", False):
            frame = types.SimpleNamespace(frame_buffer=np.zeros((4, 4, 3), dtype=np.uint8))
            self.handlers["on_frame_arrived"](frame, self.control)
        return self.control

    def stop(self):
        if self.control:
            self.control.stop()


fake_wc = types.ModuleType("windows_capture")
fake_wc.WindowsCapture = FakeCapture
sys.modules["windows_capture"] = fake_wc

from app.video.session import CaptureSession, CaptureState


MONITOR = {"left": 0, "top": 0, "width": 1920, "height": 1080}
A = {"hwnd": 101, "title": "Chrome", "pid": 1}
B = {"hwnd": 202, "title": "PowerPoint", "pid": 2}
C = {"hwnd": 303, "title": "VLC", "pid": 3}



def _capture_exception(bucket, fn):
    try:
        fn()
    except Exception as exc:
        bucket.append(exc)


class TestCaptureSession(unittest.TestCase):
    def setUp(self):
        FakeCapture.instances.clear()
        FakeCapture.active_count = 0
        FakeCapture.max_active = 0
        FakeCapture.factory = None
        FakeCapture.start_hook = None
        _FakeQApplication._instance = None

    def make_session(self):
        return CaptureSession(MONITOR, fps=30)

    def test_callback_immediately_after_start_sees_capture_as_current(self):
        session = self.make_session()
        cap = None

        def hook(c):
            c.emit_immediate_frame = True

        FakeCapture.start_hook = hook
        session.start(A)
        cap = FakeCapture.instances[-1]

        self.assertIs(session.capture, cap)
        self.assertIsNotNone(session.capture_control)
        self.assertEqual(session.state, CaptureState.RUNNING)
        self.assertIsNotNone(session.output._frame)
        self.assertEqual(FakeCapture.max_active, 1)
        session.stop()

    def test_old_callback_after_switch_is_ignored(self):
        session = self.make_session()
        session.start(A)
        old = FakeCapture.instances[-1]
        session.switch_window(B)
        new = FakeCapture.instances[-1]
        self.assertIsNot(old, new)
        new.handlers["on_frame_arrived"](
            types.SimpleNamespace(frame_buffer=np.full((4, 4, 3), 3, dtype=np.uint8)),
            new.control,
        )
        before = session.output._frame.copy()

        old.handlers["on_frame_arrived"](
            types.SimpleNamespace(frame_buffer=np.full((4, 4, 3), 7, dtype=np.uint8)),
            old.control,
        )
        self.assertTrue(np.array_equal(session.output._frame, before))
        self.assertIs(session.capture, new)
        self.assertEqual(session.state, CaptureState.RUNNING)

        old.on_closed()
        self.assertIs(session.capture, new)
        self.assertEqual(session.state, CaptureState.RUNNING)
        session.stop()

    def test_start_failure_rolls_back_cleanly(self):
        session = self.make_session()

        def fail(c):
            if c.kwargs.get("window_hwnd") == B["hwnd"]:
                raise RuntimeError("native start failed")

        FakeCapture.factory = fail
        with self.assertRaises(RuntimeError):
            session.start(B)
        self.assertIsNone(session.capture)
        self.assertIsNone(session.capture_control)
        self.assertEqual(session.state, CaptureState.STOPPED)
        self.assertFalse(session._closed)
        session.stop()

    def test_switch_failure_restores_previous_window(self):
        session = self.make_session()
        session.start(A)

        def fail(c):
            if c.kwargs.get("window_hwnd") == B["hwnd"]:
                raise RuntimeError("native start failed")

        FakeCapture.factory = fail
        with self.assertRaises(RuntimeError):
            session.switch_window(B)

        self.assertEqual(session.selected["hwnd"], A["hwnd"])
        self.assertEqual(session.capture.kwargs["window_hwnd"], A["hwnd"])
        self.assertEqual(session.state, CaptureState.RUNNING)
        self.assertEqual(FakeCapture.active_count, 1)
        session.stop()

    def test_two_switches_are_serialized_and_never_overlap(self):
        session = self.make_session()
        session.start(A)
        entered_b = threading.Event()
        release_b = threading.Event()

        def hook(c):
            if c.kwargs.get("window_hwnd") == B["hwnd"]:
                entered_b.set()
                release_b.wait(2)

        FakeCapture.start_hook = hook
        t1 = threading.Thread(target=lambda: session.switch_window(B))
        t1.start()
        self.assertTrue(entered_b.wait(1))

        t2 = threading.Thread(target=lambda: session.switch_window(C))
        t2.start()
        time.sleep(0.1)
        self.assertTrue(t2.is_alive(), "segunda troca deveria aguardar a operação nativa")

        release_b.set()
        t1.join(2)
        t2.join(2)
        self.assertFalse(t1.is_alive())
        self.assertFalse(t2.is_alive())
        self.assertEqual(session.selected["hwnd"], C["hwnd"])
        self.assertEqual(session.state, CaptureState.RUNNING)
        self.assertEqual(FakeCapture.active_count, 1)
        self.assertEqual(FakeCapture.max_active, 1)
        session.stop()


    def test_old_on_closed_cannot_clear_new_capture(self):
        session = self.make_session()
        session.start(A)
        old = FakeCapture.instances[-1]
        session.switch_window(B)
        new = FakeCapture.instances[-1]

        old.on_closed()

        self.assertIs(session.capture, new)
        self.assertEqual(session.selected["hwnd"], B["hwnd"])
        self.assertEqual(session.state, CaptureState.RUNNING)
        session.stop()

    def test_switch_waits_for_stop_and_never_creates_second_capture(self):
        session = self.make_session()
        session.start(A)
        old = FakeCapture.instances[-1]
        entered_wait = threading.Event()
        release_wait = threading.Event()
        original_wait = old.control.wait

        def blocked_wait():
            entered_wait.set()
            release_wait.wait(2)
            original_wait()

        old.control.wait = blocked_wait

        stop_thread = threading.Thread(target=session.stop)
        stop_thread.start()
        self.assertTrue(entered_wait.wait(1))

        switch_result = []
        switch_thread = threading.Thread(
            target=lambda: _capture_exception(
                switch_result, lambda: session.switch_window(B)
            )
        )
        switch_thread.start()
        time.sleep(0.1)
        self.assertTrue(switch_thread.is_alive())

        release_wait.set()
        stop_thread.join(2)
        switch_thread.join(2)

        self.assertFalse(stop_thread.is_alive())
        self.assertFalse(switch_thread.is_alive())
        self.assertEqual(session.state, CaptureState.CLOSED)
        self.assertEqual(FakeCapture.active_count, 0)
        self.assertEqual(FakeCapture.max_active, 1)
        self.assertTrue(switch_result and isinstance(switch_result[0], RuntimeError))

    def test_stop_is_idempotent(self):
        session = self.make_session()
        session.start(A)
        session.stop()
        session.stop()
        session.stop()
        self.assertEqual(session.state, CaptureState.CLOSED)
        self.assertEqual(FakeCapture.active_count, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
