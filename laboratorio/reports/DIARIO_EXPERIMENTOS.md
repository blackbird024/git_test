# Diario de experimentos (9 de octubre de 2026)

Se anotan todos los experimentos, también los fallidos o parciales. Cada carpeta de `experiments/` tiene su `manifest.json` con los datos, la versión del código, los parámetros, los costes, los periodos y la semilla.

**Aviso sobre la versión del código:** hasta este commit, la etiqueta de versión solo detectaba cambios en archivos ya versionados, no los scripts nuevos sin commit. Los experimentos marcados con `52966a2` se ejecutaron con scripts (`run_topstep.py`, `run_swing_extra.py`, `run_plan.py`) que se versionaron en el commit siguiente. Ya está corregido: `git status --porcelain`.

| Hora | Carpeta | Qué | Resultado | Estado |
|---|---|---|---|---|
| — | (previo) | Reproducción de la zona de ruido original con `alpaca/mnq_intraday_lab.py` sin cambios | PF 1,33; +2.791 $/año; peor racha −3.430 $; 8/9 años. Idéntico a lo publicado. | ✅ reproducido |
| — | (previo) | Origen del "PF 1,19" | Pertenece a EMA 9/21 + CHOP (salida del transcript), no a la zona de ruido | ⚠️ etiqueta confundida |
| 19:35:00 | `20261009_193500_sistema_a` | Prueba rápida, una sola variante (ORB close 2R) | Desarrollo −6,02 $/op; validación +3,00 | Parcial, no usado |
| 19:35:11 | `20261009_193511_sistema_a` | Sistema A completo, desarrollo + validación, 3 costes, 26 variantes | Solo la zona de ruido es positiva y significativa en los dos periodos; ORB principal negativo en desarrollo; tendencia negativa | ✅ |
| 19:41:22 | `20261009_194122_sistema_b` | Sistema B, desarrollo + validación | B1 positiva, B4 negativa en validación, ninguna bate al benchmark en rentabilidad | ✅ (bug del % en 1-4 semanas, corregido después) |
| 19:41:26 | `20261009_194126_robustez_a` | Costes (+0…+4 ticks, fijo ×2), perturbación de parámetros (9-27 vecinos) y placebo (20 semillas) en desarrollo + validación | Ruido 27/27 vecinos positivos y muy por encima del placebo; ORB immediate-eod 33 %; ORB close peor que el placebo en desarrollo | ✅ |
| — | `reglas_congeladas.yaml` (commit `52966a2`) | Congelación de las reglas antes de la prueba | Filtro vol en ORB immediate y close; VWAP en tendencia; B1 sin filtro | ✅ |
| 19:42:05 | `20261009_194205_sistema_a_con_prueba` | **Prueba final A** (una sola vez) | Ruido: PF 1,18, +12,5 $/op; tendencia: −16 $/op; ORB: −5 a +6 $/op | ✅ |
| 19:43:37 | `20261009_194337_sistema_b_con_prueba` | **Prueba final B** | B1 PF 1,41 (3,7 %/año) frente a 25,8 %/año del benchmark; RSI(2) PF 2,57 | ✅ |
| 19:46:03 | `20261009_194603_topstep_combine` | Combine simulado (sin control) | Ruido, 2 MNQ: aprueba el 41 % / pierde el 58 % | Sustituido por el siguiente |
| 19:46:43 | `20261009_194643_topstep_combine` | + control de dirección aleatoria | Control: aprueba el 5-17 % | Sustituido (faltaba la duración media) |
| 19:47:27 | `20261009_194727_swing_extra` | IC fuera de muestra, fiscalidad italiana, RSI(2) en NQ, riesgo MNQ swing | Después de impuestos: B1 1,3 %, B3 1,1 %, comprar y mantener 17,6 %/año | ✅ |
| 19:48:07 | `20261009_194807_topstep_combine` | Combine con la duración media de cada intento | ~70 días por intento con el ruido a 2 MNQ | ✅ (vigente) |
| 19:48:24 | `20261009_194824_plan_financiero` | Plan v1 (75 % al fondo de emergencia) | Comprar 50 € con 3 € de comisión = 6 %: plan corregido | Sustituido |
| 19:48:36 | `20261009_194836_plan_financiero` | Plan v2 (100 % al fondo) | Cobraba comisión con compra 0 € (valor negativo) | ❌ bug |
| 19:48:40 | `20261009_194840_plan_financiero` | Plan v3 corregido | Ver INFORME §5 | ✅ (vigente) |
| — | (sin carpeta) | Zona de ruido con salida solo por banda (por defecto en `BandasRuidoNY.pine`; variante preexistente "sin media") | PF 1,33 / 1,34 / 1,20; IC90 FM [7,3; 28,2]; top-10 = 70 % | ✅ coherencia indicador-backtest |
| — | (sin carpeta) | Sensibilidad a las semanas de vencimiento (fuera de muestra) | Todas las estrategias rinden peor en esas semanas; ruido 4,0 frente a 15,0 $/op | ✅ (INFORME §7) |

| 20:06:18 | `20261009_200618_orb_italia_13h` | ORB 5 min desde las 13:00 Italia (hipótesis nueva; 3 variantes × 3 salidas, reglas fijadas antes) | Ninguna variante gana en los tres periodos; con salida antes de NY: PF 0,65-1,00; con salida al cierre de NY: alterna años buenos y malos | ❌ todas RECHAZADAS |

| 20:09:46 | `20261009_200946_orb_italia_14h` | ORB 5 min desde las 14:00 Italia (`run_orb_italia.py --hora 14`) | Peor que a las 13:00: esperanza negativa en casi todo; el retesteo pierde con IC90 entero por debajo de 0 | ❌ todas RECHAZADAS |

| 20:16:26 | `20261009_201626_sweep_fvg_robin_hood` | Barrida del máx/mín de la sesión anterior (15 min) + reversión en FVG de 1 min ("Robin Hood"), 12 variantes fijadas antes | Con niveles de ayer (PDH/PDL): ninguna gana en los 3 periodos. Con niveles nocturnos y sin confirmación: las 3 salidas ganan en validación y prueba, pero poco (+1,6 a +8,5 $/op), IC90 incluye 0, top-10 = 146 % del neto | ⚠️ mejor variante INCONCLUSA; resto rechazadas |

| 20:20:12 | `20261009_202012_orb_retest_pdhl` | ORB 5 min ruptura + retesteo con objetivo en PDH/PDL (4 variantes) | Negativa en desarrollo y prueba en todas; el objetivo queda a ~5,6 R y solo se alcanza en el 16-19 % | ❌ RECHAZADAS |

## Hipótesis descartadas en el camino (ya no hay que volver a probarlas con estos datos)

- **ORB con retesteo según tu especificación:** negativo en los tres periodos.
- **ORB 2R con salida a las 11:30:** negativo en desarrollo en las tres variantes. Con stop estructural no es operable con 50-100 $ de riesgo.
- **Filtro de tendencia (EMA50 diaria) en el ORB:** empeora en validación (immediate) o en desarrollo (close).
- **Continuación de tendencia:** base y filtros EMA200 / vol negativos; el filtro VWAP pierde en la prueba.
- **Retroceso a la EMA20 (swing):** gana en desarrollo (PF 4,5) y pierde en validación. Ejemplo típico de sobreajuste al régimen.
- **Filtros de la ruptura de 20 sesiones (EMA200, pendiente, volatilidad):** ninguno cumple la regla de selección.

## Hipótesis nuevas para el futuro (no validables con los datos ya vistos)

- **Zona de ruido con stop de protección:** necesario para Topstep. Hay que definirlo y evaluarlo **solo con datos posteriores al 2 de octubre de 2026**.
- **Zona de ruido solo en régimen de volatilidad media/alta:** surge de mirar el desglose por régimen. Es una hipótesis *a posteriori* y debe probarse en forward.
