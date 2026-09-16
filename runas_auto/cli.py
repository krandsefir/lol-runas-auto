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
    if tipo == "sin_configurar":
        print(f"{evento.get('campeon_nombre')} no tiene página asignada.")
        return
    if tipo == "cliente":
        print("Cliente conectado." if evento.get("conectado") else "Cliente desconectado.")
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
