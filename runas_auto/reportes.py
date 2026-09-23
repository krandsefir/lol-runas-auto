from __future__ import annotations

from typing import Any

from runas_auto.lcu import ClienteLCU, ClienteNoDisponible

FASES_REPORTE = frozenset({"WaitingForStats", "PreEndOfGame", "EndOfGame"})


def listar_reportes_en_juego(cliente: ClienteLCU) -> list[dict[str, Any]]:
    """Reportes que ya marcaste en la partida y aún no se han enviado."""
    datos = cliente.get("/lol-player-report-sender/v1/in-game-reports")
    pendientes = _como_lista(datos)
    if pendientes:
        return pendientes
    pantalla = cliente.get("/lol-end-of-game/v1/reported-players")
    return _como_lista(pantalla)


def enviar_reportes_pendientes(
    cliente: ClienteLCU,
    ya_enviados: set[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Reenvía al fin de partida solo los reportes guardados dentro del juego.

    Devuelve los enviados y las claves que fallaron en este intento.
    """
    pendientes = listar_reportes_en_juego(cliente)
    if not pendientes:
        return [], []
    game_id = _game_id_de(pendientes) or _game_id_actual(cliente)
    nombres = _nombres_jugadores(cliente)
    enviados: list[dict[str, Any]] = []
    fallos: list[str] = []
    for reporte in pendientes:
        cuerpo = cuerpo_reporte(reporte, game_id)
        if cuerpo is None:
            continue
        clave = clave_reporte(cuerpo)
        if clave in ya_enviados:
            continue
        try:
            cliente.post("/lol-player-report-sender/v1/end-of-game-reports", cuerpo)
        except ClienteNoDisponible:
            fallos.append(clave)
            continue
        ya_enviados.add(clave)
        enviados.append(
            {
                "clave": clave,
                "nombre": _nombre_de(cuerpo, nombres),
            }
        )
    return enviados, fallos


def cuerpo_reporte(reporte: dict[str, Any], game_id: int = 0) -> dict[str, Any] | None:
    categorias = reporte.get("categories")
    if not isinstance(categorias, list):
        categorias = reporte.get("reportCategories")
    if not isinstance(categorias, list):
        return None
    categorias_texto = [str(item) for item in categorias if item]
    if not categorias_texto:
        return None

    puuid = str(reporte.get("offenderPuuid") or "").strip()
    ofuscado = str(reporte.get("obfuscatedOffenderPuuid") or "").strip()
    summoner = reporte.get("offenderSummonerId")
    if not puuid and not ofuscado and not summoner:
        return None

    try:
        juego = int(reporte.get("gameId") or 0)
    except (TypeError, ValueError):
        juego = 0
    if juego <= 0:
        juego = int(game_id or 0)
    if juego <= 0:
        return None

    cuerpo: dict[str, Any] = {
        "gameId": juego,
        "categories": categorias_texto,
        "offenderPuuid": puuid,
        "comment": str(reporte.get("comment") or ""),
    }
    if ofuscado:
        cuerpo["obfuscatedOffenderPuuid"] = ofuscado
    if summoner not in (None, ""):
        try:
            cuerpo["offenderSummonerId"] = int(summoner)
        except (TypeError, ValueError):
            pass
    return cuerpo


def clave_reporte(cuerpo: dict[str, Any]) -> str:
    quien = (
        cuerpo.get("offenderPuuid")
        or cuerpo.get("obfuscatedOffenderPuuid")
        or cuerpo.get("offenderSummonerId")
        or ""
    )
    return f"{cuerpo.get('gameId')}:{quien}"


def _como_lista(datos: Any) -> list[dict[str, Any]]:
    if isinstance(datos, list):
        return [item for item in datos if isinstance(item, dict)]
    if isinstance(datos, dict):
        for clave in ("reports", "inGameReports", "playerReports"):
            valor = datos.get(clave)
            if isinstance(valor, list):
                return [item for item in valor if isinstance(item, dict)]
        if datos.get("offenderPuuid") or datos.get("categories"):
            return [datos]
    return []


def _game_id_de(reportes: list[dict[str, Any]]) -> int:
    for reporte in reportes:
        try:
            juego = int(reporte.get("gameId") or 0)
        except (TypeError, ValueError):
            continue
        if juego > 0:
            return juego
    return 0


def _game_id_actual(cliente: ClienteLCU) -> int:
    try:
        bloque = cliente.get("/lol-end-of-game/v1/eog-stats-block")
    except ClienteNoDisponible:
        bloque = None
    juego = _leer_game_id(bloque)
    if juego:
        return juego
    try:
        sesion = cliente.get("/lol-gameflow/v1/session")
    except ClienteNoDisponible:
        return 0
    if isinstance(sesion, dict):
        return _leer_game_id(sesion.get("gameData")) or _leer_game_id(sesion)
    return 0


def _leer_game_id(datos: Any) -> int:
    if not isinstance(datos, dict):
        return 0
    try:
        juego = int(datos.get("gameId") or 0)
    except (TypeError, ValueError):
        return 0
    return juego if juego > 0 else 0


def _nombres_jugadores(cliente: ClienteLCU) -> dict[str, str]:
    try:
        bloque = cliente.get("/lol-end-of-game/v1/eog-stats-block")
    except ClienteNoDisponible:
        return {}
    if not isinstance(bloque, dict):
        return {}
    nombres: dict[str, str] = {}
    equipos = bloque.get("teams") or []
    if isinstance(equipos, dict):
        equipos = list(equipos.values())
    for equipo in equipos:
        if not isinstance(equipo, dict):
            continue
        for jugador in equipo.get("players") or []:
            if not isinstance(jugador, dict):
                continue
            nombre = (
                jugador.get("riotIdGameName")
                or jugador.get("summonerName")
                or ""
            )
            puuid = str(jugador.get("puuid") or "")
            if nombre and puuid:
                nombres[puuid] = str(nombre)
    return nombres


def _nombre_de(cuerpo: dict[str, Any], nombres: dict[str, str]) -> str:
    puuid = str(cuerpo.get("offenderPuuid") or "")
    return nombres.get(puuid, "")
