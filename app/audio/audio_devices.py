"""Enumeração básica de endpoints de áudio via Windows (diagnóstico)."""
def list_audio_devices():
    try:
        import sounddevice as sd
        return [f"{i}: {d['name']}" for i, d in enumerate(sd.query_devices())]
    except Exception:
        return ["Não foi possível enumerar dispositivos. Verifique sounddevice/PortAudio."]
