# Pre-registro: combinaciones de estrategias con fundamento (oro)

Fecha: 2026-10-01. Escrito antes de calcular ningún resultado de estas estrategias.

## Idea
En vez de minar 50.000 reglas al azar, elijo **5 estrategias con una razón económica o con literatura detrás**. Los
parámetros son los estándar de la literatura y no se ajustan. Después las combino: todas las combinaciones posibles
(31) son descriptivas, pero **solo hay una hipótesis confirmatoria: la cartera equiponderada de las 5**.

| # | Estrategia | Regla (señal al cierre, ejecución en el periodo siguiente) | Fundamento |
|---|---|---|---|
| S1 | TSMOM 12 meses | signo del rendimiento de los últimos 252 días → largo/corto el día siguiente | Moskowitz, Ooi y Pedersen (2012), momentum de series temporales en futuros |
| S2 | TSMOM 1 mes | ídem con 21 días | ídem, horizonte corto |
| S3 | Tendencia MA200 | largo si cierre > media de 200 días, corto si no | trend-following clásico de CTAs |
| S4 | Momentum intradía | signo(cierre 09:00 NY − cierre de la sesión anterior) → posición en la vela 12:00-13:00 NY | Gao, Han, Li y Zhou (2018): el inicio del día predice el final |
| S5 | Deriva de la sesión asiática | largo desde la apertura de las 18:00 NY hasta el cierre de las 08:00 NY, todos los días | hipótesis práctica: el oro sube en horario asiático y la presión vendedora llega con Londres/NY |

Cada estrategia apunta a un **10 % de volatilidad anual** con la volatilidad de los 60 días anteriores (tope 3×), un overlay de
volatilidad (Moreira y Muir, 2017). Coste: 0.185 USD/oz por lado, convertido a % del precio.

## Datos
Databento GC.v.0, con ajuste por ratio en cada rollover (rendimiento excess-return de futuros). Tramos: TRAIN 2010-06 → 2020-03,
VALIDATION 2020-03 → 2023-05, TEST 2023-05 → 2026-09.

**Advertencia sobre TEST.** (a) Ya lo usé una vez para una estrategia del generador. (b) Sé, por los datos, que el oro tuvo
una tendencia alcista muy fuerte en 2024-2025 (precio ajustado de unos 2.500 a 4.500). Eso favorece a S1-S3 y lo conocía antes de
elegirlas, así que TEST **no es un hold-out limpio** para las estrategias de tendencia. Por eso el criterio principal se apoya en
TRAIN+VALIDATION y en la comparación con comprar y mantener.

## Controles
- **Comprar y mantener** largo con el mismo objetivo de volatilidad (benchmark). Se mide el alfa de la cartera frente a él
  (regresión de rendimientos diarios).
- **Desplazamiento circular** (500 permutaciones): cada señal se desplaza un número aleatorio de días (≥ 60) respecto a los
  rendimientos. Así se conservan su frecuencia y su persistencia, pero se rompe el timing. p = proporción de Sharpe nulos ≥ observado.

## Criterio de éxito de la cartera de 5
Sharpe > 0 en TRAIN **y** en VALIDATION · p del desplazamiento circular < 0.05 (TRAIN+VALIDATION) · alfa frente a comprar y mantener con
t > 2 (TRAIN+VALIDATION) · Sharpe > 0 en TEST, mostrado con su advertencia.
