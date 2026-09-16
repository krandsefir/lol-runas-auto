from __future__ import annotations

import json
import unicodedata
from typing import Any

import requests

from runas_auto.config import ARCHIVO_CAMPEONES
from runas_auto.lcu import ClienteLCU, ClienteNoDisponible


def _sin_acentos(texto: str) -> str:
    nfd = unicodedata.normalize("NFD", texto)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").lower()


class CatalogoCampeones:
    def __init__(self, cliente: ClienteLCU) -> None:
        self.cliente = cliente
        self._campeones: list[dict[str, Any]] = []

    def cargar(self) -> list[dict[str, Any]]:
        campeones = self._desde_lcu() or self._desde_ddragon() or self._desde_cache()
        self._campeones = sorted(campeones, key=lambda c: c["nombre"].lower())
        if self._campeones:
            self._guardar_cache(self._campeones)
        return self._campeones

    def todos(self) -> list[dict[str, Any]]:
        if not self._campeones:
            self.cargar()
        return list(self._campeones)

    def buscar(self, texto: str) -> list[dict[str, Any]]:
        campeones = self.todos()
        consulta = _sin_acentos(texto or "").strip()
        if not consulta:
            return campeones
        return [
            campeon
            for campeon in campeones
            if consulta in _sin_acentos(campeon["nombre"])
            or consulta in _sin_acentos(campeon.get("alias", ""))
        ]

    def por_id(self, campeon_id: int) -> dict[str, Any] | None:
        campeon_id = int(campeon_id)
        for campeon in self._campeones:
            if campeon["id"] == campeon_id:
                return campeon
        return None

    def _desde_lcu(self) -> list[dict[str, Any]]:
        try:
            datos = self.cliente.get("/lol-game-data/assets/v1/champion-summary.json")
        except ClienteNoDisponible:
            return []
        if not isinstance(datos, list):
            return []
        resultado: list[dict[str, Any]] = []
        for item in datos:
            campeon_id = int(item.get("id") or 0)
            if campeon_id <= 0:
                continue
            alias = str(item.get("alias") or item.get("name") or "")
            resultado.append(
                {
                    "id": campeon_id,
                    "nombre": str(item.get("name") or alias),
                    "alias": alias,
                    "icono": self._icono(campeon_id),
                }
            )
        return resultado

    def _desde_ddragon(self) -> list[dict[str, Any]]:
        try:
            versiones = requests.get(
                "https://ddragon.leagueoflegends.com/api/versions.json",
                timeout=8,
            )
            versiones.raise_for_status()
            version = versiones.json()[0]
            respuesta = requests.get(
                f"https://ddragon.leagueoflegends.com/cdn/{version}/data/es_MX/champion.json",
                timeout=12,
            )
            respuesta.raise_for_status()
            datos = respuesta.json().get("data", {})
        except (requests.RequestException, ValueError, IndexError, KeyError):
            return []
        resultado: list[dict[str, Any]] = []
        for alias, item in datos.items():
            campeon_id = int(item["key"])
            resultado.append(
                {
                    "id": campeon_id,
                    "nombre": str(item.get("name") or alias),
                    "alias": alias,
                    "icono": self._icono(campeon_id),
                }
            )
        return resultado

    def _desde_cache(self) -> list[dict[str, Any]]:
        if not ARCHIVO_CAMPEONES.exists():
            return []
        try:
            with ARCHIVO_CAMPEONES.open(encoding="utf-8") as f:
                datos = json.load(f)
        except (OSError, json.JSONDecodeError):
            return []
        if isinstance(datos, list):
            return datos
        return []

    def _guardar_cache(self, campeones: list[dict[str, Any]]) -> None:
        try:
            ARCHIVO_CAMPEONES.parent.mkdir(parents=True, exist_ok=True)
            with ARCHIVO_CAMPEONES.open("w", encoding="utf-8") as f:
                json.dump(campeones, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    @staticmethod
    def _icono(campeon_id: int) -> str:
        return f"https://cdn.communitydragon.org/latest/champion/{campeon_id}/square"
