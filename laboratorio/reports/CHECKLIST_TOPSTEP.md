# Checklist diario: Topstep / forward test de la zona de ruido (en papel)

> Estado del sistema: **INCONCLUSO, solo simulación en papel**. Nada de esto autoriza a operar con dinero ni a
> arriesgar el Combine. Reglas exactas = las originales (`laboratorio/strategies/noise.py`), sin cambios.

## Horario (Italia), con los cambios de hora gestionados

| Periodo | Apertura NY 9:30 ET | Decisiones (cada 30 min) | Cierre forzoso 15:55 ET |
|---|---|---|---|
| Normal | 15:30 | 16:00, 16:30, … 21:30 | 21:55 |
| 25 oct → 31 oct 2026, 14 mar → 27 mar 2027, 31 oct → 6 nov 2027 | 14:30 | 15:00, 15:30, … 20:30 | 20:55 |

## Antes de la sesión (5 min, antes de las 15:25 en Italia)

- [ ] Hay sesión hoy (calendario NYSE). En **media jornada** (3 jul, viernes de Acción de Gracias, 24 dic) la regla original **no opera**.
- [ ] Indicador `tradingview/BandasRuidoNY.pine` en MNQ1! de 5 min, con alertas activas (lookback 14, 30 min, banda ×1,0).
- [ ] Anotar el cierre de ayer y la apertura de hoy (las bandas usan max/min de los dos).
- [ ] Noticias de alto impacto (CPI, FOMC, NFP): **no** se filtran en la regla original. Solo se anotan.
- [ ] Límites personales en papel: 1 MNQ; stop diario de 300 $; si la cuenta simulada queda a < 500 $ del MLL → pausa.

## En cada alerta (1-2 min)

- [ ] Al **cierre** de la vela de 5 min (9:55, 10:25, … ET): cierre > banda superior y sin posición → **largo**; < inferior → **corto**.
- [ ] Con posición: salir si el cierre vuelve dentro de la banda (indicador por defecto, sin VWAP: es la variante "solo banda", medida en el INFORME).
- [ ] Anotar la hora de la señal, el precio de la alerta y el precio que habrías obtenido a mercado (deslizamiento real).
- [ ] Anotar las alertas que no has podido atender (dato clave del forward test).

## Cierre (2 min)

- [ ] 15:55 ET (el indicador avisa a las 16:00): cerrar cualquier posición simulada.
- [ ] Rellenar `diario_forward.csv` (fecha, hora, lado, precio de la señal, tu precio, motivo de salida, P&L, alertas perdidas).

## Revisión semanal (15 min, fin de semana)

- [ ] ¿Cuántas alertas se atendieron en < 2 min? Objetivo ≥ 95 %.
- [ ] Deslizamiento medio frente al modelo (2 ticks por lado). Si sale > 3 ticks, el backtest base es optimista.
- [ ] Comparar tus operaciones con las del modelo para los mismos días (pídemelo; necesito datos nuevos de 1 min).
- [ ] No cambiar ningún parámetro. Las ideas nuevas van al diario de hipótesis, no a las reglas.

## Criterios escritos para la decisión tras 30 días (no dependen del P&L)

1. Fidelidad: ≥ 95 % de las señales ejecutadas a tiempo y deslizamiento medio ≤ 3 ticks.
2. Tiempo: el total diario real cabe en tu vida (si no, la regla es inviable sin automatizar).
3. Reglas de Topstep verificadas por escrito (MLL, DLL, consistencia, automatización permitida).
4. Si se cumplen 1-3 → seguir **otros 2-3 meses en papel** (≥ 60 operaciones) antes de cualquier decisión con dinero.
5. Si no se cumplen → la estrategia no es operable para ti, aunque tenga ventaja histórica.

## En el Combine real (si decides seguir pagándolo)

- [ ] Nunca más de lo que dice el plan; el máximo permitido por Topstep no es un tamaño recomendado.
- [ ] No aumentar el tamaño tras pérdidas ni tras rachas ganadoras.
- [ ] No operar si el stop no cabe en el presupuesto de riesgo.
- [ ] No existe "objetivo diario": un día sin señal es un día correcto.
