# Informe de calidad de los datos

Todas las horas en UTC. Fuente principal: futuros de CME (Databento), contrato continuo por volumen.

| mercado   | desde_utc                 | hasta_utc                 |   velas |   duplicados |   velas_imposibles |   sesiones |   sesiones_cortas_(<600_velas) |   huecos_inesperados_>30min | hueco_mayor     |   picos_que_se_deshacen_(error_o_noticia) |   movimientos_extremos_reales |   cambios_de_contrato |   dias_iliquidos_previsibles |
|:----------|:--------------------------|:--------------------------|--------:|-------------:|-------------------:|-----------:|-------------------------------:|----------------------------:|:----------------|------------------------------------------:|------------------------------:|----------------------:|-----------------------------:|
| NQ        | 2015-01-01 23:00:00+00:00 | 2026-09-27 23:59:00+00:00 | 4086419 |            0 |                  0 |       3034 |                              5 |                          10 | 0 days 10:46:00 |                                       287 |                          4659 |                    47 |                           65 |
| GC        | 2015-01-01 23:00:00+00:00 | 2026-09-27 23:59:00+00:00 | 4088399 |            0 |                  0 |       3030 |                             31 |                         178 | 0 days 10:42:00 |                                       111 |                          2478 |                    59 |                           58 |

## Corte desarrollo / fuera de muestra (fijado ahora, antes de cualquier resultado)

```json
{
  "NQ": {
    "primera_sesion": "2015-01-02",
    "ultima_sesion": "2026-09-28",
    "inicio_fuera_de_muestra": "2023-03-22"
  },
  "GC": {
    "primera_sesion": "2015-01-02",
    "ultima_sesion": "2026-09-28",
    "inicio_fuera_de_muestra": "2023-03-22"
  },
  "diario_6A": {
    "primera_sesion": "2010-06-07",
    "ultima_sesion": "2026-09-27",
    "inicio_fuera_de_muestra": "2021-11-12"
  },
  "diario_6B": {
    "primera_sesion": "2010-06-07",
    "ultima_sesion": "2026-09-27",
    "inicio_fuera_de_muestra": "2021-11-12"
  },
  "diario_6E": {
    "primera_sesion": "2010-06-07",
    "ultima_sesion": "2026-09-27",
    "inicio_fuera_de_muestra": "2021-11-12"
  },
  "diario_6J": {
    "primera_sesion": "2010-06-07",
    "ultima_sesion": "2026-09-27",
    "inicio_fuera_de_muestra": "2021-11-12"
  },
  "diario_CL": {
    "primera_sesion": "2010-06-07",
    "ultima_sesion": "2026-09-27",
    "inicio_fuera_de_muestra": "2021-11-08"
  },
  "diario_ES": {
    "primera_sesion": "2010-06-07",
    "ultima_sesion": "2026-09-27",
    "inicio_fuera_de_muestra": "2021-11-12"
  },
  "diario_GC": {
    "primera_sesion": "2010-06-07",
    "ultima_sesion": "2026-09-27",
    "inicio_fuera_de_muestra": "2021-11-09"
  },
  "diario_HG": {
    "primera_sesion": "2010-06-07",
    "ultima_sesion": "2026-09-27",
    "inicio_fuera_de_muestra": "2021-11-09"
  },
  "diario_HO": {
    "primera_sesion": "2010-06-07",
    "ultima_sesion": "2026-09-27",
    "inicio_fuera_de_muestra": "2021-11-08"
  },
  "diario_NG": {
    "primera_sesion": "2010-06-07",
    "ultima_sesion": "2026-09-27",
    "inicio_fuera_de_muestra": "2021-11-09"
  },
  "diario_NQ": {
    "primera_sesion": "2010-06-07",
    "ultima_sesion": "2026-09-27",
    "inicio_fuera_de_muestra": "2021-11-12"
  },
  "diario_RTY": {
    "primera_sesion": "2017-07-09",
    "ultima_sesion": "2026-09-27",
    "inicio_fuera_de_muestra": "2023-12-22"
  },
  "diario_SI": {
    "primera_sesion": "2010-06-07",
    "ultima_sesion": "2026-09-27",
    "inicio_fuera_de_muestra": "2021-11-09"
  },
  "diario_YM": {
    "primera_sesion": "2010-06-07",
    "ultima_sesion": "2026-09-27",
    "inicio_fuera_de_muestra": "2021-11-10"
  },
  "diario_ZB": {
    "primera_sesion": "2010-06-07",
    "ultima_sesion": "2026-09-27",
    "inicio_fuera_de_muestra": "2021-11-10"
  },
  "diario_ZF": {
    "primera_sesion": "2010-06-07",
    "ultima_sesion": "2026-09-27",
    "inicio_fuera_de_muestra": "2021-11-10"
  },
  "diario_ZN": {
    "primera_sesion": "2010-06-07",
    "ultima_sesion": "2026-09-27",
    "inicio_fuera_de_muestra": "2021-11-10"
  },
  "diario_ZT": {
    "primera_sesion": "2010-06-07",
    "ultima_sesion": "2026-09-27",
    "inicio_fuera_de_muestra": "2021-11-10"
  }
}
```

## Detalle por mercado

### NQ

Huecos inesperados de más de 30 min dentro de la sesión: **10**. Los 10 mayores:

| inicio_utc                | duracion        |
|:--------------------------|:----------------|
| 2025-11-28 02:44:00+00:00 | 0 days 10:46:00 |
| 2015-06-30 21:14:00+00:00 | 0 days 03:31:00 |
| 2019-02-27 00:40:00+00:00 | 0 days 03:05:00 |
| 2020-06-30 21:59:00+00:00 | 0 days 02:01:00 |
| 2020-03-16 05:27:00+00:00 | 0 days 01:21:00 |
| 2020-03-16 11:47:00+00:00 | 0 days 01:14:00 |
| 2020-03-17 03:42:00+00:00 | 0 days 00:55:00 |
| 2020-03-16 09:16:00+00:00 | 0 days 00:51:00 |
| 2020-03-16 11:07:00+00:00 | 0 days 00:39:00 |
| 2020-03-16 07:00:00+00:00 | 0 days 00:31:00 |

Picos de 1 minuto que se deshacen en el minuto siguiente (errores o latigazos de noticias; NO se borran): **287**. Los 10 mayores:

| tiempo_utc                |   rendimiento_% |
|:--------------------------|----------------:|
| 2020-03-17 13:32:00+00:00 |           0.885 |
| 2020-03-16 14:39:00+00:00 |           0.824 |
| 2020-03-18 20:06:00+00:00 |           0.812 |
| 2025-04-07 14:14:00+00:00 |          -0.72  |
| 2020-03-18 13:30:00+00:00 |          -0.7   |
| 2022-07-13 12:29:00+00:00 |           0.69  |
| 2020-03-16 19:59:00+00:00 |          -0.689 |
| 2025-04-09 17:18:00+00:00 |          -0.68  |
| 2020-03-23 12:03:00+00:00 |          -0.667 |
| 2020-03-13 19:59:00+00:00 |           0.666 |

Días ilíquidos previsibles (se excluyen de los backtests): **65**. Ejemplos: 2015-09-14, 2015-09-15, 2015-10-13, 2015-12-29, 2015-12-31, 2016-03-14, 2016-12-12, 2016-12-13

### GC

Huecos inesperados de más de 30 min dentro de la sesión: **178**. Los 10 mayores:

| inicio_utc                | duracion        |
|:--------------------------|:----------------|
| 2025-11-28 02:48:00+00:00 | 0 days 10:42:00 |
| 2020-02-27 21:59:00+00:00 | 0 days 10:01:00 |
| 2020-06-30 14:10:00+00:00 | 0 days 09:50:00 |
| 2020-02-28 13:59:00+00:00 | 0 days 06:01:00 |
| 2024-11-28 18:59:00+00:00 | 0 days 04:23:00 |
| 2015-06-30 21:14:00+00:00 | 0 days 03:31:00 |
| 2020-02-27 18:20:00+00:00 | 0 days 03:10:00 |
| 2026-07-30 20:52:00+00:00 | 0 days 03:08:00 |
| 2018-05-31 20:57:00+00:00 | 0 days 03:03:00 |
| 2019-02-27 00:43:00+00:00 | 0 days 03:02:00 |

Picos de 1 minuto que se deshacen en el minuto siguiente (errores o latigazos de noticias; NO se borran): **111**. Los 10 mayores:

| tiempo_utc                |   rendimiento_% |
|:--------------------------|----------------:|
| 2026-02-01 23:11:00+00:00 |          -1.169 |
| 2026-01-30 18:28:00+00:00 |          -0.895 |
| 2020-03-24 10:54:00+00:00 |           0.835 |
| 2020-12-21 10:06:00+00:00 |          -0.798 |
| 2026-02-02 06:02:00+00:00 |          -0.658 |
| 2026-01-29 15:32:00+00:00 |          -0.657 |
| 2016-06-24 03:56:00+00:00 |           0.654 |
| 2026-01-29 15:44:00+00:00 |          -0.65  |
| 2020-03-24 10:59:00+00:00 |          -0.574 |
| 2026-01-29 15:19:00+00:00 |          -0.57  |

Días ilíquidos previsibles (se excluyen de los backtests): **58**. Ejemplos: 2015-01-30, 2016-01-04, 2016-03-29, 2016-04-05, 2016-05-30, 2016-12-27, 2018-07-31, 2019-03-29
