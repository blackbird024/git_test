# Sistema multiestrategia para futuros (oro y Nasdaq) — metodología de 4 pasos

1. **Ventaja**: hipótesis con causa explicable (`edges/`).
2. **Mejora**: filtros de régimen, gestión y salidas, uno a uno.
3. **Validación**: fuera de muestra, sensibilidad ±20 %, otros mercados, costes x2, Monte Carlo.
4. **Implementación**: simulación Apex (drawdown EOD), incubación y forward test (sin enviar órdenes).

## Ejecutar todo

```bash
pip install -r requirements.txt
python run_all.py        # datos -> calidad -> (pasos aprobados) -> informes en reports/
python -m pytest         # tests: look-ahead, horas, stop/objetivo en la misma vela, datos
```

## Estructura

| Carpeta | Contenido |
|---|---|
| `data/raw/` | Futuros de CME (Databento, 1 minuto y diario). No se suben a GitHub (licencia) |
| `data/mt5/` | CSV exportados de MT5 (opcional) |
| `data/processed/` | Velas limpias en UTC y marcos 5M, 1H, 4H, 1D |
| `config/particion.json` | Corte desarrollo (70 %) / fuera de muestra (30 %), fijado una sola vez |
| `src/data/` | Cargadores (Databento y MT5), control de calidad, marcos temporales |
| `src/engine/` | Costes, ejecución (entrada en la vela siguiente; SL y TP en la misma vela = pérdida), look-ahead |
| `src/strategies/`, `src/metrics/`, `src/apex/`, `src/report/` | Estrategias, métricas, simulador Apex, informes HTML |
| `edges/` | Una ficha por ventaja: hipótesis, causa, reglas y qué la refutaría |
| `reports/` | Informes (`calidad_datos.md`, y un HTML por estrategia) |
| `archive/` | Experimentos anteriores a esta metodología (solo referencia) |

## Reglas del proyecto

- Todo en UTC; las reglas de sesión se escriben en hora de Italia o de Nueva York y se convierten
  (los cambios de horario de verano de EE. UU. y de Europa no coinciden).
- Señales solo con velas cerradas; ejecución en la apertura de la vela siguiente.
- Máximo 3 parámetros libres por estrategia; criterios de aprobado fijados antes de ver resultados.
- Costes: comisión + 1 tick por lado (2 en aperturas de Londres, Nueva York y Globex).

## Estado

- [x] Paso 0: datos, calidad, marcos temporales, tests base
- [x] Paso 1: versión mínima de cada ventaja (sobrevive solo RSI(2) en NQ; ver `reports/paso1_ventajas.md`)
- [x] Paso 2: ninguna mejora se queda (`reports/paso2_mejoras.md`)
- [x] Paso 3: **RSI(2) en NQ APROBADA** (`reports/nq_rsi2.html`); barrido de Londres y viernes→lunes RECHAZADAS
- [ ] Paso 4: Apex no aplica al RSI(2) (mantiene posiciones de noche). Incubación en papel: al menos 2 meses

## Modo papel (cada día, después de las 23:00 de Italia)

```bash
python scripts/senal_hoy.py      # actualiza NQ desde Databento (céntimos) y dice: COMPRAR / MANTENER / VENDER / NADA
```

Alternativa en TradingView: `pine/nq_rsi2.pine` (gráfico diario de NQ1!/MNQ1!, con alertas al cierre).
