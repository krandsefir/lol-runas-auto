import sys
import traceback


def _registrar_error(exc: BaseException) -> None:
    try:
        from runas_auto.rutas import dir_datos

        ruta = dir_datos() / "error.log"
        ruta.write_text(
            "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            encoding="utf-8",
        )
    except Exception:
        pass


def lanzar() -> int:
    from runas_auto.arranque import mostrar_ventana_existente, reclamar_instancia_unica

    if not reclamar_instancia_unica():
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
        _registrar_error(exc)
        raise
