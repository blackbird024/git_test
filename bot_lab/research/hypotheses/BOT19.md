# BOT 19 — VWAP + régimen

Ficha pre-registrada el 30-sep-2026, antes de ejecutar ningún backtest del laboratorio. Se genera desde el módulo `bot_lab/strategies/regime.py`.

**Hipótesis:** La reversión al VWAP funciona en rango y falla en tendencia; en tendencia funciona la continuación a favor del VWAP.

**Mercado:** NQ/MNQ (salvo el BOT 26: oro/plata). **Marco:** 5m. **Sesión:** NY 10:00-15:00 (salida 15:55). **Frecuencia:** intradia.

## Reglas
BOT 19 — VWAP + DETECCIÓN DE RÉGIMEN (NQ, velas de 5 min, entradas 10:00-15:00 NY, salida 15:55).

Hipótesis: la reversión al VWAP funciona en mercados laterales pero falla en tendencias fuertes; en tendencia funciona
la continuación a favor del VWAP.

Régimen (causal, con la vela de la señal):
  - ADX(14) de 5 min: TENDENCIA si > 25; RANGO si < 20.
  - Ratio de eficiencia de la sesión RTH hasta la vela (|cierre − cierre de la 1.ª vela de 5 min| / suma de |Δcierre|):
    TENDENCIA si ≥ 0,4; RANGO si ≤ 0,2.
Estrategias:
  - MR: reglas de la base del BOT 13 (banda 1,5 desviaciones, confirmación, objetivo VWAP, stop extremo), solo en RANGO.
  - Tendencia: precio del lado del VWAP en TENDENCIA; la vela toca el VWAP (mínimo ≤ VWAP en largos), cierra a favor
    y por encima del máximo anterior -> entrada; stop extremo de 3 velas ± 1 tick; objetivo 2R.
Controles (no seleccionables): MR solo en TENDENCIA y tendencia solo en RANGO, para medir si el régimen importa.

## Variantes pre-registradas (6)
| Variante | Parámetros |
|---|---|
| 19.01 MR solo en RANGO (ADX) | `{'estrategia': 'mr', 'medida': 'adx', 'regimen': 'rango'}` |
| 19.02 MR solo en RANGO (eficiencia) | `{'estrategia': 'mr', 'medida': 'er', 'regimen': 'rango'}` |
| 19.03 Tendencia VWAP solo en TENDENCIA (ADX) | `{'estrategia': 'tend', 'medida': 'adx', 'regimen': 'tendencia'}` |
| 19.04 Tendencia VWAP solo en TENDENCIA (eficiencia) | `{'estrategia': 'tend', 'medida': 'er', 'regimen': 'tendencia'}` |
| 19.05 control: MR en TENDENCIA (ADX) | `{'estrategia': 'mr', 'medida': 'adx', 'regimen': 'tendencia', 'control': True}` |
| 19.06 control: tendencia en RANGO (ADX) | `{'estrategia': 'tend', 'medida': 'adx', 'regimen': 'rango', 'control': True}` |

**Base:** 19.01 MR solo en RANGO (ADX)

**Vecindad de sensibilidad (se aplica a la variante que resulte elegida):** ver `vecindad()` en el módulo.
