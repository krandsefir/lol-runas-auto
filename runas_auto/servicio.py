from __future__ import annotations

import time
import webbrowser
from collections.abc import Callable
from threading import Event, Lock, Thread
from typing import Any

from runas_auto.campeones import CatalogoCampeones
from runas_auto.config import Configuracion
from runas_auto.lcu import ClienteLCU, ClienteNoDisponible
from runas_auto.runas import listar_paginas, pagina_actual, resolver_pagina
from runas_auto.twitch import ChatTwitch, normalizar_canal
from runas_auto.twitch_auth import (
    TwitchAuthError,
    esperar_token,
    pedir_dispositivo,
    refrescar_token,
    validar_token,
)
from runas_auto.vigilancia import Vigilante


class ServicioRunas:
    """API para la GUI: buscar campeón, elegir página y ver lo ya configurado."""

    def __init__(self) -> None:
        self.config = Configuracion()
        self.cliente = ClienteLCU(self.config.datos.get("ruta_lockfile"))
        self.catalogo = CatalogoCampeones(self.cliente)
        self.vigilante = Vigilante(self.cliente, self.config, self.catalogo)
        self.chat = ChatTwitch()
        self._al_evento: Callable[[dict[str, Any]], None] | None = None
        self._login_cancelar = Event()
        self._reauth_lock = Lock()

    def estado(self) -> dict[str, Any]:
        conectado = self.cliente.conectado()
        invocador = None
        pagina = None
        twitch = self.config.twitch()
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
            "twitch_habilitado": bool(twitch["habilitado"]),
            "twitch_conectado": self.chat.conectado,
            "twitch_canal": twitch["canal"],
            "twitch_login": twitch.get("login") or "",
            "twitch_puede_hablar": bool(twitch.get("puede_hablar")),
            "twitch_client_id": twitch.get("client_id") or "",
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

    def modo_skin(self) -> str:
        return self.config.modo_skin()

    def set_modo_skin(self, modo: str) -> str:
        self.config.set_modo_skin(modo)
        return self.config.modo_skin()

    def twitch(self) -> dict[str, Any]:
        return self.config.twitch()

    def set_twitch(self, habilitado: bool, canal: str, comando: str = "!skin") -> dict[str, Any]:
        canal = normalizar_canal(canal)
        comando = (comando or "!skin").strip() or "!skin"
        self.config.set_twitch(habilitado, canal, comando)
        self._sincronizar_twitch()
        return self.config.twitch()

    def set_twitch_client_id(self, client_id: str) -> None:
        self.config.set_twitch_client_id(client_id)

    def iniciar_sesion_twitch(
        self,
        client_id: str,
        al_codigo: Callable[[dict[str, Any]], None] | None = None,
        cancelar: Event | None = None,
    ) -> dict[str, Any]:
        client_id = (client_id or "").strip()
        self.config.set_twitch_client_id(client_id)
        self._login_cancelar = cancelar or Event()
        dispositivo = pedir_dispositivo(client_id)
        if al_codigo is not None:
            al_codigo(dispositivo)
        uri = str(dispositivo.get("verification_uri") or "https://www.twitch.tv/activate")
        try:
            webbrowser.open(uri)
        except Exception:
            pass
        tokens = esperar_token(
            client_id,
            str(dispositivo.get("device_code") or ""),
            float(dispositivo.get("interval") or 5),
            float(dispositivo.get("expires_in") or 1800),
            self._login_cancelar,
        )
        if tokens is None:
            raise TwitchAuthError("Inicio de sesión cancelado o caducado.")
        cuenta = validar_token(str(tokens["access_token"]))
        login = str(cuenta.get("login") or "").lower()
        self.config.set_twitch_sesion(
            str(tokens.get("access_token") or ""),
            str(tokens.get("refresh_token") or ""),
            login,
            float(tokens.get("expires_in") or cuenta.get("expires_in") or 14400),
        )
        canal = self.config.twitch()["canal"] or login
        self.config.set_twitch(True, canal)
        self._sincronizar_twitch()
        return self.config.twitch()

    def cancelar_login_twitch(self) -> None:
        self._login_cancelar.set()

    def cerrar_sesion_twitch(self) -> dict[str, Any]:
        self.config.borrar_twitch_sesion()
        self._sincronizar_twitch()
        return self.config.twitch()

    def iniciar(self, al_evento: Callable[[dict[str, Any]], None] | None = None) -> None:
        """Arranca la vigilancia de champ select en segundo plano."""
        self._al_evento = al_evento
        self.vigilante.iniciar(self._evento_interno)
        self._sincronizar_twitch()

    def detener(self) -> None:
        self.cancelar_login_twitch()
        self.chat.detener()
        self.vigilante.detener()

    def _evento_interno(self, evento: dict[str, Any]) -> None:
        texto = evento.get("respuesta_chat")
        if texto:
            self.chat.decir(str(texto))
        if evento.get("reauth"):
            Thread(target=self._reautenticar_twitch, daemon=True, name="twitch-reauth").start()
        if self._al_evento is not None:
            self._al_evento(evento)

    def _reautenticar_twitch(self) -> None:
        if not self._reauth_lock.acquire(blocking=False):
            return
        try:
            try:
                self._asegurar_token()
            except TwitchAuthError as exc:
                self.config.borrar_twitch_sesion()
                if self._al_evento is not None:
                    self._al_evento(
                        {
                            "tipo": "twitch",
                            "conectado": False,
                            "mensaje": str(exc),
                        }
                    )
                return
            self._sincronizar_twitch()
        finally:
            self._reauth_lock.release()

    def _asegurar_token(self) -> tuple[str, str]:
        cred = self.config.twitch_credenciales()
        access = cred["access_token"]
        refresh = cred["refresh_token"]
        login = cred["login"]
        client_id = cred["client_id"]
        if not access or not login:
            return "", ""
        if cred["expira"] > time.time() + 30:
            return access, login
        if not refresh or not client_id:
            raise TwitchAuthError("La sesión de Twitch caducó. Vuelve a iniciar sesión.")
        tokens = refrescar_token(client_id, refresh)
        cuenta = validar_token(str(tokens["access_token"]))
        login = str(cuenta.get("login") or login).lower()
        self.config.set_twitch_sesion(
            str(tokens.get("access_token") or ""),
            str(tokens.get("refresh_token") or refresh),
            login,
            float(tokens.get("expires_in") or cuenta.get("expires_in") or 14400),
        )
        return str(tokens["access_token"]), login

    def _sincronizar_twitch(self) -> None:
        datos = self.config.twitch()
        if not datos["habilitado"] or not datos["canal"]:
            self.chat.detener()
            return
        token = ""
        nick = ""
        try:
            token, nick = self._asegurar_token()
        except TwitchAuthError as exc:
            if self._al_evento is not None:
                self._al_evento({"tipo": "twitch", "conectado": False, "mensaje": str(exc)})
        try:
            self.chat.iniciar(
                datos["canal"],
                datos["comando"],
                self.vigilante.pedido_desde_chat,
                self._evento_interno,
                token=token,
                nick=nick,
            )
        except ValueError as exc:
            if self._al_evento is not None:
                self._al_evento(
                    {"tipo": "twitch", "conectado": False, "mensaje": str(exc)}
                )
