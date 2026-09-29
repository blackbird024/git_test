# Plan operativo: cartera NQ (zona de ruido + RSI(2))

*29-sep-2026. Decisiones tomadas con los datos de este proyecto. Todo lo que aquí se dice sale de backtests con
costes, auditados contra el look-ahead. Un backtest no garantiza nada: por eso hay una fase en papel antes de
arriesgar dinero.*

## 1. La verdad sobre "un ingreso todos los meses"
Ninguna estrategia honesta gana todos los meses. Con la mejor combinación que hemos encontrado:

| Cartera 1 MNQ + 1 MNQ (backtest con costes) | 2015-2026 | Desde abr-2023 (precios actuales) |
|---|---|---|
| Meses positivos | 61 % | 67 % |
| Trimestres positivos | 71 % | 73 % |
| Media por mes | +293 $ | +556 $ |
| Mediana por mes | +178 $ | +343 $ |
| 1 de cada 10 meses, peor que | −612 $ | −1.028 $ |
| Peor mes | −2.260 $ | −1.917 $ |
| Mayor racha de meses negativos | 3 | 3 |
| Años positivos | 11 de 12 (solo 2016 negativo) | — |

Lo realista: **ganar casi todos los años, y 2 de cada 3 meses**. Si necesitas cobrar una cantidad fija cada mes, el
trading no es la fuente adecuada. Sí puede serlo como ingreso complementario, que se retira por trimestres o por
años.

## 2. Decisiones

### Decisión 1: qué operar
Las **dos únicas estrategias del proyecto que han superado la validación**, ambas en el Nasdaq micro (MNQ):

| | Zona de ruido | RSI(2) |
|---|---|---|
| Tipo | Momentum intradía | Reversión a la media (swing) |
| Cuándo se opera | Cada día, 16:00-22:00 Italia (revisión cada media hora) | Revisión 1 vez al día, tras el cierre (23:00 Italia) |
| Operaciones | ~230 al año | ~13 al año |
| Reglas | `edges/zona_ruido_mnq.md` | `edges/nq_rsi2.md` |

- Los resultados mensuales de las dos casi no se parecen (correlación 0,04), así que se compensan.
- Detalle: `reports/CARTERA_NQ_v1.0/`.

### Decisión 2: lo que dejamos
- **Oro intradía y swing:** 7 estudios sin ventaja. No se prueban más variantes.
- **Rupturas de apertura, scalping, grid y martingala:** o no tienen ventaja (probado) o arruinan la cuenta tarde o
  temprano.
- **Reoptimizar parámetros:** las reglas no se tocan. Un cambio sería una versión nueva con su propia validación.

### Decisión 3: dónde operar
- **En una cuenta propia de futuros** (por ejemplo, en Tradovate, que ya usas). **No en Apex:**
  - el RSI(2) mantiene posiciones de un día para otro;
  - la zona de ruido no tiene stop fijo entre medias horas;
  - una caída normal de 3 meses (hasta 2.900 $ con 1 MNQ) supera el drawdown de 2.000 $ de una cuenta de 50K.
  Lo más probable es que se quemaran evaluaciones.
- **No en CFD de OANDA:** tienen más coste que el micro futuro, y el backtest está hecho con los costes de MNQ.

### Decisión 4: capital
- **Cuánto puede caer:**
  - las dos juntas, en el peor caso histórico con 1 + 1 MNQ: −2.786 $ (contando por meses; dentro del mes puede
    ser algo más);
  - el Monte Carlo del RSI(2) solo da una caída de −7.664 $ en el percentil 95.
- **Mínimo recomendado: 20.000 $** (mejor 25.000 $) para 1 + 1 MNQ. Así una caída mala sería del 15-30 % de la
  cuenta, no el final de la cuenta.
- **Con menos capital:** operar solo la zona de ruido (1 MNQ), con un mínimo de 10.000 $.

### Decisión 5: las fases
| Fase | Duración | Qué se hace | Para pasar a la siguiente |
|---|---|---|---|
| **1. Papel / demo** | 3 meses | Las dos estrategias en demo, 1 MNQ cada una. Todo anotado en `papel/registro.csv` | 0 señales saltadas; deslizamiento ≤ 1 tick; zona de ruido a 3 meses > −1.334 $ (criterios de `edges/zona_ruido_mnq.md`) |
| **2. Real pequeño** | 6 meses | 1 + 1 MNQ con dinero real | Resultado dentro de lo esperado (tabla del punto 1). **Parar** si la cartera cae más de 5.000 $ desde su máximo |
| **3. Escalar** | Después | +1 MNQ por estrategia por cada 20.000-25.000 $ adicionales | Solo si la fase 2 fue coherente con el backtest |

### Decisión 6: la rutina diaria (15-30 minutos de pantalla)
1. **Antes de las 15:30:** `python scripts/plan_del_dia.py`
2. **15:30:** `python scripts/plan_del_dia.py --sin-descarga --apertura PRECIO` → tabla de bandas de hoy.
3. **16:00-21:30, en cada media hora:** comprobar el precio frente a la banda y el VWAP, y actuar según la tabla (no
   hace falta estar mirando la pantalla entre medias horas).
4. **22:00:** cerrar la posición de la zona de ruido.
5. **Tras el cierre (≈23:00):** mirar la acción del RSI(2) para la reapertura.

Guía detallada: `papel/LEEME.md`.

## 3. Lo que haré a continuación (mientras dura la fase 1)
1. **Indicador de TradingView** para la zona de ruido: dibuja las bandas y el VWAP, y marca la señal en cada media
   hora. Así no tendrás que copiar números.
2. **Siguiente investigación, con el mismo protocolo:** una tercera estrategia **no relacionada con el Nasdaq**, para
   que la cartera tenga más meses positivos. La primera candidata es **pares oro/plata**: reversión del ratio, con
   datos diarios que ya tenemos, sin coste. Se registra antes de mirar y, si falla, se descarta.
3. **Revisión mensual** del registro en papel frente a lo esperado.

## 4. Riesgos que no desaparecen
- Las dos estrategias operan el **Nasdaq**. Un cambio de régimen en ese mercado afectaría a las dos.
- **Ya no queda fuera de muestra "virgen":** la prueba en papel es la única evidencia nueva que nos falta.
- **Hay días de hueco o de noticias** en que el precio real se alejará del backtest.
- **Nada de esto se automatiza en Apex.** Las herramientas solo dan señales; las órdenes las pones tú.
