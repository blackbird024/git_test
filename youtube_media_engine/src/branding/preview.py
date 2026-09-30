"""Vista previa de la identidad visual (Fase 2): paleta con contraste, logo, miniatura de ejemplo y banner.

Todo se dibuja en código con las fuentes OFL de assets/fonts/, sin imágenes de terceros.
Uso: python main.py brand-preview  ->  reports/marca/*.png
"""
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "reports" / "marca"


def config() -> dict:
    return yaml.safe_load((RAIZ / "config" / "channel.yaml").read_text())


def fuente(clave: str, tam: int, cfg: dict) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(RAIZ / cfg["marca"]["tipografia"][clave]), tam)


def _rgb(h: str) -> tuple[int, int, int]:
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def luminancia(h: str) -> float:
    c = [v / 255 for v in _rgb(h)]
    c = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contraste(a: str, b: str) -> float:
    """Relación de contraste WCAG 2.x (1 a 21). Texto normal: >= 4,5; texto grande: >= 3."""
    la, lb = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


MARGEN = 60          # margen de seguridad de la miniatura (px)

# Combinaciones de texto sobre fondo que usa la marca
PARES = [("tinta", "papel"), ("papel", "tinta"), ("papel", "sello"), ("papel", "plano"), ("tinta", "ocre"),
         ("sello", "papel"), ("gris", "papel")]


def _centrado(d: ImageDraw.ImageDraw, xy, texto, f, relleno):
    x0, y0, x1, y1 = d.textbbox((0, 0), texto, font=f)
    d.text((xy[0] - (x1 - x0) / 2 - x0, xy[1] - (y1 - y0) / 2 - y0), texto, font=f, fill=relleno)


def paleta(cfg: dict) -> Image.Image:
    col = cfg["marca"]["colores"]
    im = Image.new("RGB", (1400, 560), col["papel"])
    d = ImageDraw.Draw(im)
    d.text((40, 30), "Paleta y contraste (WCAG)", font=fuente("subtitulos", 40, cfg), fill=col["tinta"])
    for i, (nombre, h) in enumerate(col.items()):
        x = 40 + i * 225
        d.rectangle([x, 100, x + 200, 260], fill=h, outline=col["tinta"], width=2)
        d.text((x, 272), f"{nombre}  {h}", font=fuente("texto_semibold", 22, cfg), fill=col["tinta"])
    for i, (t, f) in enumerate(PARES):
        x, y = 40 + (i % 4) * 335, 330 + (i // 4) * 110
        d.rectangle([x, y, x + 310, y + 90], fill=col[f])
        r = contraste(col[t], col[f])
        d.text((x + 16, y + 12), f"{t} / {f}", font=fuente("etiquetas", 24, cfg), fill=col[t])
        d.text((x + 16, y + 50), f"{r:.1f}:1 {'✓ texto' if r >= 4.5 else '✓ solo grande' if r >= 3 else '✗'}",
               font=fuente("texto_semibold", 22, cfg), fill=col[t])
    return im


def logo(cfg: dict, tam: int = 800, fondo: str | None = "tinta") -> Image.Image:
    """Sello circular con 'v1', la versión 1 de todo. `fondo=None` lo deja transparente."""
    col = cfg["marca"]["colores"]
    im = Image.new("RGBA", (tam, tam), col[fondo] if fondo else (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    m = tam * 0.08
    d.ellipse([m, m, tam - m, tam - m], fill=col["sello"])
    d.ellipse([m * 1.9, m * 1.9, tam - m * 1.9, tam - m * 1.9], outline=col["papel"], width=max(4, tam // 90))
    _centrado(d, (tam / 2, tam / 2), "v1", fuente("titulos_cursiva", int(tam * 0.42), cfg), col["papel"])
    return im


def _teclado(d, x, y, ancho, col, cfg):
    filas = ["QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"]
    t = ancho / 10.6
    for i, fila in enumerate(filas):
        for j, letra in enumerate(fila):
            kx, ky = x + i * t * 0.5 + j * t, y + i * t * 1.08
            resalta = i == 0 and j < 6
            d.rounded_rectangle([kx, ky, kx + t * 0.9, ky + t * 0.9], radius=t * 0.14,
                                fill=col["papel"] if resalta else col["plano"], outline=col["papel"], width=3)
            _centrado(d, (kx + t * 0.45, ky + t * 0.45), letra, fuente("etiquetas", int(t * 0.5), cfg),
                      col["tinta"] if resalta else col["papel"])


def ajustar(d: ImageDraw.ImageDraw, lineas: list[str], clave: str, ancho_max: int, tam_max: int, cfg: dict):
    """Mayor tamaño de fuente con el que todas las líneas caben en `ancho_max` píxeles."""
    tam = tam_max
    while tam > 10:
        f = fuente(clave, tam, cfg)
        if max(d.textlength(l, font=f) for l in lineas) <= ancho_max:
            return f
        tam -= 4
    raise ValueError("El texto no cabe ni con la fuente mínima")


def miniatura_ejemplo(cfg: dict) -> Image.Image:
    """Sistema de miniatura: objeto dibujado a la izquierda, 2-4 palabras grandes, un sello rojo como pregunta."""
    col = cfg["marca"]["colores"]
    im = Image.new("RGB", (1280, 720), col["tinta"])
    d = ImageDraw.Draw(im)
    for gx in range(0, 1280, 40):                                   # retícula de plano técnico, sutil
        d.line([(gx, 0), (gx, 720)], fill="#22232B", width=1)
    for gy in range(0, 720, 40):
        d.line([(0, gy), (1280, gy)], fill="#22232B", width=1)
    _teclado(d, 50, 250, 620, col, cfg)
    f = ajustar(d, ["¿Por qué", "QWERTY?"], "titulos", 1280 - 700 - MARGEN, 130, cfg)
    d.text((700, 150), "¿Por qué", font=f, fill=col["papel"])
    d.text((700, 290), "QWERTY?", font=f, fill=col["ocre"])
    # sello rotado
    s = Image.new("RGBA", (420, 150), (0, 0, 0, 0))
    ds = ImageDraw.Draw(s)
    ds.rounded_rectangle([6, 6, 414, 144], radius=18, outline=col["sello"], width=10)
    _centrado(ds, (210, 76), "¿MITO?", fuente("etiquetas", 84, cfg), col["sello"])
    s = s.rotate(8, expand=True, resample=Image.BICUBIC)
    im.paste(s, (760, 470), s)
    d.ellipse([1180, 20, 1260, 100], fill=col["sello"])            # marca de canal pequeña y constante
    _centrado(d, (1220, 60), "v1", fuente("titulos_cursiva", 44, cfg), col["papel"])
    return im


def banner(cfg: dict) -> Image.Image:
    """2560x1440. Zona segura para todos los dispositivos: 1546x423 centrada."""
    col = cfg["marca"]["colores"]
    im = Image.new("RGB", (2560, 1440), col["papel"])
    d = ImageDraw.Draw(im)
    for gx in range(0, 2560, 64):
        d.line([(gx, 0), (gx, 1440)], fill="#E6DCC8", width=2)
    for gy in range(0, 1440, 64):
        d.line([(0, gy), (2560, gy)], fill="#E6DCC8", width=2)
    x0, y0 = (2560 - 1546) // 2, (1440 - 423) // 2
    lg = logo(cfg, 300, fondo=None)
    im.paste(lg, (x0 + 20, y0 + 60), lg)
    d.text((x0 + 360, y0 + 70), cfg["canal"]["nombre"], font=fuente("titulos", 150, cfg), fill=col["tinta"])
    d.text((x0 + 366, y0 + 260), cfg["canal"]["lema"], font=fuente("texto_semibold", 40, cfg), fill=col["plano"])
    return im


def generar(salida: Path = SALIDA) -> list[Path]:
    cfg = config()
    salida.mkdir(parents=True, exist_ok=True)
    piezas = {"paleta": paleta, "logo": logo, "miniatura_ejemplo": miniatura_ejemplo, "banner": banner}
    rutas = []
    for nombre, f in piezas.items():
        p = salida / f"{nombre}.png"
        f(cfg).convert("RGB").save(p, optimize=True)
        rutas.append(p)
    return rutas
