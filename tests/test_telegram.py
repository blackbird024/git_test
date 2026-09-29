"""Pruebas del aviso por Telegram (sin red: se simula la llamada)."""
import json

from src.alerts import telegram


def test_dry_run_without_credentials(monkeypatch, capsys):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert telegram.enviar("hola") is False
    assert "modo seco" in capsys.readouterr().out


def test_sends_json_and_splits_long_messages(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN_FALSO")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    enviados = []

    class Resp:
        def __init__(self, req):
            enviados.append((req.full_url, json.loads(req.data)))

        def read(self):
            return b'{"ok": true}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(telegram.urllib.request, "urlopen", lambda req, timeout: Resp(req))
    texto = "\n".join(f"linea {i} " + "x" * 80 for i in range(100))       # ~9.000 caracteres
    assert telegram.enviar(texto, monoespaciado=True) is True
    assert len(enviados) == 3
    url, cuerpo = enviados[0]
    assert url.endswith("/botTOKEN_FALSO/sendMessage") and cuerpo["chat_id"] == "123"
    assert cuerpo["parse_mode"] == "HTML" and cuerpo["text"].startswith("<pre>")
    assert all(len(c["text"]) < 4096 for _, c in enviados)
