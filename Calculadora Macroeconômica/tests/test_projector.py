"""Testes do engine/projector.py — nova metodologia composta uniforme."""
import numpy as np
import pandas as pd
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.projector import (
    distribute_annual_to_monthly,
    build_projected_series,
)


def test_distribute_uniform_reconstructs_annual():
    """Taxa mensal uniforme: produto dos 12 deve reconstituir a taxa anual."""
    annual_pct = 6.0
    # Série realizada sem nenhum mês de 2099 (ano inteiramente futuro)
    realized = pd.Series(
        [0.5] * 12,
        index=pd.period_range("2098-01", periods=12, freq="M"),
    )
    monthly = distribute_annual_to_monthly(annual_pct, 2099, realized)

    assert len(monthly) == 12
    reconstructed = np.prod([(1 + v / 100) for v in monthly.values])
    assert abs(reconstructed - (1 + annual_pct / 100)) < 1e-8


def test_distribute_all_months_equal_for_future_year():
    """Ano inteiramente futuro → todas as 12 taxas iguais."""
    realized = pd.Series(
        [0.5] * 12,
        index=pd.period_range("2098-01", periods=12, freq="M"),
    )
    monthly = distribute_annual_to_monthly(5.0, 2099, realized)
    rates = monthly.values
    assert np.allclose(rates, rates[0])


def test_distribute_current_year_residual(ipca_like_series):
    """
    Ano corrente com alguns meses realizados:
    o produto dos realizados × projetados deve fechar na taxa anual.
    """
    # Tomar o último ano completo da série como "ano corrente com 6 meses realizados"
    last = ipca_like_series.index.max()
    year = last.year
    # Manter só os primeiros 6 meses do ano (simula meses realizados)
    realized_partial = ipca_like_series[ipca_like_series.index.year <= year].copy()
    # Remover últimos 6 meses do ano para simular ano em curso
    cutoff = pd.Period(f"{year}-06", freq="M")
    realized_partial = realized_partial[realized_partial.index <= cutoff]

    annual_pct = 5.0
    projected = distribute_annual_to_monthly(annual_pct, year, realized_partial)

    # Deve projetar apenas os 6 meses restantes (Jul–Dez)
    assert len(projected) == 6

    # Produto: realizados (Jan–Jun) × projetados (Jul–Dez) ≈ taxa anual
    realized_in_year = realized_partial[realized_partial.index.year == year]
    realized_factor = float(np.prod((1 + realized_in_year / 100).values))
    proj_factor = float(np.prod((1 + projected / 100).values))
    total_factor = realized_factor * proj_factor
    expected_factor = 1 + annual_pct / 100
    assert abs(total_factor - expected_factor) < 1e-8


def test_distribute_current_year_equal_remaining(ipca_like_series):
    """Os meses projetados do ano corrente devem ter taxas iguais entre si."""
    last = ipca_like_series.index.max()
    year = last.year
    cutoff = pd.Period(f"{year}-06", freq="M")
    realized_partial = ipca_like_series[ipca_like_series.index <= cutoff]

    projected = distribute_annual_to_monthly(5.0, year, realized_partial)
    rates = projected.values
    assert np.allclose(rates, rates[0], atol=1e-10)


def test_build_projected_no_projection_needed(ipca_like_series):
    """Se destino <= último realizado, retorna sem projeção."""
    last = ipca_like_series.index.max()
    target = last - 3
    unified, last_real, source = build_projected_series(
        ipca_like_series, pd.DataFrame(), pd.DataFrame(), target
    )
    assert source == "realized only"
    assert last_real == ipca_like_series.index.max()


def test_build_projected_ignores_monthly_focus(ipca_like_series):
    """Focus mensal é ignorado — apenas o anual é usado (premissa: taxa plana composta)."""
    last = ipca_like_series.index.max()
    target = last + 2
    target_year = target.year

    future_months = [last + 1, last + 2]
    focus_monthly = pd.DataFrame({
        "DataReferencia": future_months,
        "Mediana": [99.9, 99.9],  # valores absurdos que não devem aparecer
        "Media": [99.9, 99.9],
        "numeroRespondentes": [30, 30],
        "Data": pd.Timestamp("2024-01-01"),
    })
    focus_annual = pd.DataFrame({
        "DataReferencia": pd.array([target_year], dtype="Int64"),
        "Mediana": [5.0],
        "Media": [5.0],
        "Data": pd.Timestamp("2024-01-01"),
    })

    unified, last_real, source = build_projected_series(
        ipca_like_series, focus_monthly, focus_annual, target
    )
    assert source == "Focus Anual"
    assert target in unified.index
    # Taxas projetadas devem ser iguais (distribuição plana)
    proj = unified[unified.index > last_real]
    assert float(proj.iloc[0]) < 10  # não é 99.9


def test_build_projected_annual_closes_correctly(ipca_like_series):
    """Focus anual distribui corretamente e a série resultante cobre o target."""
    last = ipca_like_series.index.max()
    target_year = last.year + 1
    target = pd.Period(f"{target_year}-06", freq="M")

    focus_annual = pd.DataFrame({
        "DataReferencia": pd.array([target_year], dtype="Int64"),
        "Mediana": [5.0],
        "Media": [5.0],
        "Data": pd.Timestamp("2024-01-01"),
    })

    unified, last_real, source = build_projected_series(
        ipca_like_series, pd.DataFrame(), focus_annual, target
    )
    assert "Focus Anual" in source
    assert target in unified.index
