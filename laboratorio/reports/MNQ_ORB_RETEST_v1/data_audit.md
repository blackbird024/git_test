# Auditoría de datos · MNQ_ORB_RETEST_v1

Generada por `orb_retest/audit.py` (solo lectura). Datos en el entorno del laboratorio, no en el proyecto local descrito en el encargo (`src/engine/...`, 2015-2026, 4,1 M velas): esos archivos no existen aquí.

- **fuente**: ['/home/user/git_test/alpaca/.lab_cache/databento_nq_1m_2018_2024.pkl', '/home/user/git_test/alpaca/.lab_cache/databento_glbx_1m.pkl']
- **simbolo**: NQ.c.0 (Databento GLBX.MDP3, ohlcv-1m): E-mini Nasdaq-100 continuo por CALENDARIO, SIN ajuste de rollover. MNQ tiene el mismo precio (índice NDX × 0,1 de multiplicador); se usa el precio de NQ.
- **zona_horaria_original**: UTC; convertida a America/New_York con tz_convert (respeta los cambios de horario)
- **convencion_timestamp**: hora de INICIO de cada vela de 1 min (Databento ts_event)
- **primer_timestamp_ET**: 2018-01-01 18:00:00-05:00
- **ultimo_timestamp_ET**: 2026-10-02 16:59:00-04:00
- **filas**: 3056144
- **duplicados**: 0
- **indice_ordenado**: True
- **nan_ohlc**: 0
- **velas_imposibles**: 0
- **precios_fuera_de_rejilla_0_25**: 0
- **volumen_cero**: 0
- **huecos_mayores_de_60_min_fuera_de_fines_de_semana**: 1787
- **contratos_distintos**: 36
- **cambios_de_contrato**: 35 elementos (lista completa en data_audit.json)
- **sesiones_XNYS_con_datos**: 2165
- **primera_sesion**: 2018-01-02
- **ultima_sesion**: 2026-10-02
- **medias_jornadas**: 18 elementos (lista completa en data_audit.json)
- **sesiones_con_mas_de_un_contrato_en_RTH**: 0
- **sesiones_con_rango_9_30_9_44_incompleto**: [['2020-03-09', 5], ['2020-03-12', 7], ['2020-03-16', 1]]
- **sesiones_RTH_con_minutos_sin_operaciones**: 8
- **minutos_RTH_sin_operaciones_total**: 58
- **sesiones_sin_vela_09_30**: 0

**Notas**
- Los ~1.800 'huecos > 60 min' son la pausa diaria de CME (17:00-18:00 ET): uno por sesión. No son datos perdidos.
- Las 3 sesiones con rango 9:30-9:44 incompleto (9, 12 y 16-mar-2020) corresponden a las suspensiones por caída límite; el 9 y el 12 no se operan (regla: ≥ 14 de 15 minutos con datos).
- NQ.c.0 es continuo por calendario SIN ajustar: cada sesión usa precios reales negociables del contrato del día (ninguna sesión regular mezcla contratos). En la semana de vencimiento el continuo sigue en el contrato que vence; esas sesiones se marcan (roll_week) y se desglosan, no se eliminan.
- Festivos, medias jornadas y horario de verano: calendario XNYS (exchange_calendars) y conversión UTC → America/New_York por fecha; la vela de 9:30 ET existe en todas las sesiones.
- Precio de NQ usado como MNQ (mismo subyacente y misma rejilla de 0,25 pts). MNQ cotiza desde may-2019: los años 2018-2019 son una aproximación con el contrato grande.
