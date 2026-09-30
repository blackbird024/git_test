# Auditoría, validación y cartera (30-sep-2026)

Carpeta independiente: **no modifica ningún archivo original** del proyecto. Cada ejecución crea
`experimentos/<AAAAMMDD_HHMM>/` con su configuración, manifiesto (commit, versiones, SHA-1 de los datos, semilla),
resultados, gráficos e informe.

| Archivo | Qué es |
|---|---|
| `CRITERIOS.md` | Criterios de evaluación, asignaciones de cartera y configuraciones de riesgo, registrados ANTES de ejecutar |
| `AUDITORIA_CODIGO.md` | Fase 1: revisión del código, los datos y la metodología (errores, supuestos, gravedad) |
| `config/auditoria.yaml` | Parámetros de las pruebas (vecindades, costes, bootstrap, semilla) |
| `src/metricas.py` | Métricas, IC por bootstrap por bloques e IID, tablas por periodo |
| `src/validadas.py` | Fases 1-4 para zona de ruido y RSI(2) |
| `src/variantes_zr.py` | Copia de la zona de ruido con latencia configurable (con 0 = idéntica al original, probado) |
| `src/rechazadas.py` | Fases 5-6: re-ejecución de las rechazadas y del bot con su código original |
| `src/cartera.py` | Fases 7-8: cartera, correlaciones, solapamiento, simulación de riesgo |
| `run_auditoria.py` / `generar_informe.py` | Ejecución completa e informe |
| `tests/` | Pruebas de métricas, bootstrap, latencia, pesos, simulación y clasificación |

## Reproducir (desde la raíz del repositorio)
```bash
python -m pytest -q tests auditoria/tests          # 104 + pruebas de la auditoría
python -m auditoria.run_auditoria                  # ~15-25 min
python -m auditoria.generar_informe auditoria/experimentos/<carpeta>
```
Necesita los datos de `data/raw/` (Databento; copia privada en el repositorio `apex-datos`) y `data/processed/`
(se generan con `run_all.py` paso 0 o con `cargar_databento` + `limpiar`).
