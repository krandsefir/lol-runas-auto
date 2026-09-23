from __future__ import annotations

import time
from collections.abc import Callable
from threading import Event, Lock, Thread
from typing import Any

from runas_auto.campeones import CatalogoCampeones
from runas_auto.config import Configuracion
from runas_auto.lcu import ClienteLCU, ClienteNoDisponible
from runas_auto.reportes import FASES_REPORTE, enviar_reportes_pendientes
from runas_auto.runas import activar_pagina, resolver_pagina
from runas_auto.skins import (
    aplicar_skin,
    elegir_skin,
    elegir_skin_desde_chat,
    listar_skins_poseidas,
    skin_actual_en_select,
)

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
        self._al_evento: EventoCallback | None = None
        self._pedido_chat: dict[str, str] | None = None
        self._ultimo_chat = 0.0
        self._lock_chat = Lock()
        self._reportes_enviados: set[str] = set()
        self._reportes_fallidos: set[str] = set()

    @property
    def activo(self) -> bool:
        return self._hilo is not None and self._hilo.is_alive()

    def iniciar(self, al_evento: EventoCallback | None = None) -> None:
        if self.activo:
            return
        self._al_evento = al_evento
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
        if self._ultima_fase in FASES_REPORTE:
            return 1.0
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
            self._reportes_fallidos.clear()
            return

        fase_texto = str(fase or "")
        if fase_texto != self._ultima_fase:
            self._ultima_fase = fase_texto
            self._avisar(al_evento, {"tipo": "fase", "fase": fase_texto})
            if fase_texto != "ChampSelect":
                self._ultimo_campeon = 0

        if fase_texto in FASES_REPORTE:
            self._enviar_reportes(al_evento)

        if fase_texto != "ChampSelect":
            return

        campeon_id = self._campeon_actual()
        if campeon_id <= 0 or campeon_id == self._ultimo_campeon:
            return
        self._ultimo_campeon = campeon_id
        self._aplicar_runas(campeon_id, al_evento)
        self._aplicar_skin(campeon_id, al_evento)

    def pedido_desde_chat(self, usuario: str, argumento: str, login: str = "") -> None:
        ahora = time.monotonic()
        if ahora - self._ultimo_chat < 4:
            self._avisar(
                self._al_evento,
                {
                    "tipo": "twitch",
                    "conectado": True,
                    "mensaje": f"{usuario}: espera un momento para otro !skin.",
                },
            )
            return
        self._ultimo_chat = ahora
        login = (login or usuario or "").strip()
        with self._lock_chat:
            self._pedido_chat = {
                "usuario": usuario,
                "login": login,
                "argumento": argumento or "",
            }
        mencion = f"@{login}" if login else usuario
        if self._ultima_fase != "ChampSelect":
            self._avisar(
                self._al_evento,
                {
                    "tipo": "twitch",
                    "conectado": True,
                    "mensaje": f"{usuario} pidió skin; se aplica en champ select.",
                    "respuesta_chat": (
                        f"{mencion} pidió la skin; se selecciona en champ select."
                    ),
                },
            )
            return
        campeon_id = self._campeon_actual()
        if campeon_id <= 0:
            self._avisar(
                self._al_evento,
                {
                    "tipo": "twitch",
                    "conectado": True,
                    "mensaje": f"{usuario} pidió skin; elige el campeón y se aplica.",
                    "respuesta_chat": (
                        f"{mencion} pidió la skin; se selecciona al elegir campeón."
                    ),
                },
            )
            return
        self._aplicar_skin(campeon_id, self._al_evento)

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

    def _aplicar_runas(self, campeon_id: int, al_evento: EventoCallback | None) -> None:
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

    def _aplicar_skin(self, campeon_id: int, al_evento: EventoCallback | None) -> None:
        with self._lock_chat:
            pedido = self._pedido_chat
            if pedido is not None:
                self._pedido_chat = None
        modo = self.config.modo_skin()
        if pedido is None and modo == "ninguna":
            return
        campeon = self.catalogo.por_id(campeon_id)
        nombre_campeon = campeon["nombre"] if campeon else str(campeon_id)
        try:
            skins = listar_skins_poseidas(self.cliente, campeon_id)
        except ClienteNoDisponible as exc:
            self._devolver_pedido(pedido)
            self._avisar(al_evento, {"tipo": "error", "mensaje": str(exc)})
            return
        if not skins:
            self._avisar(
                al_evento,
                {
                    "tipo": "error",
                    "mensaje": f"No hay skins disponibles para {nombre_campeon}.",
                },
            )
            return
        actual_id = skin_actual_en_select(self.cliente)
        usuario = ""
        login = ""
        if pedido is not None:
            usuario = pedido.get("usuario") or ""
            login = pedido.get("login") or usuario
            elegida = elegir_skin_desde_chat(
                skins,
                pedido.get("argumento") or "",
                actual_id or None,
                self.config.ultima_skin(campeon_id),
            )
            if elegida is None:
                mencion = f"@{login}" if login else usuario
                self._avisar(
                    al_evento,
                    {
                        "tipo": "twitch",
                        "conectado": True,
                        "mensaje": (
                            f"No encontré esa skin para {nombre_campeon} "
                            f"(pide una que ya tengas)."
                        ),
                        "respuesta_chat": (
                            f"{mencion} esa skin no está entre las que tienes de "
                            f"{nombre_campeon}."
                        ),
                    },
                )
                return
        else:
            elegida = elegir_skin(
                skins,
                modo,
                actual_id or None,
                self.config.ultima_skin(campeon_id),
            )
        if elegida is None:
            return
        try:
            aplicar_skin(self.cliente, elegida["id"])
        except ClienteNoDisponible as exc:
            self._devolver_pedido(pedido)
            self._avisar(al_evento, {"tipo": "error", "mensaje": str(exc)})
            return
        self.config.set_ultima_skin(campeon_id, elegida["id"])
        evento: dict[str, Any] = {
            "tipo": "skin",
            "campeon_id": campeon_id,
            "campeon_nombre": nombre_campeon,
            "skin_id": elegida["id"],
            "skin_nombre": elegida["nombre"],
            "modo": "chat" if usuario else modo,
        }
        if usuario:
            evento["usuario"] = usuario
            mencion = f"@{login}" if login else usuario
            evento["respuesta_chat"] = (
                f"{mencion} eligió {elegida['nombre']} para {nombre_campeon}. "
                "Skin seleccionada para esta partida."
            )
        self._avisar(al_evento, evento)

    def _enviar_reportes(self, al_evento: EventoCallback | None) -> None:
        try:
            enviados, fallos = enviar_reportes_pendientes(
                self.cliente,
                self._reportes_enviados,
            )
        except ClienteNoDisponible:
            return
        for clave in fallos:
            if clave in self._reportes_fallidos:
                continue
            self._reportes_fallidos.add(clave)
            self._avisar(
                al_evento,
                {
                    "tipo": "error",
                    "mensaje": "No pude enviar un reporte pendiente. Lo reintento.",
                },
            )
        if not enviados:
            return
        for item in enviados:
            self._reportes_fallidos.discard(item["clave"])
        nombres = [item["nombre"] for item in enviados if item.get("nombre")]
        if len(enviados) == 1 and nombres:
            mensaje = f"Reporte enviado: {nombres[0]}."
        elif nombres:
            mensaje = "Reportes enviados: " + ", ".join(nombres) + "."
        elif len(enviados) == 1:
            mensaje = "Reporte de la partida enviado."
        else:
            mensaje = f"{len(enviados)} reportes de la partida enviados."
        self._avisar(
            al_evento,
            {"tipo": "reporte", "mensaje": mensaje, "cantidad": len(enviados)},
        )

    def _devolver_pedido(self, pedido: dict[str, str] | None) -> None:
        if pedido is None:
            return
        with self._lock_chat:
            if self._pedido_chat is None:
                self._pedido_chat = pedido

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
