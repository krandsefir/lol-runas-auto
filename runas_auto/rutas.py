from __future__ import annotations

import sys
from pathlib import Path

NOMBRE_APP = "LoLRunasAuto"


def congelado() -> bool:
    return bool(getattr(sys, "frozen", False))


def dir_recursos() -> Path:
    if congelado():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def dir_datos() -> Path:
    if congelado():
        base = Path.home() / "AppData" / "Roaming" / NOMBRE_APP
    else:
        base = Path(__file__).resolve().parent.parent / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base


def dir_instalacion() -> Path:
    return Path.home() / "AppData" / "Local" / NOMBRE_APP


def ruta_icono() -> Path:
    return dir_recursos() / "assets" / "icon.ico"


def ruta_config() -> Path:
    return dir_datos() / "config.json"


def ruta_campeones_cache() -> Path:
    return dir_datos() / "campeones_cache.json"


def ruta_ejecutable() -> Path:
    if congelado():
        return Path(sys.executable)
    return Path(__file__).resolve().parent.parent / "main.py"
