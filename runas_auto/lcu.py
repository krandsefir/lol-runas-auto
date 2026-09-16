from __future__ import annotations

import base64
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_PUERTO = re.compile(r"--app-port=(\d+)")
_TOKEN = re.compile(r"--remoting-auth-token=([\w-]+)")


class ClienteNoDisponible(RuntimeError):
    """El cliente de LoL no está abierto o no se pudo leer el lockfile."""


@dataclass
class CredencialesLCU:
    puerto: int
    token: str
    protocolo: str = "https"

    @property
    def origen(self) -> str:
        return f"{self.protocolo}://127.0.0.1:{self.puerto}"

    @property
    def encabezado_auth(self) -> str:
        crudo = f"riot:{self.token}".encode("utf-8")
        return "Basic " + base64.b64encode(crudo).decode("ascii")


class ClienteLCU:
    def __init__(self, ruta_lockfile: str | None = None) -> None:
        self.ruta_lockfile = ruta_lockfile
        self._credenciales: CredencialesLCU | None = None
        self._lock = Lock()
        self._sesion = requests.Session()
        self._sesion.verify = False
        self._sesion.headers.update({"Accept": "application/json"})

    def conectar(self) -> CredencialesLCU:
        credenciales = self._buscar_credenciales()
        self._credenciales = credenciales
        self._sesion.headers["Authorization"] = credenciales.encabezado_auth
        return credenciales

    def conectado(self) -> bool:
        try:
            self.conectar()
            self.get("/lol-summoner/v1/current-summoner")
            return True
        except (ClienteNoDisponible, requests.RequestException):
            self._credenciales = None
            return False

    def get(self, ruta: str) -> Any:
        return self._pedir("GET", ruta)

    def put(self, ruta: str, cuerpo: Any = None) -> Any:
        return self._pedir("PUT", ruta, cuerpo)

    def post(self, ruta: str, cuerpo: Any = None) -> Any:
        return self._pedir("POST", ruta, cuerpo)

    def delete(self, ruta: str) -> Any:
        return self._pedir("DELETE", ruta)

    def _pedir(self, metodo: str, ruta: str, cuerpo: Any = None) -> Any:
        with self._lock:
            if self._credenciales is None:
                self.conectar()
            assert self._credenciales is not None
            url = self._credenciales.origen + ruta
            try:
                respuesta = self._sesion.request(
                    metodo,
                    url,
                    json=cuerpo,
                    timeout=4,
                )
            except requests.RequestException as exc:
                self._credenciales = None
                raise ClienteNoDisponible(f"No hay conexión con el cliente: {exc}") from exc

            if respuesta.status_code == 404:
                return None
            if respuesta.status_code >= 400:
                raise ClienteNoDisponible(
                    f"LCU {metodo} {ruta} → {respuesta.status_code}: {respuesta.text[:300]}"
                )
            if not respuesta.content:
                return None
            try:
                return respuesta.json()
            except ValueError:
                return respuesta.text

    def _buscar_credenciales(self) -> CredencialesLCU:
        candidatos: list[Path] = []
        if self.ruta_lockfile:
            candidatos.append(Path(self.ruta_lockfile))
        for letra in "CDEFG":
            candidatos.append(Path(fr"{letra}:\Riot Games\League of Legends\lockfile"))
        candidatos.append(Path(r"C:\Program Files\Riot Games\League of Legends\lockfile"))
        candidatos.append(Path(r"C:\Program Files (x86)\Riot Games\League of Legends\lockfile"))

        for ruta in candidatos:
            if ruta.is_file():
                leidas = _credenciales_desde_lockfile(ruta)
                if leidas:
                    return leidas

        desde_proceso = _credenciales_desde_proceso()
        if desde_proceso:
            return desde_proceso
        raise ClienteNoDisponible(
            "No encontré el cliente de LoL. Ábrelo e inténtalo de nuevo."
        )


def _credenciales_desde_lockfile(ruta: Path) -> CredencialesLCU | None:
    try:
        texto = ruta.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    partes = texto.split(":")
    if len(partes) < 5:
        return None
    try:
        return CredencialesLCU(
            puerto=int(partes[2]),
            token=partes[3],
            protocolo=partes[4],
        )
    except ValueError:
        return None


def _flags_oculto() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _credenciales_desde_proceso() -> CredencialesLCU | None:
    try:
        lista = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq LeagueClientUx.exe", "/NH"],
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=_flags_oculto(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if "LeagueClientUx.exe" not in (lista.stdout or ""):
        return None

    comando = (
        "Get-CimInstance Win32_Process -Filter \"Name='LeagueClientUx.exe'\" "
        "| Select-Object -ExpandProperty CommandLine"
    )
    try:
        resultado = subprocess.run(
            ["powershell", "-NoProfile", "-Command", comando],
            capture_output=True,
            text=True,
            timeout=8,
            creationflags=_flags_oculto(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    linea = (resultado.stdout or "").strip()
    if not linea:
        return None
    puerto = _PUERTO.search(linea)
    token = _TOKEN.search(linea)
    if not puerto or not token:
        return None
    return CredencialesLCU(puerto=int(puerto.group(1)), token=token.group(1))
