# Plan: sistema multiestrategia intradía (semiautomático) para Apex EOD

## Decisiones tomadas

| Tema | Decisión | Por qué |
|---|---|---|
| Prop firm | Apex Trader Funding, evaluación **EOD** | Elección del usuario |
| Modo | **Semiautomático**: el sistema genera la señal y **tú** colocas la orden en Tradovate | Apex prohíbe la automatización ("No Automation or Algorithm Usage allowed") |
| Instrumentos | MNQ y MGC, con datos históricos de NQ y GC | Mismo precio y más historia (MNQ existe solo desde 2019) |
| Motor de backtest | Propio, vela a vela | Hay que simular reglas muy concretas (umbral EOD, límite diario, cierre forzado) y debe ser fácil de auditar |
| Reglas | Archivos `config/*.yaml` | Si Apex cambia una regla, se edita un archivo de texto, no el código |

## Qué cambia por ser semiautomático

1. **Retraso humano.** En el backtest entramos en la apertura de la vela *siguiente* a la señal, no al precio exacto de la señal. Es más pesimista y más realista.
2. **Pocas señales y a horas previsibles.** Máximo 3 operaciones al día. Las ventanas de ORB (9:35 / 9:45 / 10:00 ET) y la del momentum de cierre (15:20 ET) son fáciles de vigilar. VWAP tendrá un filtro para no generar demasiadas señales.
3. **Orden bracket obligatoria.** Cada señal indica: instrumento, dirección, contratos, entrada, stop y objetivo. En Tradovate se coloca como bracket (OCO), así que el stop y el objetivo quedan en el servidor aunque se te cierre el ordenador.
4. **Pine Script (fase final).** Las alertas de TradingView servirán para **avisarte** (app o email), no para ejecutar órdenes.

## Cómo funciona la regla EOD (y por qué nos favorece)

- Al cierre de cada día: `umbral = max(umbral_anterior, saldo_cierre − drawdown_max)`.
- Durante el día siguiente, si el saldo (incluyendo lo no realizado) toca el umbral, la cuenta se pierde.
- **Ventaja frente al trailing intradía:** las ganancias no realizadas durante el día **no** suben el umbral. Solo lo sube el saldo de cierre.
- **Límite de pérdida diaria (DLL) de Apex:** fijo (1.000 $ en una cuenta de 50K). El sistema para antes, al 50 %.

## Métrica principal del backtest

Simularemos miles de "evaluaciones de 30 días" empezando en fechas distintas y contaremos:

- **% de evaluaciones aprobadas** (objetivo alcanzado sin tocar el umbral),
- **% quemadas**,
- **% caducadas** (pasan 30 días sin llegar ni al objetivo ni al umbral).

## Fases

0. **Entorno y configuración** ← *hecho*
1. **Datos**: descarga, paso a hora de NY, unión de contratos, control de calidad ← *hecho: NQ y GC 2015–2026; filtros de días cortos e ilíquidos*
2. **Motor + simulador Apex EOD**, con tests hechos a mano ← *hecho*
3. **ORB (MNQ)**: variantes 5/15/30 min × stop en el rango o por ATR, promediadas ← *in-sample: las 6 variantes pierden tras costes (reports/orb_is.md)*
4. **Validación**: in-sample / out-of-sample, walk-forward, Monte Carlo ← *Monte Carlo y viabilidad Apex hechos (reports/apex_viabilidad.md)*
5. **VWAP (MNQ + MGC)** ← *in-sample: pierde tras costes; MGC tiene ventaja bruta estable (reports/vwap_is.md)*
6. **Momentum de cierre (MNQ)**: ventana 15:20–15:50 ET por el margen de seguridad ← *in-sample: pierde tras costes (reports/cm_is.md)*
7. **Portafolio**: riesgo igual por estrategia y correlaciones
8. **Pine Script v6**: alertas para ejecución manual

En cada fase se reporta: beneficio neto, drawdown máximo, profit factor, % de días ganadores, correlación entre estrategias y % de evaluaciones aprobadas / quemadas.

## Registro de estudios con criterios fijados de antemano

Nota: el filtro de días ilíquidos (src/data/loader.py) usa el volumen del propio día, que por la mañana no se conoce. En la zona de ruido se comprobó que quitarlo no empeora el resultado (PF 1,21, t 2,25 solo con el filtro de calendario).

Criterios: profit factor > 1,15 en el periodo completo, t > 2 y neto positivo en desarrollo y fuera de muestra.

| Estudio | Configuración | Resultado |
|---|---|---|
| ORB 5 min (especificación original, filtro de ATR) | config/orb_5m.yaml | Descartada: pierde en desarrollo; fuera de muestra no significativa (t=0,73) |
| ORB 5 min, última prueba (sin filtro, stop 10 % ATR) | config/orb_5m_final.yaml | **DESCARTADA**: 0 de 12 variantes cumplen (mejor t = 1,28) |
| Momentum de cierre 15:30-15:58 | config/close_momentum.yaml | **DESCARTADA**: sin costes PF 1,01 (t=0,25); con costes PF 0,80 |
| Reversión a la media al VWAP (MNQ) | config/mean_reversion.yaml | **DESCARTADA**: 0 de 6 variantes; PF 0,41-0,87, pierde incluso antes de costes |
| Tendencia VWAP en MGC con stops anchos (0,4 y 0,8 ATR) | config/vwap_mgc.yaml | **DESCARTADA**: 0 de 6 variantes; la ventaja bruta solo existe con stops de 0,1-0,2 ATR y es menor que el coste de ejecución |
| Power of Three / Judas swing (MNQ y MGC) | config/po3_mnq.yaml, config/po3_mgc.yaml | **DESCARTADA**: 0 de 16 variantes; tras una barrida de un lado, la dirección posterior acierta el 49-52 % (azar) |
| Cruce de medias EMA con filtro ADX (MNQ y MGC) | config/ma_mnq.yaml, config/ma_mgc.yaml | **DESCARTADA**: 0 de 24 variantes; el filtro ADX mejora algo la 20/50 pero sin costes el mejor t es 1,58 |
| Setup ICT de oro, horario de Italia (MGC) — SIN SMT | config/gold_ict.yaml | Versión parcial: 0 de 4 variantes; PF 0,47-0,70, pierde antes de costes. **Pendiente: versión con SMT (requiere datos de plata)** |
| **Zona de ruido (Zarattini, Aziz y Barbon 2024) en MNQ** | config/noise_area.yaml | **CUMPLE** la versión fiel con 1 contrato (PF 1,19, t 2,15; 2015-2026). La versión con stop duro no cumple (t 1,2). Ventaja real pero pequeña: NO sirve para aprobar Apex en 30 días (se quema más que se aprueba) |
| Seguimiento de tendencia (AQR) solo en GC, NQ y ES | config/tsmom.yaml (--mercados GC NQ ES) | **NO CUMPLE**: Sharpe 0,18, t 0,79; fuera de muestra -0,3 % anual. Con 3 mercados (NQ y ES correlación 0,93) no hay diversificación |

## Estructura

```
config/            reglas de la firma, del sistema y de los instrumentos
data/raw/          datos descargados (nunca se modifican)
data/processed/    datos limpios
src/data/          carga y limpieza
src/indicators/    ATR, VWAP, rango de apertura
src/strategies/    orb.py, vwap_trend.py, close_momentum.py
src/engine/        motor de backtest
src/risk/          tamaño de posición, límites, simulador Apex EOD
src/validation/    métricas, IS/OOS, walk-forward, Monte Carlo ← *Monte Carlo y viabilidad Apex hechos (reports/apex_viabilidad.md)*
scripts/           lo que se ejecuta
reports/           resultados de cada fase
tests/             comprobaciones automáticas
pine/              Pine Script v6
```

## Pendiente de confirmar con Apex

- ¿"Max Contracts" cuenta contratos mini? ¿1 mini = 10 micros?
- ¿El umbral EOD deja de subir en algún nivel (p. ej., saldo inicial + 100 $)?
- ¿Tocar el límite diario (DLL) pierde la cuenta o solo para el día?
- ¿Qué significa exactamente "Fixed position size during evaluation"?
- ¿Se permiten herramientas que *solo avisan* (alertas de TradingView) si la orden la pones tú a mano?
