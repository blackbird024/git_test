#!/usr/bin/env python3
"""Genera el banner (2560x1440) y la foto de perfil (800x800) del canal."""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import generar_short as g  # noqa: E402

NOMBRE = "CURIOSIDADES AL INSTANTE"
LEMA = "Una curiosidad nueva cada día"
OUT = Path(__file__).resolve().parent


def gradient(w, h, c1, c2):
    import numpy as np
    a, b = np.array(g.hex2rgb(c1), float), np.array(g.hex2rgb(c2), float)
    y = np.linspace(0, 1, h)[:, None, None]
    x = np.linspace(0, 1, w)[None, :, None]
    m = np.clip(0.6 * x + 0.4 * y, 0, 1)
    return Image.fromarray((a * (1 - m) + b * m).astype(np.uint8), "RGB").convert("RGBA")


def glow(img, xy, r, color, alpha):
    b = g.make_blob(r, color, alpha)
    img.paste(b, (xy[0] - r, xy[1] - r), b)


def banner():
    W, H = 2560, 1440
    img = gradient(W, H, "#1a1446", "#6a1b9a")
    for xy, r in (((500, 400), 600), ((2100, 1000), 700), ((1280, 720), 500)):
        glow(img, xy, r, (190, 120, 255), 70)
    # emojis decorativos fuera de la zona segura central (1546x423)
    deco = [("🐙", 330, 560, -12), ("🪐", 2230, 560, 10), ("🧠", 640, 1080, 8), ("🚀", 1950, 1100, -8),
            ("📜", 260, 1020, 6), ("🍌", 2330, 1050, -10), ("🦒", 1020, 300, 0), ("🍓", 1560, 290, 0)]
    for e, x, y, rot in deco:
        em = g.render_emoji(e, 190).rotate(rot, expand=True, resample=Image.BICUBIC)
        img.paste(em, (x - em.width // 2, y - em.height // 2), em)
    d = ImageDraw.Draw(img)
    f = g.font("Anton-Regular.ttf", 150)
    d.text((W / 2, 680), NOMBRE, font=f, fill=(255, 225, 77), anchor="mm", stroke_width=10, stroke_fill=(0, 0, 0))
    f2 = g.font("Montserrat-Black.ttf", 64)
    d.text((W / 2, 820), LEMA.upper(), font=f2, fill=(255, 255, 255), anchor="mm", stroke_width=6, stroke_fill=(0, 0, 0))
    img.convert("RGB").save(OUT / "banner.png")


def avatar():
    S = 800
    img = gradient(S, S, "#2a1a6e", "#8e24aa")
    glow(img, (400, 400), 380, (255, 200, 255), 80)
    em = g.render_emoji("🤯", 520)
    img.paste(em, ((S - em.width) // 2, (S - em.height) // 2 + 10), em)
    img.convert("RGB").save(OUT / "foto_perfil.png")


if __name__ == "__main__":
    banner()
    avatar()
    print("Listo: canal/banner.png y canal/foto_perfil.png")
