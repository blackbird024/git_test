# Generador de estrategias en oro: resultado

Pre-registro: `docs/GENERATOR_PREREG.md` (commit `fc5d093`). Lista congelada antes de TEST: commit `b889e58`.
Datos: CME GC (Databento) H1, 2010-06 → 2026-09. Coste: 0.37 USD/oz por operación.

## VERDICT: NO SE ENCONTRÓ EDGE

No se cumple ninguno de los tres criterios pre-registrados.

| Criterio | Resultado | ¿Cumple? |
|---|---|---|
| Supervivientes en oro real > cada serie nula (paso 3) | 1 frente a 33 / 5 / 7 | **No** |
| Cartera TEST con expectativa > 0 y p < 0.05 | +0.046 R, 82 trades, p = 0.35 | **No** |
| Al menos una estrategia significativa en TEST tras Holm | p_holm = 0.35 | **No** |

## El embudo

| Serie | Estrategias | Pasan TRAIN | Pasan robustez | Pasan VALIDATION | "TEST" de las supervivientes |
|---|---|---|---|---|---|
| **Oro real** | 50.000 | 31 | 18 | **1** | +0.046 R (82 trades, p = 0.35) |
| Nula 1 (velas barajadas) | 50.000 | 100 | 76 | 33 | −0.050 R (6.728 trades) |
| Nula 2 | 50.000 | 34 | 14 | 5 | +0.066 R (410 trades, p = 0.17) |
| Nula 3 | 50.000 | 47 | 28 | 7 | +0.022 R (963 trades) |

**Precios sin ninguna estructura producen tantas o más estrategias "rentables y robustas" que el oro real.** Las
supervivientes nulas, por construcción, no pueden tener edge, y aun así en su "TEST" muestran resultados del mismo
orden que la superviviente real.

## La única superviviente

`SHORT [4 cierres bajistas seguidos & inside bar & ATR14/ATR100 < 1.2] SL = 3×ATR, sin TP, salida a las 24 h`

| | Trades | Expectativa | PF |
|---|---|---|---|
| TRAIN | 242 | +0.129 R | 1.30 |
| VALIDATION | 75 | +0.087 R | 1.18 |
| TEST | 82 | +0.046 R | 1.11 (p = 0.35) |

La degradación TRAIN → VALIDATION → TEST es la típica de una superviviente de minería de datos.

## Deflated Sharpe
La mejor estrategia de TRAIN (Sharpe por trade 0.186 con 241 trades, `SHORT [RSI14 < 20]`) tiene una
probabilidad deflactada de **0.024**: después de 50.000 intentos, su Sharpe es exactamente lo esperable por azar. Haría falta
superar 0.95.

## Lectura
Con 50.000 intentos, los filtros típicos (PF ≥ 1.2, ≥ 200 trades, robustez por vecinos, costes ×2, entrada retrasada y
validación fuera de muestra) **no separan el edge del ruido** en este experimento. Lo demuestra que el mismo embudo deja pasar
estrategias en datos aleatorios. Una cartera hecha con esas supervivientes tendría buen aspecto en el backtest y no tendría
ningún fundamento.

## Límites
- Es una rejilla de 24 familias de condiciones (~89 M combinaciones posibles) en H1 y en un solo activo. Herramientas comerciales
  exploran más espacio, lo que empeora el problema de pruebas múltiples, no lo mejora.
- Entradas solo a mercado: no se probaron órdenes stop/limit en niveles.
- El TEST de oro ya está usado; cualquier búsqueda futura necesita otro hold-out o datos en vivo.
