# NQ_LONDON_FALSE_BREAK_v1.0: las mismas reglas de GOLD_LONDON_FALSE_BREAK_v1.0, en el Nasdaq (MNQ)

*Ficha escrita el 29-sep-2026, ANTES de ejecutar, a petición del usuario ("prueba en nasdaq"), después de ver que la
versión del oro fue rechazada.*

## Qué se prueba
Las reglas de `edges/gold_london_false_break.md` **sin ningún cambio**:
- rango de 08:00 a 09:00 de Londres en velas de 15m;
- señales de 09:00 a 11:30;
- primer break (una ruptura real gasta ese extremo) y una sola señal al día;
- entrada en la apertura siguiente;
- SL en la vela de la falsa ruptura ± 0,10 × ATR(14) de 15m;
- TP 2R y salida a las 12:00 de Londres.

## Qué cambia (solo lo que depende del mercado)
- **Datos:** futuros NQ (Databento), con el mismo ajuste por cambios de contrato (`ajustar_rolls`).
- **Tamaño:** contratos MNQ (2 $ por punto), con `position_sizing`, 50.000 $ y 0,5 % de riesgo. Si sale menos de 1
  contrato, no se opera.
- **Costes:** los del oro, en $ por onza, no se pueden trasladar. Se usan los **estándar del proyecto para MNQ** (los
  de OR_VWAP_v1.0):

| Escenario | Deslizamiento (entrada y salidas a mercado: stop y tiempo) | Comisión |
|---|---|---|
| A | 0 | 0 |
| B | 1 tick (0,25 puntos) por lado | 1 $ por contrato y lado (= 1 punto de MNQ por operación completa) |
| C | 2 ticks por lado | 1 $ por contrato y lado |

El objetivo (límite) nunca lleva deslizamiento.

- **Horario:** de 08:00 a 12:00 de Londres son, casi todo el año, las **03:00-07:00 de Nueva York**. Es la sesión
  europea del Nasdaq, antes de los datos macro de EE. UU. (08:30 NY) y de la apertura del contado. Hay poca liquidez,
  pero es el mismo horario que la regla original.
- **Días excluidos:** las sesiones ilíquidas previsibles de NQ (regla causal del proyecto).

## Periodo y criterios
- **Desarrollo:** sesiones del 2-ene-2015 al 21-mar-2023. **Fuera de muestra: BLOQUEADO.**
- **Criterios del desarrollo**, con el escenario B, deben cumplirse todos:
  - al menos 100 operaciones;
  - PF > 1;
  - R medio > 0 con t ≥ 2.

## Aviso de pruebas múltiples
- Es la **segunda** prueba de la misma regla (la primera, en el oro, falló).
- Si el NQ pasara, sería con un listón algo menos exigente de lo que parece: se ha probado en dos mercados y se
  informaría del que funciona.
- Además, el proyecto ya probó varias ideas de rango y apertura en NQ (ORB, OR + VWAP) sin ventaja tras costes.
