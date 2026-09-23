"""Punto de entrada en consola. La GUI va en ui/."""

from __future__ import annotations

import json
import sys

from runas_auto.lcu import ClienteNoDisponible
from runas_auto.servicio import ServicioRunas
from runas_auto.vigilancia import esperar_interrupcion


def _imprimir_evento(evento: dict) -> None:
    tipo = evento.get("tipo")
    if tipo == "aplicado":
        print(
            f"Aplicadas runas '{evento.get('pagina_nombre')}' "
            f"para {evento.get('campeon_nombre')}."
        )
        return
    if tipo == "skin":
        quien = evento.get("usuario")
        if quien:
            print(
                f"{quien} eligió '{evento.get('skin_nombre')}' "
                f"para {evento.get('campeon_nombre')}."
            )
        else:
            print(
                f"Skin '{evento.get('skin_nombre')}' para {evento.get('campeon_nombre')}."
            )
        return
    if tipo == "twitch":
        estado = "conectado" if evento.get("conectado") else "desconectado"
        extra = evento.get("mensaje")
        print(f"Twitch {estado}" + (f": {extra}" if extra else "."))
        return
    if tipo == "sin_configurar":
        print(f"{evento.get('campeon_nombre')} no tiene página asignada.")
        return
    if tipo == "cliente":
        print("Cliente conectado." if evento.get("conectado") else "Cliente desconectado.")
        return
    if tipo == "reporte":
        print(evento.get("mensaje") or "Reporte de la partida enviado.")
        return
    if tipo == "fase":
        print(f"Fase: {evento.get('fase')}")
        return
    if tipo == "error":
        print(f"Error: {evento.get('mensaje')}")
        return
    print(json.dumps(evento, ensure_ascii=False))


def main() -> int:
    servicio = ServicioRunas()
    estado = servicio.estado()
    if estado["conectado"]:
        print(f"Conectado como {estado.get('invocador') or 'invocador'}.")
    else:
        print("Cliente de LoL no detectado. Lo seguiré buscando.")

    print(f"Campeones configurados: {estado['configurados']}")
    for item in servicio.configurados():
        print(f"  - {item.get('campeon_nombre')}: {item.get('pagina_nombre')}")

    twitch = servicio.twitch()
    if twitch.get("habilitado") and twitch.get("canal"):
        extra = f"Twitch: escuchando #{twitch['canal']} ({twitch.get('comando') or '!skin'})"
        if twitch.get("puede_hablar"):
            extra += f", responde como {twitch.get('login')}."
        else:
            extra += ". Sin sesión: no responde en el chat."
        print(extra)
    else:
        print("Twitch: desactivado. Actívalo en la ventana con tu canal.")

    try:
        servicio.iniciar(_imprimir_evento)
    except ClienteNoDisponible as exc:
        print(exc)
        return 1

    print("Vigilando champ select. Ctrl+C para salir.")
    print("La interfaz gráfica va en la carpeta ui/.")
    esperar_interrupcion()
    servicio.detener()
    return 0


if __name__ == "__main__":
    sys.exit(main())
