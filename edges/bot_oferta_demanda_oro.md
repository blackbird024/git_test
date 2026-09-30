# BOT_OFERTA_DEMANDA_ORO_v1.0: verificación del bot `mt5_live_bot.py` del usuario (XAUUSD, H1)

*Ficha escrita el 30-sep-2026, ANTES de ejecutar ningún backtest. Las reglas NO se diseñan aquí: se copian del código
del bot (repositorio privado `apex-datos`, `mt5_live_bot.py`), que afirma "backtest 22 años XAUUSD, walk-forward OK,
PF~1.44, DD máx 8 %". Aquí se comprueba con nuestros datos.*

## Reglas (idénticas al código del bot)
- **Velas de 1 hora**, 24 h (sin filtro de sesión), solo velas cerradas. Se evalúa al cierre de cada vela nueva.
- **Indicadores:** ATR(14) = media simple del rango verdadero; SMA(200) del cierre.
- **Zonas** en las últimas 100 velas (i−100 … i−2):
  - Demanda: mínimo local (low < low anterior y siguiente) con cierre > low. Zona = [low, low + 5 % del rango de las
    últimas 21 velas]. Cuenta los "toques" de las 50 velas anteriores; solo vale si hay ≥ 2.
  - Oferta: simétrico con máximos locales.
- **Mitigación:** la penetración de las últimas 5 velas en la zona ≥ 85 % de su anchura.
- **Confirmaciones (≥ 2 de 4):** vela a favor (alcista en demanda); zona con ≥ 3 toques; precio al otro lado de la
  SMA200 (compras por debajo, ventas por encima: contra-tendencia); ATR actual < 3 × su media de 50 velas.
- Se recorren primero las zonas de demanda (de la más reciente a la más antigua) y luego las de oferta; se toma la
  primera válida.
- **Stop:** borde exterior de la zona ∓ max(1,2 × ATR, 0,1 % del precio). Se descarta si el riesgo < 0,5 × esa
  distancia o si el precio ya está fuera de la zona. **Objetivo:** 2,5 R desde el cierre de la vela de señal.
- **Ejecución:** a mercado tras el cierre de la vela (apertura de la siguiente); stop y objetivo como niveles fijos
  (los calculados por el bot). Sin salida por tiempo: la posición sigue abierta (también de noche y fines de semana)
  hasta el stop o el objetivo.
- **Riesgo:** 0,5 % del balance por operación (tamaño con la distancia real al stop); máximo **2 posiciones a la
  vez**; no abre nuevas si la pérdida del día (UTC) supera el 5 %.

## Datos y adaptaciones (necesarias, fijadas de antemano)
- **Precio:** futuro GC (Databento, 1 min → 1 h), no el CFD XAUUSD (no hay datos del CFD). GC = oro al contado +
  coste de financiación; los patrones de precio son casi iguales.
- **Cambios de contrato:** el continuo GC salta en cada vencimiento (contango). Como el bot mantiene posiciones
  varios días, se usa una serie **ajustada hacia atrás de forma aditiva** (el salto del cambio se resta del pasado),
  más parecida al CFD, que no tiene vencimientos. Las decisiones del bot solo dependen de diferencias de precio y
  del cruce con la SMA200 dentro de la ventana, así que el ajuste no mete información futura en las señales.
- **Intravela:** con los minutos se sabe si llega antes el stop o el objetivo; si caen en el mismo minuto, stop.
- **Costes (XAUUSD Pepperstone Razor, aprox.):** spread 0,15 $, comisión 0,035 $/oz por lado (7 $ por lote ida y
  vuelta), deslizamiento 0,05 $ en entradas y stops. **Swap no incluido** (limitación: favorece al bot).
- Tamaño en onzas (0,01 lote = 1 oz), capital inicial 50.000 $.

## Periodo y criterio
Desarrollo: hasta el 21-mar-2023; fuera de muestra: desde el 22-mar-2023 (partición del proyecto para GC). Aviso: el
bot se diseñó con datos que probablemente incluyen el periodo fuera de muestra, así que no es virgen para él.
**Pasa** si, después de costes, en desarrollo PF > 1 y R medio > 0 con t ≥ 2, y fuera de muestra PF > 1 y R > 0.

## Resultado (añadido tras ejecutar). Informe: `reports/BOT_OFERTA_DEMANDA_ORO_v1.0/`
| Variante | Tramo | Operaciones | Acierto | PF | R medio | t | Neto | Max DD |
|---|---|---|---|---|---|---|---|---|
| **Con costes** | desarrollo 2015–mar 2023 | 802 | 28,8 % | **0,95** | **−0,027** | −0,50 | −6.148 $ | −21,6 % |
| **Con costes** | fuera de muestra | 473 | 30,2 % | 1,03 | +0,030 | 0,41 | +1.846 $ | −15,9 % |
| Sin costes | completo | 1.251 | 30,1 % | 1,05 | +0,043 | 0,95 | +11.869 $ | −18,5 % |
| Costes x2 | completo | 1.316 | 28,7 % | 0,92 | −0,044 | −1,04 | −15.049 $ | −42,6 % |

**Veredicto: RECHAZADO.** Con costes, el bot no gana en desarrollo (PF 0,95) y fuera de muestra queda en +0,03 R sin
significación (t 0,4). Ni siquiera sin costes se acerca al "PF ~1,44" que cita su código (aquí 1,05). Detalles:
- **Cortos −0,18 R de media (434), largos +0,08 R (841):** el lado corto resta todo lo que suma el largo.
- **Fallo de diseño encontrado:** el 9-nov-2020 (anuncio de la vacuna) el ATR se disparó y el bot abrió 2 cortos con
  stop a ~100 $ y objetivo a ~240 $. Sin salida por tiempo, siguieron abiertos **16 meses** (hasta mar-2022) y, con el
  máximo de 2 posiciones ocupado, **el bot no operó en todo 2021**. En real pasaría lo mismo.
- Años: 7 de 11 negativos.
- Limitaciones: precio del futuro GC ajustado (no el CFD) y **sin swap**: el swap de posiciones de varios días
  (media 105 h) empeoraría el resultado.
