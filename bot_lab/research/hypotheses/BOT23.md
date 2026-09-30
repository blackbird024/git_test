# BOT 23 — Niveles del día anterior

Ficha pre-registrada el 30-sep-2026, antes de ejecutar ningún backtest del laboratorio. Se genera desde el módulo `bot_lab/strategies/previous_day.py`.

**Hipótesis:** El máximo, el mínimo y el cierre de la sesión regular anterior son zonas de liquidez donde el precio reacciona de forma medible.

**Mercado:** NQ/MNQ (salvo el BOT 26: oro/plata). **Marco:** 5m. **Sesión:** NY 09:35-15:00 (salida 15:55). **Frecuencia:** intradia.

## Reglas
BOT 23 — NIVELES DEL DÍA ANTERIOR (NQ, velas de 5 min, entradas 09:35-15:00 NY, salida 15:55).

Hipótesis: el máximo (PDH), el mínimo (PDL) y el cierre (PDC) de la sesión regular anterior son zonas de liquidez
donde el precio reacciona de forma medible.

Definiciones (todas en precios ajustados por cambio de contrato; niveles del día RTH anterior 09:30-16:00 NY):
  23.1 Ruptura: primera vela del día que CIERRA por encima de PDH (largo) o por debajo de PDL (corto).
       Stop 1 × ATR(14) de 5 min; objetivo 2R.
  23.2 Barrido: primera vela cuyo máximo supera PDH pero cierra por debajo (corto), sin cierre previo del día por
       encima de PDH; simétrico en PDL. Stop: extremo de la vela ± 1 tick; objetivo 2R.
  23.3 Rechazo: la vela se acerca a PDH a menos de 0,25 ATR sin superarlo y cierra bajista (corto), sin toque previo
       del día por encima de PDH; simétrico. Stop: PDH + 0,25 ATR; objetivo 2R.
  23.4 Cierre del hueco: si la apertura RTH deja un hueco respecto a PDC mayor que 0,25 × ATR(14) diario, al cierre de
       la primera vela de 5 min (09:35) se opera hacia PDC si el hueco sigue abierto. Objetivo PDC; stop a la misma
       distancia en contra (1:1).

## Variantes pre-registradas (4)
| Variante | Parámetros |
|---|---|
| 23.1 ruptura PDH/PDL | `{'modelo': 'ruptura', 'atr_k': 1.0}` |
| 23.2 barrido PDH/PDL | `{'modelo': 'barrido'}` |
| 23.3 rechazo PDH/PDL | `{'modelo': 'rechazo', 'zona': 0.25}` |
| 23.4 cierre del hueco hacia PDC | `{'modelo': 'hueco', 'min_hueco': 0.25}` |

**Base:** 23.1 ruptura PDH/PDL

**Vecindad de sensibilidad (se aplica a la variante que resulte elegida):** ver `vecindad()` en el módulo.
