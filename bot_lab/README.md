# Trading Bot Lab

Laboratorio de investigación sistemática de estrategias para NQ/MNQ. Parte de la infraestructura existente (datos, sesiones, costes y métricas de la auditoría) y no modifica ningún archivo original.

**Resultado del 30-sep-2026: NO HAY NUEVO EDGE ROBUSTO.** Ver `reports/FINAL_REPORT.md`.

| Archivo | Qué es |
|---|---|
| `PROJECT_AUDIT.md` | Mapa del proyecto antes de programar |
| `CRITERIOS.md` | Partición, costes, protocolo y clasificación A-E, pre-registrados |
| `research/hypotheses/` | Ficha de cada BOT (hipótesis, reglas, variantes) |
| `RESEARCH_LOG.md` | Registro de todas las hipótesis probadas |
| `research/finalistas.json` | Finalistas congelados antes de abrir el TEST |
| `core/` | Datos (contexto de 1 min, velas de 5/15 min, VWAP, ajuste causal de roll), indicadores, motor numba y métricas |
| `strategies/` | Un módulo por familia (BOT 13-26) y envoltorios de BOT 01/02 |
| `validation/` | Protocolo, walk-forward, sensibilidad/estabilidad, bootstrap/Monte Carlo, regímenes, clasificación |
| `portfolio/` | Cartera y correlaciones, tamaño, prop firm |
| `tests/` | Motor, look-ahead por truncamiento, ventanas, costes, casos límite, validación |

## Reproducir (desde la raíz del repositorio)
```bash
python -m pytest -q tests auditoria/tests bot_lab/tests     # 181 pruebas
python -m bot_lab.run_lab investigacion                     # etapa 1 (TEST fuera de memoria), ~1 min
python -m bot_lab.run_lab test                              # etapa 2: abre el TEST UNA vez (se niega si ya se abrió)
python -m bot_lab.generar_informe                           # informe, panel y gráficos
```

Necesita `numba` y `scipy`, además de `requirements.txt`.
