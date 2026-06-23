"""Construção de número-índice acumulado a partir de variações mensais."""
import numpy as np
import pandas as pd


def build_accumulated_index(
    monthly_pct: pd.Series,
    base_period: str,
) -> pd.Series:
    """
    Converte série de variações mensais (%) em número-índice base 100.

    Args:
        monthly_pct: pd.Series com PeriodIndex mensal e valores em % (ex: 0.42)
        base_period: "MM/YYYY" — mês base = 100.0

    Returns:
        pd.Series com mesmo índice e valores do índice acumulado.
    """
    base = _parse_period(base_period)
    if base not in monthly_pct.index:
        raise ValueError(
            f"Período base '{base_period}' não encontrado na série. "
            f"Range: {monthly_pct.index.min()} — {monthly_pct.index.max()}"
        )

    factors = (1 + monthly_pct / 100).fillna(1.0)
    cumulative = factors.cumprod()

    # Normalizar para que base_period == 100
    base_value = cumulative.loc[base]
    return (cumulative / base_value) * 100.0


def get_factor_between(
    monthly_pct: pd.Series,
    start_period: str,
    end_period: str,
) -> float:
    """
    Calcula o fator acumulado de correção entre dois meses (ambos INCLUSIVOS).
    Compatível com a Calculadora do Cidadão do BCB:
    corrigir Jan→Mar multiplica as taxas de Jan, Fev e Mar.

    Para deflação (end < start): retorna 1 / fator_forward.
    """
    start = _parse_period(start_period)
    end = _parse_period(end_period)

    if start == end:
        return 1.0

    inverted = end < start
    if inverted:
        start, end = end, start

    # Selecionar o intervalo inclusivo
    mask = (monthly_pct.index >= start) & (monthly_pct.index <= end)
    interval = monthly_pct.loc[mask]

    if interval.empty:
        raise ValueError(
            f"Sem dados no intervalo {start_period}–{end_period}. "
            f"Range disponível: {monthly_pct.index.min()} — {monthly_pct.index.max()}"
        )

    factor = float(np.prod((1 + interval.fillna(0) / 100).values))

    return 1.0 / factor if inverted else factor


def get_accumulated_variation_pct(
    monthly_pct: pd.Series,
    start_period: str,
    end_period: str,
) -> float:
    """Conveniência: retorna variação acumulada em % (não fator)."""
    factor = get_factor_between(monthly_pct, start_period, end_period)
    return (factor - 1) * 100.0


def _parse_period(period_str: str) -> pd.Period:
    """Converte "MM/YYYY" para pd.Period com freq='M'."""
    parts = str(period_str).strip().split("/")
    if len(parts) != 2:
        raise ValueError(
            f"Formato de período inválido: '{period_str}'. Esperado: 'MM/YYYY'"
        )
    mm, yyyy = parts
    return pd.Period(f"{yyyy}-{mm.zfill(2)}", freq="M")
