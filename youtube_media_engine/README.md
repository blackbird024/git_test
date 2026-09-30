# youtube_media_engine

Sistema de ayuda a la producción de un canal de YouTube: investigación, guion con fuentes, producción, control de
calidad y publicación. **Asiste a una persona; no publica ni fabrica vídeos sin revisión humana.**

## Estado

| Etapa | Estado |
|---|---|
| 1. Investigación y nicho | ✅ `reports/fase1_investigacion_nicho.md`: concepto A, en español |
| 2. Marca | ✅ `reports/fase2_marca.md` (pendiente de aprobar) |
| 3. Esqueleto técnico y base de temas | ✅ CLI, fichas de temas con reglas de estado, proyectos con manifiesto reanudable, logs JSON |
| 4-7. Ideas, guion, producción, control de calidad, paquete de publicación, piloto | ⏳ |

## Uso

```bash
pip install -r requirements.txt
python main.py niche           # puntuación de nichos y sensibilidad a los pesos
python main.py brand-preview   # paleta, logo, miniatura y banner en reports/marca/
python main.py ideas list      # temas (data/topics/T####.yaml) con su estado
python main.py ideas show T0001
python main.py ideas new "Título" "Pregunta central"
python main.py ideas state T0001 estado_investigacion investigado --nota "fuentes revisadas"
python main.py project new T0001   # carpeta projects/V####/ con manifiesto
python main.py project status
python -m pytest               # tests
```

## Arquitectura

| Pieza | Dónde | Notas |
|---|---|---|
| Configuración del canal | `config/channel.yaml` | Nombre, colores, fuentes, voz, formatos |
| Secretos | Variables de entorno (`.env.example`) | Nunca en el código ni en los logs |
| Temas | `data/topics/T####.yaml` | Un fichero por tema, versionado en git. Reglas: no se investiga sin fuente con URL; no se produce sin estar investigado; cada cambio queda en el historial |
| Proyectos de vídeo | `projects/V####/` | Carpetas research, sources, script, storyboard, audio, assets, subtitles, edit, render, thumbnail, qc, publish y analytics, más `manifest.yaml` |
| Reanudación | `manifest.yaml` → `pasos` | Cada paso guarda el hash de sus entradas; si no cambian, no se repite (evita pagar dos veces o publicar dos veces) |
| Logs | `logs/engine.jsonl` | Una línea JSON por evento (no se sube a git) |

**Por qué ficheros YAML y no SQLite:** cada sesión en la nube empieza con un contenedor vacío. Git es lo único que
persiste, y un fichero legible por registro deja un historial revisable.

Solo aparecen en el CLI los comandos que ya funcionan.
