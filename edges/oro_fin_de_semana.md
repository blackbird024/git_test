# Ventaja 2 — Oro: comprar el viernes y vender el lunes

*Escrita el 29-sep-2026, ANTES de ejecutar ningún backtest.*

## Hipótesis
El oro tiende a subir entre el cierre del viernes y el cierre del lunes.

## Por qué debería funcionar (la causa)
El oro es un activo refugio. Antes del fin de semana, cuando los mercados están cerrados y no se puede
reaccionar a las noticias, los fondos compran oro como cobertura. Esa demanda empuja el precio el viernes
y durante el fin de semana, y habría una prima que se cobra al mantener la posición.

**Nota:** no conozco una publicación académica concreta de esta idea con fecha, así que no se puede
separar un periodo "después de publicarse".

## Reglas exactas (versión mínima)
| Elemento | Regla |
|---|---|
| Mercado | MGC (datos de GC), 1 contrato |
| Entrada | Compra al cierre de la última sesión de la semana (normalmente el viernes; apertura de la última vela de 1M antes de las 17:00 de Nueva York) |
| Salida | Venta al cierre de la primera sesión de la semana siguiente (normalmente el lunes; mismo criterio) |
| Stop / objetivo | Ninguno (versión mínima) |
| Costes | 1 $ por contrato y lado + 1 tick por lado |
| Días excluidos | Sesiones ilíquidas previsibles |

Es una regla de calendario: se conoce de antemano y no usa ningún precio, así que no puede mirar el futuro.

**Parámetros libres:** ninguno.

## Comparación
Mismo cálculo para el resto de pares de sesiones consecutivas (lunes→martes, martes→miércoles, etc.). Si
el viernes→lunes no es mejor que un día cualquiera, no hay ventaja propia del fin de semana (solo la
subida general del oro en estos años). También se separa el hueco del fin de semana (del cierre del
viernes a la reapertura del domingo) del movimiento del lunes.

## Qué la refutaría
- Rendimiento medio neto ≤ 0, o no mejor que el de los demás pares de días → **descartada**.
- Resultado concentrado en pocos años (no persiste año a año).

**Aviso: incompatible con Apex** (obliga a mantener la posición el fin de semana). Solo para cuenta propia.
