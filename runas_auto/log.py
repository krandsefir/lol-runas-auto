from __future__ import annotations

import traceback
from datetime import datetime
from pathlib import Path

from runas_auto.rutas import congelado, dir_datos, dir_instalacion


def rutas_log() -> list[Path]:
    rutas = [dir_datos() / "error.log"]
    if congelado():
        rutas.append(dir_instalacion() / "error.log")
    return rutas


def registrar(texto: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    bloque = f"[{stamp}] {texto}\n"
    for ruta in rutas_log():
        try:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            with ruta.open("a", encoding="utf-8") as f:
                f.write(bloque)
        except OSError:
            continue


def registrar_excepcion(exc: BaseException | None = None) -> str:
    if exc is None:
        texto = traceback.format_exc()
    else:
        texto = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    registrar(texto)
    return texto
