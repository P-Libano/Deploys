"""Coleta de expectativas do Boletim Focus via python-bcb."""
import pandas as pd
from config import FOCUS_INDICATOR_MAP


class FocusAPIError(Exception):
    """Levantada quando a coleta do Focus falha ou retorna dados inesperados."""
    pass


def fetch_focus_monthly(
    series_key: str,
    reference_months: list[str] | None = None,
) -> pd.DataFrame:
    """
    Busca ExpectativaMercadoMensais do Boletim Focus.
    Filtro: baseCalculo == 0 (expectativas padrão, não de base de comparação).
    Para cada DataReferencia retorna a pesquisa mais recente (maior Data).

    Returns:
        DataFrame com colunas: DataReferencia (Period M), Mediana, Media,
        numeroRespondentes, Data (date da pesquisa)
    """
    from bcb import Expectativas

    indicator = FOCUS_INDICATOR_MAP.get(series_key)
    if indicator is None:
        raise FocusAPIError(f"Série '{series_key}' não tem mapeamento Focus.")

    try:
        em = Expectativas()
        ep = em.get_endpoint("ExpectativaMercadoMensais")
        df = ep.query().filter(
            ep.Indicador == indicator,
            ep.baseCalculo == 0,
        ).collect()
    except Exception as e:
        raise FocusAPIError(f"Falha ao coletar Focus mensal para {series_key}: {e}") from e

    if df is None or len(df) == 0:
        raise FocusAPIError(f"Focus mensal retornou DataFrame vazio para '{indicator}'.")

    df = _parse_monthly(df)

    if reference_months is not None:
        target_periods = {_parse_period(m) for m in reference_months}
        df = df[df["DataReferencia"].isin(target_periods)]

    return df.reset_index(drop=True)


def fetch_focus_annual(
    series_key: str,
    reference_years: list[int] | None = None,
) -> pd.DataFrame:
    """
    Busca ExpectativasMercadoAnuais do Boletim Focus.
    Filtro: baseCalculo == 0.
    Para cada DataReferencia retorna a pesquisa mais recente.

    Returns:
        DataFrame com colunas: DataReferencia (int), Mediana, Media, Data
    """
    from bcb import Expectativas

    indicator = FOCUS_INDICATOR_MAP.get(series_key)
    if indicator is None:
        raise FocusAPIError(f"Série '{series_key}' não tem mapeamento Focus.")

    try:
        em = Expectativas()
        ep = em.get_endpoint("ExpectativasMercadoAnuais")
        df = ep.query().filter(
            ep.Indicador == indicator,
            ep.baseCalculo == 0,
        ).collect()
    except Exception as e:
        raise FocusAPIError(f"Falha ao coletar Focus anual para {series_key}: {e}") from e

    if df is None or len(df) == 0:
        raise FocusAPIError(f"Focus anual retornou DataFrame vazio para '{indicator}'.")

    df = _parse_annual(df)

    if reference_years is not None:
        df = df[df["DataReferencia"].isin(reference_years)]

    return df.reset_index(drop=True)


def fetch_focus_annual_history(series_key: str, reference_year: int) -> pd.DataFrame:
    """
    Retorna toda a série histórica de pesquisas Focus para um ano de referência.
    Usado para o gráfico de evolução das expectativas.

    Returns:
        DataFrame com colunas: Data (date), Mediana, Media, numeroRespondentes
    """
    from bcb import Expectativas

    indicator = FOCUS_INDICATOR_MAP.get(series_key)
    if indicator is None:
        raise FocusAPIError(f"Série '{series_key}' não tem mapeamento Focus.")

    try:
        em = Expectativas()
        ep = em.get_endpoint("ExpectativasMercadoAnuais")
        df = ep.query().filter(
            ep.Indicador == indicator,
            ep.DataReferencia == reference_year,
            ep.baseCalculo == 0,
        ).collect()
    except Exception as e:
        raise FocusAPIError(f"Falha ao coletar histórico Focus para {series_key}: {e}") from e

    if df is None or len(df) == 0:
        return pd.DataFrame(columns=["Data", "Mediana", "Media", "numeroRespondentes"])

    df["Data"] = pd.to_datetime(df["Data"])
    df["Mediana"] = pd.to_numeric(df.get("Mediana", pd.Series(dtype=float)), errors="coerce")
    df["Media"] = pd.to_numeric(df.get("Media", pd.Series(dtype=float)), errors="coerce")
    if "numeroRespondentes" in df.columns:
        df["numeroRespondentes"] = pd.to_numeric(df["numeroRespondentes"], errors="coerce")
    else:
        df["numeroRespondentes"] = float("nan")

    return (
        df[["Data", "Mediana", "Media", "numeroRespondentes"]]
        .sort_values("Data")
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _parse_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza o DataFrame mensal.
    Mantém apenas a pesquisa mais recente por DataReferencia.
    """
    df = df.copy()
    df["Data"] = pd.to_datetime(df["Data"])
    df["Mediana"] = pd.to_numeric(df.get("Mediana", pd.Series(dtype=float)), errors="coerce")
    df["Media"] = pd.to_numeric(df.get("Media", pd.Series(dtype=float)), errors="coerce")

    if "numeroRespondentes" in df.columns:
        df["numeroRespondentes"] = pd.to_numeric(df["numeroRespondentes"], errors="coerce")
    else:
        df["numeroRespondentes"] = float("nan")

    df["DataReferencia"] = df["DataReferencia"].apply(_parse_period)

    df = (
        df.sort_values("Data")
        .groupby("DataReferencia", group_keys=False)
        .tail(1)
    )
    return df[["DataReferencia", "Mediana", "Media", "numeroRespondentes", "Data"]]


def _parse_annual(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza DataFrame do endpoint anual.
    Mantém apenas a pesquisa mais recente por ano de referência.
    """
    df = df.copy()
    df["Data"] = pd.to_datetime(df["Data"])
    df["Mediana"] = pd.to_numeric(df.get("Mediana", pd.Series(dtype=float)), errors="coerce")
    df["Media"] = pd.to_numeric(df.get("Media", pd.Series(dtype=float)), errors="coerce")

    df["DataReferencia"] = pd.to_numeric(df["DataReferencia"], errors="coerce").astype("Int64")

    df = (
        df.sort_values("Data")
        .groupby("DataReferencia", group_keys=False)
        .tail(1)
    )
    return df[["DataReferencia", "Mediana", "Media", "Data"]]


def _parse_period(date_str: str) -> pd.Period:
    """Converte "MM/YYYY" para pd.Period com freq='M'."""
    parts = str(date_str).strip().split("/")
    if len(parts) != 2:
        raise ValueError(f"Formato inválido para período mensal: '{date_str}'")
    mm, yyyy = parts
    return pd.Period(f"{yyyy}-{mm.zfill(2)}", freq="M")
