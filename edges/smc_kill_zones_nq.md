# SMC_KZ_NQ_v1.0: barrido + desplazamiento + FVG en las kill zones de London y Nueva York (MNQ)

*Ficha escrita el 29-sep-2026, ANTES de ejecutar ningún backtest de esta versión ni de la ficha original en NQ.*

## Por qué
El usuario opera las dos kill zones (London y Nueva York) y observa entradas en London. En este proyecto ya se
rechazaron en NQ las ideas simples de London (`NQ_LONDON_FALSE_BREAK_v1.0`: PF 0,91 antes de costes). Aquí se prueba
la idea ICT/SMC tal y como está definida en `edges/smc_sweep_displacement_fvg.md`, **sin cambiar ninguna regla**,
solo la ventana horaria en la que se busca el patrón.

## Reglas
Las de `edges/smc_sweep_displacement_fvg.md` (columna MNQ) **sin ningún cambio**: niveles PDH/PDL de la sesión
anterior de CME, primer cruce, vuelta dentro en N = 6 velas de 5M, desplazamiento ≥ 1,5 × ATR(14), FVG, orden límite
en el borde cercano (llenado con 1 tick de cruce), validez M = 12 velas, stop a 2 ticks del extremo, objetivo en la
siguiente liquidez con RR mínimo 1, una operación al día, 1 MNQ, costes estándar del proyecto.

Solo cambian la ventana del patrón y el cierre forzado (horas de **Nueva York**, convertidas a UTC día a día; en
Italia son 6 h más casi todo el año):

| Variante | Ventana del patrón (NY) | Italia | Cierre forzado (NY) | Motivo del cierre |
|---|---|---|---|---|
| A. Original de la ficha | 09:30–15:30 | 15:30–21:30 | 15:55 | Registrado en la ficha original |
| B. London kill zone | 02:00–05:00 | 08:00–11:00 | 08:25 | Antes de los datos macro de las 08:30 NY |
| C. New York kill zone | 07:00–10:00 | 13:00–16:00 | 12:00 | Fin de la mañana de NY (antes del almuerzo) |

La regla del "primer cruce" se sigue contando desde las 18:00 NY de la víspera: si el nivel se barrió antes de la
ventana, ese lado no cuenta ese día.

## Periodo
Desarrollo: sesiones anteriores al 22-mar-2023 (`config/particion.json`, sin cambios). El fuera de muestra no se
evalúa en este paso. Se excluyen las sesiones ilíquidas previsibles.

## Criterio (paso 1, igual que la ficha original)
Se decide **por variante, por separado**. Pasa al paso 2 solo si, después de costes: profit factor > 1 **y** R medio
> 0 con **t ≥ 2**. Si no: rechazada, sin filtros para salvarla.

## Sesgos a tener en cuenta
1. **Tres pruebas:** con tres ventanas, la probabilidad de que alguna pase por azar es mayor que con una. Se informa
   de las tres, pasen o no.
2. **Conocimiento previo:** London en NQ ya falló con otras reglas; la ventana B no se ha ajustado a aquel resultado
   (son las horas estándar de la kill zone).
3. Resto de sesgos: los de la ficha original (llenado de límites, velas de 1M, contrato continuo).
