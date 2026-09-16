from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

from runas_auto.rutas import ruta_campeones_cache, ruta_config

DATOS = ruta_config().parent
ARCHIVO_CONFIG = ruta_config()
ARCHIVO_CAMPEONES = ruta_campeones_cache()


def _vacio() -> dict[str, Any]:
    return {
        "ruta_lockfile": None,
        "intervalo_segundos": 1.0,
        "iniciar_con_windows": True,
        "mapeos": [],
    }


class Configuracion:
    def __init__(self, ruta: Path | None = None) -> None:
        self.ruta = ruta or ARCHIVO_CONFIG
        self._lock = Lock()
        DATOS.mkdir(parents=True, exist_ok=True)
        self.datos = self._cargar()

    def _cargar(self) -> dict[str, Any]:
        if not self.ruta.exists():
            return _vacio()
        try:
            with self.ruta.open(encoding="utf-8") as f:
                datos = json.load(f)
        except (OSError, json.JSONDecodeError):
            return _vacio()
        base = _vacio()
        base.update(datos)
        if not isinstance(base.get("mapeos"), list):
            base["mapeos"] = []
        return base

    def guardar(self) -> None:
        with self._lock:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.ruta.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(self.datos, f, ensure_ascii=False, indent=2)
            tmp.replace(self.ruta)

    def mapeos(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self.datos.get("mapeos", [])]

    def upsert_mapeo(self, mapeo: dict[str, Any]) -> dict[str, Any]:
        campeon_id = int(mapeo["campeon_id"])
        with self._lock:
            actuales = [
                item
                for item in self.datos.get("mapeos", [])
                if int(item.get("campeon_id", -1)) != campeon_id
            ]
            actuales.append(mapeo)
            actuales.sort(key=lambda item: str(item.get("campeon_nombre", "")).lower())
            self.datos["mapeos"] = actuales
        self.guardar()
        return dict(mapeo)

    def quitar_mapeo(self, campeon_id: int) -> bool:
        campeon_id = int(campeon_id)
        with self._lock:
            antes = self.datos.get("mapeos", [])
            despues = [item for item in antes if int(item.get("campeon_id", -1)) != campeon_id]
            if len(despues) == len(antes):
                return False
            self.datos["mapeos"] = despues
        self.guardar()
        return True

    def mapeo_de(self, campeon_id: int) -> dict[str, Any] | None:
        campeon_id = int(campeon_id)
        for item in self.mapeos():
            if int(item.get("campeon_id", -1)) == campeon_id:
                return item
        return None

    def iniciar_con_windows(self) -> bool:
        return bool(self.datos.get("iniciar_con_windows", True))

    def set_iniciar_con_windows(self, activo: bool) -> None:
        with self._lock:
            self.datos["iniciar_con_windows"] = bool(activo)
        self.guardar()
