# POST-HOC OBSERVATIONS

Patrones vistos **después** de mirar los datos del Survivor Analysis v1.0 (experimento `survivor/experimentos/20260930_0939`). Todos son:

```text
OBSERVATION — NOT VALIDATED
```

Ninguno se convierte en filtro ni cambia el EA. Solo podrían estudiarse con un pre-registro nuevo y datos del forward. Con decenas de tablas, es esperable que alguno aparezca por azar.

| # | Observación | Datos | Por qué no se usa |
|---|---|---|---|
| 1 | La zona de ruido rinde peor cuando hay un RSI(2) abierto | −4,78 $/op (mismo sentido), −3,66 (opuesto) frente a +11,52 sin RSI(2) abierto; 646 de 2.725 operaciones | Comparación no pre-registrada. Filtrar por ello sería optimizar la cartera a posteriori |
| 2 | RSI(2) por día: la sesión del martes +370 $/op y la del jueves −100 $/op | 31 y 33 operaciones | Muestra minúscula; el análisis de día es exploratorio por pre-registro |
| 3 | RSI(2): mejor cuando el día de la señal abre por debajo del mínimo anterior, o cuando la noche fue bajista (terciles "bajo") | ≈ +190-235 $/op frente a ≈ +60-80 | Terciles descriptivos con toda la muestra; no causal como umbral |
| 4 | ZR: tras un día de EXPANSIÓN de rango (rango previo > 1,2 ATR), −4,5 $/op | 599 operaciones, IC (−17,2, +10,7) | Variable pre-registrada solo como descriptiva; el IC incluye 0 |
| 5 | ZR: apertura en la mitad baja del rango anterior ≈ −0,7 $/op; en la mitad alta +15,7 | 822 / 908 operaciones | Exploratorio |
| 6 | ZR: los largos (+10,9 $/op) rinden más que los cortos (+4,9) | IC de los cortos incluye 0 | Coherente con el mercado alcista 2015-2026; operar solo largos sería apostar por la deriva |
| 7 | Correlación ZR/RSI(2) en días con ambas y volatilidad BAJA: +0,43 | 62 días | Muestra pequeña; cartera no ajustable a eso |
| 8 | RSI(2): retrasar la ejecución 1-5 min tras la reapertura de Globex **mejora** ligeramente el resultado | +126 → +133 $/op | Diferencia pequeña, probablemente ruido de los primeros minutos (spread amplio); no se cambia la ejecución |
| 9 | Con 1+1 MNQ, algún día ≤ −1.000 $ en el 37 % de los años simulados (casi siempre por el RSI(2) de noche) | Monte Carlo | Afecta al freno diario del EA (bloquea entradas de la ZR). Hay que vigilarlo en forward; no se toca el EA sin pre-registro |
