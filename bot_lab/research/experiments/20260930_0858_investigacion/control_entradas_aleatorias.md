# Control del motor: entradas aleatorias (TRAIN+VALIDATION, antes de abrir el TEST)

4.000 señales aleatorias por semilla en velas de 5 min entre las 10:00 y las 15:00 NY. La dirección es aleatoria, el stop es 1 ATR(14) y se sale a los 60 min (o a las 15:55). Los costes son los de BASE.

Si el motor no tiene sesgo, el resultado bruto (que ya incluye el deslizamiento) debería rondar −1 $ por operación: 1 tick de deslizamiento por lado × 0,50 $ × 2.

| semilla | operaciones | expectativa neta $ | bruto medio $ (con deslizamiento) | comisión $ |
|---|---|---|---|---|
| 0 | 3.390 | −3,48 | −1,48 | 2,0 |
| 1 | 3.367 | −2,73 | −0,73 | 2,0 |
| 2 | 3.360 | −1,61 | +0,39 | 2,0 |
| 3 | 3.332 | −2,44 | −0,44 | 2,0 |
| 4 | 3.319 | −4,19 | −2,19 | 2,0 |

**Media del bruto: −0,89 $ por operación**, frente a unos −1,0 $ esperados.

- El motor no crea ventaja de la nada.
- Una estrategia sin ventaja pierde aproximadamente los costes: unos −3 $ por operación con 1 MNQ, que es exactamente lo que se ve en la mayoría de las familias.
