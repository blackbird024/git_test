# PARES_ORO_PLATA_v1.0: reversión del ratio oro/plata (MGC + SIL, swing diario)

*Ficha escrita el 29-sep-2026, ANTES de cargar los datos y de ejecutar ningún backtest. Candidata registrada en
`PLAN_OPERATIVO.md` (tercera estrategia no relacionada con el Nasdaq); el usuario la eligió entre tres opciones.*

## Hipótesis
El oro y la plata responden a los mismos factores (dólar, tipos reales, demanda de refugio). Cuando el ratio
oro/plata se aleja mucho de su nivel reciente, suele ser por un flujo pasajero en uno de los dos metales, y el ratio
tiende a volver. Se vende el metal "caro" y se compra el "barato"; la exposición al nivel general de los metales se
cancela en buena parte.

## Reglas exactas (versión mínima, sin filtros)
| Elemento | Regla |
|---|---|
| Datos | Velas diarias de Databento (día UTC) de GC y SI, contrato continuo; precios **ajustados por rolls** con `ajustar` (solo usa el pasado). Se descartan sábados y domingos y se usan solo los días con dato en los dos mercados |
| Serie | `x = ln(oro ajustado) − ln(plata ajustada)` al cierre |
| z-score | `z = (x − media de 60 días) / desviación de 60 días`, ventana que acaba en el día de la señal (incluido) |
| Entrada | Al cierre del día con `z > +2`: **corto oro + largo plata**. Con `z < −2`: **largo oro + corto plata**. Se entra en la **apertura del día siguiente** |
| Salida | Al cierre del día en que `z` cruza 0 (corto oro: `z ≤ 0`; largo oro: `z ≥ 0`) o tras **20 sesiones**; se sale en la apertura siguiente. Sin stop |
| Una sola posición a la vez | Tras salir, se puede volver a entrar desde el cierre del día de salida |
| Tamaño | **1 MGC** (10 onzas, 10 $/punto, tick 0,10) **+ 1 SIL** (1.000 onzas, 1.000 $/punto, tick 0,005). Con un ratio de 70–90, las dos patas tienen un nominal parecido |
| P&L de cada pata | `dirección × nominal de entrada × (apertura ajustada de salida / apertura ajustada de entrada − 1)`, nominal = precio real × onzas |
| Costes | Por pata y lado: 1 $ de comisión + 1 tick de deslizamiento (MGC 1 $, SIL 5 $). Total ida y vuelta: **16 $ por operación** |

**Parámetros libres (3), fijos:** ventana 60 días, umbral 2, máximo 20 sesiones. Salida en z = 0.

## Periodo
Partición ya fijada en `config/particion.json` para los diarios de GC y SI: desarrollo hasta el **8-nov-2021**,
fuera de muestra desde el **9-nov-2021** (las dos series tienen el mismo corte). Se asigna cada operación por su
fecha de entrada.

## Criterio
Pasa si, **después de costes**: en desarrollo profit factor > 1 **y** neto medio por operación > 0 con **t ≥ 2**; y
en el fuera de muestra profit factor > 1. Si no: rechazada, sin ajustes.

## Qué la refutaría / sesgos
1. Pocas operaciones (se esperan ~10-15 al año): con t ≥ 2 exigido, puede quedarse sin significación aunque gane.
2. Cambios de régimen del ratio (2020: ratio > 100) pueden romper la reversión: sin stop, una operación puede
   perder mucho; se informa de la peor.
3. Velas diarias por día UTC (no la sesión de CME): la apertura "del día siguiente" es la de las 00:00 UTC.
4. En MT5 se operaría XAUUSD + XAGUSD (CFD): swap en las dos patas cada noche.

## Resultado (añadido tras ejecutar). Informe: `reports/PARES_ORO_PLATA_v1.0/`
| Tramo | Operaciones | PF | Media | t | Neto | Peor operación |
|---|---|---|---|---|---|---|
| Desarrollo (2010 – nov 2021) | 56 | **0,60** | −316 $ | **−1,24** | −17.676 $ | −5.165 $ |
| Fuera de muestra (nov 2021 – 2026) | 28 | 2,27 | +1.124 $ | 1,04 | +31.466 $ | −11.197 $ |

**Veredicto: RECHAZADA** (pierde en desarrollo). 63 de 84 operaciones salen por tiempo: el ratio casi nunca vuelve a
su media en 20 sesiones. El fuera de muestra positivo sale casi entero de 4 operaciones de 2026 (+40.178 $, año de
movimientos extremos de la plata) y convive con −20.500 $ en 2025: no es una ventaja estable. No se opera.
