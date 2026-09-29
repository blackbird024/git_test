"""Envío de mensajes al bot de Telegram del usuario. Solo AVISA; nunca envía órdenes.

Configuración (NUNCA en el código ni en el chat): variables de entorno
    TELEGRAM_BOT_TOKEN   token que da @BotFather
    TELEGRAM_CHAT_ID     id del chat donde el bot escribe
Sin ellas, los mensajes solo se imprimen (modo seco) y `enviar` devuelve False.
"""
import html
import json
import os
import urllib.request

LIMITE = 3900                                   # Telegram admite 4096 caracteres por mensaje


def configurado() -> bool:
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))


def trozos(texto: str, limite: int = LIMITE) -> list[str]:
    """Parte el texto por líneas para no pasar del límite de Telegram."""
    out, actual = [], ""
    for linea in texto.splitlines(keepends=True):
        if len(actual) + len(linea) > limite and actual:
            out.append(actual)
            actual = ""
        actual += linea
    if actual.strip():
        out.append(actual)
    return out


def enviar(texto: str, monoespaciado: bool = False, timeout: float = 15) -> bool:
    """Envía `texto` (en varios mensajes si es largo). `monoespaciado` lo muestra como bloque de código (tablas)."""
    if not configurado():
        print("[Telegram no configurado: modo seco]\n" + texto)
        return False
    token, chat = os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]
    ok = True
    for t in trozos(texto):
        cuerpo = {"chat_id": chat, "text": f"<pre>{html.escape(t)}</pre>" if monoespaciado else t,
                  "disable_web_page_preview": True}
        if monoespaciado:
            cuerpo["parse_mode"] = "HTML"
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
                                     data=json.dumps(cuerpo).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                ok &= json.loads(r.read().decode()).get("ok", False)
        except Exception as e:                   # noqa: BLE001 — un fallo de aviso no debe parar nada
            print(f"[Telegram] error al enviar: {type(e).__name__}")   # sin imprimir el token
            ok = False
    return ok
