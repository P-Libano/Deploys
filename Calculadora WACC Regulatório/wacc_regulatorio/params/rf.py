"""
Taxa Livre de Risco — NTN-B yield real.

Metodologia ANEEL (Despacho 675/2026):
    1. Cada vencimento em cada dia = mean(taxa_compra_manha, taxa_venda_manha)
    2. Cada dia = média dos vencimentos abertos
    3. Valor anual X = média das médias diárias dos últimos 10 anos [X-9, X]
    4. Rf publicado = média dos 5 valores anuais [P-5, P-1] (P = ano publicação)
    Resultado esperado 2026 (dados até 2025): Rf = 5,1377%
"""
import numpy as np
import pandas as pd


def _taxa_media(df: pd.DataFrame) -> pd.Series:
    """Retorna média de compra/venda (usa venda se disponível, senão só compra)."""
    if "taxa_venda_manha" in df.columns:
        venda = pd.to_numeric(df["taxa_venda_manha"], errors="coerce")
        compra = pd.to_numeric(df["taxa_compra_manha"], errors="coerce")
        # Média das duas quando ambas disponíveis; fallback para compra
        return compra.where(venda.isna(), (compra + venda) / 2)
    return pd.to_numeric(df["taxa_compra_manha"], errors="coerce")


def calcular_rf_anual_10a(ano: int, ntnb_df: pd.DataFrame) -> float:
    """
    Valor anual do Rf para o ano X = média diária de 10 anos [X-9, X].
    Cada dia = mean(taxa_compra, taxa_venda) across vencimentos abertos.

    Args:
        ano: Ano de referência do valor anual (e.g. 2025)
        ntnb_df: DataFrame de load_ntnb()

    Returns:
        Rf anual como decimal
    """
    inicio = pd.Timestamp(f"{ano - 9}-01-01")
    fim = pd.Timestamp(f"{ano}-12-31")

    df = ntnb_df.copy()
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df["vencimento"] = pd.to_datetime(df["vencimento"], errors="coerce")
    df = df[(df["data"] >= inicio) & (df["data"] <= fim)]
    df = df[df["vencimento"] > df["data"]]  # só vencimentos ainda ativos
    df["taxa_compra_manha"] = pd.to_numeric(df["taxa_compra_manha"], errors="coerce")
    # ANEEL inclui taxas negativas (NTN-B próxima ao vencimento pode ter yield real negativo).
    # Filtra só valores claramente errados (>25% ou NaN).
    df = df[df["taxa_compra_manha"].notna() & (df["taxa_compra_manha"] <= 0.25)]

    if df.empty:
        raise ValueError(f"Sem dados NTN-B para janela [{ano-9}, {ano}]")

    df["taxa_media"] = _taxa_media(df)
    daily = df.groupby("data")["taxa_media"].mean()

    if daily.empty:
        raise ValueError(f"Sem médias diárias para janela [{ano-9}, {ano}]")

    return float(daily.mean())


def calcular_rf_media_5a(
    ano_publicacao: int,
    ntnb_df: pd.DataFrame,
) -> tuple[float, list[tuple[int, float]]]:
    """
    Rf ANEEL = média dos 5 valores anuais [P-5, P-1] onde P = ano de publicação.
    Cada valor anual = média diária dos últimos 10 anos (calcular_rf_anual_10a).

    Args:
        ano_publicacao: Ano de publicação do WACC (e.g. 2026)
        ntnb_df: DataFrame de load_ntnb()

    Returns:
        (rf_final, [(ano, rf_anual), ...])
    """
    valores: list[tuple[int, float]] = []
    for ano in range(ano_publicacao - 5, ano_publicacao):
        try:
            rf_ano = calcular_rf_anual_10a(ano, ntnb_df)
            valores.append((ano, rf_ano))
        except ValueError:
            pass

    if not valores:
        raise ValueError(f"Sem dados suficientes para Rf 5a (publicação {ano_publicacao})")

    rf_final = float(np.mean([v for _, v in valores]))
    return rf_final, valores


def calcular_rf_historico(ano: int, ntnb_df: pd.DataFrame) -> float:
    """
    [LEGADO] Rf para um único ano (sem janela de 10 anos).
    Mantido para compatibilidade com calcular_rf_spot_serie e C3.
    Para C2, use calcular_rf_media_5a.

    Args:
        ano: Ano base dos dados (e.g. 2025 para WACC 2026)
        ntnb_df: DataFrame de load_ntnb()
    """
    df = ntnb_df.copy()
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df["vencimento"] = pd.to_datetime(df["vencimento"], errors="coerce")
    df_ano = df[df["data"].dt.year == ano].copy()

    if df_ano.empty:
        raise ValueError(f"Sem dados NTN-B para o ano {ano}")

    ano_inicio = pd.Timestamp(f"{ano}-01-01")
    df_ano = df_ano[df_ano["vencimento"] > ano_inicio]
    df_ano["taxa_compra_manha"] = pd.to_numeric(df_ano["taxa_compra_manha"], errors="coerce")
    df_ano = df_ano[
        (df_ano["taxa_compra_manha"] >= 0.01) &
        (df_ano["taxa_compra_manha"] <= 0.25)
    ]

    if df_ano.empty:
        raise ValueError(f"Sem taxas NTN-B válidas para o ano {ano}")

    df_ano["taxa_media"] = _taxa_media(df_ano)
    medias_por_venc = df_ano.groupby("vencimento")["taxa_media"].mean()
    return float(medias_por_venc.mean())


def build_ettj_from_ntnb_fixture(
    ntnb_df: pd.DataFrame,
    ano_ref: int,
    ano_base: int,
) -> pd.DataFrame:
    """
    Constrói curva de yields por prazo a partir dos fixtures NTN-B.

    Usa os yields médios do ano_ref para cada vencimento como proxy da
    estrutura a termo quando a API ANBIMA está indisponível.

    Returns:
        DataFrame com colunas 'prazo_anos' e 'yield_real'
    """
    df = ntnb_df.copy()
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df["vencimento"] = pd.to_datetime(df["vencimento"], errors="coerce")
    df = df[df["data"].dt.year == ano_ref].copy()
    df = df[(df["taxa_compra_manha"] >= 0.01) & (df["taxa_compra_manha"] <= 0.25)]
    df = df[df["vencimento"] > pd.Timestamp(f"{ano_ref}-12-31")]

    if df.empty:
        return pd.DataFrame(columns=["prazo_anos", "yield_real"])

    # Prazo em anos: vencimento.year - ano_base, mínimo 1
    df["prazo_anos"] = (df["vencimento"].dt.year - ano_base + 1).clip(lower=1).astype(float)
    curve = (
        df.groupby("prazo_anos")["taxa_compra_manha"]
        .mean()
        .reset_index()
        .rename(columns={"taxa_compra_manha": "yield_real"})
        .sort_values("prazo_anos")
        .reset_index(drop=True)
    )
    return curve


def calcular_rf_spot_serie(
    ntnb_df: pd.DataFrame,
    ano_inicio: int = 2013,
    ano_fim: int = 2025,
) -> dict:
    """
    Retorna dict {ano: rf_spot} com a taxa anual média NTN-B para cada ano.

    rf_spot[ano] = média dos vencimentos ativos no ano (mesma metodologia
    de calcular_rf_historico, mas para todos os anos disponíveis).
    """
    resultado = {}
    for ano in range(ano_inicio, ano_fim + 1):
        try:
            resultado[ano] = calcular_rf_historico(ano, ntnb_df)
        except Exception:
            pass
    return resultado


def calcular_rf_rolling_projetado(
    ano_publicacao: int,
    rf_spot_historico: dict,
    rf_spot_projetado: float,
    janela: int = 10,
) -> tuple[float, str]:
    """
    Rf da janela rolante para um ano futuro de publicação ANEEL.

    ANEEL publica o WACC do ano P usando dados do ano P-1 como mais recente.
    A janela de 10 anos para o WACC P é: [P-10, P-9, ..., P-1].

    Para anos históricos disponíveis usa rf_spot_historico.
    Para anos além do último dado histórico, usa rf_spot_projetado
    (taxa anual projetada constante = nível atual de mercado).

    Fonte:
        'ettj'         — janela com até 3 anos projetados (confiável)
        'ettj_extrapol'— 4 a 7 anos projetados
        'extrapol_longo'— 8+ anos projetados (horizonte além de 10 anos)

    Returns:
        (rf_rolling, fonte)
    """
    ano_dados_final = ano_publicacao - 1
    anos_janela = list(range(ano_dados_final - janela + 1, ano_dados_final + 1))

    rf_values = []
    n_projetados = 0
    for ano in anos_janela:
        if ano in rf_spot_historico:
            rf_values.append(rf_spot_historico[ano])
        else:
            rf_values.append(rf_spot_projetado)
            n_projetados += 1

    if not rf_values:
        return rf_spot_projetado, "extrapol_longo"

    rf_rolling = sum(rf_values) / len(rf_values)

    if n_projetados <= janela // 3:
        fonte = "ettj"
    elif n_projetados <= (janela * 2) // 3:
        fonte = "ettj_extrapol"
    else:
        fonte = "extrapol_longo"

    return rf_rolling, fonte


def calcular_rf_forward(
    ano_base: int,
    horizonte_t: int,
    ettj_df: pd.DataFrame,
) -> tuple[float, str]:
    """
    Interpola yield real NTN-B da curva ETTJ para o prazo t anos a partir do ano_base.

    NOTA: O uso de NTN-B com vencimentos futuros como Rf é uma heurística do custo
    de capital CORRENTE, não uma projeção do Rf futuro. O mercado precifica hoje o
    yield de vencimentos longos (ex.: NTN-B 2050), mas esses yields podem divergir
    substancialmente do Rf realizado no futuro conforme as condições macroeconômicas
    evoluam. Para fins de projeção em C3, o vetor de Rf representa o custo de capital
    implícito de mercado em cada ano t, não uma estimativa do Rf ex-post.

    Args:
        ano_base: Ano de início da projeção
        horizonte_t: Anos à frente (1-30)
        ettj_df: DataFrame com colunas 'prazo_anos' e 'yield_real' — de fetch_ettj_anbima()

    Returns:
        (rf_t, fonte) onde fonte é 'ettj' | 'ettj_extrapol' | 'extrapol_longo'
    """
    if ettj_df is None or ettj_df.empty:
        raise ValueError("Curva ETTJ vazia — execute fetch_ettj_anbima()")

    prazos = ettj_df["prazo_anos"].values
    yields = ettj_df["yield_real"].values
    ano_alvo = ano_base + horizonte_t

    # Limite aproximado de liquidez da curva ANBIMA
    ULTIMO_ANO_LIQUIDO = ano_base + float(prazos.max())
    ANO_EXTRAPOL_LONGO = 2060

    if ano_alvo <= ULTIMO_ANO_LIQUIDO:
        rf_t = float(np.interp(horizonte_t, prazos, yields))
        fonte = "ettj"
    elif ano_alvo <= ANO_EXTRAPOL_LONGO:
        rf_t = float(yields[-1])
        fonte = "ettj_extrapol"
    else:
        rf_t = float(yields[-1])
        fonte = "extrapol_longo"

    return rf_t, fonte
