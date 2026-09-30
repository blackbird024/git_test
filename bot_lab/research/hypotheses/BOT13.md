# BOT 13 — VWAP mean reversion

Ficha pre-registrada el 30-sep-2026, antes de ejecutar ningún backtest del laboratorio. Se genera desde el módulo `bot_lab/strategies/vwap_mean_reversion.py`.

**Hipótesis:** Cuando NQ se aleja significativamente del VWAP de la sesión, el precio tiende a volver hacia el VWAP.

**Mercado:** NQ/MNQ (salvo el BOT 26: oro/plata). **Marco:** 5m. **Sesión:** NY 10:00-15:00 (salida 15:55). **Frecuencia:** intradia.

## Reglas
BOT 13 — VWAP MEAN REVERSION (NQ, velas de 5 min, RTH).

Hipótesis: cuando NQ se aleja significativamente del VWAP de la sesión, el precio tiende a volver hacia el VWAP.

Reglas (variante base):
  1. Banda = VWAP ± k · desviación (desviación del precio respecto al VWAP ponderada por volumen, desde 09:30 NY).
  2. Entrada "confirmación": la vela de 5 min anterior cerró FUERA de la banda y la actual cierra DENTRO (y todavía
     por encima/debajo del objetivo) -> operación hacia el VWAP en la apertura del minuto siguiente.
  3. Stop: extremo de las 3 últimas velas ± 1 tick. Objetivo: el VWAP (dinámico). Salida 15:55 NY.
  Entradas con velas que empiezan entre 10:00 y 15:00 NY; como máximo 2 operaciones por sesión.
Componentes que se prueban de uno en uno: k (0,5 / 1 / 1,5 / 2), tipo de entrada, objetivo, stop, VWAP de la sesión
Globex y distancia medida en ATR en lugar de desviación.

## Variantes pre-registradas (11)
| Variante | Parámetros |
|---|---|
| 13.01 base k1.5 confirmación→VWAP stop extremo | `{'k': 1.5, 'entrada': 'confirmacion', 'objetivo': 'vwap', 'stop': 'extremo', 'vwap': 'rth', 'medida': 'sd'}` |
| 13.02 k0.5 | `{'k': 0.5, 'entrada': 'confirmacion', 'objetivo': 'vwap', 'stop': 'extremo', 'vwap': 'rth', 'medida': 'sd'}` |
| 13.03 k1.0 | `{'k': 1.0, 'entrada': 'confirmacion', 'objetivo': 'vwap', 'stop': 'extremo', 'vwap': 'rth', 'medida': 'sd'}` |
| 13.04 k2.0 | `{'k': 2.0, 'entrada': 'confirmacion', 'objetivo': 'vwap', 'stop': 'extremo', 'vwap': 'rth', 'medida': 'sd'}` |
| 13.05 entrada extensión | `{'k': 1.5, 'entrada': 'extension', 'objetivo': 'vwap', 'stop': 'extremo', 'vwap': 'rth', 'medida': 'sd'}` |
| 13.06 entrada rechazo | `{'k': 1.5, 'entrada': 'rechazo', 'objetivo': 'vwap', 'stop': 'extremo', 'vwap': 'rth', 'medida': 'sd'}` |
| 13.07 objetivo 0.5 SD | `{'k': 1.5, 'entrada': 'confirmacion', 'objetivo': 'media_sd', 'stop': 'extremo', 'vwap': 'rth', 'medida': 'sd'}` |
| 13.08 objetivo 1.5R | `{'k': 1.5, 'entrada': 'confirmacion', 'objetivo': 'R', 'stop': 'extremo', 'vwap': 'rth', 'medida': 'sd'}` |
| 13.09 stop 1 ATR | `{'k': 1.5, 'entrada': 'confirmacion', 'objetivo': 'vwap', 'stop': 'atr', 'vwap': 'rth', 'medida': 'sd'}` |
| 13.10 VWAP Globex | `{'k': 1.5, 'entrada': 'confirmacion', 'objetivo': 'vwap', 'stop': 'extremo', 'vwap': 'globex', 'medida': 'sd'}` |
| 13.11 distancia en ATR | `{'k': 1.5, 'entrada': 'confirmacion', 'objetivo': 'vwap', 'stop': 'extremo', 'vwap': 'rth', 'medida': 'atr'}` |

**Base:** 13.01 base k1.5 confirmación→VWAP stop extremo

**Vecindad de sensibilidad (se aplica a la variante que resulte elegida):** ver `vecindad()` en el módulo.
