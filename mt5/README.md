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
3. En MT5, abre un gráfico de **NAS100** (Pepperstone). El EA se niega a correr en otro símbolo;
   para usarlo con otro, cambia `InpSymbolPrefix` (o déjalo vacío).
4. Arrastra el EA al gráfico, activa **Permitir trading algorítmico** y el botón **Algo Trading**.

## Ajustar el horario

Las horas son **del servidor del bróker** (la que muestra la Observación del Mercado), no la tuya.
Para índices de EE. UU. la sesión abre a las 9:30 de Nueva York. Con un servidor en GMT+3
(muy común) eso son las **16:30**, que es el valor por defecto. **Pepperstone** usa GMT+2/GMT+3
sincronizado con el horario de Nueva York, así que los valores por defecto sirven todo el año. Si tu bróker usa otra zona horaria,
cambia `InpSessionStartHour`/`Min`, `InpLastEntryHour`/`Min` y `InpCloseAllHour`/`Min`.

## Probar antes de operar

Primero en el **Probador de Estrategias** (Ctrl+R): elige el EA, el símbolo, el modelo
"Cada tick basado en ticks reales" y al menos 3-6 meses. Revisa el resultado neto, el drawdown
máximo y el número de operaciones. Luego déjalo correr unas semanas en la cuenta demo.

---

# MT5 – IBS swing trading (`IbsSwing.mq5`)

Estrategia de varios días en **NAS100** y **XAUUSD** (oro), la mejor del laboratorio de swing
(`alpaca/swing_lab.py`): de 2016 a 2026, la cartera QQQ + GLD ganó un 14% anual con una caída
máxima del 9.7% (con exposición 1x).

## Cómo funciona

1. A las **15:55 de Nueva York** mira dónde está el precio dentro del rango de la sesión de hoy
   (9:30-15:55 de Nueva York): **IBS** = (precio - mínimo) / (máximo - mínimo).
2. **IBS < 0.2** (cerca del mínimo del día) y sin posición: **compra**.
3. **IBS > 0.8** (cerca del máximo del día) con posición: **cierra**.
4. Solo compras. Cada operación dura unos 3-4 días. Un solo gráfico opera los dos símbolos.

## Parámetros importantes

| Parámetro | Por defecto | Nota |
|-----------|-------------|------|
| `InpSymbol1` / `InpSymbol2` | NAS100 / XAUUSD | Nombres exactos del bróker (en otros puede ser US100, USTEC, GOLD...) |
| `InpServerMinusNY` | 7 | Horas que el servidor va por delante de Nueva York. Pepperstone: 7 todo el año |
| `InpAllocationPct` | 50 | % del equity por símbolo |
| `InpExposure` | 1.0 | Usa **0.5** en cuentas con límite de pérdida total del 6% (CFT 1 fase) |
| `InpMaxDailyLossPct` | 3.5 | Cierra todo si la cuenta cae este % en el día |

## Instalación

Igual que el EA de VWAP: MetaEditor → Archivo → Nuevo → Asesor Experto (plantilla) → nombre
`IbsSwing` → borrar todo, pegar el código, compilar (F7). Arrástralo a **un** gráfico (cualquiera,
por ejemplo NAS100 en M1) con el trading algorítmico activado. Debe quedar abierto todos los días a
las 15:55 de Nueva York (21:55 en Italia): usa un VPS o deja el ordenador encendido.

## Probarlo

En el Probador de Estrategias (Ctrl+R): EA IbsSwing, símbolo NAS100, periodo M1, modelo
"OHLC en M1", al menos 1-2 años. El probador carga también el oro automáticamente.

## Probar otra sesión (por ejemplo, Londres en el oro)

El rango del IBS va de `InpSessionStartHour:InpSessionStartMin` a `InpDecisionHour:InpDecisionMin`,
siempre en hora de **Nueva York**. Para la sesión de Londres (8:00-16:25 de Londres):

| Parámetro | Valor |
|-----------|-------|
| `InpSymbol1` | (vacío) |
| `InpSymbol2` | XAUUSD |
| `InpSessionStartHour` / `Min` | 3 / 0 |
| `InpDecisionHour` / `Min` | 11 / 25 |
| `InpMagic` | otro número, p. ej. 240602 |
| `InpLabel` | LON |

Con un número mágico distinto puede convivir con el EA de la sesión de Nueva York en la misma cuenta.
La etiqueta (`InpLabel`) aparece en el comentario de las órdenes y en los mensajes, para distinguirlos.
Consejo: guarda cada configuración con el botón **Guardar** de la pestaña de parámetros
(por ejemplo `IbsSwing_NY.set` e `IbsSwing_LON.set`) y cárgala con **Cargar**.
Pruébalo antes en el Probador de Estrategias.

---

# MT5 – Copiador de operaciones (`TradeCopier.mq5`)

Replica las posiciones de una cuenta (**MASTER**) en otras (**SLAVE**). Todas las cuentas tienen que
estar abiertas en terminales MT5 del **mismo ordenador o VPS** (se comunican por la carpeta común
de MetaTrader, `Common\Files`).

> Para IbsSwing no hace falta: es más fiable poner el EA directamente en cada cuenta.
> El copiador sirve para operaciones manuales u otros EAs.

## Qué copia
Aperturas, cierres, cierres parciales y stop-loss / take-profit. Si el master deja de actualizar
(terminal cerrado), los slaves **no tocan nada**. Si una copia se cierra en el slave (por su propio
límite), no se vuelve a abrir.

## Instalación (una instalación de MT5 por cuenta)
1. **Varias instalaciones de MT5:** al instalar, elige "Configuración" y una carpeta distinta para cada cuenta.
2. **Master:** en la cuenta origen, pon el EA con `Modo = COPIER_MASTER` y un `Canal` (p. ej. "IBS").
3. **Slave:** en cada cuenta copia, pon el EA con `Modo = COPIER_SLAVE` y **el mismo canal**.
4. Activa Algo Trading en todos.

## Parámetros del slave
| Parámetro | Para qué |
|-----------|----------|
| Lote | `LOTS_BALANCE_RATIO`: proporcional al balance (cuenta de 50k copia la mitad que una de 100k). `LOTS_MULTIPLIER`: lote del master × multiplicador |
| Multiplicador | 0.5 = la mitad de riesgo (recomendado en challenges con 6% de DD máx) |
| Sufijo / Equivalencias | Si el símbolo se llama distinto: sufijo ".a", o `NAS100=US100,XAUUSD=GOLD` |
| Pérdida diaria máxima | Cierra las copias y deja de copiar ese día (3.5% por defecto) |

**Ojo:** si en dos brókers el mismo símbolo tiene distinto tamaño de contrato (mira *Especificación*),
el lote no equivale: ajusta el multiplicador.

**Reglas de las prop firms:** muchas permiten copiar entre cuentas propias, pero algunas lo prohíben
o limitan el capital total con operaciones idénticas. Revísalo en cada firma.

---

# Avisos por Telegram (IbsSwing)

El EA avisa cuando **compra**, **cierra** (con el resultado), si alcanza la **pérdida diaria** o si
una orden **falla**, y al **iniciarse**.

1. En Telegram, habla con **@BotFather**, envía `/newbot` y sigue los pasos. Te dará un **token**.
2. Abre el chat con tu bot nuevo y envíale cualquier mensaje (si no, no podrá escribirte).
3. Habla con **@userinfobot**: te dice tu **chat ID** (un número).
4. En MT5: **Herramientas → Opciones → Asesores Expertos**, marca **Permitir WebRequest para las
   URL listadas** y añade `https://api.telegram.org`.
5. En los parámetros del EA (grupo **Avisos**) pon el token y el chat ID.

Al cargar el EA llega el mensaje "EA iniciado". Si no llega, mira la pestaña **Expertos**.

Sin Telegram: activa **Avisar también en la app MetaTrader del móvil** y pon tu MetaQuotes ID
(app MetaTrader → Ajustes → Mensajes) en **Herramientas → Opciones → Notificaciones**.

El token es privado: no lo compartas ni lo subas a ningún sitio.
