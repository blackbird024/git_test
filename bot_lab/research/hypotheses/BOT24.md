# BOT 24 — Rango nocturno → NY

Ficha pre-registrada el 30-sep-2026, antes de ejecutar ningún backtest del laboratorio. Se genera desde el módulo `bot_lab/strategies/overnight.py`.

**Hipótesis:** La relación entre el rango nocturno y la apertura de NY contiene información sobre expansión o reversión.

**Mercado:** NQ/MNQ (salvo el BOT 26: oro/plata). **Marco:** 5m. **Sesión:** NY 09:35-11:30 (salida 15:55). **Frecuencia:** intradia.

## Reglas
BOT 24 — RANGO NOCTURNO → NY (NQ, velas de 5 min, salida 15:55).

Hipótesis: la relación entre el rango nocturno (18:00-09:30 NY) y la apertura de NY contiene información sobre
expansión o reversión.

Definiciones (precios ajustados; ONH/ONL = máximo/mínimo de la sesión Globex antes de las 09:30; ONM = punto medio):
  24.1 Ruptura: primera vela de 5 min (09:35-11:30) que cierra por encima de ONH (largo) o por debajo de ONL (corto).
       Stop 1 × ATR(14) de 5 min; objetivo 2R.
  24.2 Reversión (ruptura fallida): entre 09:30 y 11:30 el precio supera ONH (o pierde ONL) y una vela de 5 min
       vuelve a cerrar dentro del rango -> operación hacia ONM (objetivo ONM); stop: extremo RTH hasta esa vela
       ± 1 tick. (Corregido el 30-sep ANTES de ver resultados: la versión "abre fuera del rango" casi nunca ocurre
       porque el rango nocturno incluye el precio de las 09:29; ver CRITERIOS.md, cambios.)
  24.3 Interacción con VWAP: a las 10:00 (cierre de la vela 09:55-10:00), largo si el precio está por encima del VWAP
       y de ONM; corto si está por debajo de ambos. Stop 2 × ATR(14) de 5 min; salida 15:55.

## Variantes pre-registradas (3)
| Variante | Parámetros |
|---|---|
| 24.1 ruptura del rango nocturno | `{'modelo': 'ruptura', 'atr_k': 1.0}` |
| 24.2 reversión al punto medio | `{'modelo': 'reversion'}` |
| 24.3 VWAP + punto medio a las 10:00 | `{'modelo': 'vwap', 'atr_k': 2.0}` |

**Base:** 24.1 ruptura del rango nocturno

**Vecindad de sensibilidad (se aplica a la variante que resulte elegida):** ver `vecindad()` en el módulo.
