"""Genera el .exe, lo instala y lo deja en el inicio de Windows."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from runas_auto.arranque import crear_acceso, crear_acceso_escritorio
from runas_auto.icono import guardar_ico
from runas_auto.rutas import dir_instalacion


def main() -> int:
    raiz = Path(__file__).resolve().parent
    guardar_ico(raiz / "assets" / "icon.ico")
    comando = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(raiz / "LoLRunasAuto.spec")]
    print("Generando ejecutable…")
    resultado = subprocess.run(comando, cwd=raiz)
    if resultado.returncode != 0:
        return resultado.returncode

    origen = raiz / "dist" / "LoLRunasAuto"
    destino = dir_instalacion()
    subprocess.run(
        ["taskkill", "/F", "/IM", "LoLRunasAuto.exe"],
        capture_output=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if destino.exists():
        shutil.rmtree(destino, ignore_errors=True)
        if destino.exists():
            shutil.rmtree(destino)
    shutil.copytree(origen, destino)
    exe = destino / "LoLRunasAuto.exe"
    crear_acceso_escritorio(exe)
    acceso_inicio = (
        Path.home()
        / "AppData"
        / "Roaming"
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
        / "LoLRunasAuto.lnk"
    )
    crear_acceso(acceso_inicio, str(exe), "--bandeja", str(destino))
    print(f"Ejecutable: {exe}")
    print("Atajo en el Escritorio y en Inicio de Windows.")
    subprocess.Popen([str(exe), "--bandeja"], cwd=str(destino))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
