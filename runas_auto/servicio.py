from __future__ import annotations

from collections.abc import Callable
from typing import Any

from runas_auto.campeones import CatalogoCampeones
from runas_auto.config import Configuracion
from runas_auto.lcu import ClienteLCU, ClienteNoDisponible
from runas_auto.runas import listar_paginas, pagina_actual, resolver_pagina
from runas_auto.vigilancia import Vigilante


class ServicioRunas:
    """API para la GUI: buscar campeón, elegir página y ver lo ya configurado."""

    def __init__(self) -> None:
        self.config = Configuracion()
        self.cliente = ClienteLCU(self.config.datos.get("ruta_lockfile"))
        self.catalogo = CatalogoCampeones(self.cliente)
        self.vigilante = Vigilante(self.cliente, self.config, self.catalogo)

    def estado(self) -> dict[str, Any]:
        conectado = self.cliente.conectado()
        invocador = None
        pagina = None
        if conectado:
            try:
                datos = self.cliente.get("/lol-summoner/v1/current-summoner")
                if isinstance(datos, dict):
                    invocador = datos.get("displayName") or datos.get("gameName")
                pagina = pagina_actual(self.cliente)
            except ClienteNoDisponible:
                conectado = False
        return {
            "conectado": conectado,
            "invocador": invocador,
            "pagina_actual": pagina,
            "vigilando": self.vigilante.activo,
            "configurados": len(self.config.mapeos()),
        }

    def buscar_campeones(self, texto: str = "") -> list[dict[str, Any]]:
        return self.catalogo.buscar(texto)

    def paginas_runas(self) -> list[dict[str, Any]]:
        return listar_paginas(self.cliente)

    def configurados(self) -> list[dict[str, Any]]:
        """Lista campeón → página ya guardada, lista para pintar en la GUI."""
        catalogo = {c["id"]: c for c in self.catalogo._campeones}
        resultado: list[dict[str, Any]] = []
        for mapeo in self.config.mapeos():
            campeon = catalogo.get(int(mapeo["campeon_id"]))
            item = dict(mapeo)
            if campeon:
                item["campeon_nombre"] = campeon["nombre"]
                item["icono"] = campeon.get("icono")
            resultado.append(item)
        return resultado

    def asignar(
        self,
        campeon_id: int,
        pagina_id: int | None = None,
        pagina_nombre: str | None = None,
    ) -> dict[str, Any]:
        """Guarda qué página usar cuando elijas ese campeón."""
        campeon = self.catalogo.por_id(int(campeon_id))
        if campeon is None:
            raise ValueError(f"No conozco el campeón {campeon_id}.")

        pagina = None
        try:
            pagina = resolver_pagina(self.cliente, pagina_id, pagina_nombre)
        except ClienteNoDisponible:
            pagina = None

        if pagina is None and pagina_id is None and not pagina_nombre:
            raise ValueError("Elige una página de runas.")
        if pagina is None and pagina_id is None:
            raise ClienteNoDisponible(
                "Abre el cliente de LoL para elegir la página por nombre, "
                "o pasa el pagina_id."
            )

        mapeo = {
            "campeon_id": campeon["id"],
            "campeon_nombre": campeon["nombre"],
            "pagina_id": pagina["id"] if pagina else int(pagina_id or 0),
            "pagina_nombre": (pagina["nombre"] if pagina else pagina_nombre) or "",
        }
        return self.config.upsert_mapeo(mapeo)

    def quitar(self, campeon_id: int) -> bool:
        return self.config.quitar_mapeo(int(campeon_id))

    def iniciar(self, al_evento: Callable[[dict[str, Any]], None] | None = None) -> None:
        """Arranca la vigilancia de champ select en segundo plano."""
        self.vigilante.iniciar(al_evento)

    def detener(self) -> None:
        self.vigilante.detener()
