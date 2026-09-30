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
