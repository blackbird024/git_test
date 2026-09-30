# BOT 15 — Trend following

Ficha pre-registrada el 30-sep-2026, antes de ejecutar ningún backtest del laboratorio. Se genera desde el módulo `bot_lab/strategies/trend_following.py`.

**Hipótesis:** Cuando NQ presenta una tendencia suficientemente fuerte, las rupturas a su favor tienen expectativa positiva.

**Mercado:** NQ/MNQ (salvo el BOT 26: oro/plata). **Marco:** 15m. **Sesión:** NY 10:00-15:00 (salida 15:55). **Frecuencia:** intradia.

## Reglas
BOT 15 — TREND FOLLOWING (NQ, velas de 15 min, entradas 10:00-15:00 NY, salida 15:55).

Hipótesis: cuando NQ presenta una tendencia suficientemente fuerte, las rupturas en su dirección tienen expectativa
positiva (continuación).

Reglas (base, 4 reglas):
  1. Tendencia alcista: cierre > EMA(200) de 15 min y la EMA sube respecto a 4 velas antes (bajista: al revés).
  2. Entrada: cierre por encima del máximo de las 8 velas anteriores (2 horas) a favor de la tendencia.
  3. Stop: 1,5 × ATR(14) de 15 min desde la entrada. Objetivo: 2R.
  4. Salida por tiempo a las 15:55 NY.
Alternativas de tendencia (de una en una): EMA 50, EMA 100, estructura de máximos/mínimos, ADX > 25.
Salida alternativa: trailing de 3 ATR sin objetivo. Las entradas en retroceso se estudian en el BOT 17.
Antecedentes: archive/reports/estudio_ma_mnq.md y estudio_macd_mnq.md (cruces de medias/MACD: negativos o nulos).

## Variantes pre-registradas (6)
| Variante | Parámetros |
|---|---|
| 15.01 base EMA200 ruptura 8 velas, 2R | `{'tendencia': 'ema', 'ema': 200, 'ruptura': 8, 'stop_atr': 1.5, 'salida': '2R'}` |
| 15.02 EMA50 | `{'tendencia': 'ema', 'ema': 50, 'ruptura': 8, 'stop_atr': 1.5, 'salida': '2R'}` |
| 15.03 EMA100 | `{'tendencia': 'ema', 'ema': 100, 'ruptura': 8, 'stop_atr': 1.5, 'salida': '2R'}` |
| 15.04 tendencia por estructura | `{'tendencia': 'estructura', 'ema': 200, 'ruptura': 8, 'stop_atr': 1.5, 'salida': '2R'}` |
| 15.05 tendencia por ADX>25 | `{'tendencia': 'adx', 'ema': 200, 'ruptura': 8, 'stop_atr': 1.5, 'salida': '2R'}` |
| 15.06 salida trailing 3 ATR | `{'tendencia': 'ema', 'ema': 200, 'ruptura': 8, 'stop_atr': 1.5, 'salida': 'trailing'}` |

**Base:** 15.01 base EMA200 ruptura 8 velas, 2R

**Vecindad de sensibilidad (se aplica a la variante que resulte elegida):** ver `vecindad()` en el módulo.
