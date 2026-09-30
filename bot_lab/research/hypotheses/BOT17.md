# BOT 17 — Pullback trend

Ficha pre-registrada el 30-sep-2026, antes de ejecutar ningún backtest del laboratorio. Se genera desde el módulo `bot_lab/strategies/pullback.py`.

**Hipótesis:** En una tendencia establecida, entrar tras un retroceso ofrece mejor relación riesgo/beneficio que perseguir la ruptura.

**Mercado:** NQ/MNQ (salvo el BOT 26: oro/plata). **Marco:** 5m. **Sesión:** NY 10:00-15:00 (salida 15:55). **Frecuencia:** intradia.

## Reglas
BOT 17 — PULLBACK TREND (NQ, velas de 5 min, entradas 10:00-15:00 NY, salida 15:55).

Hipótesis: en una tendencia establecida, entrar tras un retroceso ofrece mejor relación riesgo/beneficio que
perseguir la ruptura.

Reglas (largos; cortos al revés):
  1. Tendencia: cierre > EMA(200) de 5 min y EMA(200) más alta que 12 velas antes (1 hora).
  2. Retroceso: en alguna de las 3 últimas velas el mínimo tocó la EMA(20) (base) o el VWAP de la sesión.
  3. Disparo: la vela cierra por encima del máximo de la vela anterior -> compra en la apertura siguiente.
  4. Stop: mínimo de las 5 últimas velas − 1 tick. Objetivo 2R (o solo salida 15:55).

## Variantes pre-registradas (4)
| Variante | Parámetros |
|---|---|
| 17.01 base EMA200 + EMA20, 2R | `{'ema_larga': 200, 'retroceso': 'ema20', 'ema_corta': 20, 'salida': '2R'}` |
| 17.02 EMA200 + VWAP, 2R | `{'ema_larga': 200, 'retroceso': 'vwap', 'ema_corta': 20, 'salida': '2R'}` |
| 17.03 EMA200 + EMA20, salida 15:55 | `{'ema_larga': 200, 'retroceso': 'ema20', 'ema_corta': 20, 'salida': 'tiempo'}` |
| 17.04 EMA200 + VWAP, salida 15:55 | `{'ema_larga': 200, 'retroceso': 'vwap', 'ema_corta': 20, 'salida': 'tiempo'}` |

**Base:** 17.01 base EMA200 + EMA20, 2R

**Vecindad de sensibilidad (se aplica a la variante que resulte elegida):** ver `vecindad()` en el módulo.
