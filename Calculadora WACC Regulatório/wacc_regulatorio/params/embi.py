"""
Prêmio de Risco Brasil — EMBI+ (JPMorgan).

Metodologia ANEEL:
    Média aritmética dos spreads diários nos últimos 10 anos
    Resultado esperado WACC 2026 (janela 2016-2025): EMBI = 2,765%
"""
import pandas as pd
from datetime import date


def calcular_embi_historico(
    ano: int,
    embi_df: pd.DataFrame = None,
    embi_medias_df: pd.DataFrame = None,
    janela_anos: int = 10,
) -> float:
    """
    Calcula a média EMBI+ dos últimos `janela_anos` anos terminando em `ano`.

    Prefere os valores pré-calculados pelo ANEEL (embi_medias_df) quando disponíveis,
    pois estes são os valores oficiais usados no Despacho. Se não disponível, calcula
    a partir da série diária.

    Args:
        ano: Ano de referência (e.g. 2025 para WACC 2026)
        embi_df: DataFrame de load_embi_diario() — colunas: data, embi_decimal
        embi_medias_df: DataFrame de load_embi_medias() — ano_wacc, embi_media_10a
        janela_anos: Tamanho da janela em anos

    Returns:
        EMBI como decimal (ex: 0.02765 para 2,765%)
    """
    # Tenta usar valor pré-calculado do ANEEL para o ano de publicação (ano + 1)
    ano_wacc = ano + 1
    if embi_medias_df is not None and not embi_medias_df.empty:
        row = embi_medias_df[embi_medias_df["ano_wacc"] == ano_wacc]
        if not row.empty:
            return float(row["embi_media_10a"].iloc[0])

    # Fallback: calcula da série diária
    if embi_df is None or embi_df.empty:
        raise ValueError("Sem dados EMBI — forneça embi_df ou embi_medias_df")

    start = pd.Timestamp(f"{ano - janela_anos + 1}-01-01")
    end = pd.Timestamp(f"{ano}-12-31")
    serie = embi_df[(embi_df["data"] >= start) & (embi_df["data"] <= end)]

    if serie.empty:
        raise ValueError(f"Sem dados EMBI na janela {ano - janela_anos + 1}–{ano}")

    return float(serie["embi_decimal"].mean())


def calcular_embi_projetado(
    ano_base: int,
    t: int,
    embi_base: float,
    embi_delta: dict | None = None,
) -> float:
    """
    Retorna o EMBI para o ano (ano_base + t) aplicando delta de cenário opcional.

    Args:
        ano_base: Ano de partida da projeção
        t: Horizonte em anos
        embi_base: EMBI base (último valor calculado)
        embi_delta: Dicionário {ano: delta_decimal} para sensibilização.
                    Ex: {2027: +0.015, 2028: +0.008}

    Returns:
        EMBI projetado como decimal
    """
    ano = ano_base + t
    delta = (embi_delta or {}).get(ano, 0.0)
    return embi_base + delta
