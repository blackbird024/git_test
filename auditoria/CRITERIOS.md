# Criterios de evaluación (registrados el 30-sep-2026, ANTES de ejecutar la auditoría)

Se aplican igual a todas las estrategias. No se cambian después de ver resultados. Si una regla resulta inaplicable
(p. ej. una estrategia sin stop no tiene R por stop), se dice y se usa la métrica equivalente indicada.

## Honestidad sobre los periodos
- **No existe un test final intocable** para ninguna estrategia de NQ ni de oro: la partición del proyecto (desarrollo
  hasta el 21-mar-2023) ya se usó y el periodo posterior se miró en los informes originales (zona de ruido: incluso en
  el estudio del que salió; RSI(2): en su paso 3; el resto: en sus fichas). En este informe se llama a ese periodo
  **"posterior (ya visto)"**, nunca "fuera de muestra".
- El único dato realmente nuevo será el que llegue **después del 30-sep-2026** (prueba hacia delante).
- Walk-forward: como las reglas están congeladas (no se re-ajusta nada), el walk-forward consiste en medir cada
  **ventana anual** por separado, en orden cronológico, sin mezclar periodos.

## Métricas de referencia
- Zona de ruido no tiene stop fijo: su "R" no existe; se usa el **resultado neto por operación en $** (1 MNQ) y su t.
- RSI(2) tampoco tiene stop: su R del proyecto es rendimiento / volatilidad de 20 sesiones; se informa en $ y en ese R.
- t por operación = media / (desv. típica / raíz de n), que supone independencia. Se acompaña de un **intervalo de
  confianza del 95 % por bootstrap por bloques** (bloques de 20 sesiones sobre el P&L diario, 5.000 remuestreos,
  semilla 20260930), que respeta la dependencia temporal de corto plazo.

## Estados (uno por estrategia)
1. **Validación adicional respaldada por los datos**: se cumplen TODAS:
   a. Expectativa neta > 0 en el total y límite inferior del IC 95 % por bloques > 0.
   b. Ventanas anuales: ≥ 60 % con resultado neto > 0, y ningún año aporta más del 50 % del neto total.
   c. Con costes ×2 (deslizamiento y comisión dobles), la expectativa neta sigue > 0.
   d. Vecindad de parámetros (rejilla ±20–30 % fijada en la configuración): ≥ 80 % de las combinaciones con PF > 1.
   e. Periodo posterior (ya visto) con expectativa neta > 0 (sin exigir significación: es corto).
   f. ≥ 100 operaciones y ningún error metodológico crítico en la auditoría de código.
2. **Evidencia insuficiente**: estimación positiva o nula, pero falla alguno de a–f; o muestra < 100 operaciones.
3. **Evidencia negativa en las pruebas realizadas**: el límite superior del IC 95 % de la expectativa neta por
   operación es < 0 en el total o en desarrollo (con muestra ≥ 100).
4. **No verificable**: faltan datos o código para reproducirla.
Aunque se cumpla 1, la estrategia NO se declara rentable: solo justifica seguir con la prueba hacia delante.

## Cartera (fase 7) — asignaciones fijadas ahora
Todas con los mismos costes y el mismo modelo de capital (P&L en $ por día de salida; capital inicial 25.000 $):
1. Solo zona de ruido (1 MNQ).
2. Solo RSI(2) (1 MNQ).
3. **Igual presupuesto de riesgo**: pesos inversos a la volatilidad diaria de cada una estimada SOLO en desarrollo
   (hasta el 21-mar-2023), escalados para que la volatilidad diaria de la cartera sea igual a la de la zona de ruido
   sola (no se aumenta el riesgo total por añadir una estrategia).
4. Igual que 3 con pesos 2:1 y 1:2 (zona:RSI), también reescalados a la misma volatilidad.
5. 1 + 1 MNQ (el plan actual): se informa como lo que es, **más riesgo total** que una sola.
Los pesos fraccionarios se informan como "contratos equivalentes"; en real solo hay enteros.

## Riesgo (fase 8) — configuraciones fijadas ahora
Bootstrap por bloques del P&L diario de la cartera (bloques de 20 sesiones, horizonte 252 sesiones, 5.000
simulaciones, semilla 20260930). Configuraciones: capital 25.000 y 50.000 $; 1+1 y 2+2 MNQ; límite diario 1.000 y
2.000 $; caída máxima 5.000 y 10.000 $. Se informa la frecuencia de incumplimiento de cada límite, no un "óptimo".
Una simulación no es una predicción.
