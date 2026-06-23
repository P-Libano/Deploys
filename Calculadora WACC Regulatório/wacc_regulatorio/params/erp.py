"""
Prêmio de Risco de Mercado (PRM) — metodologia ANEEL.

Metodologia ANEEL (Despacho 675/2026):
    PRM = média dos 5 valores anuais acumulados [P-5, P-1]
    Cada valor anual X = média de todos os PRM mensais desde 1928 até dez/X
    PRM mensal t = Rm_12m_t - Rf_10y_t/100, onde:
        Rm_12m_t = retorno S&P500 Total Return nos 12 meses anteriores
        Rf_tbill_t = yield US T-Bill 3M no mês t (em %); T-Bond 10Y para período ECB SDW
    Fontes:
        S&P500: Bloomberg TOT_RETURN_INDEX_GROSS_DVDS (equivalente: ^SP500TR yfinance)
        US 10Y: ECB SDW FM.M.US.USD.4F.BB.US10YT_RR.YLDA
    Resultado esperado para WACC 2026 (dados 2021-2025): PRM = 6,8481% (delta 0bp)
"""
import numpy as np
import pandas as pd


def _prm_acumulado_ate_ano(ano: int, df_prep: pd.DataFrame) -> float:
    """PRM acumulado até dez/ano = média de todos os prm_mensal desde 1928 até dez/ano."""
    sub = df_prep[df_prep["data"].dt.year <= ano].dropna(subset=["prm_mensal"])
    if sub.empty:
        raise ValueError(f"Sem dados PRM até {ano}")
    return float(sub["prm_mensal"].mean())


def _preparar_prm_df(prm_df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona rm_12m, rf_tbill_dec e prm_mensal ao DataFrame."""
    df = prm_df.copy()
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df = df.sort_values("data").dropna(subset=["sp500"])
    df["rm_12m"] = df["sp500"].pct_change(12)
    df["rf_tbill_dec"] = pd.to_numeric(df["rf_tbill"], errors="coerce") / 100.0
    df["prm_mensal"] = df["rm_12m"] - df["rf_tbill_dec"]
    return df


def calcular_prm(
    ano_publicacao: int,
    prm_df: pd.DataFrame,
) -> tuple[float, list[tuple[int, float]]]:
    """
    PRM ANEEL = média dos 5 valores anuais acumulados [P-5, P-1].

    Estrutura idêntica ao Rf (5 anos de médias), mas a janela interna é
    acumulada desde 1928 (não rolling de 10 anos como no Rf).

    Args:
        ano_publicacao: Ano de publicação do WACC (e.g. 2026)
        prm_df: DataFrame de load_prm_sp500() — colunas: data, sp500, rf_tbill

    Returns:
        (prm_final, [(ano, prm_acumulado), ...])
    """
    df = _preparar_prm_df(prm_df)

    valores: list[tuple[int, float]] = []
    for ano in range(ano_publicacao - 5, ano_publicacao):
        try:
            v = _prm_acumulado_ate_ano(ano, df)
            valores.append((ano, v))
        except ValueError:
            pass

    if not valores:
        raise ValueError(f"Sem dados suficientes para PRM (publicação {ano_publicacao})")

    prm_final = float(np.mean([v for _, v in valores]))
    return prm_final, valores


def calcular_erp(ano: int, prm_df: pd.DataFrame) -> float:
    """
    [LEGADO] ERP geométrico acumulado S&P500 vs. média aritmética Treasury 10Y.
    Mantido para referência. Para C2, use calcular_prm.
    """
    df = _preparar_prm_df(prm_df)
    df = df[df["data"].dt.year <= ano]
    df = df.dropna(subset=["sp500"])

    if len(df) < 2:
        raise ValueError(f"Dados insuficientes para ERP até {ano}")

    p_inicial = float(df["sp500"].iloc[0])
    p_final = float(df["sp500"].iloc[-1])
    n_anos = len(df) / 12.0
    rm_geo = (p_final / p_inicial) ** (1.0 / n_anos) - 1.0
    rf_eua = float(df["rf_tbill_dec"].dropna().mean())
    return rm_geo - rf_eua
