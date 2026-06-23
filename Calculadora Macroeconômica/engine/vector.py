"""
Geração de vetor de inflação: série de fatores acumulados desde uma data-base.
Útil para deflacionar/inflacionar fluxos de modelos financeiros em lote.
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass

from collectors.updater import get_realized_series, get_focus_projections
from engine.index_builder import _parse_period
from engine.projector import build_ettj_projection, build_projected_series
import config


@dataclass
class InflationVector:
    base_date: str          # "MM/YYYY" — período onde fator = 1.0000
    indice: str
    data: pd.DataFrame      # colunas descritas abaixo
    last_realized: str      # "MM/YYYY" — último dado realizado
    has_projection: bool


def build_inflation_vector(
    base_date: str,
    start_date: str,
    end_date: str,
    indice: str = "IPCA",
    force_refresh: bool = False,
    projecao: str = "focus",
) -> InflationVector:
    """
    Constrói o vetor de inflação entre start_date e end_date,
    com fator acumulado relativo a base_date (= 1.0000).

    Colunas do DataFrame retornado:
        Período         : "MM/YYYY"
        Taxa Mensal (%) : variação mensal do índice
        Fator Mensal    : 1 + taxa/100
        Fator Acumulado : produto encadeado desde base_date (base = 1.0)
        Variação Acum. (%): (fator_acumulado - 1) × 100
        Tipo            : "Realizado" | "Projeção Focus"

    O fator acumulado > 1 significa inflação em relação à base;
    < 1 significa deflação (base_date está no futuro em relação ao período).
    """
    if indice not in config.SERIES:
        raise KeyError(f"Índice '{indice}' inválido. Opções: {list(config.SERIES)}")

    base   = _parse_period(base_date)
    start  = _parse_period(start_date)
    end    = _parse_period(end_date)

    # Garantir que start <= end
    if start > end:
        start, end = end, start

    # Incluir base_date no range para garantir normalização correta
    range_start = min(start, base)
    range_end   = max(end,   base)

    # Carregar série + projeção
    realized, _, warning = get_realized_series(indice, force_refresh=force_refresh)

    if projecao == "ettj" and indice == "IPCA":
        from collectors.anbima_ettj import fetch_ettj
        ettj_df, _ = fetch_ettj(force_refresh=force_refresh)
        unified, last_real, source = build_ettj_projection(realized, ettj_df, range_end)
    else:
        focus_monthly, focus_annual = get_focus_projections(indice, force_refresh=force_refresh)
        unified, last_real, source = build_projected_series(
            realized, focus_monthly, focus_annual, range_end
        )

    has_projection = source != "realized only"

    # Recortar ao range pedido
    mask = (unified.index >= range_start) & (unified.index <= range_end)
    series_slice = unified.loc[mask].copy()

    if series_slice.empty:
        raise ValueError(
            f"Sem dados no intervalo {start_date}–{end_date} para {indice}."
        )

    # Calcular fatores mensais e acumulado com base em base_date
    factors = (1 + series_slice.fillna(0) / 100)
    cumulative = factors.cumprod()

    # Normalizar: fator no base_date = 1.0
    if base in cumulative.index:
        base_value = float(cumulative.loc[base])
    else:
        # base_date fora do range — normalizar pelo primeiro valor
        base_value = float(cumulative.iloc[0])

    normalized = cumulative / base_value

    # Montar DataFrame final
    rows = []
    for period in pd.period_range(start=start, end=end, freq="M"):
        if period not in series_slice.index:
            continue
        monthly_pct = float(series_slice.loc[period])
        fator_mensal = 1 + monthly_pct / 100
        fator_acum = float(normalized.loc[period]) if period in normalized.index else float("nan")
        if period <= last_real:
            tipo = "Realizado"
        elif "ETTJ" in source:
            tipo = "Projeção ETTJ BEI"
        else:
            tipo = "Projeção Focus"

        rows.append({
            "Período": period.strftime("%m/%Y"),
            "Taxa Mensal (%)": round(monthly_pct, 4),
            "Fator Mensal": round(fator_mensal, 6),
            "Fator Acumulado": round(fator_acum, 6),
            "Variação Acum. (%)": round((fator_acum - 1) * 100, 4),
            "Tipo": tipo,
        })

    df = pd.DataFrame(rows)

    return InflationVector(
        base_date=base_date,
        indice=indice,
        data=df,
        last_realized=last_real.strftime("%m/%Y"),
        has_projection=has_projection,
    )
