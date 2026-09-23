from __future__ import annotations

import json
import time
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
        "modo_skin": "ninguna",
        "skins_ultima": {},
        "twitch_habilitado": False,
        "twitch_canal": "",
        "twitch_comando": "!skin",
        "twitch_client_id": "",
        "twitch_access_token": "",
        "twitch_refresh_token": "",
        "twitch_token_expira": 0.0,
        "twitch_login": "",
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
        if not isinstance(base.get("skins_ultima"), dict):
            base["skins_ultima"] = {}
        if base.get("modo_skin") not in ("ninguna", "aleatoria", "siguiente"):
            base["modo_skin"] = "ninguna"
        if not isinstance(base.get("twitch_canal"), str):
            base["twitch_canal"] = ""
        if not isinstance(base.get("twitch_comando"), str) or not base.get("twitch_comando"):
            base["twitch_comando"] = "!skin"
        for clave in ("twitch_client_id", "twitch_access_token", "twitch_refresh_token", "twitch_login"):
            if not isinstance(base.get(clave), str):
                base[clave] = ""
        try:
            base["twitch_token_expira"] = float(base.get("twitch_token_expira") or 0)
        except (TypeError, ValueError):
            base["twitch_token_expira"] = 0.0
        base["twitch_habilitado"] = bool(base.get("twitch_habilitado"))
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

    def modo_skin(self) -> str:
        modo = str(self.datos.get("modo_skin") or "ninguna")
        if modo not in ("ninguna", "aleatoria", "siguiente"):
            return "ninguna"
        return modo

    def set_modo_skin(self, modo: str) -> None:
        modo = (modo or "ninguna").strip().lower()
        if modo not in ("ninguna", "aleatoria", "siguiente"):
            modo = "ninguna"
        with self._lock:
            self.datos["modo_skin"] = modo
        self.guardar()

    def ultima_skin(self, campeon_id: int) -> int | None:
        clave = str(int(campeon_id))
        with self._lock:
            valor = (self.datos.get("skins_ultima") or {}).get(clave)
        if valor is None:
            return None
        try:
            return int(valor)
        except (TypeError, ValueError):
            return None

    def set_ultima_skin(self, campeon_id: int, skin_id: int) -> None:
        clave = str(int(campeon_id))
        with self._lock:
            ultimas = dict(self.datos.get("skins_ultima") or {})
            ultimas[clave] = int(skin_id)
            self.datos["skins_ultima"] = ultimas
        self.guardar()

    def twitch(self) -> dict[str, Any]:
        with self._lock:
            login = str(self.datos.get("twitch_login") or "")
            token = str(self.datos.get("twitch_access_token") or "")
            return {
                "habilitado": bool(self.datos.get("twitch_habilitado")),
                "canal": str(self.datos.get("twitch_canal") or ""),
                "comando": str(self.datos.get("twitch_comando") or "!skin"),
                "client_id": str(self.datos.get("twitch_client_id") or ""),
                "login": login,
                "puede_hablar": bool(login and token),
            }

    def set_twitch(self, habilitado: bool, canal: str, comando: str = "!skin") -> None:
        with self._lock:
            self.datos["twitch_habilitado"] = bool(habilitado)
            self.datos["twitch_canal"] = (canal or "").strip()
            self.datos["twitch_comando"] = (comando or "!skin").strip() or "!skin"
        self.guardar()

    def set_twitch_client_id(self, client_id: str) -> None:
        with self._lock:
            self.datos["twitch_client_id"] = (client_id or "").strip()
        self.guardar()

    def set_twitch_sesion(
        self,
        access_token: str,
        refresh_token: str,
        login: str,
        expires_in: float,
    ) -> None:
        with self._lock:
            self.datos["twitch_access_token"] = (access_token or "").strip()
            if refresh_token:
                self.datos["twitch_refresh_token"] = refresh_token.strip()
            self.datos["twitch_login"] = (login or "").strip().lower()
            self.datos["twitch_token_expira"] = time.time() + max(60.0, float(expires_in or 14400) - 120)
        self.guardar()

    def borrar_twitch_sesion(self) -> None:
        with self._lock:
            self.datos["twitch_access_token"] = ""
            self.datos["twitch_refresh_token"] = ""
            self.datos["twitch_token_expira"] = 0.0
            self.datos["twitch_login"] = ""
        self.guardar()

    def twitch_credenciales(self) -> dict[str, Any]:
        with self._lock:
            return {
                "client_id": str(self.datos.get("twitch_client_id") or ""),
                "access_token": str(self.datos.get("twitch_access_token") or ""),
                "refresh_token": str(self.datos.get("twitch_refresh_token") or ""),
                "expira": float(self.datos.get("twitch_token_expira") or 0),
                "login": str(self.datos.get("twitch_login") or ""),
            }
