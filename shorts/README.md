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
