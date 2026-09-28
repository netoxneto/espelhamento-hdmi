from __future__ import annotations

import sys
import threading

from app.windows.monitor_manager import list_monitors
from app.windows.window_manager import list_windows
from app.video.session import CaptureSession
from app.input.mouse_lock import MouseLock


def choose(items, prompt):
    if not items:
        print("Nenhum item encontrado.")
        return None
    while True:
        raw = input(prompt).strip()
        if raw.lower() in {"q", "sair", "0"}:
            return None
        try:
            n = int(raw)
            if 1 <= n <= len(items):
                return items[n - 1]
        except ValueError:
            pass
        print("Opção inválida. Digite um número da lista ou Q para sair.")


def print_windows():
    windows = list_windows()
    print("\nJanelas disponíveis:")
    for i, w in enumerate(windows, 1):
        print(f"[{i}] {w['title']}  (PID {w['pid']})")
    return windows


def command_loop(session):
    """Console de controle paralelo à janela Qt."""
    while True:
        try:
            raw = input(
                "\nComandos: [T] trocar janela  [L] mouse bloqueado/liberado  [Q] encerrar\n> "
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            session.app.quit()
            return

        if raw in {"q", "sair", "0"}:
            session.app.quit()
            return

        if raw in {"l", "mouse"}:
            if session.mouse_lock.locked:
                session.mouse_lock.unlock()
            else:
                session.mouse_lock.lock()
            continue

        if raw in {"t", "trocar", "troca"}:
            windows = print_windows()
            selected = choose(windows, "\nDigite o número da nova janela: ")
            if selected:
                session.switch(selected)
            continue

        print("Comando inválido. Use T, L ou Q.")


def main():
    if sys.platform != "win32":
        print("Este aplicativo foi desenvolvido exclusivamente para Windows 11.")
        input("Pressione ENTER para sair.")
        return 2

    print("=" * 52)
    print("              ESPELHAMENTO HDMI")
    print("=" * 52)

    monitors = list_monitors()
    print("\nMonitores encontrados:")
    for i, m in enumerate(monitors, 1):
        print(
            f"[{i}] {m['name']} — {m['width']}x{m['height']} "
            f"({m['left']},{m['top']})"
            f"{' [principal]' if m['primary'] else ''}"
        )
    monitor = choose(monitors, "\nDigite o número da TV/monitor de saída: ")
    if not monitor:
        return 0

    windows = print_windows()
    selected = choose(windows, "\nDigite o número da janela a transmitir: ")
    if not selected:
        return 0

    print(f"\nJanela selecionada: {selected['title']}")
    print(f"Saída: {monitor['name']}")
    print("Status: INICIALIZANDO")

    mouse_lock = MouseLock(enabled=True)
    session = CaptureSession(monitor, mouse_lock=mouse_lock, fps=30)
    try:
        session.start(selected)
        print("Status: TRANSMITINDO")
        print("A saída permanece aberta enquanto você troca a janela pelo comando T.")
        print("O mouse fica fisicamente confinado ao monitor principal por ClipCursor.")
        print("Ctrl+Alt+F12 também alterna o bloqueio do mouse.")

        controller = threading.Thread(target=command_loop, args=(session,), daemon=True)
        controller.start()
        session.run()
    except KeyboardInterrupt:
        print("\nEncerrando transmissão...")
    except Exception as exc:
        print(f"\nERRO: {exc}")
        input("Pressione ENTER para sair.")
        return 1
    finally:
        mouse_lock.release()
        session.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
