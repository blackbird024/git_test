# EAs de MetaTrader 5 (cuenta DEMO de Pepperstone)

**Usa `APEX_Multiestrategia.mq5`** (versión 2). `APEX_Cartera_NAS100.mq5` es la versión 1, sin gestor de cartera; se
conserva como referencia. Los pasos de instalación son los mismos cambiando el nombre del archivo.

## Qué incluye la multiestrategia
| Estrategia | Estado | Presupuesto por defecto |
|---|---|---|
| Zona de ruido (intradía, NAS100) | ✅ validada | 2 $/punto (= 1 MNQ) |
| RSI(2) (swing, NAS100) | ✅ validada | 2 $/punto (= 1 MNQ) |
| SMC kill zones, rango+London+VWAP, VWAP 15m, VWAP+EMAs, oro (zona ruido, RSI2, pares oro/plata), bot de oferta/demanda de oro | ❌ probadas y rechazadas: **no se incluyen** | — |

Cada estrategia tiene su interruptor (`ActivarZonaRuido`, `ActivarRSI2`) y su presupuesto (`DineroPorPuntoZona`,
`DineroPorPuntoRSI`).

## Gestor de riesgo de la cartera
Solo cuenta las operaciones de este EA (por sus magic numbers): tu bot de oro u otros EAs de la misma cuenta no le
afectan, ni él a ellos.

| Regla | Por defecto | Qué hace | Base histórica (1+1 MNQ, 2015-2026) |
|---|---|---|---|
| `PerdidaDiariaMax` | 1.000 $ | Pérdida del día (cerrado + abierto) → **no abre más** hasta mañana. No cierra lo abierto (`CerrarAlFrenarDia = false`) para no alterar las reglas validadas | 8 días en 11 años superan 1.000 $ (peor día: −2.798 $) |
| `CaidaMaximaCartera` | 5.000 $ | Caída desde el máximo → **cierra todo y se detiene** hasta que la reanudes | Peor caída del backtest: 4.713 $ (en 2026) |

- La detención se guarda en las variables globales del terminal: sobrevive a reinicios de MT5.
- Para reanudar tras una detención: `ReiniciarFreno = true`, aceptar, y volver a ponerlo en `false`. Antes, revisa si
  la caída está fuera de lo esperado (PLAN_OPERATIVO.md).
- **Si cambias el tamaño** (más $/punto), escala los dos límites en la misma proporción.
- Aviso: el backtest está ahora mismo cerca de su peor caída histórica (−4.713 $ en 2026). Con el límite de 5.000 $,
  una racha algo peor que la histórica detendría la cartera: es la intención.

## Añadir una estrategia en el futuro
Solo si pasa el protocolo del proyecto (ficha antes de mirar, desarrollo y fuera de muestra, costes). En el código:
nuevo índice `E_xxx` + fila en `InicializarRegistro()`, su función `ProcesarXxx()` usando `Abrir()/Cerrar()/Posicion()`,
y llamarla en `Procesar()`. El gestor de cartera la incluye automáticamente.

---

## Versión 1: EA de la cartera (referencia)

`APEX_Cartera_NAS100.mq5` opera solo las dos estrategias validadas del proyecto, en el CFD **NAS100**:

| Estrategia | Qué hace | Horas (Italia, casi todo el año) |
|---|---|---|
| Zona de ruido (`edges/zona_ruido_mnq.md`) | Intradía: compra/vende si el precio sale del "ruido normal" de cada media hora; cierra si pierde la banda o el VWAP | Chequeos 16:00–21:30, cierre de todo a las 21:59:50 |
| RSI(2) (`edges/nq_rsi2.md`) | Swing: compra si RSI(2) < 20 y cierre > SMA(200); sale si RSI(2) > 70 o tras 5 sesiones | Al abrir cada vela diaria (reapertura, ~00:00) |

Tamaño: el equivalente a **1 MNQ = 2 $ por punto** (entrada `DineroPorPunto`); el EA calcula los lotes con el valor
del tick de tu cuenta.

## Si usas MT5 con Wine en Linux (tu caso: prefix `~/.mt5`)
```bash
# 1. Descargar el EA directamente en la carpeta de expertos
EXP="$HOME/.mt5/drive_c/Program Files/MetaTrader 5/MQL5/Experts"
ls "$EXP" || find "$HOME/.mt5/drive_c" -type d -path "*MQL5/Experts" 2>/dev/null   # si la ruta cambia, usa la que salga aquí
curl -L -o "$EXP/APEX_Multiestrategia.mq5" \
  https://raw.githubusercontent.com/blackbird024/git_test/claude/apex-telegram-token-fix-m74opt/mt5/APEX_Multiestrategia.mq5

# 2. Compilar sin abrir MetaEditor (deja el resultado en APEX_Multiestrategia.log)
cd "$EXP/../.." && WINEPREFIX=$HOME/.mt5 wine "C:\\Program Files\\MetaTrader 5\\MetaEditor64.exe" \
  /compile:"MQL5\\Experts\\APEX_Cartera_NAS100.mq5" /log
iconv -f UTF-16 -t UTF-8 "MQL5/Experts/APEX_Multiestrategia.log" | tail -5   # "0 errors" = compilado
```
Si prefieres, también vale abrir MetaEditor y pulsar F7 (paso 2 de abajo).

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
