from PIL import Image

from src.branding import preview as pv


def test_contraste_valores_conocidos():
    assert round(pv.contraste("#000000", "#FFFFFF"), 1) == 21.0
    assert pv.contraste("#777777", "#777777") == 1.0


def test_pares_de_texto_de_la_marca_son_legibles():
    col = pv.config()["marca"]["colores"]
    for texto, fondo in pv.PARES:
        if texto == "gris":                       # texto secundario: solo en tamaños grandes
            assert pv.contraste(col[texto], col[fondo]) >= 3, (texto, fondo)
        else:
            assert pv.contraste(col[texto], col[fondo]) >= 4.5, (texto, fondo)


def test_generar_piezas_con_tamanos_correctos(tmp_path):
    rutas = {p.stem: p for p in pv.generar(tmp_path)}
    assert Image.open(rutas["miniatura_ejemplo"]).size == (1280, 720)
    assert Image.open(rutas["banner"]).size == (2560, 1440)
    assert rutas["miniatura_ejemplo"].stat().st_size < 2 * 1024 * 1024     # límite de YouTube para miniaturas


def test_titulo_ajustado_cabe_en_el_ancho():
    from PIL import ImageDraw
    cfg = pv.config()
    d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    lineas = ["¿Por qué", "QWERTY?", "UN TÍTULO BASTANTE MÁS LARGO"]
    f = pv.ajustar(d, lineas, "titulos", 520, 130, cfg)
    assert max(d.textlength(l, font=f) for l in lineas) <= 520
