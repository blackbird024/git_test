# Conclusión del analista (escrita tras leer `INFORME.md`, 29-sep-2026)

**La hipótesis "operar en la dirección del precio respecto al VWAP de 15 min tiene ventaja neta en MNQ" NO recibe
apoyo de los datos.**

1. **Hay una señal bruta muy pequeña, pero los costes la anulan.** El baseline gana +0,015 R por operación antes de
   costes en train, +0,019 R en validación y +0,025 R en test. Los costes (≈ 0,06 R por operación con 1 tick y 0,85 $)
   la convierten en −0,044 R (t −3,2) en train, 0,000 R en validación y +0,008 R (t 0,3) en test.
2. **Es mejor que el azar, no mejor que cero.** Con las mismas horas y dirección aleatoria se pierde −0,11 R por
   operación en train: la dirección del VWAP aporta algo de información, pero no lo suficiente para pagar el
   deslizamiento y la comisión de ~1,6 operaciones al día.
3. **La candidata (filtro horario 09:30–11:30 / 13:00) apenas cambia nada:** validación +0,006 R (t 0,18), test
   +0,008 R (t 0,30, PF 1,01). El bootstrap del test da un 47 % de probabilidad de resultado neto negativo.
4. **Filtros llamativos que se descartaron con razón:** la distancia mínima al VWAP (G) dio +0,071 R con t 2,18 en
   validación, pero −0,064 R en train. Elegirla por la validación habría sido sobreajuste; el protocolo la rechazó.
5. **Salidas:** ninguna salida supera al baseline en train; con stop y target fijos el resultado empeora en train.
   El walk-forward (2018–2022) da +0,015 R, t 0,87: la optimización de stop/target no generaliza.
6. **Sensibilidad:** con 2 ticks de deslizamiento la pérdida en train pasa a −0,064 R. El resultado depende más de los
   costes que de cualquier parámetro.
7. **Número de pruebas:** 147 variantes (con rejilla y walk-forward). Con tantas pruebas, algún resultado positivo
   aislado es esperable por azar; ninguno se sostuvo en train, validación y test a la vez.

**Recomendación:** no pasar a paper trading con esta versión (el protocolo del informe lo condiciona a que la
candidata quede apoyada). Si se quiere seguir, la única dirección con fundamento es **reducir el coste por operación**
(menos operaciones, órdenes límite): la ventaja bruta existe pero es del orden de 1 tick.
