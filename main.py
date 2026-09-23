import sys
import traceback


def _registrar_error(exc: BaseException | None = None) -> str:
    try:
        from runas_auto.log import registrar_excepcion

        return registrar_excepcion(exc)
    except Exception:
        return traceback.format_exc()


def _avisar(texto: str) -> None:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, texto[:1000], "LoL Runas Auto", 0x10)
    except Exception:
        pass


def lanzar() -> int:
    from runas_auto.arranque import (
        mostrar_ventana_existente,
        pedir_mostrar_ventana,
        reclamar_instancia_unica,
    )
    from runas_auto.log import registrar

    registrar("Arranque")
    if not reclamar_instancia_unica():
        registrar("Ya había una instancia; pido mostrar la ventana.")
        pedir_mostrar_ventana()
        mostrar_ventana_existente()
        return 0

    if "--consola" in sys.argv:
        from runas_auto.cli import main

        return main()

    from ui.ventana import main

    return main(iniciar_oculto="--bandeja" in sys.argv)


if __name__ == "__main__":
    try:
        raise SystemExit(lanzar())
    except SystemExit:
        raise
    except Exception as exc:
        detalle = _registrar_error(exc)
        _avisar(f"Error al iniciar:\n{detalle}")
        raise
