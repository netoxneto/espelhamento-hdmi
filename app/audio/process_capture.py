"""Captura de áudio por processo ainda não habilitada nesta versão inicial.

A captura WASAPI Process Loopback requer integração COM/WinRT nativa específica
do Windows 11. Este módulo existe para deixar explícito o ponto de integração,
sem fingir capturar áudio do processo nem recorrer ao áudio global do sistema.
"""
class ProcessAudioCapture:
    def __init__(self, pid: int):
        self.pid = pid

    def start(self):
        raise NotImplementedError(
            "Captura WASAPI Process Loopback não está implementada nesta versão. "
            "O vídeo pode funcionar, mas o áudio do processo não será transmitido."
        )
