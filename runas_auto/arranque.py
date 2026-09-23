from __future__ import annotations

import ctypes
import subprocess
import sys
from pathlib import Path

from runas_auto.rutas import congelado, dir_datos, ruta_ejecutable

NOMBRE_ACCESO = "LoLRunasAuto.lnk"
MUTEX_NOMBRE = "Local\\LoLRunasAutoSingleton"
ERROR_YA_EXISTE = 183
SW_RESTORE = 9


def carpeta_inicio() -> Path:
    return (
        Path.home()
        / "AppData"
        / "Roaming"
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
    )


def ruta_acceso_inicio() -> Path:
    return carpeta_inicio() / NOMBRE_ACCESO


def esta_en_inicio() -> bool:
    return ruta_acceso_inicio().is_file()


def _destino_atajo() -> tuple[str, str, str]:
    if congelado():
        exe = ruta_ejecutable()
        return str(exe), "--bandeja", str(exe.parent)
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.exists():
        pythonw = Path(sys.executable)
    script = Path(__file__).resolve().parent.parent / "main.py"
    return str(pythonw), f'"{script}" --bandeja', str(script.parent)


def crear_acceso(destino: Path, target: str, argumentos: str, trabajo: str) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino_ps = str(destino).replace("'", "''")
    target_ps = target.replace("'", "''")
    args_ps = argumentos.replace("'", "''")
    trabajo_ps = trabajo.replace("'", "''")
    comando = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%s'); "
        "$s.TargetPath = '%s'; "
        "$s.Arguments = '%s'; "
        "$s.WorkingDirectory = '%s'; "
        "$s.WindowStyle = 7; "
        "$s.Description = 'LoL Runas Auto'; "
        "$s.Save()"
    ) % (destino_ps, target_ps, args_ps, trabajo_ps)
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", comando],
        capture_output=True,
        text=True,
        timeout=8,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def crear_acceso_escritorio(exe: Path) -> Path:
    escritorio = Path.home() / "Desktop"
    if not escritorio.is_dir():
        escritorio = Path.home() / "Escritorio"
    acceso = escritorio / NOMBRE_ACCESO
    crear_acceso(acceso, str(exe), "", str(exe.parent))
    return acceso


def activar_inicio_windows(activo: bool) -> None:
    acceso = ruta_acceso_inicio()
    if not activo:
        if acceso.exists():
            acceso.unlink()
        return
    destino, argumentos, trabajo = _destino_atajo()
    crear_acceso(acceso, destino, argumentos, trabajo)


_mutex_handle = None


def reclamar_instancia_unica() -> bool:
    """True si esta es la instancia nueva. False si ya había otra."""
    global _mutex_handle
    kernel32 = ctypes.windll.kernel32
    kernel32.SetLastError(0)
    _mutex_handle = kernel32.CreateMutexW(None, False, MUTEX_NOMBRE)
    return int(kernel32.GetLastError()) != ERROR_YA_EXISTE


def mostrar_ventana_existente(titulo: str = "LoL Runas Auto") -> bool:
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, titulo)
    if not hwnd:
        return False
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    return True


def ruta_pedido_mostrar() -> Path:
    return dir_datos() / "mostrar.flag"


def pedir_mostrar_ventana() -> None:
    try:
        ruta_pedido_mostrar().write_text("1", encoding="utf-8")
    except OSError:
        pass


def consumir_pedido_mostrar() -> bool:
    ruta = ruta_pedido_mostrar()
    if not ruta.exists():
        return False
    try:
        ruta.unlink()
    except OSError:
        return True
    return True
