# Experimento en 1 minuto: cruce EMA 9/21 + VWAP (C), con retesteo (E) y con EMA 50 (F)

- **Datos:** velas de 1 minuto con volumen.
  - MNQ: NQ.c.0.
  - MGC: GC.v.0, comprado.
  - Periodo: 2018 a octubre de 2026.
- **Reglas:** las de 5 minutos con EMA, ATR y VWAP calculados sobre velas de 1 minuto.
  - La pendiente del VWAP y la de la EMA 50 se miden en 30 minutos (30 velas).
  - El retesteo de E sigue siendo de 3 velas.
- **Protocolo:** selección con desarrollo y validación, reglas congeladas (commit previo al OOS), OOS una sola vez.

## Resultado
- **Sin candidatos.** De 45 configuraciones por combinación (3 estrategias × 5 umbrales × 3 objetivos), **ninguna** gana en desarrollo ni en validación. Combinaciones: MNQ Londres, MNQ Nueva York, MGC Londres y MGC Nueva York.
- **Todo es negativo**, en todos los periodos, umbrales y combinaciones: entre −0,04R y −0,53R por operación con costes base.
  - En el OOS, entre −0,08R y −0,32R.
- **Peor que en 5 minutos.** Los stops son mucho más pequeños, así que los costes pesan más.
  - La regla "riesgo ≥ 3 × coste ida y vuelta" descarta muchas señales: en el oro, más de 6.000 de C sin filtro.
  - Sin esa regla los costes se comerían todavía más.
- **El filtro de VWAP plano casi no filtra en 1 minuto.** El ATR de 1 minuto es pequeño, así que la pendiente normalizada supera los umbrales con facilidad. Tampoco mejora el resultado.

## Conclusión
En 1 minuto, el cruce EMA 9/21 + VWAP **no tiene ventaja**; queda rechazado en MNQ y en oro, en Londres y en Nueva York.
