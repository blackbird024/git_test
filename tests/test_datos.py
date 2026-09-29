"""Cargador de MT5, control de calidad y marcos temporales."""
import pandas as pd

from src.data.calidad import dias_iliquidos, huecos, informe, limpiar, velas_imposibles
from src.data.cargadores import cargar_mt5
from src.data.marcos import remuestrear


def test_mt5_csv_parsing(tmp_path):
    f = tmp_path / "XAUUSD_M1.csv"
    f.write_text("<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\n"
                 "2024.01.15\t10:00:00\t2050.1\t2051.0\t2049.9\t2050.5\t120\n"
                 "2024.01.15\t10:01\t2050.5\t2050.9\t2050.2\t2050.8\t80\n")
    df = cargar_mt5(f)
    assert list(df.index) == [pd.Timestamp("2024-01-15 08:00", tz="UTC"), pd.Timestamp("2024-01-15 08:01", tz="UTC")]
    assert df.volume.tolist() == [120, 80] and df.close.iloc[1] == 2050.8


def velas(filas, inicio="2024-01-16 15:00"):
    idx = pd.DatetimeIndex([pd.Timestamp(inicio, tz="UTC") + pd.Timedelta(minutes=m) for m, *_ in filas])
    return pd.DataFrame([f[1:] for f in filas], columns=["open", "high", "low", "close", "volume"], index=idx)


def test_quality_flags_duplicates_impossible_and_gaps():
    df = velas([(0, 10, 11, 9, 10, 1), (1, 10, 9, 11, 10, 1),        # máximo < mínimo
                (1, 10, 11, 9, 10, 1),                                # duplicada
                (90, 10, 11, 9, 10, 1)])                              # hueco de 89 min a mitad de sesión
    assert velas_imposibles(df).sum() == 1
    assert len(huecos(df)) == 1
    info = informe(df, "prueba")
    assert info["duplicados"] == 1 and info["velas_imposibles"] == 1
    assert len(limpiar(df)) == 3      # la imposible era la primera del minuto duplicado: se va al quitar duplicados


def test_daily_break_is_not_an_unexpected_gap():
    # 21:59 UTC -> 23:00 UTC en enero = 16:59 -> 18:00 de Nueva York: pausa diaria normal.
    df = velas([(0, 10, 11, 9, 10, 1), (61, 10, 11, 9, 10, 1)], inicio="2024-01-16 21:59")
    assert len(huecos(df)) == 0


def test_illiquid_days_use_only_previous_session():
    # 28 sesiones completas; la 26 tiene poco volumen. En la 27 el contrato sigue igual -> se marca la 27.
    # En la 28 el contrato ya cambió -> no se marca aunque la 27 también fuera baja.
    ses, vols, ids = range(28), [100] * 25 + [10, 10, 100], [1] * 27 + [2]
    df = pd.concat([pd.DataFrame({"volume": v / 1300, "instrument_id": i},
                                 index=pd.date_range(pd.Timestamp("2024-01-02 23:00", tz="UTC") + pd.Timedelta(days=k),  # 18:00 NY
                                                     periods=1300, freq="1min"))
                    for k, v, i in zip(ses, vols, ids)])
    dias = sorted(dias_iliquidos(df))
    todas = sorted(set(pd.Series(df.index).map(lambda t: (t.tz_convert("America/New_York") + pd.Timedelta(hours=6)).date())))
    assert todas[26] in dias and todas[27] not in dias


def test_resample_5m_and_daily_session():
    idx = pd.date_range("2024-01-16 22:58", periods=6, freq="1min", tz="UTC")   # cruza las 18:00 NY (23:00 UTC)
    df = pd.DataFrame({"open": range(6), "high": range(1, 7), "low": range(6), "close": range(6), "volume": 1.0},
                      index=idx, dtype=float)
    d1 = remuestrear(df, "1D")
    assert len(d1) == 2                                               # 22:58-22:59 sesión del 16; desde 23:00 la del 17
    assert d1.iloc[1].open == 2 and d1.iloc[1].volume == 4
    m5 = remuestrear(df, "5M")
    assert list(m5.index.strftime("%H:%M")) == ["22:55", "23:00"]
    assert m5.iloc[0].disponible_utc == pd.Timestamp("2024-01-16 23:00", tz="UTC")
