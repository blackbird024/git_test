# Plan ORB 5 min (versión elegida por el usuario)

Estado según el laboratorio: **INCONCLUSA**.
- Esperanza fuera de muestra de +8,8 $/operación, con un IC90 de [−3,2; +22,9] $.
- Vecinos de parámetros positivos solo en el 33 %.
- La regla se eligió entre 9 secundarias, así que hay sesgo de selección.

Es la mejor versión de ORB del laboratorio, pero **no tiene una ventaja demostrada**.

## Reglas exactas (`strategies/orb.py`: variant=immediate, stop_mode=rango, exit=eod)

| Paso | Nueva York | Italia (normal / 25 oct–1 nov y 14–27 mar) |
|---|---|---|
| Rango = máximo y mínimo de las velas de 9:30 a 9:34 | 9:30–9:35 | 15:30–15:35 / 14:30–14:35 |
| Colocar **compra stop** en máximo + 1 tick y **venta stop** en mínimo − 1 tick (OCO: al llenarse una, se cancela la otra) | 9:35 | 15:35 / 14:35 |
| Cancelar las dos si ninguna se ha activado | 11:00 | 17:00 / 16:00 |
| Stop-loss = el otro lado del rango ∓ 1 tick. **Sin objetivo** | — | — |
| Cerrar a mercado | 15:55 | 21:55 / 20:55 |

- **Una sola operación al día.** Si salta el stop, no hay segunda entrada.
- **No operar** las medias jornadas.

## Tamaño y cuándo no operar

Riesgo de 1 MNQ en 2025-26: es la anchura del rango × 2 $ + costes.
- Mediana **158 $**.
- Percentil 25: 116 $.
- Percentil 75: 213 $.
- Percentil 90: 264 $.

| Riesgo máximo por operación | Días sin operar (el stop no cabe) | Contratos |
|---|---|---|
| 100 $ | 84 % | 1 |
| 150 $ | 54 % | 1 |
| 200 $ | 30 % | 1 |

## Qué esperar (historial)

- **Acierto ~31 %.**
  - Ganancia media +371 $ y pérdida media −164 $ por MNQ.
  - El 68 % de las operaciones acaban en stop.
- **Peor racha:** 18 pérdidas seguidas (2018-2026).

## Riesgo frente a tu Combine actual

- **Colchón:** unos 990 $ hasta el MLL (49.561,70 $).
- **Margen:** con 1 MNQ y el stop típico de 158 $, **6 pérdidas seguidas** bastan para perder la cuenta.
- **Lo histórico:** rachas de 6 o más pérdidas seguidas han ocurrido muchas veces.

Por eso, operar este ORB con el saldo actual tiene una probabilidad alta de suspender el Combine aunque la estrategia tuviera una pequeña ventaja.

## Recomendación

1. **Recomendado:** forward en papel 30 días (≥ 20 operaciones), anotando todo en `diario_forward.csv`.
2. **Si aun así lo operas en real:**
   - 1 MNQ, sin excepciones.
   - No operar si el riesgo supera los 200 $.
   - Una operación al día.
   - Parar el Combine y volver a papel si el colchón baja de 500 $. Con 990 $ de colchón, eso son unas 3 pérdidas.
3. No mover el stop.
4. No añadir objetivos ni cambiar la regla a mitad del periodo de prueba.
