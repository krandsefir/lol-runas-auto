from __future__ import annotations

from typing import Any

from runas_auto.lcu import ClienteLCU, ClienteNoDisponible

MAX_PARTIDAS = 2
MAX_BLOQUEOS = 3
_SALIENTES = frozenset({"out", "outgoing", "sent"})


def solicitudes_entrantes(cliente: ClienteLCU) -> list[dict[str, Any]]:
    datos = cliente.get("/lol-chat/v2/friend-requests")
    if not isinstance(datos, list):
        return []
    entrantes: list[dict[str, Any]] = []
    for item in datos:
        if not isinstance(item, dict):
            continue
        direccion = str(item.get("direction") or "").strip().lower()
        if direccion in _SALIENTES:
            continue
        if item.get("puuid") or item.get("id"):
            entrantes.append(item)
    return entrantes


def puuids_recientes(cliente: ClienteLCU, incluir_espera: bool) -> set[str] | None:
    """Jugadores de las últimas partidas y, en cola, de la sala actual.

    None si no se pudo leer el historial: en ese caso no se bloquea a nadie.
    """
    try:
        historial = cliente.get(
            "/lol-match-history/v1/products/lol/current-summoner/matches"
            f"?begIndex=0&endIndex={MAX_PARTIDAS}"
        )
    except ClienteNoDisponible:
        return None
    if not isinstance(historial, dict):
        return None
    juegos = (historial.get("games") or {}).get("games")
    if not isinstance(juegos, list):
        return None
    puuids = _puuids_en(juegos)
    propio = _puuid_propio(cliente)
    if propio:
        puuids.discard(propio)
    if incluir_espera:
        puuids.update(_puuids_en_espera(cliente))
        if propio:
            puuids.discard(propio)
    return puuids


def bloquear_solicitud(cliente: ClienteLCU, solicitud: dict[str, Any]) -> None:
    cuerpo: dict[str, Any] = {}
    for origen, destino in (
        ("puuid", "puuid"),
        ("gameName", "gameName"),
        ("tagLine", "gameTag"),
        ("name", "name"),
        ("pid", "pid"),
        ("summonerId", "summonerId"),
        ("icon", "icon"),
    ):
        valor = solicitud.get(origen)
        if valor not in (None, ""):
            cuerpo[destino] = valor
    if not cuerpo.get("puuid"):
        raise ClienteNoDisponible("La solicitud no trae puuid.")
    cliente.post("/lol-chat/v1/blocked-players", cuerpo)
    identificador = str(solicitud.get("id") or solicitud.get("puuid") or "")
    if identificador:
        try:
            cliente.delete(f"/lol-chat/v2/friend-requests/{identificador}")
        except ClienteNoDisponible:
            pass


def nombre_solicitud(solicitud: dict[str, Any]) -> str:
    juego = str(solicitud.get("gameName") or solicitud.get("name") or "").strip()
    etiqueta = str(solicitud.get("tagLine") or "").strip()
    if juego and etiqueta:
        return f"{juego}#{etiqueta}"
    return juego or str(solicitud.get("puuid") or "jugador")


def _puuid_propio(cliente: ClienteLCU) -> str:
    try:
        datos = cliente.get("/lol-summoner/v1/current-summoner")
    except ClienteNoDisponible:
        return ""
    if isinstance(datos, dict):
        return str(datos.get("puuid") or "")
    return ""


def _puuids_en_espera(cliente: ClienteLCU) -> set[str]:
    encontrados: set[str] = set()
    for ruta in ("/lol-gameflow/v1/session", "/lol-lobby/v2/lobby"):
        try:
            datos = cliente.get(ruta)
        except ClienteNoDisponible:
            continue
        encontrados.update(_puuids_en(datos))
    return encontrados


def _puuids_en(datos: Any) -> set[str]:
    encontrados: set[str] = set()

    def visitar(nodo: Any) -> None:
        if isinstance(nodo, dict):
            puuid = nodo.get("puuid")
            if isinstance(puuid, str) and puuid:
                encontrados.add(puuid)
            for valor in nodo.values():
                visitar(valor)
        elif isinstance(nodo, list):
            for valor in nodo:
                visitar(valor)

    visitar(datos)
    return encontrados
