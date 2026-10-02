"""Avisos por Telegram para los scripts de Alpaca.

Variables de entorno (si faltan, no se envía nada):
    TELEGRAM_BOT_TOKEN   token del bot (de @BotFather)
    TELEGRAM_CHAT_ID     tu chat ID (de @userinfobot)
"""

import os

import requests


def notify(text):
    token, chat_id = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      data={"chat_id": chat_id, "text": f"Alpaca: {text}"}, timeout=10)
    except requests.RequestException as error:
        print(f"No se pudo enviar el aviso a Telegram: {error}")
