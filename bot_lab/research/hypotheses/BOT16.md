# BOT 16 — Momentum breakout

Ficha pre-registrada el 30-sep-2026, antes de ejecutar ningún backtest del laboratorio. Se genera desde el módulo `bot_lab/strategies/momentum.py`.

**Hipótesis:** Una expansión repentina de volatilidad con ruptura del rango reciente continúa durante cierto tiempo.

**Mercado:** NQ/MNQ (salvo el BOT 26: oro/plata). **Marco:** 5m. **Sesión:** NY 09:45-15:30. **Frecuencia:** intradia.

## Reglas
BOT 16 — MOMENTUM BREAKOUT (NQ, velas de 5 min, entradas 09:45-15:30 NY).

Hipótesis: una expansión repentina de volatilidad acompañada de ruptura continúa durante cierto tiempo.

Reglas (base, 3 reglas):
  1. Expansión: rango de la vela > m × ATR(20) de las velas ANTERIORES (m = 1,25).
  2. Ruptura: cierre por encima del máximo (o por debajo del mínimo) de las N velas anteriores (N = 10).
  3. Stop 1 × ATR(20); salida por tiempo 60 min después de la entrada (o 15:55).
De una en una: N 5/20, m 1,0/1,5, salida 2R, trailing 1,5 ATR, 30 min, filtro de volumen relativo > 1,5.

## Variantes pre-registradas (9)
| Variante | Parámetros |
|---|---|
| 16.01 base N10 m1.25 stop 1 ATR, 60 min | `{'n': 10, 'm': 1.25, 'salida': 'tiempo', 'minutos': 60, 'filtro_vol': None}` |
| 16.02 N5 | `{'n': 5, 'm': 1.25, 'salida': 'tiempo', 'minutos': 60, 'filtro_vol': None}` |
| 16.03 N20 | `{'n': 20, 'm': 1.25, 'salida': 'tiempo', 'minutos': 60, 'filtro_vol': None}` |
| 16.04 m1.0 | `{'n': 10, 'm': 1.0, 'salida': 'tiempo', 'minutos': 60, 'filtro_vol': None}` |
| 16.05 m1.5 | `{'n': 10, 'm': 1.5, 'salida': 'tiempo', 'minutos': 60, 'filtro_vol': None}` |
| 16.06 salida 2R | `{'n': 10, 'm': 1.25, 'salida': '2R', 'minutos': 60, 'filtro_vol': None}` |
| 16.07 trailing 1.5 ATR | `{'n': 10, 'm': 1.25, 'salida': 'trailing', 'minutos': 60, 'filtro_vol': None}` |
| 16.08 salida 30 min | `{'n': 10, 'm': 1.25, 'salida': 'tiempo', 'minutos': 30, 'filtro_vol': None}` |
| 16.09 + volumen relativo > 1.5 | `{'n': 10, 'm': 1.25, 'salida': 'tiempo', 'minutos': 60, 'filtro_vol': 1.5}` |

**Base:** 16.01 base N10 m1.25 stop 1 ATR, 60 min

**Vecindad de sensibilidad (se aplica a la variante que resulte elegida):** ver `vecindad()` en el módulo.
