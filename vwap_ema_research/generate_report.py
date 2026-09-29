"""Genera plots/ y reports/FINAL_REPORT.md a partir de results/ (ejecuta antes run_backtest.py y optimize.py)."""
from src.report import construir

if __name__ == "__main__":
    construir()
    print("reports/FINAL_REPORT.md generado")
