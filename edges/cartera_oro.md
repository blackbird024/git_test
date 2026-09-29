# CARTERA_ORO_v1.0: zona de ruido y RSI(2) en el oro (MGC), mismas reglas que en NQ

*Ficha escrita el 29-sep-2026, ANTES de ejecutar ningún backtest en el oro. Petición del usuario: "misma
estrategia" en el oro, para operarla en XAUUSD (Pepperstone, demo).*

## Qué se prueba
Las dos estrategias validadas en NQ, **sin cambiar ninguna regla ni parámetro**, en futuros de oro (GC, operado
como MGC: 10 $ por punto, tick 0,10):

1. **Zona de ruido** (`edges/zona_ruido_mnq.md`, código `src/strategies/zona_ruido.py`): misma sesión 09:30–16:00
   NY, sigma de 14 días, chequeos cada media hora de 10:00 a 15:30 NY, salida por banda/VWAP, cierre al final de la
   sesión. 1 MGC fijo. Costes: 1 tick por lado + 1 $ por contrato y lado (igual que en NQ).
   - Nota: la sesión "regular" del oro en CME es 08:20–13:30 NY; se mantienen las horas de NY de la versión validada
     porque el usuario pide la misma estrategia. No se probarán otras horas en esta versión.
2. **RSI(2)** (`edges/nq_rsi2.md`, código `src/strategies/nq_rsi2.py`): sesiones diarias de CME, cierre ajustado >
   SMA(200) y RSI(2) < 20 → compra en la reapertura; salida si RSI(2) > 70 o tras 5 sesiones; sin stop. 1 MGC.
   Costes estándar del proyecto.

## Periodo
Desarrollo: sesiones anteriores al **22-mar-2023** (`config/particion.json`, GC). Se informa también del periodo
posterior por separado; como estas reglas ya se vieron en NQ en ese periodo, para el oro sigue siendo fuera de
muestra (nunca se ha mirado el oro con ellas).

## Criterio (por estrategia, por separado)
Pasa si, **después de costes**, en desarrollo: profit factor > 1 **y** R medio (o rendimiento medio por operación)
> 0 con **t ≥ 2**; y en el periodo posterior profit factor > 1. Si no: no se opera en el oro, sin ajustes para
salvarla.

## Sesgos
1. El oro no es el Nasdaq: la zona de ruido se basa en el momentum intradía de los índices (Zarattini et al. usan
   SPY); no hay motivo teórico fuerte para que funcione igual en el oro.
2. El RSI(2) con filtro de tendencia es de índices de acciones (Connors); en materias primas la evidencia es menor.
3. Dos pruebas (dos estrategias): con t ≥ 2 en cada una, sigue existiendo probabilidad de un falso positivo.

## Resultado (añadido tras ejecutar). Informe: `reports/CARTERA_ORO_v1.0/`
| Oro (1 MGC) | Tramo | Operaciones | PF | Media por op. | t | Neto |
|---|---|---|---|---|---|---|
| Zona de ruido | desarrollo | 1.953 | 0,74 | −4,16 $ | −4,34 | −8.128 $ |
| Zona de ruido | posterior | 831 | 1,08 | +2,99 $ | 0,59 | +2.484 $ |
| RSI(2) | desarrollo | 89 | 1,15 | R +0,082 | 0,34 | +1.400 $ |
| RSI(2) | posterior | 61 | 1,29 | R +0,108 | 0,39 | +4.409 $ |

Referencia NQ con el mismo cálculo (reproduce lo validado): zona de ruido PF 1,19 / t 2,26 en desarrollo;
RSI(2) PF 1,46 / t 1,22.

**Veredicto: las dos RECHAZADAS en el oro.** La zona de ruido pierde claramente en desarrollo (t −4,3): en el oro el
movimiento fuera del "ruido" no continúa, más bien revierte. El RSI(2) gana poco y sin significación (t 0,3-0,4),
con un drawdown de −8.615 $ en el periodo posterior. No se operan en XAUUSD.
