# Sistema multiestrategia intradía (semiautomático) — Apex EOD

Investigación y backtest en Python de 3 estrategias intradía en MNQ y MGC,
con simulación de las reglas de la evaluación EOD de Apex Trader Funding.
El sistema **genera señales**; las órdenes las coloca una persona a mano (Apex no permite automatización).

Plan completo y decisiones: [PLAN.md](PLAN.md).

## Puesta en marcha

```bash
pip install -r requirements.txt
python -m pytest -q                              # comprobar que el motor funciona
python scripts/download_databento.py             # ver cuánto costaría descargar los datos
python scripts/download_databento.py --confirmar # descargarlos (necesita DATABENTO_API_KEY)
```

## Dónde está cada cosa

| Carpeta | Contenido |
|---|---|
| `config/` | Reglas de Apex, del sistema y de los instrumentos (se editan aquí, no en el código) |
| `src/engine/` | Motor de backtest vela a vela |
| `src/risk/` | Tamaño de posición y simulador de evaluación Apex EOD |
| `src/validation/` | Métricas |
| `src/data/` | Carga de datos |
| `tests/` | Pruebas automáticas con casos calculados a mano |
