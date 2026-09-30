# Notas del analista: ejecución del 2026-09-30

Complementan a `CRT_XAUUSD_FINAL.md`, que se genera automáticamente. Commit `1c0dda3`, pre-registro v2.1.0,
dataset sha256 `9df218f8…` (Databento GLBX.MDP3 GC.v.0, 1M agregado a 15M, 2010-06-07 → 2026-09-28).

## VERDICT: NO ROBUST EDGE

La regla BASE (4H → primer sweep 15M → engulfing inmediato + volumen ≥ 1.5×SMA20 → 1:1) pierde dinero
después de costes en London, en NY y en ambas juntas, tanto en TRAIN como en VALIDATION.

| Grupo | Trades T+V | Expectativa neta | Expectativa bruta (sin costes) | PF neto | p (una cola) |
|---|---|---|---|---|---|
| LONDON | 113 | −0.151 R | −0.009 R | 0.74 | 0.94 |
| NY | 237 | −0.037 R | +0.054 R | 0.92 | 0.73 |
| LONDON+NY | 350 | −0.074 R | +0.034 R | 0.85 | 0.93 |

**Ni siquiera sin costes hay evidencia.** El mejor caso bruto (LONDON+NY, +0.034 R en 350 trades, con error
estándar ≈ 0.053 R) está a unas 0,6 desviaciones de cero, así que no se distingue del azar. Los costes (mediana ≈ 9,5 % del
riesgo por trade, porque los stops son cortos: mediana de 3,90 USD) lo vuelven negativo.

## Por qué no es mala suerte de costes

- **Controles aleatorios:** la regla no bate a ninguno (todos los p ≥ 0.12). En London, los niveles de sweep
  **falsos** rinden más que los reales (media del null −0.023 R frente a −0.151 R observados; p = 0.91). En NY y
  LONDON+NY, mover la entrada a otra vela al azar dentro de la misma KZ rinde igual o mejor (p ≈ 0.87-0.88).
- **Ablaciones:** quitar el sweep (solo engulfing + volumen en la KZ) da −0.149 R en 4.778 trades; quitar
  el volumen da −0.126 R. El sweep y el volumen mejoran algo esa base negativa, pero sin llegar a positivo ni a
  ser significativos.
- **Walk-forward:** solo el 42 % de las ventanas OOS son positivas (el umbral es 60 %).
- **Parámetros vecinos:** volumen 1.3/1.7, percentiles 70/80/90, TP 1.5R/2R/3R y entrada retrasada son todos ≤ 0 en
  LONDON y en LONDON+NY. **Ningún vecino rescata la regla.**
- **Con 2× y 3× costes** todo se hunde (LONDON+NY: −0.18 R y −0.29 R).

## Observaciones POST-HOC (no se incorporan al sistema)

1. NY con TP 1.5R: +0.004 R (236 trades). Es indistinguible de cero y sale de mirar 19 niveles × 3 grupos, así que es exactamente
   el tipo de resultado que no hay que perseguir.
2. Los LONG (−0.033 R) van mejor que los SHORT (−0.119 R) en 2010-2023. El oro subió mucho en ese periodo; lo más
   probable es que sea deriva del activo, no un efecto de la regla.
3. El 10 % de los trades salen por cierre de sesión: el 1R no se alcanza en el día en una parte relevante de los casos.

## TEST

**Sigue bloqueado y recomiendo no desbloquearlo.** El veredicto ya es negativo con TRAIN+VALIDATION. Desbloquearlo
no cambiaría la conclusión y gastaría el único hold-out limpio (2023-05 → 2026-09). Es mejor reservarlo para una
futura hipótesis que se pre-registre antes de mirarla.

## Limitaciones de esta prueba

- **No es XAUUSD spot:** son futuros GC de CME, con volumen **real de bolsa**. La geometría intradía es casi idéntica,
  pero las velas 4H, el volumen y el spread de un CFD concreto serán algo distintos. Un export de MT5 de tu broker
  permitiría repetir la prueba exactamente sobre el instrumento que operarías (`docs/DATA_REQUIREMENTS.md`).
- **Costes provisionales:** 0.37 USD/oz por operación en el escenario base. Pero la conclusión no depende de ellos: con
  0 costes tampoco hay significación.
- **SL primero en empates:** si SL y TP caen en la misma vela de 15M se asume SL, lo que sesga ligeramente a la baja. El efecto es acotado:
  la mediana de MFE es 0.89 R y la de MAE 0.79 R.
- **Calidad de datos:** Databento marca como "degraded" algunos días (p. ej. 2017-11-13, 2018-10-21, 2019-01-15, 2022-01-02 y
  varios de 2025-2026). No se excluyeron; son pocos días frente a unos 4.000.

## Condición de falsificación: cumplida

La hipótesis pre-registrada queda **rechazada**: expectativa ≤ 0 en TRAIN y en VALIDATION, Holm p = 1.0 y no bate
ningún null. **La fase 2 (automatización) no procede.** Por la regla 28, no se intenta arreglarla añadiendo filtros.
