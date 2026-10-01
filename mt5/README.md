# MT5 – Reversión a la VWAP (intradía)

Expert Advisor para MetaTrader 5: `VwapReversion.mq5`.

## Cómo funciona

1. Desde la apertura de la sesión calcula la **VWAP** (precio medio ponderado por volumen)
   y su desviación estándar, con velas de 1 minuto.
2. **Entrada:** si una vela cierra 2 desviaciones **por debajo** de la VWAP, compra; si cierra
   2 desviaciones **por encima**, vende en corto. Apuesta a que el precio vuelve a su media.
3. **Salida:** cuando el precio vuelve a la VWAP (ganancia), en el stop-loss
   (1.5 desviaciones más allá de la entrada) o a la hora de cierre forzoso.
4. **Nunca** deja posiciones abiertas de un día para otro.

## Gestión de riesgo (valores por defecto)

| Parámetro | Valor |
|-----------|-------|
| Riesgo por operación | 0.5% del equity (el lote se calcula según el stop) |
| Máximo de operaciones al día | 3 |
| Pérdida diaria máxima | 2% del balance: cierra y deja de operar ese día |
| Primeros minutos de la sesión | 30 sin operar (la VWAP aún no es fiable) |
| Solo cuentas demo | Sí (`InpDemoOnly`) |

## Instalación

1. En MT5: **Archivo → Abrir carpeta de datos** → `MQL5/Experts/` y copia `VwapReversion.mq5`.
2. Ábrelo en **MetaEditor** (F4) y compílalo (F7). Debe terminar con 0 errores.
3. En MT5, abre un gráfico del instrumento (p. ej. `US500`, `NAS100` o `USTEC`; el nombre depende del bróker).
4. Arrastra el EA al gráfico, activa **Permitir trading algorítmico** y el botón **Algo Trading**.

## Ajustar el horario

Las horas son **del servidor del bróker** (la que muestra la Observación del Mercado), no la tuya.
Para índices de EE. UU. la sesión abre a las 9:30 de Nueva York. Con un servidor en GMT+3
(muy común) eso son las **16:30**, que es el valor por defecto. Si tu bróker usa otra zona horaria,
cambia `InpSessionStartHour`/`Min`, `InpLastEntryHour`/`Min` y `InpCloseAllHour`/`Min`.

## Probar antes de operar

Primero en el **Probador de Estrategias** (Ctrl+R): elige el EA, el símbolo, el modelo
"Cada tick basado en ticks reales" y al menos 3-6 meses. Revisa el resultado neto, el drawdown
máximo y el número de operaciones. Luego déjalo correr unas semanas en la cuenta demo.
