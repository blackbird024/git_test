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

0. **Entorno y configuración** ← *hecho (configs)*
1. **Datos**: descarga, paso a hora de NY, unión de contratos, control de calidad
2. **Motor + simulador Apex EOD**, con tests hechos a mano
3. **ORB (MNQ)**: variantes 5/15/30 min × stop en el rango o por ATR, promediadas
4. **Validación**: in-sample / out-of-sample, walk-forward, Monte Carlo
5. **VWAP (MNQ + MGC)**
6. **Momentum de cierre (MNQ)**: ventana 15:20–15:50 ET por el margen de seguridad
7. **Portafolio**: riesgo igual por estrategia y correlaciones
8. **Pine Script v6**: alertas para ejecución manual

En cada fase se reporta: beneficio neto, drawdown máximo, profit factor, % de días ganadores, correlación entre estrategias y % de evaluaciones aprobadas / quemadas.

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
src/validation/    métricas, IS/OOS, walk-forward, Monte Carlo
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
