# Fase 1: investigación y elección de nicho

*30-sep-2026. Reproducible con `python main.py niche`. Pesos en `config/niche_criteria.yaml`; puntuaciones, notas y
fuentes en `data/research/niche_scores.yaml`.*

## 0. Qué es verificado y qué no

| Tipo | Qué incluye |
|---|---|
| **Verificado** | Nada de lo que hay aquí ha salido de datos propios de YouTube: no hay credenciales de la YouTube Data API ni de Analytics. |
| **Fuentes secundarias** | Informes de agencias y blogs del sector (S1-S12). Son útiles para orientarse, pero no se han auditado. |
| **Juicio** | Valoraciones razonadas del equipo. Cada una va marcada como `juicio` en el YAML: son hipótesis. |
| **No usado** | No se han inventado visualizaciones, volúmenes de búsqueda ni audiencias de competidores. |

El sitio de ayuda de YouTube (support.google.com) y su blog oficial (blog.youtube) están **bloqueados por la red de
este entorno**. Por eso, lo que se dice aquí de las políticas viene de fuentes secundarias y hay que contrastarlo con
el texto oficial antes del lanzamiento (tarea manual n.º 1).

## 1. Hallazgos que condicionan todo el proyecto

1. **Política de contenido no auténtico (julio de 2025).** Según S1 y S2, YouTube renombró la política de "contenido
   repetitivo" a "contenido no auténtico". Su objetivo es el contenido **hecho en serie, con plantilla y poca
   intervención humana**, no la IA en sí. S1 informa de cierres masivos de canales de IA en enero de 2026. Lo que se
   mantiene monetizable es el vídeo con **aportación humana real** (criterio, investigación, punto de vista).
   → **Consecuencia de diseño:** el sistema tiene que *ayudar* a una persona a hacer buenos vídeos, no fabricarlos
   sin ella. La revisión humana del guion y de las fuentes es un requisito de negocio, no un trámite.
2. **Etiqueta de contenido sintético.** Según S5, hay que declarar el contenido **realista** alterado o generado por IA
   (personas, lugares o sucesos que podrían confundirse con reales). No hace falta declarar lo claramente animado ni
   el uso de IA para guion o subtítulos.
   → Un estilo gráfico (mapas, diagramas, ilustración) evita la mayoría de las etiquetas y el riesgo de engañar.
3. **Dinero: el idioma pesa más que el nicho.** RPM de vídeos largos en educación y ciencia: mediana de 10,22 $ (S3);
   historia y documental, 4-6 $ (S4). Ambas cifras son para audiencias de países de RPM alto. CPM en España:
   ~0,40-1 € (S6); en México, 1-2 $ (S7).
4. **Shorts pagan muy poco:** unos 0,01-0,10 $ por cada 1.000 visualizaciones (S8).
   → Los Shorts sirven para **descubrimiento**, no para ingresos.
5. **Saturación desigual.** Según S9, lo saturado son los temas genéricos; los subnichos concretos siguen teniendo hueco.

## 2. Marco de evaluación

Pesos fijados **antes** de puntuar. La escala va de 1 a 5, normalizada a 0-100. "Riesgo" se puntúa al revés (5 =
riesgo bajo).

| Criterio | Peso | Por qué pesa así |
|---|---|---|
| Demanda | 12 | Sin público no hay canal. |
| Retención | 12 | Es la métrica que más controla el propio vídeo. |
| Evergreen | 12 | Un canal pequeño vive del catálogo, no del día de publicación. |
| Diferenciación | 12 | Es la defensa frente a la política de contenido no auténtico y frente a la competencia. |
| Coste con 0 $ | 12 | Restricción real de la fase piloto. |
| Monetización | 10 | Importa, pero depende más del idioma y de la geografía de la audiencia que del tema. |
| Riesgo | 10 | Copyright, desinformación y anunciantes. |
| Internacional | 8 | |
| Formatos (Shorts + largo) | 7 | |
| Tendencias | 5 | Útil como complemento; un canal que depende de ellas se agota. |

### Resultado (`python main.py niche`)

| Categoría | Puntos | % del peso basado en juicio | 1.ª con pesos ±20 % | Puesto medio |
|---|---|---|---|---|
| Personas, inventos y descubrimientos | 80,5 | 78 % | 49,6 % | 1,50 |
| Geografía, culturas y lugares insólitos | 80,5 | 90 % | 50,4 % | 1,50 |
| Ciencia, psicología y comportamiento | 74,5 | 66 % | 0 % | 3,00 |
| Historia, misterios e inexplicado | 65,0 | 66 % | 0 % | 4,00 |
| Desarrollo personal | 61,5 | 90 % | 0 % | 5,52 |
| Tecnología e IA | 60,8 | 90 % | 0 % | 6,24 |
| Naturaleza y fauna | 60,5 | 90 % | 0 % | 6,24 |

**Lectura:**
- Hay un **empate técnico** entre inventos y geografía. Con los pesos variando ±20 %, cada una sale primera la mitad
  de las veces, así que la elección entre ellas no la decide el número.
- Ciencia y psicología queda tercera de forma estable.
- **Entre el 66 % y el 90 % del peso descansa en juicio.** Esta tabla es una hipótesis bien ordenada, no una medición.

## 3. Competencia y formatos (observación cualitativa)

- **En español** hay canales de divulgación grandes y asentados: en ciencia, *QuantumFracture*, *Date un Voltio*,
  *CuriosaMente* y *Antroporama* (S11); en historia, *Academia Play* y otros (S12). No se han medido sus datos.
- **Formatos que se repiten** en los canales sin rostro de éxito (S9, S10):
  - documental largo de 15-40 minutos con mapas animados;
  - explicador animado de 8-12 minutos;
  - Short con un dato y una pregunta.
- **Hueco hipotético:** documentales narrativos basados en fuentes primarias (patentes, archivos, mapas históricos),
  con estética gráfica propia y **fuentes visibles en pantalla**. Hay que confirmarlo con el flujo de la sección 8.

## 4. Tres conceptos de canal

### Concepto A: "La historia detrás de las cosas" (inventos y descubrimientos)
- **Idea:** la historia real, con documentos, de objetos y descubrimientos cotidianos. Incluye los mitos que no se
  sostienen.
- **Audiencia:** de 18 a 45 años, curiosos, que ven documentales en su tiempo libre y valoran "ahora lo entiendo".
- **Firma propia:** cada vídeo termina con **"lo que sabemos y lo que no"** y muestra las fuentes en pantalla.
- **Ideas de muestra** (hechos pendientes de verificar):
  1. ¿Por qué el teclado es QWERTY? (la explicación del atasco de las teclas está discutida)
  2. El pegamento que "fracasó" y acabó en el pósit
  3. ¿Quién inventó el wifi? La respuesta es complicada
  4. El código de barras: de un dibujo en la arena al supermercado
  5. Por qué los semáforos son rojo, ámbar y verde
- **Producción:**
  - **Viable con 0 $:** documentos de dominio público, líneas de tiempo y diagramas generados en código.
  - **Coste real:** la investigación en archivos, que lleva horas por vídeo.
- **Monetización:** YPP en vídeos largos y patrocinios educativos (plataformas de cursos, libros). Más adelante, fichas
  o libros digitales.

### Concepto B: "El mundo explicado en mapas" (geografía y lugares insólitos)
- **Idea:** por qué el mundo es como es (fronteras, ciudades, husos horarios, rutas), contado con mapas animados y
  datos abiertos.
- **Audiencia:** de 16 a 40 años; mucho público de Hispanoamérica.
- **Firma propia:** un estilo cartográfico único y reconocible, y **datos abiertos citados**.
- **Ideas de muestra:**
  1. Por qué Bolivia tiene armada sin tener mar
  2. El pueblo que está en dos países a la vez (Baarle)
  3. Por qué China tiene un solo huso horario
  4. Por qué casi toda Australia vive en la costa
  5. Las fronteras más raras de Sudamérica
- **Producción:**
  - **Lo más barato de automatizar:** Natural Earth es de dominio público, y OpenStreetMap se puede usar con
    atribución (ODbL).
  - **Riesgo:** que todos los vídeos se parezcan (plantilla), justo lo que penaliza la política de contenido no
    auténtico.
- **Monetización:** YPP. Patrocinios de viajes, idiomas y educación.

### Concepto C: "Lo que la ciencia sí sabe" (psicología y comportamiento, con evidencia)
- **Idea:** preguntas cotidianas sobre la mente, respondidas separando lo que se ha replicado de lo que no.
- **Audiencia:** de 20 a 45 años, interesados en psicología y hartos de los "hacks".
- **Firma propia:** un **semáforo de evidencia** en cada afirmación.
- **Ideas de muestra:**
  1. El experimento de la prisión de Stanford: lo que no te contaron
  2. ¿Se replicó el test de la golosina?
  3. ¿Existe la multitarea?
  4. El efecto Dunning-Kruger: ¿es real?
  5. Por qué recordamos mal lo que vimos
- **Producción:** diagramas sencillos. Pide mucha revisión científica.
- **Monetización:** es la que tiene más RPM (educación y ciencia, S3). Patrocinios de apps y libros.
- **Riesgo:** el mayor de desinformación. Los errores dañan la credibilidad del canal.

### Viabilidad comparada

| | A Inventos | B Mapas | C Ciencia |
|---|---|---|---|
| Horas por vídeo largo (estimación, a validar) | 10-16 | 8-12 | 12-20 |
| Riesgo de parecer "plantilla" | Bajo (cada historia es distinta) | **Alto** | Medio |
| Riesgo de error factual | Medio | Bajo-medio | **Alto** |
| Shorts naturales | Muy buenos | Muy buenos | Buenos |

## 5. Idioma de lanzamiento

| | Español | Inglés |
|---|---|---|
| Audiencia potencial | Grande: ~270 millones de usuarios en España e Hispanoamérica (S6) | La más grande |
| RPM | **Bajo** (S6, S7) | **Alto** (S3) |
| Competencia | Menor | Mucho mayor |
| Revisión humana nativa | **Sí (tú)** | Limitada |
| Voz local gratuita (Piper) | Sí (es_ES, es_MX) | Sí |

**Recomendación: empezar en español.** El motivo principal no es el dinero. La política de YouTube premia la
aportación humana real, y tú puedes revisar y dar criterio a los guiones en español. Un canal en inglés sin revisión
nativa sería justo el tipo de producción que se desmonetiza. La adaptación al inglés se valora cuando el flujo esté
validado (Fase 13).

## 6. Recomendación: Concepto A, "La historia detrás de las cosas"

**Por qué A, dado el empate con B:**
- **Retención:** cada historia tiene su propio arco narrativo (problema, intento, giro y resultado).
- **Contenido no auténtico:** cada vídeo es distinto por naturaleza, así que protege mejor frente a esa política.
  B depende de un formato visual repetido.
- **Riesgo de desinformación:** menor que en C.
- **Visuales de B:** los mapas y líneas de tiempo pueden entrar en A cuando la historia lo pida.

**Qué se sacrifica:**
- B es más barato de producir.
- C tiene más RPM.
- A exige más horas de investigación en fuentes, y ese trabajo no se automatiza sin perder calidad.

## 7. Riesgos y supuestos principales

1. **Supuesto no verificado:** que en español hay hueco para el concepto A. Se valida con el flujo de la sección 8.
2. **Tiempo:** el cuello de botella es tu tiempo de revisión, no la máquina. Un calendario demasiado ambicioso es el
   riesgo número uno.
3. **Voz local:** puede sonar artificial y restar retención. Hay que medirlo y cambiarla por otra de pago si hace falta.
4. **Plazo hasta el YPP:** según los requisitos publicados por YouTube (verificar), hacen falta 1.000 suscriptores y
   4.000 horas de visualización en 12 meses, o 1.000 suscriptores y 10 millones de visualizaciones de Shorts en 90
   días. Hasta entonces, los ingresos son 0 $.
5. **Imágenes antiguas:** que sea de dominio público en EE. UU. no significa que lo sea en todo el mundo. Se registra
   la licencia de cada imagen.
6. **Datos secundarios:** las cifras de RPM de S3, S4, S6 y S7 vienen de agencias con interés comercial.

## 8. Flujo para convertir hipótesis en datos (cuando haya credenciales)

1. **YouTube Data API** (clave gratuita de Google Cloud; `search.list` cuesta 100 unidades de una cuota diaria de
   10.000):
   - para 30 temas candidatos, contar vídeos en español del último año y su mediana de visualizaciones;
   - registrar los 10 canales principales de cada tema.
2. **Google Trends:** comparar el interés en España, México, Argentina y Colombia (exportación manual en CSV).
3. **Criterio de hueco:** un tema tiene hueco si hay demanda (vídeos con visualizaciones altas en relación con los
   suscriptores de su canal) pero pocos vídeos en español de calidad en los últimos 2 años.
4. Los resultados se guardan en `data/research/` con fecha y consulta, y se vuelve a ejecutar `python main.py niche`
   con las puntuaciones actualizadas. El % basado en juicio debe bajar.

## Fuentes

- S1 [AIR Media-Tech: YouTube Monetization Policy Changes 2026](https://air.io/en/monetization/youtube-monetization-policy-changes-2026-a-complete-dated-timeline)
- S2 [AuditSocials: YouTube Inauthentic Content Policy 2026](https://www.auditsocials.com/blog/youtube-inauthentic-content-policy-2026-mass-produced-ai-generated-monetization-creators-brands)
- S3 [AIR Media-Tech: YouTube RPM by niche 2026](https://air.io/en/air-data-findings/which-youtube-niche-makes-the-most-money-in-2026-ranked-by-real-rpm-and-cpm)
- S4 [OutlierKit: Most Profitable YouTube Niches 2026](https://outlierkit.com/blog/most-profitable-youtube-niches)
- S5 [Influencer Marketing Hub: AI Disclosure Rules](https://influencermarketinghub.com/ai-disclosure-rules/)
- S6 [AIR Media-Tech: Most popular languages on YouTube 2026](https://air.io/en/audience-growth/what-are-the-most-popular-languages-on-youtube)
- S7 [Fluxnote: YouTube CPM Latin America 2026](https://fluxnote.io/guides/youtube-cpm-latin-america-by-country)
- S8 [AIR Media-Tech: Shorts RPM vs long-form](https://air.io/en/air-data-findings/youtube-shorts-rpm-vs-long-form-how-much-do-shorts-earn-in-2026)
- S9 [Kineclip: Do Faceless Channels Still Work in 2026?](https://kineclip.com/blog/do-faceless-channels-still-work-2026/)
- S10 [Fliki: Best Faceless YouTube Niches 2026](https://fliki.ai/blog/best-faceless-youtube-niches)
- S11 [Blog Lenovo: canales para aprender ciencia](https://www.bloglenovo.es/ciencia-en-youtube/)
- S12 [Educación 3.0: canales para aprender historia](https://www.educaciontrespuntocero.com/recursos/canales-youtube-aprender-historia/)
