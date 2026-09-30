# BOT 18 — RSI(2) extremo + filtro de tendencia

Ficha pre-registrada el 30-sep-2026, antes de ejecutar ningún backtest del laboratorio. Se genera desde el módulo `bot_lab/strategies/rsi2_extremo.py`.

**Hipótesis:** La reversión tras un extremo de RSI(2) funciona mejor cuando el mercado no está en una tendencia extrema en contra.

**Mercado:** NQ/MNQ (salvo el BOT 26: oro/plata). **Marco:** 1D. **Sesión:** sesión CME completa. **Frecuencia:** diaria.

## Reglas
BOT 18 — RSI(2) EXTREMO + FILTRO DE TENDENCIA (NQ diario, largos y cortos). Variante NUEVA y separada: no toca
src/strategies/nq_rsi2.py (BOT 01, en forward test).

Hipótesis: la reversión a la media tras un extremo de RSI(2) funciona mejor cuando el mercado no está en una
tendencia extrema en contra.

Reglas (mismo cálculo y ejecución que el BOT 01: sesiones de CME, cierres ajustados por cambio de contrato, señal al
cierre y entrada en la reapertura de Globex con 2 ticks de deslizamiento):
  - Largo si RSI(2) < L; corto si RSI(2) > 100 − L (L = 5 o 3).
  - Salida: largo si RSI(2) > 70, corto si RSI(2) < 30, o tras 5 sesiones; en la apertura siguiente.
  - Filtros (A, B, C, D):
      A: ninguno.
      B: EMA200 diaria (largos solo con cierre > EMA200; cortos solo con cierre < EMA200).
      C: VWAP de 20 sesiones (media de los VWAP de sesión ponderada por volumen): largos por encima, cortos debajo.
      D: B y C.
Se informa cuánto mejora o empeora cada filtro respecto a A, y largos/cortos por separado.

## Variantes pre-registradas (8)
| Variante | Parámetros |
|---|---|
| 18.1A RSI<5/>95 puro | `{'umbral': 5, 'filtro': 'A', 'max_dias': 5}` |
| 18.1B RSI<5/>95 EMA200 | `{'umbral': 5, 'filtro': 'B', 'max_dias': 5}` |
| 18.1C RSI<5/>95 VWAP20 | `{'umbral': 5, 'filtro': 'C', 'max_dias': 5}` |
| 18.1D RSI<5/>95 EMA200+VWAP20 | `{'umbral': 5, 'filtro': 'D', 'max_dias': 5}` |
| 18.2A RSI<3/>97 puro | `{'umbral': 3, 'filtro': 'A', 'max_dias': 5}` |
| 18.2B RSI<3/>97 EMA200 | `{'umbral': 3, 'filtro': 'B', 'max_dias': 5}` |
| 18.2C RSI<3/>97 VWAP20 | `{'umbral': 3, 'filtro': 'C', 'max_dias': 5}` |
| 18.2D RSI<3/>97 EMA200+VWAP20 | `{'umbral': 3, 'filtro': 'D', 'max_dias': 5}` |

**Base:** 18.1B RSI<5/>95 EMA200

**Vecindad de sensibilidad (se aplica a la variante que resulte elegida):** ver `vecindad()` en el módulo.
