# FORWARD_TESTING v1.0 — README

Sistema reproducible para validar en datos NUEVOS (desde el **30/09/2026**) las dos supervivientes: **RSI(2)** y **Noise Zone**, congeladas. Reglas completas: `FORWARD_TESTING_PROTOCOL.md`.

## Estructura
```text
forward_testing/
  FORWARD_TESTING_README.md     este archivo
  FORWARD_TESTING_PROTOCOL.md   reglas del forward (fijadas antes del inicio)
  POST_HOC.md                   ideas nuevas (NO entran en el sistema)
  config/
    FORWARD_TESTING_CONFIG.json (+ .sha256)     hashes, parámetros, costes, horarios, reglas, tamaño, noche, umbrales
    bandas_deriva_v1.json, bandas_deriva_v1_pct.json, referencia_mae_mfe.csv, referencia_backtest.json
  raw/nq/          datos NQ nuevos (append-only; SHA-256 en raw/MANIFIESTO.csv; no se versionan por licencia)
  raw/ea/          copias fechadas del registro del EA (SHA-256 en raw/ea/MANIFIESTO.csv)
  logs/            trades_teorico.csv (oficial, append-only), posiciones_abiertas.csv, trades_ea.csv,
                   emparejamiento.csv, estado_dias.csv, ejecuciones.log
  alerts/          alertas.csv (solo informativas)
  daily/           informe diario AAAA-MM-DD.md
  weekly/          informe semanal AAAA-Www.md
  reports/         backtest_vs_forward.md
  src/             congelado, datos, teorico, ea, integridad, comparar, deriva, informes
  tests/           pruebas de integridad
  run_diario.py    un comando por día
  congelar.py      congelación (hecha el 30-sep-2026 antes de la apertura; no se vuelve a ejecutar)
```

## Instrucciones exactas desde el 30/09/2026

### Una vez (hoy, 30-sep)
1. **EA en MT5.** El EA solo cambia en el registro; ninguna regla cambia.
   - En MetaEditor, abre `APEX_Multiestrategia.mq5`. Copia antes la versión nueva del repositorio (`mt5/APEX_Multiestrategia.mq5`) a `MQL5/Experts`.
   - Compila con **F7**: tiene que dar 0 errores.
   - En el gráfico NAS100, abre las propiedades del EA y pon **PerdidaDiariaMax = 5000**. Deja todo lo demás igual: DineroPorPunto 2 y 2, CaidaMaximaCartera 5000.
   - A partir de ahora el EA escribe `MQL5/Files/APEX_registro_v2.csv`.
2. **Verificación externa (Myfxbook)**
   1. Crea una cuenta en myfxbook.com.
   2. En MT5, crea una **contraseña de inversor** (solo lectura), **nunca** la principal: Herramientas → Opciones → Servidor → Cambiar.
   3. En Myfxbook: Portfolio → Add Account → MetaTrader 5, con servidor `PepperstoneUK-Demo`, tu número de cuenta y la contraseña de inversor.
   4. Marca el track record como verificado (Track Record / Trading Privileges).
   5. No compartas esas contraseñas en ningún chat.

### Cada día de mercado (por la mañana, hora de Italia; el día anterior ya tiene datos completos)
```bash
python -m forward_testing.run_diario
```
- Descarga los datos nuevos: estima el coste antes y **no descarga si pasa de 0,50 $**.
- Verifica la congelación y la integridad.
- Calcula el forward teórico, lo registra, compara y escribe `daily/AAAA-MM-DD.md`. Los viernes escribe además el informe semanal.

**Si quieres incluir el EA** (recomendado al menos una vez por semana): copia `MQL5/Files/APEX_registro_v2.csv` (en MT5: Archivo → Abrir carpeta de datos → MQL5 → Files) y ejecuta:
```bash
python -m forward_testing.run_diario --ea /ruta/a/APEX_registro_v2.csv
```

**Alternativa sin ordenador:** pídeme en una sesión de Claude "ejecuta el forward diario" y adjunta el `APEX_registro_v2.csv` si lo tienes.

### Qué mirar en el informe diario
1. **ESTADO DEL DÍA.** Si sale INVALID, lee el motivo. No se añade nada al registro hasta resolverlo.
2. **DRIFT ALERTS.** Son solo informativas. Nunca se apaga ni se cambia nada por una alerta.
3. **BACKTEST VS FORWARD.** Por debajo de 50 operaciones (Noise Zone) o 15 (RSI(2)), **no es concluyente**.

## Pruebas
```bash
python -m pytest -q forward_testing/tests                                  # integridad del forward
python -m pytest -q tests auditoria/tests bot_lab/tests survivor/tests     # resto del proyecto
```
