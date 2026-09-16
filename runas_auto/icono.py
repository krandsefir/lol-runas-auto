from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from runas_auto.rutas import ruta_icono


def imagen_bandeja() -> Image.Image:
    ruta = ruta_icono()
    if ruta.is_file():
        return Image.open(ruta).convert("RGBA")
    return _dibujar(64)


def _dibujar(lado: int) -> Image.Image:
    img = Image.new("RGBA", (lado, lado), (10, 20, 40, 255))
    draw = ImageDraw.Draw(img)
    margen = max(2, lado // 16)
    draw.rounded_rectangle(
        (margen, margen, lado - margen - 1, lado - margen - 1),
        radius=lado // 5,
        fill=(17, 28, 51, 255),
        outline=(200, 170, 110, 255),
        width=max(2, lado // 32),
    )
    draw.ellipse(
        (lado * 0.28, lado * 0.22, lado * 0.72, lado * 0.66),
        outline=(200, 170, 110, 255),
        width=max(2, lado // 18),
    )
    cx, cy = lado // 2, int(lado * 0.78)
    draw.rectangle((cx - 2, int(lado * 0.58), cx + 1, cy), fill=(200, 170, 110, 255))
    return img


def guardar_ico(destino: Path | None = None) -> Path:
    destino = destino or ruta_icono()
    destino.parent.mkdir(parents=True, exist_ok=True)
    _dibujar(256).save(
        destino,
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    return destino
