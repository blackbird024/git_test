# Conclusiones (10 de octubre de 2026)

## A. Resumen ejecutivo

**Ninguna de las seis estrategias ha mostrado una ventaja neta y robusta en MNQ, ni en Londres ni en Nueva York.**

- **Ninguna configuración gana en desarrollo.** De 180 configuraciones (6 estrategias × 5 umbrales × 3 objetivos × 2 sesiones), **ninguna** tiene esperanza positiva en desarrollo (2018 a marzo de 2023). Solo 5 (Londres) y 13 (Nueva York) son positivas en validación, y ninguna lo es en los dos periodos.
- **Sin candidatos:** por la regla de selección fijada de antemano, ninguna llega al OOS como candidata.
- **Configuración de partida** (umbral 0,10, objetivo 2R):
  - Es negativa en el OOS (2025 a octubre de 2026) en las 12 combinaciones de estrategia y sesión: entre −0,06R y −0,33R por operación, con costes base.
  - El profit factor está entre 0,51 y 0,89.
- **Walk-forward anual:** la regla casi nunca encuentra una configuración positiva con los datos anteriores a cada año. Cuando la encuentra (estrategia A en Londres y en Nueva York, E en Nueva York), el año siguiente pierde.
- **MGC (oro):** evaluado el 10 de octubre con GC.v.0, velas de 1 minuto con volumen, compradas a Databento por 11,16 USD con tu autorización.
  - **Selección:** **sin candidatos** en Londres ni en Nueva York. Londres: 0 de 90 configuraciones positivas en desarrollo. Nueva York: 1 positiva en desarrollo, pero ninguna en desarrollo y validación a la vez.
  - **Configuración de partida en el OOS:** negativa en 10 de 12 casos. La excepción es F (cruce 9/21 + EMA50): +0,19R en Londres y +0,12R en Nueva York, pero con 58 y 46 operaciones, negativa en desarrollo y en validación (−0,18/−0,34 y −0,07/−0,31) y negativa en el walk-forward. Es ruido, no una ventaja.

Esto es historia, no una previsión. La conclusión correcta es **«no se ha encontrado evidencia suficiente de una ventaja estadística robusta»**.

## B. Ranking por instrumento y sesión

| Combinación | Mejor en validación (descriptivo) | Desarrollo | OOS (partida) | Estado |
|---|---|---|---|---|
| MNQ Londres | F, umbral 0,10, 1,5R: +0,11R (47 operaciones) | −0,23R | todas negativas | sin candidato |
| MNQ Nueva York | F, umbral 0,20, 2R: +0,17R (29 operaciones) | −0,25R | todas negativas | sin candidato |
| MGC Londres | ninguna positiva en validación | 0 de 90 positivas | 10 de 12 negativas (F +0,19R con 58 operaciones) | sin candidato |
| MGC Nueva York | 1 positiva en validación (no en desarrollo) | 1 de 90 positiva | F +0,12R con 46 operaciones; el resto negativas | sin candidato |

Los "mejores en validación" tienen pocas operaciones y pierden en desarrollo. Son el resultado esperable al probar 90 configuraciones por sesión, no una ventaja.

## C. Mejor candidato

No hay ninguno. No es obligatorio que exista un ganador.

## D. Filtro de VWAP plano

- **Lo que hace:**
  - Reduce mucho la frecuencia (entre un 50 % y un 90 % de las operaciones) y los costes totales.
  - En casi todas las estrategias elimina aproximadamente el doble de perdedoras que de ganadoras.
- **Pero no vuelve positiva ninguna estrategia:**
  - La esperanza por operación cambia poco y sin un patrón estable.
  - Algunos umbrales mejoran la validación (A en Nueva York: de −0,08R a +0,06R con 0,10), pero empeoran el OOS (−0,13R) o el desarrollo.
- **Pendiente frente a resultado** (descriptivo): con el VWAP más inclinado a favor de la operación, el resultado medio no mejora de forma ordenada. Todos los tramos son negativos.
- **Umbral razonable:** según desarrollo y validación, ninguno. El filtro ahorra costes, pero no crea ventaja.

## E. Siguiente paso realista

- No hay nada que pasar a simulación en tiempo real desde este laboratorio.
- Si quieres seguir:
  1. Los datos del oro ya están comprados y evaluados.
  2. No ajustes los umbrales ni las reglas con estos resultados. Cualquier idea nueva es un experimento nuevo y necesita datos posteriores a octubre de 2026.
- No se recomienda operar con dinero real ninguna de estas estrategias.

## Limitaciones

- **Ejecución:** solo con velas de 5 minutos (el orden dentro de la vela es desconocido). La comisión es supuesta y no hay datos de spread.
- **Datos ya vistos:** ya se habían probado variantes de EMA + VWAP sobre los mismos datos de NQ en este repositorio.
- **Rollover:** contrato continuo sin ajuste; se excluye la primera sesión tras cada vencimiento.
- **Costes severos mejores que los base:** en algunas filas pasa porque la regla de "stop demasiado pequeño" y el tamaño de posición cambian el conjunto de operaciones. No es un error de cálculo.

## Cambio de protocolo documentado

El 10 de octubre, antes de calcular el OOS del oro, la regla de selección pasó a exigir también una esperanza > 0 en validación, como pide tu criterio 14. Antes de este cambio, la estrategia E en Nueva York (oro) se habría seleccionado con −0,29R en validación. En MNQ no cambia nada.

## Experimento con RSI

Está en `results_rsi/` (`CONCLUSIONES_RSI.md`): las mismas reglas más RSI(14) > 50 para largos y < 50 para cortos, con su propio protocolo.
