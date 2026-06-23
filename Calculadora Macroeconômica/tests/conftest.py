"""Fixtures compartilhadas para os testes."""
import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def simple_series():
    """Série simples: Jan–Mar/2024 com taxas 1%, 2%, 3%."""
    idx = pd.period_range("2024-01", periods=3, freq="M")
    return pd.Series([1.0, 2.0, 3.0], index=idx, dtype=float)


@pytest.fixture
def ipca_like_series():
    """Série realista de 36 meses com sazonalidade."""
    rng = np.random.default_rng(42)
    months = pd.period_range("2021-01", periods=36, freq="M")
    base = np.array([0.8, 0.7, 0.8, 0.5, 0.5, 0.5, 0.7, 0.9, 0.5, 0.6, 0.9, 1.2] * 3)
    noise = rng.normal(0, 0.1, 36)
    values = np.clip(base + noise, 0.1, 2.5)
    return pd.Series(values, index=months, dtype=float)
