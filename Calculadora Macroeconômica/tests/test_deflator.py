"""
Testes de integração do engine/deflator.py.

Os casos de validação marcados com @pytest.mark.integration requerem
conexão com a internet (API BCB) e são skip por padrão.
Execute com: pytest -m integration
"""
import pandas as pd
import pytest
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.deflator import (
    FutureLimitError,
    PrePlanoRealError,
    corrigir_valor,
)
from engine.index_builder import _parse_period


def _make_series(start: str, n_months: int, rate: float = 1.0) -> pd.Series:
    """Cria série de taxa constante para testes isolados."""
    idx = pd.period_range(start, periods=n_months, freq="M")
    return pd.Series([rate] * n_months, index=idx, dtype=float)


@pytest.fixture
def mock_series_100_months():
    return _make_series("01/2010", n_months=180, rate=0.5)


def test_same_origin_destination(mock_series_100_months):
    """Mesmo mês: fator 1.0, valor inalterado."""
    with patch("engine.deflator.get_realized_series") as mock_get:
        mock_get.return_value = (mock_series_100_months, True, None)
        result = corrigir_valor(1000.0, "06/2015", "06/2015", "IPCA")
    assert result.fator_acumulado == 1.0
    assert result.valor_corrigido == 1000.0
    assert result.n_meses == 0


def test_one_month_forward(mock_series_100_months):
    """
    Avança 1 mês com taxa de 0.5%.
    Semântica inclusiva em ambos os extremos (igual BCB Calculadora do Cidadão):
    01/2015→02/2015 multiplica Jan e Fev → 1.005 × 1.005 = 1.010025.
    """
    with patch("engine.deflator.get_realized_series") as mock_get, \
         patch("engine.deflator.get_focus_projections") as mock_focus:
        mock_get.return_value = (mock_series_100_months, True, None)
        mock_focus.return_value = (pd.DataFrame(), pd.DataFrame())
        result = corrigir_valor(1000.0, "01/2015", "02/2015", "IPCA")
    expected_factor = 1.005 * 1.005  # Jan + Fev, ambos inclusivos
    assert abs(result.fator_acumulado - expected_factor) < 1e-10
    assert abs(result.valor_corrigido - 1000.0 * expected_factor) < 1e-6


def test_deflation(mock_series_100_months):
    """Deflação: destino anterior à origem, fator < 1."""
    with patch("engine.deflator.get_realized_series") as mock_get, \
         patch("engine.deflator.get_focus_projections") as mock_focus:
        mock_get.return_value = (mock_series_100_months, True, None)
        mock_focus.return_value = (pd.DataFrame(), pd.DataFrame())
        result = corrigir_valor(1000.0, "02/2015", "01/2015", "IPCA")
    assert result.fator_acumulado < 1.0
    assert result.variacao_pct < 0


def test_pre_plano_real_raises():
    """Data anterior ao início da série levanta PrePlanoRealError."""
    with pytest.raises(PrePlanoRealError):
        corrigir_valor(100.0, "01/1993", "01/2000", "IPCA")


def test_future_limit_raises():
    """Data muito no futuro levanta FutureLimitError."""
    with pytest.raises(FutureLimitError):
        corrigir_valor(100.0, "01/2020", "01/2030", "IPCA")


def test_invalid_index_raises():
    """Índice inválido levanta KeyError."""
    with pytest.raises(KeyError):
        corrigir_valor(100.0, "01/2020", "01/2021", "XPTO")


def test_result_n_meses(mock_series_100_months):
    """n_meses deve ser a diferença absoluta entre os períodos."""
    with patch("engine.deflator.get_realized_series") as mock_get, \
         patch("engine.deflator.get_focus_projections") as mock_focus:
        mock_get.return_value = (mock_series_100_months, True, None)
        mock_focus.return_value = (pd.DataFrame(), pd.DataFrame())
        result = corrigir_valor(1000.0, "01/2015", "01/2016", "IPCA")
    assert result.n_meses == 12


# ---------------------------------------------------------------------------
# Testes de integração real (requerem internet)
# ---------------------------------------------------------------------------

BCB_REFERENCE_CASES = [
    # (valor, data_origem, data_destino, indice, valor_esperado, tolerancia_pct)
    # Casos validados manualmente na Calculadora do Cidadão BCB
    # https://www3.bcb.gov.br/CALCIDADAO/publico/corrigirPorIndice.do
    (1000.0, "07/1994", "07/1994", "IPCA", 1000.0, 0.001),
]


@pytest.mark.integration
@pytest.mark.parametrize("valor,orig,dest,indice,esperado,tol", BCB_REFERENCE_CASES)
def test_against_bcb_reference(valor, orig, dest, indice, esperado, tol):
    """Valida resultado contra a Calculadora do Cidadão do BCB."""
    result = corrigir_valor(valor, orig, dest, indice)
    assert abs(result.valor_corrigido - esperado) / esperado < tol, (
        f"Esperado R$ {esperado:.2f}, obtido R$ {result.valor_corrigido:.2f} "
        f"({indice} {orig}→{dest})"
    )
