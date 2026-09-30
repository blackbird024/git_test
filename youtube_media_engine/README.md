# youtube_media_engine

Sistema de ayuda a la producción de un canal de YouTube: investigación, guion con fuentes, producción, control de
calidad y publicación. **Asiste a una persona; no publica ni fabrica vídeos sin revisión humana.**

## Estado

| Etapa | Estado |
|---|---|
| 1. Investigación y nicho | ✅ `reports/fase1_investigacion_nicho.md`: concepto A, en español |
| 2. Marca | ✅ `reports/fase2_marca.md` (pendiente de aprobar) |
| 3. Esqueleto técnico (CLI, base de datos, logs) | ⏳ (hay un CLI mínimo) |
| 4-7. Ideas, guion, producción, control de calidad, paquete de publicación, piloto | ⏳ |

## Uso

```bash
pip install -r requirements.txt
python main.py niche           # puntuación de nichos y sensibilidad a los pesos
python main.py brand-preview   # paleta, logo, miniatura y banner en reports/marca/
python -m pytest         # tests
```

Solo aparecen en el CLI los comandos que ya funcionan.
