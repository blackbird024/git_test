"""Descarga (DE PAGO, autorizada por el usuario el 15-oct-2026; coste consultado ≈ 0,56 USD) de NQ.c.0 ohlcv-1s
(Databento GLBX.MDP3) SOLO de los minutos en que la vela de 5 min del DATO (8:25 ET) o de la APERTURA (9:25 ET) se rompe
por arriba y por abajo en el MISMO minuto de 1 min: 3 minutos desde ese minuto. Se guarda en vwap_lab/data/cache/
(ignorado por git) como un único pickle {(fecha, ventana): DataFrame}."""
import os
import pickle
import sys
from pathlib import Path

import databento as db
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rangos_lib import load_days, setup  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "vwap_lab" / "data" / "cache" / "NQ_1s_doble_ruptura.pkl"


def ventanas():
    D, _ = load_days("MNQ")
    out = []
    for d, m in D:
        for a in (505, 565):
            if setup(m, a, 5, 0.25) == "mismo":
                H, L = m[:, 1], m[:, 2]
                hi, lo = np.nanmax(H[a:a + 5]), np.nanmin(L[a:a + 5])
                ex = min(a + 5 + 210, 955)
                k = a + 5 + np.nonzero((H[a + 5:ex] >= hi + 0.25) | (L[a + 5:ex] <= lo - 0.25))[0][0]
                out.append((d, a, int(k)))
    return out


def main():
    data = pickle.load(open(OUT, "rb")) if OUT.exists() else {}
    c = db.Historical(os.environ["DATABENTO_API_KEY"])
    W = ventanas()
    print(len(W), "ventanas;", len(data), "ya descargadas", flush=True)
    for i, (d, a, k) in enumerate(W):
        if (d, a) in data:
            continue
        t0 = pd.Timestamp(f"{d.date()} 00:00", tz="America/New_York") + pd.Timedelta(minutes=k)
        for intento in range(4):
            try:
                df = c.timeseries.get_range(dataset="GLBX.MDP3", symbols=["NQ.c.0"], stype_in="continuous",
                                            schema="ohlcv-1s", start=t0.tz_convert("UTC"),
                                            end=(t0 + pd.Timedelta(minutes=3)).tz_convert("UTC")).to_df()
                break
            except Exception as e:  # red: reintento
                print("reintento", d.date(), a, e, flush=True)
        data[(d, a)] = (k, df[["open", "high", "low", "close"]])
        if i % 50 == 0:
            pickle.dump(data, open(OUT, "wb"))
            print(i, flush=True)
    pickle.dump(data, open(OUT, "wb"))
    print("listo", len(data), "→", OUT)


if __name__ == "__main__":
    main()
