# Combinaciones de estrategias con fundamento (oro): resultado

Pre-registro: `docs/COMBO_PREREG.md` (commit `4ff472f`, más la corrección de datos documentada). Datos: CME GC (Databento),
ajuste por ratio, 2011-05 → 2026-09. Cada estrategia apunta a un 10 % de volatilidad anual; los costes están incluidos.

## VERDICT: NO HAY EDGE

La cartera de las 5 estrategias (la única hipótesis confirmatoria) falla los 4 criterios no contaminados.

| Tramo | Sharpe | Rentabilidad anual | Alfa frente a comprar y mantener (t, Newey-West) |
|---|---|---|---|
| TRAIN 2011-2020 | **−0.70** | −3.9 % | −2.20 |
| VALIDATION 2020-2023 | **−1.27** | −7.7 % | −2.46 |
| TEST 2023-2026 (contaminado) | +1.03 | +7.2 % | **+0.16** (beta 0.52) |

- Desplazamiento circular (500 permutaciones), TRAIN+VALIDATION: **p = 0.55**. El timing de las señales no aporta nada.
- El TEST positivo es **beta al oro**, no habilidad: el alfa frente a comprar y mantener es cero (t = 0.16). El oro subió fuerte en
  2024-2025 y cualquier exposición larga ganó.

## Por estrategia (Sharpe)

| Estrategia | TRAIN | VALIDATION | TEST |
|---|---|---|---|
| S1 TSMOM 12 meses | 0.06 | −0.57 | 1.17 |
| S2 TSMOM 1 mes | −0.09 | −0.65 | 0.32 |
| S3 Tendencia MA200 | 0.21 | −0.53 | 1.06 |
| S4 Momentum intradía | −1.68 | −0.98 | −0.64 |
| S5 Deriva asiática | −0.65 | −0.98 | 1.28 |
| Comprar y mantener | 0.08 | 0.32 | 1.19 |

## Las 31 combinaciones (descriptivo)
Ninguna de las 31 tiene Sharpe positivo con fuerza en TRAIN+VALIDATION. La mejor es S3 sola, con 0.01, y su alfa frente a comprar y mantener
es t = 0.01. En TEST casi todas son positivas porque el oro subió. Tabla completa: `ALL_31_COMBINATIONS.csv`.

## POST-HOC OBSERVATION (no se incorpora a nada)
S4 (momentum intradía) es **consistentemente negativo** en los tres tramos. Su inversa (reversión intradía) parecería buena,
pero esa conclusión sale de mirar los resultados: habría que pre-registrarla y probarla en datos nuevos (otro activo o en vivo).
El TEST de oro ya no sirve como árbitro limpio.

## Lectura
Ni la minería masiva (50.000 reglas) ni las estrategias clásicas con fundamento, combinadas de todas las formas posibles, dan
en oro un edge que supere a simplemente comprar oro con el mismo riesgo. Lo que en 2023-2026 parece funcionar es exposición
a la subida del oro.
