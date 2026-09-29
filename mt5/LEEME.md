# EA de la cartera en MetaTrader 5 (cuenta DEMO de Pepperstone)

`APEX_Cartera_NAS100.mq5` opera solo las dos estrategias validadas del proyecto, en el CFD **NAS100**:

| Estrategia | Qué hace | Horas (Italia, casi todo el año) |
|---|---|---|
| Zona de ruido (`edges/zona_ruido_mnq.md`) | Intradía: compra/vende si el precio sale del "ruido normal" de cada media hora; cierra si pierde la banda o el VWAP | Chequeos 16:00–21:30, cierre de todo a las 21:59:50 |
| RSI(2) (`edges/nq_rsi2.md`) | Swing: compra si RSI(2) < 20 y cierre > SMA(200); sale si RSI(2) > 70 o tras 5 sesiones | Al abrir cada vela diaria (reapertura, ~00:00) |

Tamaño: el equivalente a **1 MNQ = 2 $ por punto** (entrada `DineroPorPunto`); el EA calcula los lotes con el valor
del tick de tu cuenta.

## Instalación (una vez)
1. MT5 → **Archivo → Abrir carpeta de datos** → `MQL5/Experts/`. Copia ahí `APEX_Cartera_NAS100.mq5`.
2. Ábrelo con **MetaEditor** (F4) y pulsa **Compilar** (F7). Si sale algún error, cópiamelo tal cual.
3. **Herramientas → Opciones → Asesores expertos**: marca *Permitir trading algorítmico* y, para Telegram, *Permitir
   WebRequest* añadiendo `https://api.telegram.org`.
4. Abre un gráfico de **NAS100** (cualquier marco) y arrastra el EA. En las entradas:
   - `DesfaseServidorNY = 7` (Pepperstone). **Compruébalo:** al arrancar, el EA escribe la hora de Nueva York;
     tiene que ser tu hora de Italia menos 6 h (menos 5 h en las semanas de cambio de hora).
   - `TelegramToken` y `TelegramChatId` si quieres los avisos (se quedan en tu MT5, no en el código).
5. La cuenta tiene que ser de **cobertura (hedging)** para llevar las dos estrategias a la vez; si no, el EA avisa
   y no arranca (o activa solo una).
6. MT5 tiene que estar **encendido de lunes a viernes**, al menos de 15:00 a 22:30 y en la reapertura de las 00:00
   (PC siempre encendido o VPS).

## Antes de dejarlo solo: probarlo en el Probador de estrategias
Ver → Probador de estrategias → EA `APEX_Cartera_NAS100`, símbolo NAS100, modelo **"Cada tick basado en ticks
reales"**, últimos 3–6 meses. Mándame el informe: comprobaré que las entradas coinciden con las del backtest en
los mismos días (mismas horas y mismo sentido).

## Diferencias con el backtest (normal que el resultado no sea idéntico)
- **Precio:** CFD NAS100, no el futuro NQ. La zona de ruido trabaja en % desde la apertura, así que se traslada bien.
- **VWAP:** con volumen de ticks del CFD (el real del futuro no está en MT5).
- **Costes:** spread en vez de comisión; el RSI(2) paga **swap** cada noche.
- **RSI(2):** se calcula con las velas diarias del CFD (en el backtest, cierres ajustados del futuro).

## Registro
Cada operación queda en `MQL5/Files/APEX_registro.csv` (hora, estrategia, acción, precio, motivo). Sirve para
comparar con el backtest y con `papel/registro.csv`.
