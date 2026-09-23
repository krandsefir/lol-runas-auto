from __future__ import annotations

import random
import unicodedata
from typing import Any

from runas_auto.lcu import ClienteLCU, ClienteNoDisponible

MODOS_SKIN = ("ninguna", "aleatoria", "siguiente")
ETIQUETAS_SKIN = {
    "ninguna": "No cambiar",
    "aleatoria": "Aleatoria",
    "siguiente": "Siguiente",
}


def _poseida(item: dict[str, Any]) -> bool:
    if item.get("owned") or item.get("unlocked"):
        return True
    ownership = item.get("ownership")
    if isinstance(ownership, dict) and ownership.get("owned"):
        return True
    return False


def _id_skin(item: dict[str, Any]) -> int:
    for clave in ("id", "skinId", "championSkinId"):
        if item.get(clave) is not None:
            return int(item[clave])
    return 0


def _nombre_skin(item: dict[str, Any]) -> str:
    nombre = item.get("name") or item.get("nameId") or ""
    return str(nombre)


def _es_chroma(item: dict[str, Any]) -> bool:
    if item.get("isChroma") or item.get("chroma"):
        return True
    if item.get("parentSkinId") or item.get("parentSkin"):
        return True
    return False


def listar_skins_poseidas(cliente: ClienteLCU, campeon_id: int) -> list[dict[str, Any]]:
    campeon_id = int(campeon_id)
    skins: list[dict[str, Any]] = []
    vistos: set[int] = set()

    def agregar(item: dict[str, Any], chroma: bool = False) -> None:
        if not isinstance(item, dict) or not _poseida(item):
            return
        if item.get("disabled"):
            return
        skin_id = _id_skin(item)
        if skin_id <= 0 or skin_id in vistos:
            return
        vistos.add(skin_id)
        skins.append(
            {
                "id": skin_id,
                "nombre": _nombre_skin(item) or f"Skin {skin_id}",
                "base": bool(item.get("isBase")),
                "chroma": chroma or _es_chroma(item),
            }
        )

    inventario = _skins_inventario(cliente, campeon_id)
    for item in inventario:
        agregar(item)
        for chroma in item.get("chromas") or []:
            if isinstance(chroma, dict):
                agregar(chroma, chroma=True)

    permitidas = _skins_permitidas_en_select(cliente)
    if permitidas:
        skins = [s for s in skins if s["id"] in permitidas]
    skins.sort(key=lambda s: (s["chroma"], s["id"]))
    return skins


def elegir_skin(
    skins: list[dict[str, Any]],
    modo: str,
    actual_id: int | None,
    ultima_id: int | None,
) -> dict[str, Any] | None:
    if not skins:
        return None
    if len(skins) == 1:
        return skins[0]
    modo = (modo or "ninguna").strip().lower()
    if modo == "aleatoria":
        candidatos = skins
        if actual_id:
            otros = [s for s in skins if s["id"] != int(actual_id)]
            if otros:
                candidatos = otros
        return random.choice(candidatos)
    if modo == "siguiente":
        ids = [s["id"] for s in skins]
        referencia = ultima_id or actual_id
        if referencia in ids:
            indice = (ids.index(int(referencia)) + 1) % len(ids)
        else:
            indice = 0
        return skins[indice]
    return None


def _sin_acentos(texto: str) -> str:
    nfd = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").lower().strip()


def buscar_skin_por_nombre(skins: list[dict[str, Any]], texto: str) -> dict[str, Any] | None:
    consulta = _sin_acentos(texto)
    if not consulta:
        return None
    exactas = [s for s in skins if _sin_acentos(s["nombre"]) == consulta]
    if exactas:
        return exactas[0]
    parciales = [s for s in skins if consulta in _sin_acentos(s["nombre"])]
    if parciales:
        return parciales[0]
    return None


def elegir_skin_desde_chat(
    skins: list[dict[str, Any]],
    argumento: str,
    actual_id: int | None,
    ultima_id: int | None,
) -> dict[str, Any] | None:
    texto = (argumento or "").strip()
    if not texto or texto.lower() in ("random", "aleatoria", "aleatorio"):
        return elegir_skin(skins, "aleatoria", actual_id, ultima_id)
    if texto.lower() in ("siguiente", "next", "sig"):
        return elegir_skin(skins, "siguiente", actual_id, ultima_id)
    if texto.isdigit():
        indice = int(texto) - 1
        if 0 <= indice < len(skins):
            return skins[indice]
    return buscar_skin_por_nombre(skins, texto)


def skin_actual_en_select(cliente: ClienteLCU) -> int:
    sesion = cliente.get("/lol-champ-select/v1/session")
    if not isinstance(sesion, dict):
        return 0
    local = sesion.get("localPlayerCellId")
    for miembro in sesion.get("myTeam") or []:
        if miembro.get("cellId") == local:
            return int(miembro.get("selectedSkinId") or 0)
    return 0


def aplicar_skin(cliente: ClienteLCU, skin_id: int) -> None:
    skin_id = int(skin_id)
    actual = skin_actual_en_select(cliente)
    if actual == skin_id:
        return
    cliente.patch("/lol-champ-select/v1/session/my-selection", {"selectedSkinId": skin_id})


def _skins_inventario(cliente: ClienteLCU, campeon_id: int) -> list[dict[str, Any]]:
    invocador = cliente.get("/lol-summoner/v1/current-summoner")
    if not isinstance(invocador, dict):
        return []
    summoner_id = invocador.get("summonerId")
    if summoner_id is None:
        return []
    datos = cliente.get(
        f"/lol-champions/v1/inventories/{summoner_id}/champions/{campeon_id}/skins"
    )
    return datos if isinstance(datos, list) else []


def _skins_permitidas_en_select(cliente: ClienteLCU) -> set[int]:
    try:
        datos = cliente.get("/lol-champ-select/v1/pickable-skin-ids")
    except ClienteNoDisponible:
        return set()
    if not isinstance(datos, list):
        return set()
    return {int(x) for x in datos if x is not None}
