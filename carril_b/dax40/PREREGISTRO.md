# DAX40 en horario de Londres — PRE-REGISTRO (carril B)

Escrito el 05-oct-2026, **antes de recibir o mirar ningún dato del DAX/GER40**. Todo cambio posterior se anota al final, en "Cambios tras ver datos", con fecha y motivo.

Este estudio es del **carril B**:
- No toca `forward_testing/`, RSI(2) ni Noise Zone del NQ.
- No usa ningún dato forward del NQ.

## 0. Pregunta
> ¿Conviene operar el DAX40 (CFD GER40 de Pepperstone) en horario de Londres/Frankfurt? Si conviene, ¿es porque ahí es más barato operarlo o porque hay una ventaja medible después de costes?

"No hay ventaja" es un resultado válido y se publica igual.

## 1. Datos
- **Fuente:** el CFD GER40 de Pepperstone en velas de M1, exportado por el usuario desde MT5 (Símbolos → Barras → Exportar). Coste: 0 $.
- **Horas:**
  - El servidor va a NY+7: la hora de NY es la del servidor menos 7 h.
  - Se convierte a UTC y después a `Europe/Berlin`. Todas las horas de este documento son de Berlín (CET/CEST).
  - Se comprueba con los propios datos: el minuto de mayor recorrido medio tiene que caer a las 09:00 o a las 15:30 de Berlín. Si no, el desfase está mal y **no se sigue**.
- **Integridad:**
  - sin duplicados y en orden;
  - sin velas imposibles (high < max(open, close), low > min(open, close));
  - huecos > 5 min dentro de 09:00-17:30 anotados; el día se excluye si suman más de 30 min;
  - un día con menos de 300 velas entre 09:00 y 17:30 se excluye (festivos y medias sesiones).
- **Spread:** se usa la columna `SPREAD` del MT5 (en puntos del símbolo) como spread de cada vela. Si no viene, se usa la mediana del spread por hora, que el usuario anota desde el MT5, y se avisa.
- **Partición 60/20/20 por sesiones**, en orden cronológico: TRAIN, VALIDATION y TEST. El TEST se abre **una sola vez**, con las hipótesis ya congeladas.
- **Advertencia:** todo este histórico es **NO OUT-OF-SAMPLE** en sentido fuerte. Lo publicado sobre el DAX ya lo cubre en parte.

## 2. Parte 1 — Descriptivo por franja (sin estrategias)
| Franja | Horas (Berlín) |
|---|---|
| F1 Asia / noche CFD | 01:00-08:00 |
| F2 Preapertura | 08:00-09:00 |
| **F3 Apertura Xetra/Londres** | **09:00-11:00** |
| F4 Mediodía europeo | 11:00-14:30 |
| F5 Datos de EE. UU. / preapertura NY | 14:30-15:30 |
| **F6 Solape con EE. UU.** | **15:30-17:30** |
| F7 Después de Xetra | 17:30-22:00 |

Métricas por franja (en TRAIN y en el total, por separado):
1. Recorrido medio en 15 min, |close(t+15) − close(t)|, en puntos.
2. Volatilidad realizada por hora, en %.
3. Spread mediano y p90, en puntos.
4. **Ratio coste/movimiento** = (spread mediano + 1 punto de deslizamiento) / recorrido medio en 15 min. **Esta es la métrica principal de "conviene operarlo aquí".**
5. Varianza relativa VR(15) = var(ret 15 min) / (15 · var(ret 1 min)):
   - VR > 1: tendencia;
   - VR < 1: reversión;
   - IC por bootstrap con bloques de 20 sesiones.
6. Retorno medio de la franja (deriva), con su IC. Es solo informativo.

**Criterio "más barato en Londres":** el ratio coste/movimiento de F3 es menor que el de F1, F2, F4 y F7, y su IC del bootstrap no se solapa con el de esas franjas. F6 se reporta aparte: es la otra franja líquida.

## 3. Parte 2 — Como mucho 3 hipótesis de estrategia, sacadas de estudios publicados y con parámetros fijados AQUÍ
Cada hipótesis se prueba en la **franja de Londres** y en una **franja de control** con la misma regla. No se optimiza nada. No hay rejillas.

| # | Hipótesis | Fuente | Regla (fija) | Londres | Control |
|---|---|---|---|---|---|
| H1 | Zona de ruido (momentum intradía) | Zarattini, Aziz y Barbon (2024), igual que nuestra Noise Zone del NQ | Apertura de referencia a las 09:00. Sigma = media de 14 sesiones previas de \|close(m)/open − 1\| en cada minuto m. Bandas = apertura · (1 ± sigma), mult. 1,0. Chequeos cada 30 min de 09:30 a 17:00. Largo por encima de la banda superior; corto por debajo de la inferior. Salida al volver dentro de la banda o a las 17:25 | ancla 09:00, cierre 17:25 | ancla 15:30, chequeos 16:00-21:30, cierre 21:55 |
| H2 | Ruptura del rango de apertura (ORB 15 min) | Zarattini y Aziz (2023), con la misma regla pero en 15 min | Rango = high/low de los primeros 15 min. Una orden stop a cada lado (OCO), solo la primera operación del día. Stop en el otro lado del rango; sin objetivo. Cierre por tiempo | rango 09:00-09:15, cierre 17:25 | rango 15:30-15:45, cierre 21:55 |
| H3 | Momentum de la primera media hora | Gao, Han, Li y Zhou (2018), "Market intraday momentum" | Si el retorno desde el cierre anterior de las 17:30 hasta las 09:30 es > 0, largo de 17:00 a 17:30; si es < 0, corto. Sin stop | señal 09:30, operación 17:00-17:30 | señal 15:30 → 16:00, operación 21:25-21:55 |

**Tamaño:** 1 CFD = 1 €/punto. Resultados en puntos y en % del precio. No hay apalancamiento ni cartera.

**Ejecución:** igual que `bot_lab/CRITERIOS.md` §2:
- la señal sale de una vela cerrada y se ejecuta en la apertura del minuto siguiente;
- si el stop y la salida caen en el mismo minuto, cuenta el stop;
- los huecos se ejecutan en la apertura.

**Costes:** el CFD no cobra comisión, así que el coste es el spread de la vela.
- En **BASE**, cada orden a mercado o stop paga la mitad del spread de la vela al entrar y la mitad al salir, más 1 punto de deslizamiento. En la apertura de 09:00-09:05 y de 15:30-15:35 son 2 puntos.
- **STRESS ×1,5, ×2 y ×3** multiplican el spread y el deslizamiento.
- Si deja de ser positiva con ×2, la hipótesis es **frágil**.

## 4. Decisión (fijada antes de ver datos)
**Comparaciones:** son 3 hipótesis × 2 franjas, es decir 6 pruebas. Bonferroni: **α = 0,05 / 6 = 0,0083**.

**Una hipótesis "PASA en Londres"** si cumple **todo** esto:
1. Neto BASE > 0 en TRAIN, en VALIDATION y en TEST, por separado.
2. Profit factor ≥ 1,10 en VALIDATION + TEST.
3. Neto > 0 con STRESS ×2 en VALIDATION + TEST.
4. Prueba de aleatorización con 1000 réplicas (mismas horas y duraciones, dirección al azar): p < 0,0083.
5. Al menos 100 operaciones en VALIDATION + TEST.
6. No depende de un solo año: al quitar el mejor año, el neto sigue > 0.

**Clasificación** (como en el laboratorio):
| Clase | Significado |
|---|---|
| A | Pasa todo |
| B | Pasa todo salvo el p de Bonferroni (p < 0,05 sin corregir) |
| C | Positiva en TRAIN, pero falla en VALIDATION o TEST |
| D | Frágil a costes |
| E | Sin ventaja |

**Respuesta final a "¿me conviene operarlo en Londres?":**
| Resultado | Respuesta |
|---|---|
| Alguna hipótesis es **A** en Londres y **no** es A en el control | **Sí, con evidencia.** Pasaría a su propio forward, en otra cuenta demo, nunca en la de APEX |
| La Parte 1 dice "más barato en Londres", pero ninguna estrategia es A | **Es más barato operarlo ahí, pero no hay ventaja demostrada.** No se opera |
| Ninguna de las dos | **No** |

## 5. Lo que NO se hace
- No se añaden hipótesis tras ver los datos (van a `POST_HOC.md`).
- No se cambian horas, multiplicadores ni stops.
- No se mira el TEST antes de congelar.
- No se opera nada en la cuenta demo de APEX: el límite de caída de cuenta acoplaría las estrategias y contaminaría su forward.

## Cambios tras ver datos
| Fecha | Cambio | Motivo |
|---|---|---|
