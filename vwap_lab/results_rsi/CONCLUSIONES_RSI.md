# Experimento: VWAP + EMA + filtro RSI(14)

## Qué se probó
- **Regla:** las mismas 6 estrategias, umbrales y objetivos que en `results/`, más una condición en la vela de señal:
  - largos solo con RSI(14) > 50;
  - cortos solo con RSI(14) < 50.
- **Nivel del RSI:** 50, fijado antes de ver resultados y sin optimizar.
- **Protocolo propio:** selección solo con desarrollo y validación, reglas congeladas en `reglas_congeladas.yaml` (commit `42a2e0a`) antes del OOS, OOS una sola vez, estrés de costes y walk-forward.

## Resultado
- **Sin candidatos.** Ninguna configuración es positiva en desarrollo y en validación a la vez, en ninguna de las 4 combinaciones:
  - MNQ Londres: 0 positivas en desarrollo.
  - MNQ Nueva York: 0 positivas en desarrollo.
  - MGC Londres: 0 positivas en desarrollo.
  - MGC Nueva York: 2 positivas en desarrollo, pero ninguna también en validación.
- **El RSI casi no cambia nada:** el número de operaciones y la esperanza son prácticamente iguales con y sin RSI.
  - Motivo: cuando la EMA cruza el VWAP o la otra EMA hacia arriba, el RSI(14) ya está casi siempre por encima de 50 (y por debajo en los cortos). Es redundante con las señales de cruce.
- **Configuración de partida** (umbral 0,10, objetivo 2R) en el OOS: negativa en 22 de 24 casos.
  - La excepción es la estrategia F del oro (+0,19R en Londres, +0,12R en Nueva York), la misma que sin RSI: pocas operaciones, negativa en desarrollo y validación.

## Conclusión
Añadir el RSI **no aporta ventaja**: no se ha encontrado evidencia de una estrategia robusta.
