import numpy as np
import pandas as pd

from carril_b.dax40 import cargar_mt5 as C


def _csv(tmp_path, utf16=False):
    # 2 sesiones de invierno (Berlín = UTC+1, NY = UTC-5, servidor = UTC+2): 09:00 Berlín = 10:00 servidor
    filas = ["<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>"]
    for dia in ("2025.01.06", "2025.01.07"):
        t0 = pd.Timestamp(dia.replace(".", "-") + " 09:00")
        for k in range(510):
            t = t0 + pd.Timedelta(minutes=k)
            r = 20.0 if k == 0 else 2.0
            filas.append(f"{t:%Y.%m.%d}\t{t:%H:%M:%S}\t20000\t{20000 + r}\t{20000 - r}\t20000\t10\t0\t12")
    p = tmp_path / "GER40.csv"
    txt = "\n".join(filas) + "\n"
    p.write_bytes(b"\xff\xfe" + txt.encode("utf-16-le") if utf16 else txt.encode())
    return p


def test_hora_y_integridad(tmp_path):
    for u in (False, True):
        df = C.leer_csv_mt5(_csv(tmp_path, u))
        assert str(df.index.tz) == "UTC"
        # 09:00 servidor (NY+7) = 02:00 NY = 07:00 UTC en enero
        assert df.index[0] == pd.Timestamp("2025-01-06 07:00", tz="UTC")
        assert df.spread_pts.iloc[0] == 12
        rep = C.integridad(df)
        assert rep["duplicadas"] == 0 and rep["imposibles"] == 0
        assert rep["sesiones_xetra"] == 2


def test_desfase_detecta_apertura(tmp_path):
    # con hora de servidor = Berlín + 1, la vela grande (k=0) cae a las 08:00 Berlín → el control debe fallar
    df = C.leer_csv_mt5(_csv(tmp_path))
    d = C.comprobar_desfase(df)
    assert d["top3_minutos_berlin"][0] == "08:00" and not d["ok"]
    bien = df.copy()
    bien.index = bien.index + pd.Timedelta(hours=1)
    assert C.comprobar_desfase(bien)["ok"]


def test_vela_imposible(tmp_path):
    df = C.leer_csv_mt5(_csv(tmp_path))
    df.iloc[5, df.columns.get_loc("high")] = 1.0
    assert C.integridad(df)["imposibles"] == 1
