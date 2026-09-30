# BOT 14 — Opening range breakout

Ficha pre-registrada el 30-sep-2026, antes de ejecutar ningún backtest del laboratorio. Se genera desde el módulo `bot_lab/strategies/orb.py`.

**Hipótesis:** La ruptura del rango inicial de una sesión captura la expansión de volatilidad posterior.

**Mercado:** NQ/MNQ (salvo el BOT 26: oro/plata). **Marco:** 1m. **Sesión:** NY 09:30-12:00 (salida 15:55) / Londres. **Frecuencia:** intradia.

## Reglas
BOT 14 — OPENING RANGE BREAKOUT (NQ, 1 min).

Hipótesis: la ruptura del rango inicial de una sesión captura la expansión de volatilidad posterior.

Reglas ORB puro (variante base 14.01):
  1. Rango de apertura (OR) = máximo y mínimo de los primeros N minutos desde las 09:30 NY (N = 15 en la base).
  2. Al cerrar el OR se colocan dos órdenes stop OCO: compra en máximo + 1 tick, venta en mínimo − 1 tick, válidas
     hasta las 12:00 NY. Una operación por sesión.
  3. Stop: el lado opuesto del rango. Salida: 15:55 NY (sin objetivo).
Después se añade UN filtro cada vez sobre la base (VWAP, volumen, compresión del rango, tendencia diaria).
Londres: OR desde las 08:00 de Londres, órdenes válidas 3 h, salida 09:25 NY (antes de la apertura de NY).
Antecedente: archive/reports/estudio_orb_final.md (ORB 5/15/30 con 2R: negativo; con salida por tiempo: t ≤ 1,3).

## Variantes pre-registradas (14)
| Variante | Parámetros |
|---|---|
| 14.01 base OR15 NY puro, salida 15:55 | `{'sesion': 'NY', 'n': 15, 'salida': 'tiempo', 'stop': 'rango', 'filtro': None}` |
| 14.02 OR5 | `{'sesion': 'NY', 'n': 5, 'salida': 'tiempo', 'stop': 'rango', 'filtro': None}` |
| 14.03 OR30 | `{'sesion': 'NY', 'n': 30, 'salida': 'tiempo', 'stop': 'rango', 'filtro': None}` |
| 14.04 OR15 1R | `{'sesion': 'NY', 'n': 15, 'salida': '1R', 'stop': 'rango', 'filtro': None}` |
| 14.05 OR15 1.5R | `{'sesion': 'NY', 'n': 15, 'salida': '1.5R', 'stop': 'rango', 'filtro': None}` |
| 14.06 OR15 2R | `{'sesion': 'NY', 'n': 15, 'salida': '2R', 'stop': 'rango', 'filtro': None}` |
| 14.07 OR15 trailing 2 ATR15 | `{'sesion': 'NY', 'n': 15, 'salida': 'trailing', 'stop': 'rango', 'filtro': None}` |
| 14.08 OR15 stop 1 ATR15 | `{'sesion': 'NY', 'n': 15, 'salida': 'tiempo', 'stop': 'atr', 'filtro': None}` |
| 14.09 Londres OR15 | `{'sesion': 'LDN', 'n': 15, 'salida': 'tiempo', 'stop': 'rango', 'filtro': None}` |
| 14.10 Londres OR30 | `{'sesion': 'LDN', 'n': 30, 'salida': 'tiempo', 'stop': 'rango', 'filtro': None}` |
| 14.11 base + filtro VWAP | `{'sesion': 'NY', 'n': 15, 'salida': 'tiempo', 'stop': 'rango', 'filtro': 'vwap'}` |
| 14.12 base + filtro volumen | `{'sesion': 'NY', 'n': 15, 'salida': 'tiempo', 'stop': 'rango', 'filtro': 'volumen'}` |
| 14.13 base + filtro compresión | `{'sesion': 'NY', 'n': 15, 'salida': 'tiempo', 'stop': 'rango', 'filtro': 'compresion'}` |
| 14.14 base + filtro tendencia diaria | `{'sesion': 'NY', 'n': 15, 'salida': 'tiempo', 'stop': 'rango', 'filtro': 'tendencia'}` |

**Base:** 14.01 base OR15 NY puro, salida 15:55

**Vecindad de sensibilidad (se aplica a la variante que resulte elegida):** ver `vecindad()` en el módulo.
