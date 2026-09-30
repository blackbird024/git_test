"""Verificación del bot de oferta/demanda del usuario en GC ajustado (edges/bot_oferta_demanda_oro.md).
Uso: python -m src.report.bot_oro  ->  reports/BOT_OFERTA_DEMANDA_ORO_v1.0/ (no se sobrescribe)."""
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.cargadores import cargar_databento
from src.data.datos import inicio_fuera_de_muestra
from src.strategies import bot_oferta_demanda as bot

SALIDA = Path(__file__).resolve().parent.parent.parent / "reports" / "BOT_OFERTA_DEMANDA_ORO_v1.0"


def met(o: pd.DataFrame, capital: float) -> dict:
    if o.empty:
        return {"operaciones": 0}
    n, r = o.neto, o.r
    o = o.sort_values("t_salida")
    eq = capital + o.neto.cumsum().to_numpy()
    pk = np.maximum.accumulate(np.r_[capital, eq])[1:]
    return {"operaciones": len(o), "acierto_%": round((n > 0).mean() * 100, 1),
            "PF": round(n[n > 0].sum() / -n[n < 0].sum(), 3), "R_medio": round(r.mean(), 4),
            "t": round(r.mean() / r.std(ddof=1) * np.sqrt(len(r)), 2), "neto_$": round(n.sum(), 0),
            "max_dd_%": round(((eq - pk) / pk).min() * 100, 1), "horas_medias": round(o.horas.mean(), 1)}


def main() -> None:
    if SALIDA.exists():
        raise SystemExit(f"{SALIDA} ya existe")
    m1 = bot.ajustar_continuo(cargar_databento("GC"))
    corte = inicio_fuera_de_muestra("GC")
    filas, anual = [], None
    for nombre, cfg in {"con costes": bot.Config(),
                        "sin costes": bot.Config(spread=0.0, comision_oz_lado=0.0, deslizamiento=0.0),
                        "costes x2": bot.Config(spread=0.30, comision_oz_lado=0.07, deslizamiento=0.10)}.items():
        ops = bot.backtest(m1, cfg)
        dev, oos = ops[ops.entry_time < corte], ops[ops.entry_time >= corte]
        for tramo, o in (("desarrollo", dev), ("fuera de muestra", oos), ("completo", ops)):
            filas.append({"variante": nombre, "tramo": tramo, **met(o, cfg.capital)})
        if nombre == "con costes":
            SALIDA.mkdir(parents=True)
            ops.to_csv(SALIDA / "trades.csv", index=False)
            g = ops.groupby(pd.DatetimeIndex(ops.entry_time).year)
            anual = pd.DataFrame({"operaciones": g.size(), "neto_$": g.neto.sum().round(0), "R_medio": g.r.mean().round(3),
                                  "PF": g.neto.apply(lambda s: round(s[s > 0].sum() / -s[s < 0].sum(), 2))})
            motivos = ops.motivo.value_counts().to_dict()
            lados = ops.groupby("direction").r.agg(["count", "mean"]).round(3)
    t = pd.DataFrame(filas)
    t.to_csv(SALIDA / "summary.csv", index=False)
    anual.to_csv(SALIDA / "yearly.csv")
    (SALIDA / "README.md").write_text("\n".join([
        "# BOT_OFERTA_DEMANDA_ORO_v1.0 — verificación del bot del usuario (GC ajustado, H1)", "",
        t.to_markdown(index=False), "", "Por año (con costes):", "", anual.to_markdown(), "",
        f"Motivos de salida: {motivos}", "", "Por dirección (R medio):", "", lados.to_markdown()]), encoding="utf-8")
    print(t.to_string(index=False)); print(anual.to_string()); print(motivos); print(lados)


if __name__ == "__main__":
    main()
