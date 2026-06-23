"""
Beta desalavancado e estrutura de capital das utilities americanas.

Metodologia ANEEL (Despacho 675/2026, confirmada pela fórmula do xlsx):
    1. OLS semanal por empresa vs S&P500 Total Return, janela 5 anos (Oct-Sep)
    2. Desalavancagem Hamada por empresa: beta_u = beta_l / (1 + (1-T_us) * D/E_us)
       onde D/E_us = dívida contábil / market cap da empresa americana naquele ano
    3. Ponderação pela market cap (cap de 50% por empresa) → beta_u_janela
    4. Re-alavancagem com estrutura de capital BRASILEIRA do ano:
       beta_l_br = beta_u_janela × (1 + (1-T_br) × D/E_br_do_ano)
    5. Repetir para 13 janelas (2013–2025)
    6. beta_l final = MÉDIA das 5 janelas mais recentes de beta_l_br
       (fórmula ANEEL: =AVERAGE('WACC Histórico'!K6:O6) = anos 2021–2025)

    Para 2026: mean(beta_l_br de 2021..2025) = 0.769239 ≈ 0.769238 publicado (delta 0.01bp)

Nota sobre a fórmula do Ke:
    O beta_l retornado já está na base brasileira (re-alavancado por janela).
    O Ke é calculado como:
        ke_di = rf + beta_l × PRM
    O EMBI (risco-país) está implicitamente capturado via D/E americano maior
    (~2,35× vs ~0,66× brasileiro) na etapa de desalavancagem e re-alavancagem.
    Adicionar EMBI explicitamente no Ke seria double-counting.

    Resultado esperado WACC 2026 (Transmissão):
        beta_l = 0.769238  (média móvel 5a de beta_l re-alavancado com D/V brasileira)
        E/V    = 60,23%  (ano 2025 — mais recente)
        D/V    = 39,77%
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, List
import numpy as np
import pandas as pd
from scipy.stats import linregress

from wacc_regulatorio.config import T_IRPJ_CSLL, JANELA_ANOS, JANELA_BETA_ANOS


@dataclass
class BetaResult:
    beta_l: float         # Beta alavancado (US leverage, usado no Ke)
    beta_u: float         # Beta desalavancado (US sample)
    ev: float             # E/V estrutura de capital regulatória
    dv: float             # D/V estrutura de capital regulatória
    beta_u_por_ano: dict = field(default_factory=dict)   # diagnóstico


def _hamada_unlever(beta_l: float, de_ratio: float, T: float = T_IRPJ_CSLL) -> float:
    """beta_u = beta_l / (1 + (1-T)*D/E)"""
    return beta_l / (1.0 + (1.0 - T) * de_ratio)


def _hamada_relever(beta_u: float, de_ratio: float, T: float = T_IRPJ_CSLL) -> float:
    """beta_l = beta_u * (1 + (1-T)*D/E)"""
    return beta_u * (1.0 + (1.0 - T) * de_ratio)


def calcular_beta_from_fixture(
    ano: int,
    wacc_aplicacao_df: pd.DataFrame,
) -> BetaResult:
    """
    Retorna os valores pré-calculados de beta da planilha ANEEL para Camada 1.
    O beta_l = 0.769238 para 2026 é o valor oficial do Despacho 675/2026.

    Args:
        ano: Ano de publicação do WACC (e.g. 2026)
        wacc_aplicacao_df: DataFrame de load_wacc_aplicacao()
    """
    row = wacc_aplicacao_df[
        (wacc_aplicacao_df["ano"] == ano) &
        (wacc_aplicacao_df["segmento"] == "transmissao")
    ]
    if row.empty:
        raise ValueError(f"Sem dados para ano={ano}, segmento=transmissao em wacc_aplicacao")

    r = row.iloc[0]
    beta_l = float(r["beta_l"])
    ev = float(r["ev"])
    dv = float(r["dv"])

    # Beta_u publicado ANEEL (D/E americano) — lido de beta_historico.csv
    # Para ano de publicação P, o fixture tem dados até P-1; tenta P, depois P-1.
    from wacc_regulatorio.data.fixtures import load_beta_historico
    beta_hist = load_beta_historico()
    hist_row = beta_hist[beta_hist["ano"] == ano]
    if hist_row.empty:
        hist_row = beta_hist[beta_hist["ano"] == ano - 1]
    if not hist_row.empty and "beta_u_eua" in hist_row.columns:
        beta_u = float(hist_row.iloc[0]["beta_u_eua"])
    else:
        # Último recurso: desalavanca com D/E brasileiro — diverge ~2300bp da referência ANEEL
        beta_u = _hamada_unlever(beta_l, dv / ev)

    return BetaResult(
        beta_l=beta_l,
        beta_u=beta_u,
        ev=ev,
        dv=dv,
    )


def calcular_beta_from_historico(
    beta_historico_df: pd.DataFrame,
    wacc_historico_df: Optional[pd.DataFrame] = None,
    T: float = T_IRPJ_CSLL,
    n_anos_media: int = 5,
) -> BetaResult:
    """
    Calcula beta_l como média móvel dos n_anos_media mais recentes de beta_l_brasil.

    Metodologia ANEEL confirmada pela fórmula do xlsx:
    - Cada janela anual tem beta_l_br = beta_u_us × (1 + (1-T_br) × D/E_br_do_ano)
    - beta_l final = AVERAGE das n_anos_media janelas mais recentes (default: 5)
    - Para 2026: =AVERAGE('WACC Histórico'!K6:O6) = anos 2021–2025 = 0.769239

    Args:
        beta_historico_df: DataFrame com colunas ano, beta_u_eua, ev_brasil, dv_brasil, beta_l_brasil
        wacc_historico_df: ignorado (mantido por compatibilidade)
        T: alíquota (não usada — beta_l_brasil já está no fixture pré-calculado)
        n_anos_media: número de anos mais recentes a médiar (padrão ANEEL = 5)
    """
    df = beta_historico_df.sort_values("ano")

    ultimas = df.tail(n_anos_media)
    beta_l = float(ultimas["beta_l_brasil"].mean())

    mais_recente = df.iloc[-1]
    ev = float(mais_recente["ev_brasil"])
    dv = float(mais_recente["dv_brasil"])
    beta_u = float(ultimas["beta_u_eua"].mean())

    beta_u_por_ano = dict(zip(
        df["ano"].tolist(),
        df["beta_u_eua"].tolist()
    ))

    return BetaResult(
        beta_l=beta_l,
        beta_u=beta_u,
        ev=ev,
        dv=dv,
        beta_u_por_ano=beta_u_por_ano,
    )


def calcular_beta_from_prices(
    prices_df: pd.DataFrame,
    debt_df: Optional[pd.DataFrame],
    ano: int,
    janela_anos: int = JANELA_ANOS,
    T: float = T_IRPJ_CSLL,
) -> BetaResult:
    """
    Calcula beta a partir de preços de mercado (Camada 2 — dados ao vivo).

    Args:
        prices_df: Total Return Index semanal por ticker + SPXTIndex — de fetch_beta_prices()
        debt_df: Dívida contábil por ticker por trimestre — de yfinance ou fixture
        ano: Ano final da janela
        janela_anos: Tamanho da janela
        T: Alíquota de impostos
    """
    start = pd.Timestamp(f"{ano - janela_anos + 1}-01-01")
    end = pd.Timestamp(f"{ano}-12-31")

    df = prices_df[(prices_df.index >= start) & (prices_df.index <= end)].copy()
    if len(df) < 50:
        raise ValueError(f"Dados insuficientes: {len(df)} semanas (mínimo 50)")

    # Retorno simples P_n/P_{n-1} — replicando fórmula ANEEL COVARIANCE.S/VAR.S
    rets = (df / df.shift(1)).dropna()
    sp500_col = [c for c in rets.columns if "SPXT" in c.upper() or "^GSPC" in c.upper()]
    if not sp500_col:
        raise ValueError("Coluna S&P500 não encontrada")

    sp500 = rets[sp500_col[0]]
    tickers = [c for c in rets.columns if c not in sp500_col]

    betas_l = {}
    for t in tickers:
        if rets[t].dropna().empty:
            continue
        y = rets[t].dropna()
        x = sp500.loc[y.index]
        if len(x) < 50:
            continue
        slope, _, _, _, _ = linregress(x, y)
        betas_l[t] = slope

    if not betas_l:
        raise ValueError("Sem betas calculados — verifique os dados de preço")

    # Desalavancagem (usando D/E de mercado se disponível, senão usa beta_l diretamente)
    betas_u = {}
    ev_vals = []
    dv_vals = []

    for t, bl in betas_l.items():
        if debt_df is not None and t in debt_df.columns:
            debt_val = float(debt_df[t].dropna().iloc[-1])
            mktcap = float(prices_df[t].dropna().iloc[-1]) * 1e6  # ajustar escala
            de = debt_val / mktcap if mktcap > 0 else 0.0
        else:
            de = 0.6605  # default = estrutura brasileira
        bu = _hamada_unlever(bl, de, T)
        betas_u[t] = bu
        ev_vals.append(1 / (1 + de))
        dv_vals.append(de / (1 + de))

    # Média simples (sem ponderação por market cap sem dados confiáveis)
    beta_u_mean = float(np.mean(list(betas_u.values())))
    ev = float(np.mean(ev_vals))
    dv = 1.0 - ev

    beta_l = _hamada_relever(beta_u_mean, dv / ev, T)

    return BetaResult(
        beta_l=beta_l,
        beta_u=beta_u_mean,
        ev=ev,
        dv=dv,
        beta_u_por_ano={ano: beta_u_mean},
    )


def calcular_beta_janelas_anuais(
    prices_df: pd.DataFrame,
    market_caps_df: pd.DataFrame,
    beta_hist_df: pd.DataFrame,
    spxt_col: str = "^SP500TR",
    anos: Optional[List[int]] = None,
    T: float = T_IRPJ_CSLL,
    cap_peso: float = 0.50,
) -> BetaResult:
    """
    Replica a metodologia ANEEL: 5 OLS anuais Oct-Sep separados, média de beta_l_brasil.

    A ANEEL calcula =AVERAGE('WACC Histórico'!K6:O6) — média de 5 janelas anuais onde
    cada coluna é o resultado de uma OLS separada na janela Oct(ano-1)–Sep(ano).
    O código atual (calcular_beta_mktcap_window) faz UMA OLS concatenada de 5 anos,
    o que distorce o resultado ao misturar regimes de mercado distintos.

    Para cada ano em `anos`:
      1. Corta prices_df em [Oct(ano-1), Sep(ano)] (~52 semanas)
      2. OLS semanal por empresa vs benchmark → slope por ticker
      3. Hamada unlever com D/E_mktcap (de market_caps_df) → beta_u por empresa
      4. Pondera por D/V contábil com cap 50% (mesma metodologia ANEEL)
      5. Re-alavanca com D/V Brasil do ano (de beta_hist_df, fixture do xlsx)
    Resultado: beta_l = mean(beta_l_brasil das 5 janelas).

    Args:
        prices_df: preços semanais Total Return — fetch_beta_prices()
        market_caps_df: D/E e D/V book por ticker — fetch_market_caps()
        beta_hist_df: fixture beta histórico — load_beta_historico(); fornece D/V Brasil por ano
        spxt_col: coluna do benchmark S&P500TR
        anos: anos das janelas Oct-Sep; None = últimos 5 anos completos
        T: alíquota fiscal brasileira
        cap_peso: peso máximo por empresa (50% ANEEL)
    """
    hoje = pd.Timestamp.now()
    ano_ref = hoje.year if hoje.month >= 10 else hoje.year - 1
    if anos is None:
        anos = list(range(ano_ref - 4, ano_ref + 1))

    hist_dv: Dict[int, float] = {}
    if beta_hist_df is not None and not beta_hist_df.empty:
        for _, row in beta_hist_df.iterrows():
            hist_dv[int(row["ano"])] = float(row["dv_brasil"])

    de_map: Dict[str, float] = {}
    dv_book_map: Dict[str, float] = {}
    for _, row in market_caps_df.iterrows():
        t = str(row["ticker"])
        de_map[t] = float(row["de_ratio"])
        dv_book_map[t] = float(row.get("dv_book", 0.0))

    beta_l_por_janela: List[float] = []
    beta_u_por_ano_out: Dict[int, float] = {}

    for ano in anos:
        start = pd.Timestamp(f"{ano - 1}-10-01")
        end   = pd.Timestamp(f"{ano}-09-30")
        df_jan = prices_df.loc[start:end].copy()

        if len(df_jan) < 30 or spxt_col not in df_jan.columns:
            continue

        rets = (df_jan / df_jan.shift(1)).dropna(how="all")
        tickers_jan = [c for c in rets.columns if c != spxt_col]

        betas_u: Dict[str, float] = {}
        for t in tickers_jan:
            col = rets[[spxt_col, t]].dropna()
            if len(col) < 30:
                continue
            slope, *_ = linregress(col[spxt_col].values, col[t].values)
            de = de_map.get(t, 0.6605)
            betas_u[t] = _hamada_unlever(slope, de, T)

        if not betas_u:
            continue

        total_dv = sum(dv_book_map.get(t, 0) for t in betas_u)
        if total_dv <= 0:
            pesos = {t: 1 / len(betas_u) for t in betas_u}
        else:
            raw = {t: dv_book_map.get(t, 0) / total_dv for t in betas_u}
            excesso = sum(max(0, w - cap_peso) for w in raw.values())
            n_abaixo = sum(1 for w in raw.values() if w < cap_peso)
            pesos = {}
            for t, w in raw.items():
                if w >= cap_peso:
                    pesos[t] = cap_peso
                else:
                    pesos[t] = w + (excesso / n_abaixo if n_abaixo > 0 else 0)
            soma = sum(pesos.values())
            pesos = {t: w / soma for t, w in pesos.items()}

        beta_u_janela = sum(pesos.get(t, 0) * bu for t, bu in betas_u.items())
        beta_u_por_ano_out[ano] = beta_u_janela

        dv_br = hist_dv.get(ano, 0.397739)
        ev_br = 1.0 - dv_br
        beta_l_br = beta_u_janela * (1.0 + (1.0 - T) * (dv_br / ev_br))
        beta_l_por_janela.append(beta_l_br)

    if not beta_l_por_janela:
        raise ValueError("calcular_beta_janelas_anuais: sem janelas calculadas — dados insuficientes")

    beta_l = float(np.mean(beta_l_por_janela))
    beta_u_medio = float(np.mean(list(beta_u_por_ano_out.values()))) if beta_u_por_ano_out else 0.0

    dv_br_ref = hist_dv.get(max(hist_dv.keys()), 0.397739) if hist_dv else 0.397739
    ev_br_ref = 1.0 - dv_br_ref

    return BetaResult(
        beta_l=beta_l,
        beta_u=beta_u_medio,
        ev=ev_br_ref,
        dv=dv_br_ref,
        beta_u_por_ano=beta_u_por_ano_out,
    )


def calcular_beta_mktcap_window(
    prices_df: pd.DataFrame,
    market_caps_df: pd.DataFrame,
    spxt_col: str = "^GSPC",
    janela_anos: int = JANELA_BETA_ANOS,
    T: float = T_IRPJ_CSLL,
    cap_peso: float = 0.50,
) -> BetaResult:
    """
    Calcula beta para a janela 5 anos Oct-Sep mais recente, ponderado por D/V contábil.

    Metodologia ANEEL confirmada (Despacho 675/2026, aba Beta xlsx):
    - OLS semanal por empresa vs S&P500TR, retorno simples P_n/P_{n-1}
    - Hamada unlever: beta_u = beta_l / (1 + (1-T) * D/E_mktcap) por empresa
    - Peso = D/V_book_i / Σ(D/V_book_j), onde D/V_book = debt/(debt+book_equity)
    - Cap de 50% por empresa (o cap raramente ativa com 16+ empresas)

    Args:
        prices_df: DataFrame com preços semanais (yfinance) — colunas = tickers + spxt_col
        market_caps_df: DataFrame de fetch_market_caps() — ticker, market_cap_usd, de_ratio, dv_book
        spxt_col: coluna do benchmark S&P500
        janela_anos: tamanho da janela em anos (default: 5)
        T: alíquota fiscal
        cap_peso: peso máximo por empresa (default: 50%)
    """
    hoje = pd.Timestamp.now()
    # Janela Oct-Sep mais recente completa
    ano_fim = hoje.year if hoje.month >= 10 else hoje.year - 1
    start = pd.Timestamp(f"{ano_fim - janela_anos}-10-01")
    end = pd.Timestamp(f"{ano_fim}-09-30")

    df = prices_df[(prices_df.index >= start) & (prices_df.index <= end)].copy()
    if len(df) < 50:
        df = prices_df.copy()

    if spxt_col not in df.columns:
        raise ValueError(f"Coluna benchmark '{spxt_col}' não encontrada")

    # Retorno simples P_n/P_{n-1} — replicando COVARIANCE.S/VAR.S do xlsx ANEEL
    rets = (df / df.shift(1)).dropna(how="all")
    tickers = [c for c in rets.columns if c != spxt_col]

    de_map: Dict[str, float] = {}
    dv_book_map: Dict[str, float] = {}
    for _, row in market_caps_df.iterrows():
        t = str(row["ticker"])
        de_map[t] = float(row["de_ratio"])
        dv_book_map[t] = float(row.get("dv_book", 0.0))

    betas_u: Dict[str, float] = {}
    for t in tickers:
        col = rets[[spxt_col, t]].dropna()
        if len(col) < 50:
            continue
        slope, *_ = linregress(col[spxt_col].values, col[t].values)
        # Hamada unlever usa D/E_mktcap (debt/mktcap) por empresa
        de = de_map.get(t, 0.6605)
        betas_u[t] = _hamada_unlever(slope, de, T)

    if not betas_u:
        raise ValueError("Sem betas calculados")

    # Pesos por D/V contábil (D/(D+book_equity)) com cap de 50%
    # Metodologia ANEEL: peso_i = dv_book_i / Σ(dv_book_j)
    total_dv = sum(dv_book_map.get(t, 0) for t in betas_u)
    if total_dv <= 0:
        # Fallback: pesos iguais se dv_book não disponível
        pesos = {t: 1 / len(betas_u) for t in betas_u}
    else:
        raw = {t: dv_book_map.get(t, 0) / total_dv for t in betas_u}
        excesso = sum(max(0, w - cap_peso) for w in raw.values())
        n_abaixo = sum(1 for w in raw.values() if w < cap_peso)
        pesos = {}
        for t, w in raw.items():
            if w >= cap_peso:
                pesos[t] = cap_peso
            else:
                pesos[t] = w + (excesso / n_abaixo if n_abaixo > 0 else 0)
        soma = sum(pesos.values())
        pesos = {t: w / soma for t, w in pesos.items()}

    beta_u_mean = sum(pesos.get(t, 0) * bu for t, bu in betas_u.items())

    # Estrutura de capital americana ponderada (D/E mktcap) — diagnóstico
    # C2 re-alavanca com D/V brasileiro separadamente; este beta_l não entra no WACC
    de_w_us = sum(pesos.get(t, 0) * de_map.get(t, 0.6605) for t in betas_u)
    ev = 1 / (1 + de_w_us)
    dv = de_w_us / (1 + de_w_us)
    beta_l = _hamada_relever(beta_u_mean, de_w_us, T)

    return BetaResult(
        beta_l=beta_l,
        beta_u=beta_u_mean,
        ev=ev,
        dv=dv,
        beta_u_por_ano={ano_fim: beta_u_mean},
    )
