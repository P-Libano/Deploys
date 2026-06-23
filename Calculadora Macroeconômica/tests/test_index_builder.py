"""Testes do engine/index_builder.py."""
import numpy as np
import pandas as pd
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.index_builder import (
    _parse_period,
    build_accumulated_index,
    get_accumulated_variation_pct,
    get_factor_between,
)


def test_parse_period_valid():
    p = _parse_period("07/1994")
    assert p == pd.Period("1994-07", freq="M")


def test_parse_period_invalid():
    with pytest.raises(ValueError):
        _parse_period("1994-07")


def test_factor_simple_inclusive(simple_series):
    """Jan, Fev, Mar: 1%, 2%, 3% — intervalo inclusivo nos dois extremos."""
    factor = get_factor_between(simple_series, "01/2024", "03/2024")
    expected = 1.01 * 1.02 * 1.03
    assert abs(factor - expected) < 1e-10


def test_factor_single_month(simple_series):
    """Intervalo de um único mês: fator == 1 + taxa."""
    factor = get_factor_between(simple_series, "02/2024", "02/2024")
    assert factor == 1.0  # mesmo mês → fator 1


def test_factor_deflation(simple_series):
    """Deflação: resultado < 1."""
    factor_forward = get_factor_between(simple_series, "01/2024", "03/2024")
    factor_backward = get_factor_between(simple_series, "03/2024", "01/2024")
    assert abs(factor_forward * factor_backward - 1.0) < 1e-10


def test_factor_two_months(simple_series):
    """Jan → Fev: apenas 2 meses."""
    factor = get_factor_between(simple_series, "01/2024", "02/2024")
    expected = 1.01 * 1.02
    assert abs(factor - expected) < 1e-10


def test_accumulated_variation_pct(simple_series):
    """Variação % bate com fator calculado."""
    pct = get_accumulated_variation_pct(simple_series, "01/2024", "03/2024")
    expected_factor = 1.01 * 1.02 * 1.03
    expected_pct = (expected_factor - 1) * 100
    assert abs(pct - expected_pct) < 1e-8


def test_build_accumulated_index_base_100(simple_series):
    """Mês base deve ser exatamente 100."""
    idx = build_accumulated_index(simple_series, "01/2024")
    assert abs(idx.loc[pd.Period("2024-01", freq="M")] - 100.0) < 1e-10


def test_build_accumulated_index_monotone(simple_series):
    """Índice deve crescer com taxas positivas."""
    idx = build_accumulated_index(simple_series, "01/2024")
    assert idx.is_monotonic_increasing


def test_build_accumulated_index_invalid_base(simple_series):
    """Base fora do range deve levantar ValueError."""
    with pytest.raises(ValueError):
        build_accumulated_index(simple_series, "01/2020")
