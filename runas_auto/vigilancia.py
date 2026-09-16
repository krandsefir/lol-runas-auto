from __future__ import annotations

import time
from collections.abc import Callable
from threading import Event, Thread
from typing import Any

from runas_auto.campeones import CatalogoCampeones
from runas_auto.config import Configuracion
from runas_auto.lcu import ClienteLCU, ClienteNoDisponible
from runas_auto.runas import activar_pagina, resolver_pagina

EventoCallback = Callable[[dict[str, Any]], None]


class Vigilante:
    """Mira champ select y activa la página configurada para ese campeón."""

    def __init__(
        self,
        cliente: ClienteLCU,
        config: Configuracion,
        catalogo: CatalogoCampeones,
    ) -> None:
        self.cliente = cliente
        self.config = config
        self.catalogo = catalogo
        self._parar = Event()
        self._hilo: Thread | None = None
        self._ultimo_campeon = 0
        self._ultima_fase = ""
        self._estaba_conectado = False

    @property
    def activo(self) -> bool:
        return self._hilo is not None and self._hilo.is_alive()

    def iniciar(self, al_evento: EventoCallback | None = None) -> None:
        if self.activo:
            return
        self._parar.clear()
        self._hilo = Thread(
            target=self._bucle,
            args=(al_evento,),
            name="vigilante-runas",
            daemon=True,
        )
        self._hilo.start()

    def detener(self) -> None:
        self._parar.set()
        if self._hilo is not None:
            self._hilo.join(timeout=3)
        self._hilo = None

    def _bucle(self, al_evento: EventoCallback | None) -> None:
        while not self._parar.is_set():
            try:
                self._tick(al_evento)
            except Exception as exc:  # noqa: BLE001 — el hilo no debe morir
                self._avisar(
                    al_evento,
                    {
                        "tipo": "error",
                        "mensaje": str(exc),
                    },
                )
            self._parar.wait(self._intervalo())

    def _intervalo(self) -> float:
        if not self._estaba_conectado:
            return 8.0
        if self._ultima_fase == "ChampSelect":
            return float(self.config.datos.get("intervalo_segundos") or 1.0)
        return 3.0

    def _tick(self, al_evento: EventoCallback | None) -> None:
        try:
            fase = self.cliente.get("/lol-gameflow/v1/gameflow-phase")
            conectado = True
        except ClienteNoDisponible:
            conectado = False
            fase = None

        if conectado != self._estaba_conectado:
            self._estaba_conectado = conectado
            self._avisar(
                al_evento,
                {"tipo": "cliente", "conectado": conectado},
            )
        if not conectado:
            self._ultimo_campeon = 0
            self._ultima_fase = ""
            return

        fase_texto = str(fase or "")
        if fase_texto != self._ultima_fase:
            self._ultima_fase = fase_texto
            self._avisar(al_evento, {"tipo": "fase", "fase": fase_texto})
            if fase_texto != "ChampSelect":
                self._ultimo_campeon = 0

        if fase_texto != "ChampSelect":
            return

        campeon_id = self._campeon_actual()
        if campeon_id <= 0 or campeon_id == self._ultimo_campeon:
            return
        self._ultimo_campeon = campeon_id
        self._aplicar(campeon_id, al_evento)

    def _campeon_actual(self) -> int:
        actual = self.cliente.get("/lol-champ-select/v1/current-champion")
        if isinstance(actual, int) and actual > 0:
            return actual
        sesion = self.cliente.get("/lol-champ-select/v1/session")
        if not isinstance(sesion, dict):
            return 0
        local = sesion.get("localPlayerCellId")
        for miembro in sesion.get("myTeam") or []:
            if miembro.get("cellId") == local:
                return int(miembro.get("championId") or 0)
        return 0

    def _aplicar(self, campeon_id: int, al_evento: EventoCallback | None) -> None:
        mapeo = self.config.mapeo_de(campeon_id)
        campeon = self.catalogo.por_id(campeon_id)
        nombre_campeon = (
            mapeo.get("campeon_nombre")
            if mapeo
            else (campeon["nombre"] if campeon else str(campeon_id))
        )
        if not mapeo:
            self._avisar(
                al_evento,
                {
                    "tipo": "sin_configurar",
                    "campeon_id": campeon_id,
                    "campeon_nombre": nombre_campeon,
                },
            )
            return

        pagina = resolver_pagina(
            self.cliente,
            mapeo.get("pagina_id"),
            mapeo.get("pagina_nombre"),
        )
        if pagina is None:
            self._avisar(
                al_evento,
                {
                    "tipo": "error",
                    "mensaje": (
                        f"No encontré la página '{mapeo.get('pagina_nombre')}' "
                        f"para {nombre_campeon}."
                    ),
                },
            )
            return

        activada = activar_pagina(self.cliente, pagina["id"])
        if int(mapeo.get("pagina_id") or 0) != pagina["id"]:
            mapeo["pagina_id"] = pagina["id"]
            self.config.upsert_mapeo(mapeo)
        self._avisar(
            al_evento,
            {
                "tipo": "aplicado",
                "campeon_id": campeon_id,
                "campeon_nombre": nombre_campeon,
                "pagina_id": activada["id"],
                "pagina_nombre": activada.get("nombre") or pagina["nombre"],
            },
        )

    @staticmethod
    def _avisar(al_evento: EventoCallback | None, evento: dict[str, Any]) -> None:
        if al_evento is None:
            return
        try:
            al_evento(evento)
        except Exception:
            pass


def esperar_interrupcion() -> None:
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        return
