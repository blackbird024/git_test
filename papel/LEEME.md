# Prueba en papel: ZONA_RUIDO_MNQ_v1.0 (3 meses)

Reglas completas: `edges/zona_ruido_mnq.md`. Nada de esto envía órdenes: operas tú, en demo.

## Rutina diaria (hora de Italia)
1. **Antes de las 15:30:** ejecuta `python scripts/zona_ruido_hoy.py` (actualiza los datos y muestra el cierre de ayer
   y el "ruido normal").
2. **15:30, apertura de Nueva York:** mira en el gráfico de MNQ el precio de apertura de la vela de las 15:30 y
   ejecuta `python scripts/zona_ruido_hoy.py --sin-descarga --apertura PRECIO`. Te da una tabla con 12 horas (16:00,
   16:30, … 21:30) y, en cada una, una banda superior y otra inferior.
3. **En cada hora de la tabla,** mira el cierre de la vela de 1 minuto anterior (por ejemplo, a las 16:00 mira el
   cierre de la vela de las 15:59):
   - Sin posición: por encima de la banda superior → COMPRAR 1 MNQ; por debajo de la inferior → VENDER 1 MNQ;
     entre las dos → nada.
   - Comprado: si está por debajo de la banda superior **y** también por debajo del VWAP → cerrar. Si además está bajo
     la banda inferior → vender.
   - Vendido: al revés.
4. **22:00:** cerrar lo que haya abierto.
5. **Anota cada operación** en `papel/zona_ruido_registro.csv`.

(En las semanas del cambio de hora de marzo y de octubre/noviembre, las horas se adelantan 1 h: la herramienta ya
lo tiene en cuenta.)

## Qué esperar (con precios actuales, 1 MNQ)
- Unas 230 operaciones al año, casi 1 al día.
- Acierta solo el 35-40 %: se gana porque las ganadoras son más grandes que las perdedoras.
- Un mes normal está entre −211 $ y +720 $ (la mitad central de los meses), y 1 de cada 3 meses es negativo.
- Criterio a los 3 meses: P&L > −1.334 $. Se para antes si la caída desde el máximo supera 2.888 $.
