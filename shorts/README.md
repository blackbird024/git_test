# Fábrica de YouTube Shorts — Curiosidades

Genera Shorts verticales (1080×1920) completamente automáticos: voz neuronal en español,
subtítulos palabra a palabra, fondo animado, emojis grandes, música sin derechos y efectos.

## Uso
```bash
./instalar.sh                                             # una vez
python3 generar_short.py guiones/001_datos_que_parecen_falsos.json
```
Resultado en `salida/<slug>/`: el `.mp4`, `portada.png` y `youtube.txt` (título, descripción, etiquetas).

## Hacer un video nuevo
Copia un JSON de `guiones/` y cambia las escenas: `badge`, `emoji`, `headline`, `narration`, `colors`.
Voces disponibles: `es_MX-ald-medium` (por defecto), `es_MX-claude-high`.

## Canal de YouTube
En `canal/` están el banner, la foto de perfil, la descripción del canal y la guía paso a paso
(`canal/GUIA_CANAL.md`) para crear el canal y subir/programar los Shorts.
Para regenerar banner y foto: `python3 canal/generar_canal.py`.
