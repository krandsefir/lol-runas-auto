from __future__ import annotations

from typing import Any

from runas_auto.lcu import ClienteLCU, ClienteNoDisponible


def listar_paginas(cliente: ClienteLCU) -> list[dict[str, Any]]:
    datos = cliente.get("/lol-perks/v1/pages")
    if not isinstance(datos, list):
        return []
    paginas: list[dict[str, Any]] = []
    for item in datos:
        if item.get("isTemporary"):
            continue
        paginas.append(
            {
                "id": int(item.get("id")),
                "nombre": str(item.get("name") or f"Página {item.get('id')}"),
                "actual": bool(item.get("current")),
                "valida": bool(item.get("isValid", True)),
                "editable": bool(item.get("isEditable", True)),
            }
        )
    paginas.sort(key=lambda p: (not p["actual"], p["nombre"].lower()))
    return paginas


def pagina_actual(cliente: ClienteLCU) -> dict[str, Any] | None:
    datos = cliente.get("/lol-perks/v1/currentpage")
    if not isinstance(datos, dict):
        return None
    return {
        "id": int(datos.get("id")),
        "nombre": str(datos.get("name") or ""),
        "actual": True,
    }


def activar_pagina(cliente: ClienteLCU, pagina_id: int) -> dict[str, Any]:
    pagina_id = int(pagina_id)
    actual = pagina_actual(cliente)
    if actual and actual["id"] == pagina_id:
        return actual

    try:
        cliente.put("/lol-perks/v1/currentpage", pagina_id)
    except ClienteNoDisponible:
        cliente.put("/lol-perks/v1/currentpage", {"id": pagina_id})

    actual = pagina_actual(cliente)
    if actual and actual["id"] == pagina_id:
        return actual
    raise ClienteNoDisponible(f"No pude activar la página de runas {pagina_id}.")


def resolver_pagina(
    cliente: ClienteLCU,
    pagina_id: int | None,
    pagina_nombre: str | None,
) -> dict[str, Any] | None:
    paginas = listar_paginas(cliente)
    if pagina_id is not None:
        for pagina in paginas:
            if pagina["id"] == int(pagina_id):
                return pagina
    if pagina_nombre:
        nombre = pagina_nombre.strip().lower()
        for pagina in paginas:
            if pagina["nombre"].strip().lower() == nombre:
                return pagina
    return None
