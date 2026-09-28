"""Confinamento físico do cursor ao monitor principal usando Win32 ClipCursor.

O watchdog reaplica o clipping periodicamente para que o confinamento não
dependa do foco/minimização do terminal ou de outra janela.
"""
import ctypes
import threading
from ctypes import wintypes

user32 = ctypes.windll.user32

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
WM_HOTKEY = 0x0312
HOTKEY_ID = 0x4844
VK_F12 = 0x7B

class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

class MouseLock:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.locked = False
        self.rect = None
        self._stop = threading.Event()
        self._hotkey_thread = None
        self._watchdog_thread = None
        self._lock = threading.Lock()

    def _primary_rect(self):
        from app.windows.monitor_manager import list_monitors
        primary = next((m for m in list_monitors() if m["primary"]), None)
        if not primary:
            return None
        return RECT(primary["left"], primary["top"],
                    primary["left"] + primary["width"],
                    primary["top"] + primary["height"])

    def activate(self):
        self.rect = self._primary_rect()
        if self.rect is None:
            print("Aviso: monitor principal não encontrado; mouse não foi bloqueado.")
            return
        self._stop.clear()
        self._hotkey_thread = threading.Thread(target=self._hotkey_loop, daemon=True)
        self._watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self._hotkey_thread.start()
        self._watchdog_thread.start()
        if self.enabled:
            self.lock()

    def lock(self):
        with self._lock:
            if self.rect is None:
                self.rect = self._primary_rect()
            if self.rect is None:
                return False
            ok = bool(user32.ClipCursor(ctypes.byref(self.rect)))
            if not ok:
                print("Aviso: ClipCursor não conseguiu confinar o mouse.")
                return False
            self.locked = True
            print("Mouse: BLOQUEADO no monitor principal")
            return True

    def unlock(self):
        with self._lock:
            ok = bool(user32.ClipCursor(None))
            if ok:
                self.locked = False
                print("Mouse: LIBERADO")
            return ok

    def _watchdog_loop(self):
        # Reaplica o clipping continuamente. Isso é deliberado: o objetivo é
        # que minimizar o terminal, mudar o foco ou maximizar outra janela não
        # faça o cursor voltar para o monitor secundário.
        while not self._stop.wait(0.05):
            if not self.locked or self.rect is None:
                continue
            try:
                user32.ClipCursor(ctypes.byref(self.rect))
                # Garantia adicional: se o cursor estiver fora do retângulo
                # por uma alteração de monitor/DPI, trazemos apenas o cursor
                # para a borda válida do monitor principal.
                pt = POINT()
                if user32.GetCursorPos(ctypes.byref(pt)):
                    r = self.rect
                    x = min(max(pt.x, r.left), r.right - 1)
                    y = min(max(pt.y, r.top), r.bottom - 1)
                    if x != pt.x or y != pt.y:
                        user32.SetCursorPos(x, y)
            except Exception:
                pass

    def release(self):
        self._stop.set()
        user32.ClipCursor(None)
        self.locked = False
        try:
            user32.UnregisterHotKey(None, HOTKEY_ID)
        except Exception:
            pass

    def _hotkey_loop(self):
        if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_ALT, VK_F12):
            print("Aviso: não foi possível registrar Ctrl+Alt+F12.")
            return
        msg = wintypes.MSG()
        while not self._stop.is_set():
            result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result <= 0:
                break
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                if self.locked:
                    self.unlock()
                else:
                    self.lock()
        user32.UnregisterHotKey(None, HOTKEY_ID)
