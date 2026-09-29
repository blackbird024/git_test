# OR_LONDON_VWAP_v1.0: ruptura del rango de 30 min de NY a favor de London y del VWAP (MNQ)

*Ficha escrita el 29-sep-2026, ANTES de ejecutar ningún backtest de esta versión. Idea del usuario (reel de
Instagram); los detalles abiertos los fijó el usuario eligiendo entre opciones, antes de ver datos.*

## Idea
A las 15:30 (Italia) se marcan los máximos y mínimos de las dos primeras velas de 15 minutos de Nueva York, se mira
el VWAP y el rango de Londres. Si NY está por encima de Londres y del VWAP se buscan compras; si está por debajo de
los dos, ventas.

## Relación con lo ya probado
`OR_VWAP_v1.0` (rango de 15 min + VWAP, 2R) se rechazó en desarrollo (PF 0,905 con costes, t −0,97). Esta versión
cambia tres cosas, todas fijadas por el usuario antes de ver datos: rango de **30 min**, señal al cierre de velas de
**5 min** y, sobre todo, el **filtro de Londres** (el precio tiene que superar también el máximo/mínimo de Londres).
No hay tope de riesgo ni sizing por saldo: 1 MNQ fijo, resultados también en R.

## Reglas exactas
Datos de 1 minuto de NQ en UTC; reglas en **America/New_York** (convertidas día a día; en Italia, +6 h casi todo el año).

| Elemento | Regla |
|---|---|
| Rango NY | Velas de 1M de 09:30 a 09:59 NY (= las dos velas de 15 min de 15:30–16:00 Italia). `RH` = máximo, `RL` = mínimo. Hacen falta las 30 velas; si no, no se opera |
| Rango de Londres | Velas de 1M de 03:00 a 09:29 NY (09:00–15:29 Italia) del mismo día. `LH` = máximo, `LL` = mínimo. Si no hay velas, no se opera |
| VWAP | VWAP de la sesión regular desde las 09:30 NY (el de `OR_VWAP_v1.0`: precio típico × volumen, acumulado; valor al cierre de la vela) |
| Señal LARGO | Primer cierre de vela de **5 min** (10:00–15:50 NY, velas de 5M que acaban en :x4/:x9 de 1M) con **cierre > RH**, **cierre > LH** y **cierre > VWAP** |
| Señal CORTO | Primer cierre de vela de 5 min con **cierre < RL**, **cierre < LL** y **cierre < VWAP** |
| Entrada | Apertura de la vela de 1M siguiente, con deslizamiento (motor estándar `ejecutar`) |
| Stop | LARGO: `RL`. CORTO: `RH`. Fijo |
| Objetivo | 2R desde la entrada real |
| Salida por tiempo | 15:55 NY (21:55 Italia; 5 min antes del cierre para no operar la subasta) |
| Operaciones | 1 al día (la primera señal) |
| Tamaño | 1 MNQ fijo (2 $/punto, tick 0,25) |
| Costes | Estándar del proyecto: 1 $ por contrato y lado; 1 tick de deslizamiento (2 en aperturas de sesión) |
| Días excluidos | Sesiones ilíquidas previsibles y fines de semana |

Parámetros libres (ninguno optimizado): rango 30 min, velas de 5M, 2R, ventana de Londres 03:00–09:30 NY.

## Periodo y criterio
Desarrollo: sesiones anteriores al 22-mar-2023 (`config/particion.json`, sin cambios). Fuera de muestra sin tocar.
Pasa al paso 2 solo si, **después de costes**: profit factor > 1 **y** R medio > 0 con **t ≥ 2**. Si no: rechazada,
sin filtros para salvarla. Se informa también el resultado sin el filtro de Londres (solo como control, no como
alternativa elegible).

## Sesgos
1. Familia ya probada (OR + VWAP): la probabilidad de que un cambio pequeño "salve" la idea por azar no es nula.
2. Idea sacada de redes sociales: suelen mostrarse los días buenos; el backtest los pondrá en su sitio.
3. Velas de 1M: si stop y objetivo caen en la misma vela, pérdida.
