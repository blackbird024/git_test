# Señales en tu bot de Telegram

El sistema **solo avisa**: las órdenes las pones tú.

Necesitas dos datos de tu bot:
- el **token** (te lo da @BotFather);
- el **chat_id** del chat donde quieres recibir los avisos.

**Nunca pegues el token en el chat ni en el código.**

## A) Señales en directo, cada media hora (desde TradingView)
Es la vía para la zona de ruido, porque necesita precios en tiempo real. TradingView manda el aviso directamente a tu
bot, sin ningún servidor intermedio. Necesita un plan de TradingView con webhooks (Essential o superior).

1. Carga `pine/zona_ruido_mnq.pine` en un gráfico de **1 minuto de MNQ1!**, con al menos 15 días de historia.
2. En los ajustes del indicador, rellena **"Telegram: chat_id"** con el número de tu chat.
3. Crea una alerta:
   - Condición: el indicador → **"Cualquier llamada a la función alert()"**.
   - Notificaciones: activa **Webhook URL** y escribe `https://api.telegram.org/bot<TU_TOKEN>/sendMessage` (con tu
     token; solo queda guardado en TradingView).
   - Mensaje: déjalo como está. El indicador ya genera el JSON con el chat_id y el texto.
4. Haz lo mismo con `pine/nq_rsi2.pine` en un gráfico **diario** de MNQ1!.

Te llegarán mensajes como:
`🟢 ZONA DE RUIDO: COMPRAR 1 MNQ ahora. Precio 30.705,25, banda sup 30.697,83, VWAP 30.640,10 | MNQ1! 29-09 17:00 (Italia)`

## B) Plan del día (bandas y acción del RSI(2)), desde Python
`python scripts/plan_del_dia.py --apertura PRECIO --telegram` te envía la tabla de bandas del día y la acción del
RSI(2). Necesita estas dos variables de entorno donde se ejecute:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Sin ellas, no envía nada y solo lo muestra en pantalla.

**En tu ordenador:** define las dos variables y programa la ejecución (Programador de tareas de Windows o `cron`).

**En el entorno en la nube de Claude:**
- Añade las dos variables en la configuración del entorno.
- Permite el dominio `api.telegram.org` en el acceso a la red; ahora mismo está bloqueado.
- Con eso, se puede programar un envío automático cada tarde.
