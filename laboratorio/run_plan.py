"""Plan financiero con 200 €/mes: escenarios a 1, 3, 5 y 10 años con supuestos explícitos.

Supuestos (editables aquí; NO son previsiones):
- Fondo de emergencia: objetivo en € (desconozco tus gastos: 3.000 € es un valor de ejemplo) con 0 % de interés real.
- Inversión: ETF UCITS del Nasdaq-100 de acumulación. Rentabilidad nominal anual en EUR simulada con Monte Carlo
  (log-normal mensual) en tres escenarios: adverso 0 %, moderado 5 %, favorable 9 %, volatilidad anual 22 %
  (el Nasdaq-100 tuvo caídas de −83 % en 2000-2002 y −35 % en 2022: los escenarios no las excluyen).
- Costes: TER 0,30 %/año; IVAFE 0,20 %/año sobre el valor (aplicable a activos financieros en el extranjero, p. ej.
  IBKR; VERIFICAR); comisión de compra 3 € por aportación (VERIFICAR la tarifa de IBKR para tu plan).
- Impuesto del 26 % sobre la plusvalía solo si se vende al final del horizonte (se muestran ambos valores).
- Topstep: costes contabilizados aparte, nunca descontados del rendimiento de la estrategia.
"""
import numpy as np
import pandas as pd

from validation.runner import new_experiment, write_manifest

MONTHLY = 200.0
EMERGENCY_TARGET = 3000.0          # EJEMPLO: pon 3-6 meses de tus gastos reales
EMERGENCY_SHARE = 1.0              # todo al fondo hasta completarlo (comprar 50 € con 3 € de comisión cuesta un 6 %)
TER, IVAFE, FEE_PER_BUY, TAX = 0.0030, 0.0020, 3.0, 0.26
SCEN = {"adverso": 0.00, "moderado": 0.05, "favorable": 0.09}
VOL = 0.22
N_SIM = 5000
SEED = 11


def simulate(years, mu, rng):
    months = years * 12
    m_mu = np.log(1 + mu) / 12 - 0.5 * (VOL ** 2) / 12
    r = np.exp(rng.normal(m_mu, VOL / np.sqrt(12), size=(N_SIM, months))) - 1
    inv = np.zeros(N_SIM)
    paid = np.zeros(N_SIM)
    emerg = 0.0
    for k in range(months):
        to_e = min(MONTHLY * EMERGENCY_SHARE, max(EMERGENCY_TARGET - emerg, 0))
        emerg += to_e
        buy = MONTHLY - to_e
        inv = inv * (1 + r[:, k]) * (1 - (TER + IVAFE) / 12)
        if buy > 0:
            inv += buy - FEE_PER_BUY
        paid += buy
    after_tax = inv - np.maximum(inv - paid, 0) * TAX
    return emerg, paid, inv, after_tax


def main():
    rng = np.random.default_rng(SEED)
    rows = []
    for years in (1, 3, 5, 10):
        for name, mu in SCEN.items():
            emerg, paid, inv, net = simulate(years, mu, rng)
            rows.append(dict(años=years, escenario=name, aportado_total=years * 12 * MONTHLY, fondo_emergencia=emerg,
                             aportado_a_inversion=paid[0], inversion_p5=np.percentile(inv, 5),
                             inversion_mediana=np.median(inv), inversion_p95=np.percentile(inv, 95),
                             tras_impuestos_si_vendes_mediana=np.median(net),
                             prob_perdida_vs_aportado=(inv < paid).mean()))
    res = pd.DataFrame(rows)
    exp = new_experiment("plan_financiero")
    res.to_csv(exp / "plan_200_eur.csv", index=False)
    write_manifest(exp, experimento="plan financiero 200 €/mes", aportacion=MONTHLY, objetivo_emergencia=EMERGENCY_TARGET,
                   escenarios=SCEN, volatilidad=VOL, ter=TER, ivafe=IVAFE, comision_compra=FEE_PER_BUY, impuesto=TAX,
                   simulaciones=N_SIM, semilla=SEED)
    pd.set_option("display.width", 250)
    print(res.round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
