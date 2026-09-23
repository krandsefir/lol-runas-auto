from __future__ import annotations

import random
import re
import socket
import ssl
from collections.abc import Callable
from threading import Event, Lock, Thread, current_thread
from typing import Any

from runas_auto.log import registrar

HOST = "irc.chat.twitch.tv"
PUERTO = 6697
PRIVMSG = re.compile(
    r"^(?:@(?P<tags>\S+)\s+)?:(?P<user>[^!]+)![^ ]+ PRIVMSG #\S+ :(?P<msg>.*)$"
)

ComandoChat = Callable[[str, str, str], None]


def normalizar_canal(texto: str) -> str:
    canal = (texto or "").strip().lower()
    canal = canal.replace("https://www.twitch.tv/", "").replace("https://twitch.tv/", "")
    canal = canal.replace("http://www.twitch.tv/", "").replace("http://twitch.tv/", "")
    canal = canal.strip("/").lstrip("#")
    if "/" in canal:
        canal = canal.split("/")[0]
    return canal


class ChatTwitch:
    """Chat de Twitch por IRC. Sin token solo lee; con token también responde."""

    def __init__(self) -> None:
        self._parar = Event()
        self._hilo: Thread | None = None
        self.canal = ""
        self.comando = "!skin"
        self._al_comando: ComandoChat | None = None
        self._al_evento: Callable[[dict[str, Any]], None] | None = None
        self.conectado = False
        self._sock: ssl.SSLSocket | None = None
        self._envio = Lock()
        self._token = ""
        self.nick = ""
        self.puede_hablar = False

    @property
    def activo(self) -> bool:
        return self._hilo is not None and self._hilo.is_alive()

    def iniciar(
        self,
        canal: str,
        comando: str,
        al_comando: ComandoChat,
        al_evento: Callable[[dict[str, Any]], None] | None = None,
        token: str = "",
        nick: str = "",
    ) -> None:
        canal = normalizar_canal(canal)
        if not canal:
            raise ValueError("Escribe el nombre de tu canal de Twitch.")
        self.detener()
        self.canal = canal
        self.comando = (comando or "!skin").strip().lower() or "!skin"
        self._al_comando = al_comando
        self._al_evento = al_evento
        self._token = (token or "").strip()
        self.nick = (nick or "").strip().lower()
        self.puede_hablar = bool(self._token and self.nick)
        self._parar.clear()
        self._hilo = Thread(target=self._bucle, name="twitch-chat", daemon=True)
        self._hilo.start()

    def detener(self) -> None:
        self._parar.set()
        self.conectado = False
        sock = self._sock
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass
        if self._hilo is not None:
            self._hilo.join(timeout=2)
        self._hilo = None
        self._sock = None
        self.puede_hablar = False

    def decir(self, texto: str) -> bool:
        if not self.puede_hablar or not self.conectado:
            return False
        sock = self._sock
        if sock is None:
            return False
        mensaje = " ".join((texto or "").split())
        if not mensaje:
            return False
        if len(mensaje) > 450:
            mensaje = mensaje[:447] + "..."
        try:
            with self._envio:
                self._enviar(sock, f"PRIVMSG #{self.canal} :{mensaje}")
            return True
        except OSError as exc:
            registrar(f"Twitch decir: {exc}")
            return False

    def _avisar(self, evento: dict[str, Any]) -> None:
        if self._al_evento is None:
            return
        try:
            self._al_evento(evento)
        except Exception:
            pass

    def _bucle(self) -> None:
        yo = current_thread()
        while not self._parar.is_set() and self._hilo is yo:
            try:
                self._sesion()
            except Exception as exc:  # noqa: BLE001
                self.conectado = False
                registrar(f"Twitch: {exc}")
                self._avisar({"tipo": "twitch", "conectado": False, "mensaje": str(exc)})
            if not self._parar.is_set() and self._hilo is yo:
                self._parar.wait(5)

    def _sesion(self) -> None:
        contexto = ssl.create_default_context()
        crudo = socket.create_connection((HOST, PUERTO), timeout=15)
        sock = contexto.wrap_socket(crudo, server_hostname=HOST)
        sock.settimeout(30)
        self._sock = sock
        if self._token and self.nick:
            nick = self.nick
            self._enviar(sock, "CAP REQ :twitch.tv/tags twitch.tv/commands")
            self._enviar(sock, f"PASS oauth:{self._token}")
            self._enviar(sock, f"NICK {nick}")
        else:
            nick = f"justinfan{random.randint(10000, 99999)}"
            self._enviar(sock, "CAP REQ :twitch.tv/tags twitch.tv/commands")
            self._enviar(sock, f"NICK {nick}")
        self._enviar(sock, f"JOIN #{self.canal}")
        buffer = ""
        unido = False
        yo = current_thread()
        while not self._parar.is_set() and self._hilo is yo:
            try:
                data = sock.recv(4096)
            except TimeoutError:
                continue
            except OSError:
                break
            if not data:
                break
            buffer += data.decode("utf-8", errors="replace")
            while "\r\n" in buffer:
                linea, buffer = buffer.split("\r\n", 1)
                if not linea:
                    continue
                if linea.startswith("PING"):
                    with self._envio:
                        self._enviar(sock, "PONG :tmi.twitch.tv")
                    continue
                baja = linea.lower()
                if "login authentication failed" in baja or "improperly formatted auth" in baja:
                    self._avisar(
                        {
                            "tipo": "twitch",
                            "conectado": False,
                            "reauth": True,
                            "mensaje": "La sesión de Twitch caducó. Vuelve a iniciar sesión.",
                        }
                    )
                    self._parar.set()
                    break
                if not unido and (" 001 " in linea or "JOIN #" in linea):
                    unido = True
                    self.conectado = True
                    if self.puede_hablar:
                        mensaje = f"Conectado a #{self.canal} como {self.nick} (responde en el chat)."
                    else:
                        mensaje = f"Escuchando #{self.canal} (sin responder: inicia sesión)."
                    self._avisar(
                        {
                            "tipo": "twitch",
                            "conectado": True,
                            "canal": self.canal,
                            "mensaje": mensaje,
                        }
                    )
                self._procesar(linea)
        try:
            sock.close()
        except OSError:
            pass
        if self._sock is sock:
            self._sock = None
        self.conectado = False

    def _procesar(self, linea: str) -> None:
        match = PRIVMSG.match(linea)
        if not match:
            return
        login = match.group("user") or ""
        usuario = login
        tags = match.group("tags") or ""
        for parte in tags.split(";"):
            if parte.startswith("display-name=") and parte[13:]:
                usuario = parte[13:]
                break
        mensaje = (match.group("msg") or "").strip()
        if not mensaje:
            return
        partes = mensaje.split(None, 1)
        cmd = partes[0].lower()
        if cmd != self.comando.lower():
            return
        argumento = partes[1] if len(partes) > 1 else ""
        if self._al_comando is None:
            return
        try:
            self._al_comando(usuario, argumento, login)
        except Exception as exc:  # noqa: BLE001
            registrar(f"Comando Twitch: {exc}")

    @staticmethod
    def _enviar(sock: ssl.SSLSocket, linea: str) -> None:
        sock.sendall((linea + "\r\n").encode("utf-8"))
