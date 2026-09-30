# youtube_media_engine

Sistema de ayuda a la producción de un canal de YouTube: investigación, guion con fuentes, producción, control de
calidad y publicación. **Asiste a una persona; no publica ni fabrica vídeos sin revisión humana.**

## Estado

| Etapa | Estado |
|---|---|
| 1. Investigación y nicho | ✅ `reports/fase1_investigacion_nicho.md` (pendiente: elegir concepto e idioma) |
| 2. Marca | ⏳ |
| 3. Esqueleto técnico (CLI, base de datos, logs) | ⏳ (hay un CLI mínimo) |
| 4-7. Ideas, guion, producción, control de calidad, paquete de publicación, piloto | ⏳ |

## Uso

```bash
pip install -r requirements.txt
python main.py niche     # puntuación de nichos y sensibilidad a los pesos
python -m pytest         # tests
```

Solo aparecen en el CLI los comandos que ya funcionan.
