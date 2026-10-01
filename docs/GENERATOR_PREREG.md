# Pre-registro: generador de estrategias en oro (proyecto separado del CRT)

Fecha: 2026-10-01. Escrito **antes** de ejecutar cualquier búsqueda. Si cambia algo de lo que hay aquí después
de ver resultados, se anota como POST-HOC.

## Objetivo
Comprobar si el método "generar miles de estrategias → filtros → robustez → cartera" produce algo que
funcione **fuera de muestra** en oro, y si produce más que el mismo método aplicado a precios sin estructura.

## Datos
Databento GLBX.MDP3 `GC.v.0` (futuros de oro de CME), 15M → **H1**, con ajuste por diferencia en cada rollover.
Ninguna operación cruza un rollover.

| Tramo | Fechas (UTC) | Uso |
|---|---|---|
| TRAIN | 2010-06-07 → 2020-03-01 | búsqueda y filtros |
| VALIDATION | 2020-03-01 → 2023-05-01 | segundo filtro |
| TEST | 2023-05-01 → 2026-09-28 | **intacto**; se evalúa una sola vez, sobre la lista congelada |

## Generador
- **50.000 estrategias aleatorias** (semilla 20261001). Dirección al azar y 1-3 condiciones de entrada (AND) de
  24 familias: medias, cruces, RSI, rupturas, Bollinger, rachas, engulfing, inside bar, hora NY, día,
  régimen ATR, ROC, volumen, máximo/mínimo del día anterior. Los parámetros salen de rejillas fijas
  (`strategy_gen/rules.py`).
- **Salida:** SL ∈ {1, 1.5, 2, 3}×ATR14 · TP ∈ {1, 1.5, 2, 3, 4}×ATR14 o sin TP · salida por tiempo ∈ {4, 8, 16, 24, 48} h.
- **Ejecución:** entrada en el OPEN de la vela siguiente; si SL y TP caen en la misma vela, se asume SL; un gap a través del SL se llena en el OPEN.
- **Coste:** 0.37 USD/oz por operación (los mismos supuestos del estudio CRT).

## Embudo (todo sobre R neto; 1R = distancia al stop)
1. **TRAIN:** ≥ 200 trades · PF ≥ 1.20 · total_R / |maxDD| ≥ 3 · ≥ 70 % de años positivos.
2. **Robustez (TRAIN):** todos los vecinos de un paso en la rejilla con PF ≥ 1.0 y su mediana ≥ 1.10 · entrada +1 vela con
   PF ≥ 1.0 · costes ×2 con PF ≥ 1.0.
3. **VALIDATION:** ≥ 30 trades · expectativa > 0 · PF ≥ 1.10.
4. Las supervivientes del paso 3 forman la **lista congelada**, que se commitea antes de abrir TEST. Si son más de 50, se
   quedan las 50 con mayor expectativa en TRAIN.
5. **TEST (una vez):** cada estrategia y una cartera equiponderada. Una cola, t-test de media R > 0 y Holm sobre la lista.

## Control sin edge (el punto clave)
El **mismo embudo, idéntico y con las mismas 50.000 estrategias**, se ejecuta sobre 3 series nulas. Cada serie se
construye barajando las velas H1 de todo el histórico: se conservan la distribución de rendimientos, el volumen y
el calendario, y se destruye toda dependencia temporal. Se registra cuántas sobreviven en cada etapa y cómo rinden en
el tramo "TEST" de la serie nula.

## Deflated Sharpe
Para la mejor estrategia de TRAIN (Sharpe por trade), con N = 50.000 intentos y la varianza del Sharpe entre
intentos (Bailey y López de Prado, 2014).

## Criterio de éxito (todo a la vez)
- La cartera de la lista congelada tiene expectativa TEST > 0 con p < 0.05.
- Al menos una estrategia es significativa en TEST tras Holm.
- Las supervivientes en oro real superan a las de **cada** serie nula en el paso 3.

Si no se cumple: **NO SE ENCONTRÓ EDGE**. El generador produce supervivientes del azar.
