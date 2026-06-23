"""Testes do collectors/updater.py — foco no round-trip Parquet com PeriodIndex."""
import tempfile
from pathlib import Path
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collectors.updater import _cache_is_fresh, _load_series, _save_series
from datetime import timedelta


def test_parquet_period_roundtrip():
    """PeriodIndex deve sobreviver ao ciclo save → load."""
    original = pd.Series(
        [0.42, 0.83, 0.65],
        index=pd.period_range("2024-01", periods=3, freq="M"),
        dtype=float,
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.parquet"
        _save_series(original, path)
        loaded = _load_series(path)

    assert loaded.index.dtype == original.index.dtype, "PeriodDtype deve ser restaurado"
    pd.testing.assert_series_equal(original, loaded, check_names=False)


def test_parquet_period_dtype():
    """Index carregado deve ser PeriodDtype com freq='M'."""
    s = pd.Series([1.0], index=pd.period_range("2023-06", periods=1, freq="M"))
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "s.parquet"
        _save_series(s, path)
        loaded = _load_series(path)
    assert isinstance(loaded.index, pd.PeriodIndex)
    assert loaded.index.freqstr == "M"


def test_cache_is_fresh_missing():
    """Arquivo inexistente → não é fresh."""
    assert not _cache_is_fresh(Path("/nao/existe.parquet"), timedelta(days=1))


def test_cache_is_fresh_existing(tmp_path):
    """Arquivo recém-criado está dentro do TTL de 1 dia."""
    p = tmp_path / "test.parquet"
    s = pd.Series([1.0], index=pd.period_range("2024-01", periods=1, freq="M"))
    _save_series(s, p)
    assert _cache_is_fresh(p, timedelta(days=1))


def test_cache_is_stale(tmp_path):
    """Arquivo com TTL negativo → sempre stale (independente de timing do SO)."""
    p = tmp_path / "stale.parquet"
    s = pd.Series([1.0], index=pd.period_range("2024-01", periods=1, freq="M"))
    _save_series(s, p)
    assert not _cache_is_fresh(p, timedelta(seconds=-1))
