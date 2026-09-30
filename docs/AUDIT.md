# Auditoría del repositorio (2026-09-30)

## Estado encontrado

| Elemento | Hallazgo |
|---|---|
| Archivos | `README.md` (`# git_test`), `hello_world.txt` ("Hello World!"). Nada más. |
| Datasets | **Ninguno.** No hay XAUUSD ni ningún otro instrumento. |
| Formato / timezone / broker | No aplica (no hay datos). |
| Calidad del volumen | No aplica. |
| Histórico disponible | 0 barras. |
| Scripts existentes | Ninguno. |
| Framework de backtesting | Ninguno. |
| Costes | Ninguno definido. |

No había código previo que modificar ni que reutilizar. Todo lo que hay en `crt_xauusd/` es nuevo.

## Intentos de obtener datos reales (sin inventar nada)

| Fuente | Resultado |
|---|---|
| Dukascopy datafeed (`datafeed.dukascopy.com`) | **Bloqueado** por la política de red del entorno (HTTP 403 en CONNECT). |
| histdata.com, Yahoo Finance, stooq, Kaggle, HuggingFace, Nasdaq Data Link, Polygon, TwelveData | Sin conexión desde el entorno (bloqueado o no alcanzable). |
| Conector Interactive Brokers, `XAUUSD` (conid 69067924, IBCMDTY "London Gold") | Accesible, pero devuelve barras **MidPoint sin campo de volumen**. La hipótesis exige volumen, así que no sirve. Además, descargar años de barras de 15M por el conector no es viable (cada respuesta entra en el contexto de la conversación). |

**Conclusión:** en esta sesión no hay ningún dataset adecuado. No se ha fabricado ningún dato. Los
datos sintéticos de `tests/` solo sirven para comprobar el código (lógica, lookahead, fontanería) y nunca
se usan para resultados.

Lo que falta exactamente está en `docs/DATA_REQUIREMENTS.md`.

## Supuestos documentados

1. **Velas 4H** construidas a partir de 15M sobre el reloj de pared de New York, ancladas a las 17:00
   (17, 21, 01, 05, 09, 13). Coinciden con las 4H de un broker MT4/MT5 con servidor GMT+2/+3 (= NY+7)
   y con las "4H de las 1am/5am/9am NY" habituales en CRT. Otros brokers dibujan otras 4H. Es una convención y
   queda fijada.
2. **Sesión de XAUUSD CFD**: domingo 18:00 a viernes 17:00 NY, con pausa diaria de 17:00 a 18:00 NY. El cambio de
   horario (DST) ocurre el domingo a las 02:00 NY con el mercado cerrado, así que ningún bucket 4H cruza un
   cambio de hora.
3. **Volumen**: se asume **tick volume** del broker salvo que la metadata del dataset diga otra cosa. Mide
   actividad de cotizaciones en UN proveedor, no volumen negociado del oro.
4. **Costes**: los valores de `CONFIG.json` (spread 0.20, comisión 0.07 round-trip y slippage 0.05 por lado, en
   USD por onza) son **supuestos provisionales**, no datos reales de un broker. Hay que sustituirlos por los del
   broker antes de interpretar los resultados. La sensibilidad se estudia a 1×, 2× y 3×.
5. **Unidad de slippage**: 0.10 USD (10 puntos MT5 en un XAUUSD de 2 decimales). El tick mínimo (0.01) es
   demasiado pequeño para que la sensibilidad de "1, 2, 3 ticks" sea informativa.
6. **Buffer del stop**: 0.50 USD fijo. No se ha optimizado.
