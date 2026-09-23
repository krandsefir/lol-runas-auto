from __future__ import annotations

import time
from threading import Event
from typing import Any

import requests

SCOPES = "chat:read chat:edit"
URL_DEVICE = "https://id.twitch.tv/oauth2/device"
URL_TOKEN = "https://id.twitch.tv/oauth2/token"
URL_VALIDAR = "https://id.twitch.tv/oauth2/validate"
GRANT_DEVICE = "urn:ietf:params:oauth:grant-type:device_code"


class TwitchAuthError(RuntimeError):
    """Fallo al autorizar o renovar la sesión de Twitch."""


def pedir_dispositivo(client_id: str) -> dict[str, Any]:
    client_id = (client_id or "").strip()
    if not client_id:
        raise TwitchAuthError("Falta el Client ID de tu app de Twitch.")
    try:
        respuesta = requests.post(
            URL_DEVICE,
            data={"client_id": client_id, "scopes": SCOPES},
            timeout=20,
        )
    except requests.RequestException as exc:
        raise TwitchAuthError(f"No pude contactar con Twitch: {exc}") from exc
    datos = _json(respuesta)
    if not respuesta.ok or not datos.get("device_code"):
        raise TwitchAuthError(_mensaje_error(datos, "Twitch no aceptó el Client ID."))
    return datos


def esperar_token(
    client_id: str,
    device_code: str,
    interval: float,
    expires_in: float,
    cancelar: Event | None = None,
) -> dict[str, Any] | None:
    """Espera a que el usuario autorice. None si cancela o caduca el código."""
    parar = cancelar or Event()
    espera = max(3.0, float(interval or 5))
    limite = time.time() + max(30.0, float(expires_in or 1800))
    while time.time() < limite and not parar.is_set():
        if parar.wait(espera):
            return None
        try:
            respuesta = requests.post(
                URL_TOKEN,
                data={
                    "client_id": client_id,
                    "device_code": device_code,
                    "grant_type": GRANT_DEVICE,
                    "scopes": SCOPES,
                },
                timeout=20,
            )
        except requests.RequestException:
            continue
        datos = _json(respuesta)
        if respuesta.ok and datos.get("access_token"):
            return datos
        clave = str(datos.get("message") or datos.get("status") or "").lower()
        if "pending" in clave:
            continue
        if "slow" in clave:
            espera += 5
            continue
        if "expired" in clave or "invalid device" in clave:
            raise TwitchAuthError("El código caducó. Vuelve a iniciar sesión.")
        if "denied" in clave or "access_denied" in clave:
            raise TwitchAuthError("Cancelaste la autorización en Twitch.")
        raise TwitchAuthError(_mensaje_error(datos, "No se pudo autorizar con Twitch."))
    return None


def refrescar_token(client_id: str, refresh_token: str) -> dict[str, Any]:
    if not client_id or not refresh_token:
        raise TwitchAuthError("No hay sesión de Twitch para renovar.")
    try:
        respuesta = requests.post(
            URL_TOKEN,
            data={
                "client_id": client_id,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        raise TwitchAuthError(f"No pude renovar la sesión de Twitch: {exc}") from exc
    datos = _json(respuesta)
    if not respuesta.ok or not datos.get("access_token"):
        raise TwitchAuthError(_mensaje_error(datos, "La sesión de Twitch caducó."))
    return datos


def validar_token(access_token: str) -> dict[str, Any]:
    if not access_token:
        raise TwitchAuthError("No hay token de Twitch.")
    try:
        respuesta = requests.get(
            URL_VALIDAR,
            headers={"Authorization": f"OAuth {access_token}"},
            timeout=15,
        )
    except requests.RequestException as exc:
        raise TwitchAuthError(f"No pude validar la sesión de Twitch: {exc}") from exc
    datos = _json(respuesta)
    if not respuesta.ok or not datos.get("login"):
        raise TwitchAuthError(_mensaje_error(datos, "La sesión de Twitch no es válida."))
    return datos


def _json(respuesta: requests.Response) -> dict[str, Any]:
    try:
        datos = respuesta.json()
    except ValueError:
        return {"message": respuesta.text[:200] or f"HTTP {respuesta.status_code}"}
    return datos if isinstance(datos, dict) else {"message": str(datos)}


def _mensaje_error(datos: dict[str, Any], respaldo: str) -> str:
    return str(datos.get("message") or datos.get("error") or respaldo)
