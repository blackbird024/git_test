# FORWARD_TESTING v1.0 — PROTOCOLO

Fijado el 30-sep-2026, antes del inicio. Pregunta que responde:

> ¿El comportamiento observado históricamente de RSI(2) y Noise Zone se reproduce cuando empezamos a recibir datos completamente nuevos? Si no, ¿cómo y cuándo empieza a desviarse?

## 1. Qué se evalúa
| | RSI(2) | Noise Zone |
|---|---|---|
| Versión | RSI2_SURVIVOR_V1 | NOISE_ZONE_SURVIVOR_V1 |
| Código | `src/strategies/nq_rsi2.py` | `src/strategies/zona_ruido.py` |
| Tamaño | 1 MNQ (evaluación separada) | 1 MNQ (evaluación separada) |
| Noche | Sí (1-5 sesiones) | No |

Parámetros, costes, deslizamiento, horarios, reglas y SHA-256: `config/FORWARD_TESTING_CONFIG.json`. Su propio SHA-256 está en `config/FORWARD_TESTING_CONFIG.sha256`, guardado en git antes del inicio.

**Inicio:** una operación es forward si su **entrada es ≥ 2026-09-30 00:00 (hora de NY)**. Todo dato desde esa fecha es **NO VISTO**: no se usa para optimizar, filtrar ni modificar nada.

## 2. Dos pistas
1. **Forward teórico (OFICIAL).** Es el código congelado, ejecutado cada día sobre datos nuevos de NQ 1 min (Databento, ≈ 0,005 $/día).
   - Es exactamente la estrategia validada, sobre datos no vistos.
   - Precio teórico = precio de mercado del instante de ejecución.
   - Precio "real" = el teórico + el deslizamiento asumido en el backtest (1 tick en Noise Zone; 2 ticks en la reapertura de Globex para el RSI(2)) + 1 $/lado de comisión.
2. **Forward de ejecución (EA en la demo de Pepperstone, CFD NAS100).** Mide la ejecución real:
   - fills y deslizamiento frente al bid/ask previo;
   - spread;
   - operaciones hechas o no hechas frente al teórico.

   **No** mide la estrategia pura: el CFD no es el futuro, y el RSI(2) del EA usa velas diarias del CFD. Las dos pistas se emparejan y cada discrepancia se registra (`logs/emparejamiento.csv`).

## 3. Registro (append-only)
- `logs/trades_teorico.csv`: una fila por operación CERRADA. Campos:
  - identificación: id, estrategia, dirección, contrato, sesión, fecha;
  - tiempos: timestamps en UTC y en NY, duración;
  - precios teóricos y reales de entrada y salida;
  - costes y resultado: deslizamiento, comisión, bruto sin costes, bruto, neto en $ y neto en % del precio;
  - MAE y MFE;
  - motivo, SHA-256 de la configuración y hora de registro;
  - **rasgos previos a la entrada que ya existían en el backtest** (régimen de volatilidad, ATR, tendencia, VWAP, hueco, noche, rango previo, hora, día; RSI y distancia a la SMA200 en el RSI(2)). No se añade ningún rasgo nuevo.
- Nunca se borra ni se edita una fila. Cada día se recalcula todo y **las operaciones ya registradas deben reproducirse exactamente**. Si alguna cambia, hay información del futuro, datos revisados o código cambiado, y el día es **INVALID**.
- `logs/posiciones_abiertas.csv`: foto de la posición abierta del RSI(2), que no cuenta como cerrada.
- `logs/trades_ea.csv`, `logs/emparejamiento.csv`: la pista del EA.
- `logs/estado_dias.csv`: VALID/INVALID con motivos, commit y SHA-256 de la configuración.
- `logs/ejecuciones.log`: bitácora.
- `raw/nq/*.parquet`: datos descargados, nunca modificados. SHA-256 en `raw/MANIFIESTO.csv`.
- `raw/ea/`: copias fechadas del registro del EA, con SHA-256.

## 4. Integridad: el día es INVALID si falla
| Comprobación | Qué se verifica |
|---|---|
| Congelación | SHA-256 del código y de los archivos de referencia; parámetros idénticos a los congelados |
| Datos descargados | No modificados (SHA-256) |
| Datos del día | Zona UTC, sin duplicados, ordenados, sin velas imposibles, sin huecos > 5 min en RTH, sesión completa. Una media sesión por festivo es solo AVISO |
| Operaciones | Timestamps en UTC; entrada ≥ inicio; salida > entrada; sin duplicados; sin dos posiciones a la vez; precio teórico dentro del rango de su vela (si no, la operación es imposible); deslizamiento y comisión aplicados exactamente; neto = bruto − deslizamiento − comisión; Noise Zone cerrada en el día; como mucho 1 RSI(2) abierta |
| Append-only | Lo registrado se reproduce igual (sin look-ahead) |

Un día INVALID **no añade operaciones** al registro. Se explica en el informe diario y se investiga. Nunca se "arregla" una operación a mano.

## 5. Comparación backtest vs forward
Referencia: operaciones del Survivor Analysis v1.0 (2015-2026, NOT OUT-OF-SAMPLE).

**Métricas por estrategia:**
- operaciones, acierto, expectativa, mediana y desviación;
- profit factor, drawdown y duración;
- MAE, MFE, deslizamiento y costes;
- distribución (p5/p25/p75/p95);
- **media forward / media backtest** y **diferencia %**.

**Rango razonable:** la media forward se compara con la distribución histórica de medias de N operaciones consecutivas (bootstrap por bloques). "Dentro" = entre p5 y p95.

**Escala de precio (decisión tomada ANTES del inicio):** el NQ vale hoy 6-7 veces más que en 2015. La métrica principal de comparación es el **% del precio de entrada**; en $ se informa igual, avisando del sesgo.

**Muestras mínimas:** 50 operaciones (Noise Zone) y 15 (RSI(2)). Por debajo, todo es **descriptivo y NO concluyente**.

## 6. Deriva (solo informativa)
- **Ventanas móviles:** Noise Zone 20/50/100 operaciones; RSI(2) 10/15/25.
- **Estados** (en $ y en % del precio):

  | Estado | Condición |
  |---|---|
  | OK | Media de la ventana ≥ p5 histórico |
  | WARNING | Media < p5 histórico |
  | ALERT | Media < p1 histórico |

- **Umbrales oficiales** (Survivor Analysis):
  - Noise Zone: media de las últimas 50 < **−20,5 $**;
  - RSI(2): media de las últimas 15 < **−71 $**.
- Todo aviso va a `alerts/alertas.csv`.
- **Una alerta NO apaga ninguna estrategia, NO cambia parámetros, NO cambia el riesgo y NO crea filtros.** Solo documenta cuándo y cómo empieza la desviación.

## 7. Informes
| Informe | Archivo | Contenido |
|---|---|---|
| Diario | `daily/AAAA-MM-DD.md` | Fecha, operaciones, P&L neto (por estrategia y suma descriptiva), P&L acumulado, drawdown actual, deslizamiento, incidencias de ejecución, alertas de deriva, sección "BACKTEST VS FORWARD" y estado VALID/INVALID |
| Semanal (viernes o `--semanal`) | `weekly/AAAA-Www.md` | Por estrategia: operaciones, expectativa, expectativa móvil, drawdown, deslizamiento, comparación, distribución. Combinado solo descriptivo. **Sin ranking ni ganador** |
| Resumen | `reports/backtest_vs_forward.md` | Última comparación completa |

## 8. Riesgo
- Se evalúa **cada estrategia por separado** con 1 MNQ. El combinado es solo una suma descriptiva.
- No se implementa 1+1 como cartera evaluada.
- El tamaño no cambia por resultados.
- **EA de la demo:** tiene las dos estrategias activas, cada una con su magic, que se evalúan por separado. `PerdidaDiariaMax = 5000` para que el freno diario no acople las dos estrategias; se mantiene `CaidaMaximaCartera = 5000`.

## 9. Prohibido durante el forward
- Buscar estrategias nuevas.
- Probar EMAs o indicadores nuevos.
- Optimizar el RSI(2) o la Noise Zone.
- Crear filtros o cambiar horarios.
- Eliminar operaciones perdedoras.
- Modificar stops o salidas.
- Seleccionar días o regímenes después de ver resultados.
- Hacer backtests sobre los datos forward para ajustar nada, o reutilizarlos para optimizar.

Cualquier idea nueva va a `POST_HOC.md` y **no** entra en el sistema actual. La investigación de diversificación (el "carril B") vive fuera de `forward_testing/` y no toca estas estrategias.

## 10. Cambios del protocolo
Si algo del sistema de registro o de informes tiene un error:
- se corrige **sin tocar** la configuración congelada ni las estrategias;
- se anota aquí con fecha y motivo;
- se vuelven a generar los informes. Las operaciones registradas no se tocan.

Un cambio en una estrategia **invalida el forward**: habría que empezar otro con una versión nueva.

| Fecha | Cambio | Motivo |
|---|---|---|
| 30-sep-2026 08:58 NY | Inicio adelantado del 01/10 al **30/09/2026** a petición del usuario, antes de la apertura de NY (09:30), sin haber visto ningún dato de la sesión del 30/09 | Operar desde hoy |
| 30-sep-2026 | Comparación y deriva también en % del precio | Descubierto con un forward simulado **antes del inicio**: la escala de precio sesga las comparaciones en $ |
