from dataclasses import dataclass
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.json"
DEFAULTS = {"fps": 30, "mouse_lock": True, "fullscreen": True, "keep_aspect_ratio": True}

def load_settings():
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return {**DEFAULTS, **data}
    except (OSError, ValueError):
        return DEFAULTS.copy()
