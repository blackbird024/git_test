"""Análisis complementario del sistema B (reglas congeladas, ejecución next_open):
1. IC bootstrap y concentración fuera de muestra (validación + prueba).
2. Fiscalidad italiana simplificada: ETF armonizado → plusvalías al 26 % como "redditi di capitale"; las minusvalías
   son "redditi diversi" y NO compensan plusvalías de ETF (se suponen perdidas: escenario conservador).
   Comprar y mantener un ETF de acumulación difiere el impuesto hasta la venta. PENDIENTE de confirmación profesional.
3. RSI(2) sobre NQ diario (futuros, sesión regular) para comparar con la versión sobre QQQ.
4. MNQ como vehículo swing: pérdida monetaria del stop de 2×ATR20 y huecos nocturnos por contrato.
"""
import numpy as np
import pandas as pd

from backtests.swing import SwingCost, equity, simulate, stats
from data.loaders import daily_from_sessions, etf_daily, sessions
from run_sistema_b import LAST, cost_scenarios
from strategies.swing import SWING, atr
from validation.metrics import block_bootstrap_mean
from validation.runner import new_experiment, periods, write_manifest

TAX = 0.26


def after_tax_trades(t):
    r = t["ret"]
    return np.where(r > 0, r * (1 - TAX), r)


def main():
    d = etf_daily("QQQ", adjusted=True, last=LAST)
    per = periods("swing", include_test=True)
    a_oos, b_oos = per["validacion"][0], per["prueba"][1]
    cost = cost_scenarios()["capital 10k"]
    out = {}
    rows = []
    for name in ("B1 Ruptura 20 sesiones", "B3 RSI(2) Connors (reversión)", "B4 Retroceso a EMA20 en tendencia"):
        fn, p = SWING[name]
        t = simulate(d, fn(d, **p), cost, "next_open")
        o = t[(t.entrada >= a_oos) & (t.entrada <= b_oos)]
        lo, hi = block_bootstrap_mean(o["ret"].to_numpy(), block=3)
        r = o["ret"]
        top10 = r.nlargest(10).sum() / r.sum() if r.sum() > 0 else np.nan
        by_year = o.groupby(o.entrada.dt.year)["ret"].sum()
        # fiscalidad: capital compuesto operación a operación
        full = t[t.entrada >= per["desarrollo"][0]]
        g_pre = np.prod(1 + full["ret"])
        g_post = np.prod(1 + after_tax_trades(full))
        yrs = (d.index[-1] - full.entrada.iloc[0]).days / 365.25
        rows.append(dict(estrategia=name, n_oos=len(o), esperanza_oos=r.mean(), ic90_bajo=lo, ic90_alto=hi,
                         top10_pct=top10, mejor_año_pct=by_year.max() / r.sum() if r.sum() > 0 else np.nan,
                         cagr_antes_impuestos=g_pre ** (1 / yrs) - 1, cagr_despues_impuestos=g_post ** (1 / yrs) - 1))
    bh = d["close"].loc["2016-01-04":]
    yrs = (bh.index[-1] - bh.index[0]).days / 365.25
    g = bh.iloc[-1] / bh.iloc[0]
    rows.append(dict(estrategia="Comprar y mantener (ETF de acumulación, impuesto solo al vender al final)",
                     cagr_antes_impuestos=g ** (1 / yrs) - 1, cagr_despues_impuestos=(1 + (g - 1) * (1 - TAX)) ** (1 / yrs) - 1))
    res = pd.DataFrame(rows)

    # 3. RSI(2) sobre NQ diario
    S = sessions()
    nq = daily_from_sessions(S)
    nq.index = pd.to_datetime(nq.index)
    fn, p = SWING["B3 RSI(2) Connors (reversión)"]
    t_nq = simulate(nq, fn(nq, **p), SwingCost(0.0001, 0, 10_000), "next_open")
    rsi_nq = []
    for k, (a, b) in periods("swing", True).items():
        tk = t_nq[(t_nq.entrada >= a) & (t_nq.entrada <= b)]
        if len(tk):
            r = tk["ret"]
            rsi_nq.append(dict(periodo=k, n=len(tk), pf=r[r > 0].sum() / -r[r < 0].sum(), esperanza=r.mean()))
    rsi_nq = pd.DataFrame(rsi_nq)

    # 4. MNQ swing: riesgo monetario por contrato
    a20 = atr(nq, 20)
    stop_usd = 2 * a20 * 2.0
    gap = (nq["open"] - nq["close"].shift(1)) * 2.0
    mnq = dict(stop_2atr_usd_mediana=stop_usd.median(), stop_2atr_usd_ultimo=stop_usd.iloc[-1],
               stop_2atr_usd_p90=stop_usd.quantile(0.9), hueco_nocturno_peor_usd=gap.min(),
               hueco_nocturno_p1_usd=gap.quantile(0.01), nocional_ultimo_usd=nq["close"].iloc[-1] * 2.0)

    exp = new_experiment("swing_extra")
    res.to_csv(exp / "swing_oos_y_fiscalidad.csv", index=False)
    rsi_nq.to_csv(exp / "rsi2_nq_diario.csv", index=False)
    pd.Series(mnq).to_csv(exp / "mnq_swing_riesgo.csv")
    write_manifest(exp, experimento="sistema B complementario", impuesto=TAX, ejecucion="next_open",
                   coste=cost.__dict__, nota_fiscal="simplificación; requiere confirmación de un asesor fiscal italiano")
    pd.set_option("display.width", 250)
    print(res.round(4).to_string(index=False))
    print(rsi_nq.round(4).to_string(index=False))
    print(pd.Series(mnq).round(0))
    print("→", exp)


if __name__ == "__main__":
    main()
