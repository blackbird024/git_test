"""Modo papel / forward test del RSI(2) en NQ: ¿qué hay que hacer en la próxima reapertura?

Uso:
    python scripts/senal_hoy.py                 # actualiza datos (si hay clave de Databento) y da la señal
    python scripts/senal_hoy.py --sin-descarga  # solo con los datos que ya hay

NO envía órdenes. Ejecútalo después del cierre de la sesión de CME (17:00 Nueva York = 23:00 Italia casi
todo el año). La orden, si la hay, es para la reapertura de Globex (18:00 Nueva York = 00:00 Italia).
"""
import argparse
import os
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.data.calidad import limpiar  # noqa: E402
from src.data.cargadores import cargar_databento  # noqa: E402
from src.data.datos import sesiones  # noqa: E402
from src.horas import NUEVA_YORK, ROMA  # noqa: E402
from src.strategies import nq_rsi2  # noqa: E402

ACTUALIZACION = RAIZ / "data" / "raw" / "NQ_1m_actualizacion.parquet"


def actualizar(confirmar: bool) -> None:
    import databento as db
    clave = os.environ.get("DATABENTO_API_KEY")
    if not clave:
        print("Sin DATABENTO_API_KEY: uso los datos que ya hay.")
        return
    c = db.Historical(clave)
    desde = cargar_databento("NQ").index.max() + pd.Timedelta(minutes=1)
    hasta = pd.Timestamp(c.metadata.get_dataset_range(dataset="GLBX.MDP3")["end"])
    if hasta <= desde:
        print("Los datos ya están al día.")
        return
    coste = c.metadata.get_cost(dataset="GLBX.MDP3", symbols=["NQ.v.0"], schema="ohlcv-1m",
                                stype_in="continuous", start=desde, end=hasta)
    print(f"Actualización de {desde} a {hasta}: coste ${coste:.4f}")
    if coste > 0.50 and not confirmar:
        sys.exit("Coste > 0,50 $: repite con --confirmar si quieres descargar.")
    nuevo = c.timeseries.get_range(dataset="GLBX.MDP3", symbols=["NQ.v.0"], schema="ohlcv-1m",
                                   stype_in="continuous", start=desde, end=hasta).to_df()
    nuevo = nuevo[["open", "high", "low", "close", "volume", "instrument_id"]]
    if ACTUALIZACION.exists():
        nuevo = pd.concat([pd.read_parquet(ACTUALIZACION), nuevo])
    nuevo[~nuevo.index.duplicated(keep="last")].sort_index().to_parquet(ACTUALIZACION)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sin-descarga", action="store_true")
    ap.add_argument("--confirmar", action="store_true")
    args = ap.parse_args()
    if not args.sin_descarga:
        actualizar(args.confirmar)

    m1 = limpiar(cargar_databento("NQ"))
    s = sesiones(m1)
    # Solo sesiones cerradas: la última cuenta si tiene vela en los últimos 5 minutos antes de las 17:00 NY.
    ultima = s.index[-1]
    cierre_ny = pd.Timestamp(f"{ultima.date()} 16:55", tz=NUEVA_YORK)
    if s.t_ultima.iloc[-1] < cierre_ny:
        s = s.iloc[:-1]
    cfg = nq_rsi2.Config()
    p = nq_rsi2.preparar_sesiones(s, cfg)
    ops = nq_rsi2.backtest_sesiones(p, cfg)
    u = p.iloc[-1]
    fecha = p.index[-1].date()
    reapertura = pd.Timestamp(f"{fecha} 18:00", tz=NUEVA_YORK)
    print("\n================ RSI(2) en NQ — modo papel ================")
    print(f"Última sesión cerrada: {fecha} (cierre {u.close:,.2f})")
    print(f"RSI(2) = {u.rsi:.1f} | SMA200 (ajustada) = {u.sma:,.2f} | cierre ajustado = {u.close_aj:,.2f}"
          f" | {'POR ENCIMA' if u.close_aj > u.sma else 'POR DEBAJO'} de la media de 200")
    print(f"Próxima reapertura: {reapertura.tz_convert(ROMA):%d-%m-%Y %H:%M} (hora de Italia)")

    abierta = len(ops) and ops.iloc[-1].motivo == "fin_de_datos"
    if abierta:
        op = ops.iloc[-1]
        entrada = s.open[s.t_primera == op.t_entrada].iloc[0]
        sesiones_dentro = int((s.t_primera >= op.t_entrada).sum())
        sale = u.rsi > cfg.salida or sesiones_dentro >= cfg.max_dias
        print(f"\nPOSICIÓN ABIERTA: comprado desde {op.t_entrada.tz_convert(ROMA):%d-%m-%Y %H:%M} (Italia) "
              f"a {entrada:,.2f}. Sesiones dentro: {sesiones_dentro} de {cfg.max_dias}.")
        if sale:
            motivo = f"RSI(2) {u.rsi:.1f} > {cfg.salida:g}" if u.rsi > cfg.salida else f"{cfg.max_dias} sesiones cumplidas"
            print(f">>> ACCIÓN: VENDER (cerrar) en la reapertura. Motivo: {motivo}.")
        else:
            print(">>> ACCIÓN: MANTENER. Se vuelve a revisar tras el próximo cierre.")
    elif bool(u.senal):
        print(f"\n>>> ACCIÓN: COMPRAR 1 MNQ en la reapertura (RSI(2) {u.rsi:.1f} < {cfg.entrada:g} y precio sobre la SMA200).")
        print(f"    Salida: tras el cierre en que RSI(2) > {cfg.salida:g}, o como mucho tras {cfg.max_dias} sesiones.")
        print("    Sin stop en la estrategia validada. Si quieres uno de catástrofe, que sea lejano (ver informe).")
    else:
        print("\n>>> ACCIÓN: NADA. No hay posición ni señal.")
    print("\nRecuerda: mantiene posiciones de un día para otro -> NO compatible con Apex. Solo papel / cuenta propia.")
    ult = ops.tail(5)[["t_entrada", "t_salida", "sesiones", "ret_%", "neto", "motivo"]]
    print("\nÚltimas operaciones del sistema (1 MNQ):")
    print(ult.to_string(index=False))


if __name__ == "__main__":
    main()
