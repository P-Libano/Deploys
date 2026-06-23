"""
Extensão da série realizada com projeções do Boletim Focus.

Metodologia de distribuição anual → mensal:
- Premissa: taxa mensal uniforme composta = (1 + annual/100)^(1/12) - 1
- Ano corrente com meses já realizados: calcula o delta restante e distribui
  igualmente nos meses faltantes do ano.
"""
import numpy as np
import pandas as pd
from datetime import datetime


def build_projected_series(
    realized: pd.Series,
    focus_monthly: pd.DataFrame,
    focus_annual: pd.DataFrame,
    target_period: pd.Period,
) -> tuple[pd.Series, pd.Period, str]:
    """
    Constrói série unificada: dados realizados + projeções Focus até target_period.

    Returns:
        (unified_series, last_realized, projection_source)
        - unified_series: pd.Series com PeriodIndex mensal e valores em %
        - last_realized: último período com dado realizado
        - projection_source: "Focus Mensal" | "Focus Anual" | "realized only"
    """
    last_realized = realized.index.max()

    if target_period <= last_realized:
        return realized, last_realized, "realized only"

    months_needed = pd.period_range(
        start=last_realized + 1, end=target_period, freq="M"
    )

    projected_values: dict[pd.Period, float] = {}
    projection_source = "realized only"
    extrapolated = False

    # Usa apenas o Focus anual com distribuição uniforme composta (anual/12).
    # O Focus mensal é ignorado intencionalmente: a premissa é que a taxa
    # divulgada pelo Focus é anual, distribuída em parcelas mensais iguais.
    # Para anos além do horizonte Focus, replica a última taxa anual disponível.
    years_needed = {m.year for m in months_needed}

    if focus_annual is not None and len(focus_annual) > 0:
        valid_rows = focus_annual.dropna(subset=["Mediana"])
        if len(valid_rows) > 0:
            last_annual_pct = float(
                valid_rows.sort_values("DataReferencia").iloc[-1]["Mediana"]
            )

            for year in sorted(years_needed):
                annual_row = focus_annual[focus_annual["DataReferencia"] == year]
                if annual_row.empty or np.isnan(float(annual_row["Mediana"].iloc[0])):
                    annual_pct = last_annual_pct
                    year_extrapolated = True
                else:
                    annual_pct = float(annual_row["Mediana"].iloc[0])
                    year_extrapolated = False

                monthly_dist = distribute_annual_to_monthly(
                    annual_pct=annual_pct,
                    year=year,
                    realized=realized,
                )

                for month in months_needed:
                    if month.year == year and month in monthly_dist.index:
                        projected_values[month] = float(monthly_dist.loc[month])
                        if year_extrapolated:
                            extrapolated = True
                        else:
                            projection_source = "Focus Anual"

    if not projected_values:
        return realized, last_realized, "realized only"

    proj_series = pd.Series(
        list(projected_values.values()),
        index=pd.PeriodIndex(list(projected_values.keys()), freq="M"),
        dtype=float,
    ).sort_index()

    unified = pd.concat([realized, proj_series]).sort_index()
    unified = unified[~unified.index.duplicated(keep="first")]

    if extrapolated:
        projection_source = "Focus Anual + extrapolação"

    return unified, last_realized, projection_source


def distribute_annual_to_monthly(
    annual_pct: float,
    year: int,
    realized: pd.Series,
) -> pd.Series:
    """
    Distribui expectativa anual (%) em taxas mensais usando taxa composta uniforme.

    Lógica:
    - Taxa mensal uniforme: (1 + annual/100)^(1/12) - 1
    - Para o ano corrente: verifica quantos meses já têm dado realizado.
      Se houver meses realizados no ano, calcula o fator residual necessário
      para fechar a expectativa anual e distribui igualmente nos meses restantes.
    - Para anos futuros: aplica taxa uniforme nos 12 meses.

    Returns:
        pd.Series com PeriodIndex para os meses projetados do ano e valores em %.
    """
    annual_factor = 1 + annual_pct / 100
    uniform_monthly_rate = annual_factor ** (1 / 12) - 1

    all_months = pd.period_range(start=f"{year}-01", periods=12, freq="M")

    # Identificar meses já realizados neste ano
    realized_in_year = realized[
        (realized.index >= all_months[0]) & (realized.index <= all_months[-1])
    ].dropna()

    if len(realized_in_year) == 0:
        # Ano inteiramente futuro: taxa uniforme nos 12 meses
        return pd.Series(
            {m: uniform_monthly_rate * 100 for m in all_months},
            dtype=float,
        )

    # Ano corrente: calcular fator residual
    realized_factor = float(np.prod((1 + realized_in_year / 100).values))
    remaining_factor = annual_factor / realized_factor

    # Meses ainda sem dado realizado (os que precisam de projeção)
    last_realized_in_year = realized_in_year.index.max()
    future_months = [m for m in all_months if m > last_realized_in_year]

    if len(future_months) == 0:
        return pd.Series(dtype=float)

    n = len(future_months)
    monthly_remaining_rate = remaining_factor ** (1 / n) - 1

    return pd.Series(
        {m: monthly_remaining_rate * 100 for m in future_months},
        dtype=float,
    )


def build_ettj_projection(
    realized: pd.Series,
    ettj_df: pd.DataFrame,
    target_period: pd.Period,
) -> tuple[pd.Series, pd.Period, str]:
    """
    Constrói projeção usando inflação implícita (BEI) da curva ETTJ ANBIMA.

    Usa taxas **forward implícitas** entre vértices consecutivos — não a taxa spot.
    O BEI spot no vértice de 5 anos representa a inflação média acumulada dos
    próximos 5 anos; a taxa forward entre o vértice de 4 e 5 anos extrai o
    incremento marginal esperado especificamente naquele período.

    Âncora temporal: para cada mês futuro t, calcula du_t = t × 21 du e
    identifica o intervalo (v_i, v_{i+1}) da curva que contém du_t. A taxa
    forward desse intervalo (mesma base % a.a. do Focus) é então convertida
    para mensal composta: (1 + r/100)^(1/12) − 1.

    Antes do primeiro vértice BEI: usa o BEI spot do primeiro vértice (sem
    referência anterior para calcular forward).
    Além do último vértice: mantém a última taxa forward disponível.
    """
    last_realized = realized.index.max()

    if target_period <= last_realized:
        return realized, last_realized, "realized only"

    months_needed = pd.period_range(start=last_realized + 1, end=target_period, freq="M")

    bei_data = ettj_df.dropna(subset=["bei_pct"]).sort_values("vertice_du").reset_index(drop=True)
    if bei_data.empty:
        return realized, last_realized, "realized only"

    intervals = _bei_forward_intervals(bei_data)

    # Âncora no primeiro mês projetado (não em "hoje"), para que a transição
    # entre vértices de 6 em 6 meses corresponda ao que o usuário conta na
    # tabela.  Ancorar em today.ordinal faria meses já passados no calendário
    # (como maio/2026 quando hoje é junho) receberem max(...,1)=1 e
    # permanecerem presos no primeiro vértice por 7 meses em vez de 6.
    first_month = months_needed[0]

    projected_values: dict[pd.Period, float] = {}
    for month in months_needed:
        months_ahead = (month.ordinal - first_month.ordinal) + 1  # 1-based
        du_ahead = months_ahead * 21
        forward_annual = _forward_for_du(intervals, du_ahead)
        monthly_rate = (1 + forward_annual / 100) ** (1 / 12) - 1
        projected_values[month] = monthly_rate * 100

    proj_series = pd.Series(
        list(projected_values.values()),
        index=pd.PeriodIndex(list(projected_values.keys()), freq="M"),
        dtype=float,
    ).sort_index()

    unified = pd.concat([realized, proj_series]).sort_index()
    unified = unified[~unified.index.duplicated(keep="first")]

    return unified, last_realized, "ETTJ BEI"


def _bei_forward_intervals(
    bei_data: pd.DataFrame,
) -> list[tuple[float, float, float]]:
    """
    Constrói lista de (du_low, du_high, forward_pct_aa) a partir da curva
    de BEI spot. Cada intervalo cobre du_low <= du < du_high.

    Segmento 0 (du=0 até primeiro vértice): forward = spot do primeiro vértice.
    Segmentos 1..n-1: forward implícito entre vértices i-1 e i.
    Segmento final: extende o último forward até infinito.

    Forward entre v1 e v2 (ambos em anos):
        f = [(1 + bei2/100)^anos2 / (1 + bei1/100)^anos1]^(1/Δanos) − 1
    """
    rows = bei_data.reset_index(drop=True)
    n = len(rows)

    intervals: list[tuple[float, float, float]] = []

    # Segmento 0: antes do primeiro vértice — spot = forward (sem prior)
    du0  = float(rows.loc[0, "vertice_du"])
    bei0 = float(rows.loc[0, "bei_pct"])
    intervals.append((0.0, du0, bei0))

    for i in range(1, n):
        du1  = float(rows.loc[i - 1, "vertice_du"])
        bei1 = float(rows.loc[i - 1, "bei_pct"])
        du2  = float(rows.loc[i,     "vertice_du"])
        bei2 = float(rows.loc[i,     "bei_pct"])

        anos1 = du1 / 252
        anos2 = du2 / 252
        delta = anos2 - anos1

        f1 = (1 + bei1 / 100) ** anos1
        f2 = (1 + bei2 / 100) ** anos2
        forward = (f2 / f1) ** (1 / delta) - 1

        intervals.append((du1, du2, forward * 100))

    # Extende além do último vértice com a última taxa forward
    last_du  = float(rows.iloc[-1]["vertice_du"])
    last_fwd = intervals[-1][2]
    intervals.append((last_du, float("inf"), last_fwd))

    return intervals


def _forward_for_du(intervals: list[tuple[float, float, float]], du: float) -> float:
    """Retorna a taxa forward (% a.a.) para um dado prazo em dias úteis."""
    for lo, hi, rate in intervals:
        if lo <= du < hi:
            return rate
    return intervals[-1][2]


def _ensure_period_column(df: pd.DataFrame) -> None:
    """Garante que DataReferencia contém pd.Period. Modifica in-place."""
    if "DataReferencia" not in df.columns:
        return
    sample = df["DataReferencia"].dropna()
    if sample.empty or isinstance(sample.iloc[0], pd.Period):
        return

    def _to_period(val):
        s = str(val).strip()
        if "/" in s:
            mm, yyyy = s.split("/")
            return pd.Period(f"{yyyy}-{mm.zfill(2)}", freq="M")
        try:
            return pd.Period(s, freq="M")
        except Exception:
            return val

    df["DataReferencia"] = df["DataReferencia"].apply(_to_period)
