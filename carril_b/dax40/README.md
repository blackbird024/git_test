# DAX40 en horario de Londres (carril B)

Estudio separado del forward del NQ: no toca `forward_testing/`, RSI(2) ni Noise Zone. Reglas fijadas antes de ver datos: [`PREREGISTRO.md`](PREREGISTRO.md).

## Pasos
1. **Exportar de MT5:**
   - Ver → Símbolos (Ctrl+U) → **GER40** → pestaña **Barras**.
   - Marco **M1**, desde la fecha más antigua posible → **Solicitar** → **Exportar barras**.
2. **Cargar y comprobar** (UTC/Berlín, integridad y desfase horario del servidor):
   ```bash
   python -m carril_b.dax40.cargar_mt5 /ruta/GER40_M1.csv
   ```
   Si el desfase sale "REVISAR", se para ahí.
3. Parte 1 (descriptivo por franja) y Parte 2 (H1-H3), según el pre-registro.
