
## Conclusión

**Veredicto: esta versión no tiene una ventaja demostrada y no justifica operarla.** Según el protocolo del laboratorio
(`config/PROTOCOLO.yaml`) queda **INCONCLUSA**:
- positiva fuera de muestra, pero el IC90 incluye 0;
- 43 operaciones fuera de muestra, por debajo de las 100 que exige el protocolo.

En la práctica se descarta: el periodo con más operaciones (desarrollo) es claramente negativo, y la robustez es mala.

| Pregunta | Respuesta con los datos (coste base, 1 contrato) |
|---|---|
| 1 · ¿Esperanza positiva tras costes? | **No demostrada.** Desarrollo −0,244 R (IC90 −0,46 a −0,11, entero bajo 0). Validación +0,037 R (IC90 −0,23 a +0,40). Prueba +0,711 R, pero con solo 10 operaciones. Fuera de muestra +0,194 R (IC90 −0,22 a +0,34). |
| 2 · ¿Rendimiento con 2R? | Acierto 31 % / 36 % / 60 % y PF 0,69 / 1,06 / 4,88 (desarrollo / validación / prueba). Total 2018-2026: −11,9 R en 126 operaciones. |
| 3 · ¿Drawdown y su duración? | Desarrollo −26,3 R, sin recuperarse en 971 sesiones. Fuera de muestra −6,6 R, 415 sesiones. Racha perdedora máxima: 7. |
| 4 · ¿% que llega al TP antes que al SL? | 29 % en desarrollo, 36 % en validación, 60 % en prueba. Con 2R hace falta ~35 % solo para cubrir costes. |
| 5 · ¿Cuándo funciona o falla? | Sin un patrón estable. Los largos pierden en desarrollo y en validación (−0,38 / −0,39 R); los cortos solo ganan en validación. Los terciles de anchura del rango y de volatilidad cambian de signo entre periodos: es ruido con 30 operaciones por grupo. |
| 6 · ¿Robusta o depende de parámetros? | **No es robusta.** Solo 1 de 36 combinaciones (tolerancia × ventana × objetivo) es positiva en desarrollo y validación. La hora límite tampoco ayuda. |
| 7 · ¿Riesgo compatible con el drawdown? | Con esperanza ≈ 0, ningún riesgo es rentable en expectativa. Si la operas igualmente, con 100 $ por operación hay un 9 % de probabilidad de tocar −1.000 $ en un año. Ojo: con 25-50 $ no cabe ni un contrato en muchas operaciones (19 de 33 en validación con 50 $), porque el stop mediano ya es de 18-28 pts (37-57 $ por contrato). |
| 8 · ¿Cuántas oportunidades? | 1,7 al mes en 2018-2021; 0,9 en 2022-2024; **0,45 en 2025-2026** (una cada dos meses). |
| 9 · ¿Sobrevive a más costes? | Desarrollo es negativo incluso sin costes (−0,08 R). Validación pasa de +0,04 a −0,01 R con costes de estrés. |

### Por qué casi no hay operaciones
La tolerancia del retesteo es fija en puntos (±2 ticks = 0,5 pts), pero la volatilidad del Nasdaq en puntos se ha
multiplicado por ~3 entre 2018 y 2026. Que el mínimo de una vela de 5 min caiga justo en esa franja de 1 punto es cada
vez más raro: 30 operaciones en 2018 y solo 3 en 2026 (hasta octubre). La regla no es estable en el tiempo. Ampliar la
tolerancia a 4 ticks da más operaciones, pero sigue negativa en desarrollo y en validación.

### Recomendación
1. **Descartar MNQ_ORB_RETEST_v1 para operar** con dinero, ni en Topstep ni en Apex.
2. **Seguir en simulación no resuelve nada**: con ~0,5 operaciones al mes, las 60 operaciones que pide el protocolo para
   un forward test tardarían unos 10 años.
3. Si quieres seguir investigando el ORB con retesteo, la única hipótesis razonable es una **versión nueva** con la
   tolerancia proporcional a la volatilidad (por ejemplo, un % del rango de apertura). Sería una hipótesis nueva:
   toda la historia 2018-2026 ya está vista, así que solo se podría validar con datos futuros.

### Limitaciones
- **Datos de 1 min:** el orden dentro del minuto se aproxima de forma conservadora (SL primero). Solo 1 operación fue
  ambigua y ninguna tuvo hueco en el stop.
- **Muestra pequeña:** 126 operaciones en total y 43 fuera de muestra. Ningún intervalo de confianza excluye un
  resultado nulo fuera de muestra.
- **Precio de NQ como MNQ:** MNQ empezó en may-2019; la liquidez y el deslizamiento reales de MNQ no se han medido.
- **Costes:** las comisiones son valores de trabajo, no las de tu cuenta.
- **Datos:** desde 2018 (no desde 2015, como pedía el encargo). El proyecto local del encargo (`src/engine/...`,
  `config/particion.json`, 49 tests) no existe en este entorno: se reutilizó la infraestructura equivalente del
  laboratorio.
- **Pruebas previas:** este laboratorio ya probó otras versiones del ORB con los mismos datos (p. ej.
  `run_orb_retest_video.py`), así que ningún periodo es una prueba totalmente virgen para la familia ORB.
