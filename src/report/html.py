"""Informes HTML autocontenidos (los gráficos van incrustados como imágenes)."""
import base64
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm  # noqa: E402

SERIE = "#2a78d6"          # azul (serie única)
NEGATIVO = "#eb6834"       # naranja (polo negativo del divergente)
NEUTRO = "#e8e7e3"         # gris del punto medio
TEXTO = "#52514e"
REJILLA = "#dedcd6"

CSS = """
:root { --fondo:#fcfcfb; --texto:#0b0b0b; --secundario:#52514e; --borde:#dedcd6; --ok:#008300; --mal:#c0392b; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --fondo:#1a1a19; --texto:#ffffff; --secundario:#c3c2b7; --borde:#3a3935; --ok:#4fbf4f; --mal:#e66767; } }
:root[data-theme="dark"] { --fondo:#1a1a19; --texto:#ffffff; --secundario:#c3c2b7; --borde:#3a3935; --ok:#4fbf4f; --mal:#e66767; }
body { background:var(--fondo); color:var(--texto); font:15px/1.5 system-ui, sans-serif; margin:0 auto; max-width:1000px; padding:24px 16px; }
h1 { font-size:24px; margin:0 0 4px } h2 { font-size:18px; margin:32px 0 8px; border-bottom:1px solid var(--borde); padding-bottom:4px }
p, li { color:var(--secundario) } table { border-collapse:collapse; margin:8px 0; font-size:13px; display:block; overflow-x:auto }
th, td { border-bottom:1px solid var(--borde); padding:4px 10px; text-align:right } th:first-child, td:first-child { text-align:left }
img { max-width:100%; background:#fcfcfb; border-radius:6px } .veredicto { font-size:20px; font-weight:700; padding:12px 16px;
border:2px solid currentColor; border-radius:8px; display:inline-block; margin:8px 0 } .ok { color:var(--ok) } .mal { color:var(--mal) }
"""


def _png(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight", facecolor="#fcfcfb")
    plt.close(fig)
    return f'<img alt="gráfico" src="data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}">'


def _ejes(ax):
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.spines["left"].set_color(REJILLA)
    ax.spines["bottom"].set_color(REJILLA)
    ax.tick_params(colors=TEXTO, labelsize=9)
    ax.grid(axis="y", color=REJILLA, linewidth=0.6)
    ax.set_axisbelow(True)


def curva(ops: pd.DataFrame, corte: pd.Timestamp | None = None, titulo: str = "Saldo acumulado (USD)") -> str:
    fig, ax = plt.subplots(figsize=(9, 3.4))
    t = pd.DatetimeIndex(ops.t_entrada).tz_localize(None)
    ax.plot(t, ops.neto.cumsum(), color=SERIE, linewidth=2)
    if corte is not None:
        ax.axvspan(corte, t.max(), color=NEUTRO, alpha=0.6, linewidth=0)
        ax.text(corte, ax.get_ylim()[1], "  fuera de muestra", va="top", color=TEXTO, fontsize=9)
    ax.axhline(0, color=TEXTO, linewidth=0.8)
    ax.set_title(titulo, loc="left", color=TEXTO, fontsize=11)
    _ejes(ax)
    return _png(fig)


def barras_anuales(tabla: pd.DataFrame, columna: str = "neto_$") -> str:
    fig, ax = plt.subplots(figsize=(9, 3))
    v = tabla[columna].astype(float)
    ax.bar(v.index.astype(str), v, color=SERIE, width=0.6)
    ax.axhline(0, color=TEXTO, linewidth=0.8)
    for x, y in zip(v.index.astype(str), v):
        ax.annotate(f"{y:,.0f}", (x, y), ha="center", va="bottom" if y >= 0 else "top", fontsize=8, color=TEXTO)
    ax.set_title("Beneficio neto por año (USD)", loc="left", color=TEXTO, fontsize=11)
    _ejes(ax)
    return _png(fig)


def mapas_calor(pf: pd.DataFrame, filas: str, columnas: str, paneles: str) -> str:
    """Profit factor por combinación de parámetros; escala divergente centrada en PF = 1."""
    valores = sorted(pf[paneles].unique())
    fig, axes = plt.subplots(1, len(valores), figsize=(4 * len(valores), 3.4), squeeze=False)
    cmap = LinearSegmentedColormap.from_list("div", [NEGATIVO, NEUTRO, SERIE])
    vmax = max(pf.pf.max(), 1.01)
    norma = TwoSlopeNorm(vmin=min(pf.pf.min(), 0.99), vcenter=1.0, vmax=vmax)
    for ax, v in zip(axes[0], valores):
        sub = pf[pf[paneles] == v].pivot(index=filas, columns=columnas, values="pf")
        ax.imshow(sub.to_numpy(), cmap=cmap, norm=norma)
        ax.set_xticks(range(len(sub.columns)), [f"{c:g}" for c in sub.columns])
        ax.set_yticks(range(len(sub.index)), [f"{c:g}" for c in sub.index])
        for i in range(sub.shape[0]):
            for j in range(sub.shape[1]):
                ax.text(j, i, f"{sub.iat[i, j]:.2f}", ha="center", va="center", fontsize=10, color="#0b0b0b")
        ax.set_xlabel(columnas, color=TEXTO)
        ax.set_ylabel(filas, color=TEXTO)
        ax.set_title(f"{paneles} = {v:g}", color=TEXTO, fontsize=10)
        ax.tick_params(colors=TEXTO)
    fig.suptitle("Profit factor (naranja < 1 < azul)", x=0.01, ha="left", color=TEXTO, fontsize=11)
    return _png(fig)


def histograma_mc(dd: np.ndarray, p95: float) -> str:
    fig, ax = plt.subplots(figsize=(9, 3))
    ax.hist(dd, bins=40, color=SERIE, edgecolor="#fcfcfb", linewidth=1)
    ax.axvline(p95, color=TEXTO, linestyle="--", linewidth=1.2)
    ax.text(p95, ax.get_ylim()[1] * 0.95, f"  percentil 95: {p95:,.0f} $", color=TEXTO, fontsize=9, va="top")
    ax.set_title("Drawdown máximo en 1.000 órdenes aleatorias de las operaciones (USD)", loc="left", color=TEXTO, fontsize=11)
    _ejes(ax)
    return _png(fig)


def tabla(df: pd.DataFrame, indice: bool = True) -> str:
    return df.to_html(index=indice, border=0, float_format=lambda x: f"{x:,.3f}".rstrip("0").rstrip("."))


def pagina(titulo: str, subtitulo: str, veredicto: str, aprobada: bool, secciones: list[tuple[str, str]]) -> str:
    cuerpo = "".join(f"<h2>{h}</h2>{c}" for h, c in secciones)
    clase = "ok" if aprobada else "mal"
    return (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" '
            f'content="width=device-width, initial-scale=1"><title>{titulo}</title><style>{CSS}</style></head>'
            f'<body><h1>{titulo}</h1><p>{subtitulo}</p><div class="veredicto {clase}">{veredicto}</div>{cuerpo}</body></html>')
