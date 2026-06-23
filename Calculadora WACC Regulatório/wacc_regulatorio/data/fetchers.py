"""
Busca ao vivo de dados de mercado com cache local (Camada 2).

Fontes:
    - yfinance: preços de utilities americanas e S&P500
    - IPEADATA: série EMBI+ (JPM366_EMBI366)
    - Tesouro Nacional: taxas NTN-B correntes
    - ANBIMA: curva ETTJ (yields reais NTN-B por prazo)
"""
import json
import pickle
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

from wacc_regulatorio.config import (
    CACHE_DIR,
    CACHE_TTL_PRECO_DIAS,
    CACHE_TTL_ETTJ_DIAS,
    IPEADATA_EMBI_CODE,
    TICKERS_UTILITIES_ANEEL,
    TICKER_SP500,
    URL_IPEADATA_EMBI,
)

warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.pkl"


def _cache_get(key: str, ttl_dias: int) -> Optional[object]:
    p = _cache_path(key)
    if not p.exists():
        return None
    age = (datetime.now() - datetime.fromtimestamp(p.stat().st_mtime)).total_seconds()
    if age > ttl_dias * 86400:
        return None
    with open(p, "rb") as f:
        return pickle.load(f)


def _cache_set(key: str, data: object) -> None:
    with open(_cache_path(key), "wb") as f:
        pickle.dump(data, f)


# ---------------------------------------------------------------------------
# NTN-B ao vivo — API Tesouro Nacional
# ---------------------------------------------------------------------------

def fetch_ntnb_tesouro() -> pd.DataFrame:
    """
    Busca as taxas NTN-B atuais do Tesouro Nacional (taxa compra manhã).

    Returns:
        DataFrame com colunas: data, vencimento, taxa_compra_manha
    """
    key = "ntnb_tesouro"
    cached = _cache_get(key, CACHE_TTL_PRECO_DIAS)
    if cached is not None:
        return cached

    url = (
        "https://www.tesourotransparente.gov.br/ckan/dataset/"
        "df56aa42-484a-4a59-8184-7676580c81e3/resource/"
        "796d2059-14e9-44e3-80a7-2dff3d1f1658/download/"
        "PrecoTaxaTesouroDireto.csv"
    )
    try:
        df = pd.read_csv(url, sep=";", decimal=",", encoding="latin-1")
        df.columns = [c.strip() for c in df.columns]
        # Filtrar NTN-B
        ntnb = df[df["Tipo Titulo"].str.contains("NTN-B", na=False)].copy()
        ntnb["data"] = pd.to_datetime(ntnb["Data Base"], dayfirst=True)
        ntnb["vencimento"] = pd.to_datetime(ntnb["Data Vencimento"], dayfirst=True)
        ntnb["taxa_compra_manha"] = pd.to_numeric(
            ntnb["Taxa Compra Manha"].astype(str).str.replace(",", "."), errors="coerce"
        ) / 100.0
        result = ntnb[["data", "vencimento", "taxa_compra_manha"]].dropna()
        _cache_set(key, result)
        return result
    except Exception as e:
        warnings.warn(f"Falha ao buscar NTN-B do Tesouro: {e}")
        return pd.DataFrame(columns=["data", "vencimento", "taxa_compra_manha"])


# ---------------------------------------------------------------------------
# EMBI+ ao vivo — IPEADATA
# ---------------------------------------------------------------------------

def fetch_embi_ipeadata() -> pd.DataFrame:
    """
    Busca a série diária EMBI+ do IPEADATA.

    Returns:
        DataFrame com colunas: data, embi_decimal
    """
    key = "embi_ipeadata"
    cached = _cache_get(key, CACHE_TTL_PRECO_DIAS)
    if cached is not None:
        return cached

    url = URL_IPEADATA_EMBI
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        valores = data.get("value", [])
        records = []
        for v in valores:
            try:
                data_str = v.get("VALDATA") or v.get("valdata", "")
                val = v.get("VALVALOR") or v.get("valvalor")
                if data_str and val is not None:
                    dt = pd.to_datetime(data_str[:10])
                    # API retorna valores em bps (ex: 228 para 2,28%) → dividir por 10000
                    records.append({"data": dt, "embi_decimal": float(val) / 10000.0})
            except Exception:
                continue
        df = pd.DataFrame(records).sort_values("data").reset_index(drop=True)
        _cache_set(key, df)
        return df
    except Exception as e:
        warnings.warn(f"Falha ao buscar EMBI do IPEADATA: {e}")
        return pd.DataFrame(columns=["data", "embi_decimal"])


# ---------------------------------------------------------------------------
# Preços de utilities e S&P500 — yfinance
# ---------------------------------------------------------------------------

def fetch_beta_prices(
    tickers: list[str] = None,
    start: str = "2013-01-01",
    end: str = None,
) -> pd.DataFrame:
    """
    Busca Total Return Index semanal para utilities americanas e S&P500.

    Returns:
        DataFrame com index DatetimeIndex (sextas-feiras) e colunas = tickers
    """
    try:
        import yfinance as yf
    except ImportError:
        raise ImportError("yfinance não instalado: pip install yfinance")

    if tickers is None:
        tickers = TICKERS_UTILITIES_ANEEL + [TICKER_SP500]
    if end is None:
        end = datetime.now().strftime("%Y-%m-%d")

    key = f"beta_prices_{start[:4]}_{end[:4]}"
    cached = _cache_get(key, CACHE_TTL_PRECO_DIAS)
    if cached is not None:
        return cached

    try:
        # Adjusted close prices (inclui dividendos)
        df = yf.download(
            tickers,
            start=start,
            end=end,
            interval="1wk",
            auto_adjust=True,
            progress=False,
        )
        if isinstance(df.columns, pd.MultiIndex):
            df = df["Close"]
        df = df.dropna(how="all")
        _cache_set(key, df)
        return df
    except Exception as e:
        warnings.warn(f"Falha ao buscar preços via yfinance: {e}")
        return pd.DataFrame()


def fetch_market_caps(
    tickers: list[str] = None,
) -> pd.DataFrame:
    """
    Busca market cap corrente e dívida total para ponderação do beta (Camada 2).

    Usa yfinance fast_info.market_cap e balance_sheet['Total Debt'].
    Cache de 1 dia.

    Returns:
        DataFrame com colunas: ticker, market_cap_usd, total_debt_usd, de_ratio
        Tickers sem market cap são omitidos.
    """
    try:
        import yfinance as yf
    except ImportError:
        raise ImportError("yfinance não instalado: pip install yfinance")

    if tickers is None:
        tickers = TICKERS_UTILITIES_ANEEL

    key = "market_caps"
    cached = _cache_get(key, CACHE_TTL_PRECO_DIAS)
    if cached is not None:
        return cached

    records = []
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            mktcap = tk.fast_info.market_cap
            if not mktcap or mktcap <= 0:
                continue
            bs = tk.balance_sheet
            debt = 0.0
            book_equity = 0.0
            if bs is not None and not bs.empty:
                debt_rows = [r for r in bs.index if "Total Debt" in str(r) or "Long Term Debt" in str(r)]
                debt = float(bs.loc[debt_rows[0]].iloc[0]) if debt_rows else 0.0
                eq_rows = [r for r in bs.index if "Stockholders" in str(r) or "Total Equity Gross" in str(r)]
                book_equity = float(bs.loc[eq_rows[0]].iloc[0]) if eq_rows else 0.0
            # de_ratio: debt/mktcap (usado no Hamada unlever por empresa)
            de = debt / mktcap if mktcap > 0 else 0.0
            # dv_book: D/(D+E_book) — usado no Ponderado 50% ANEEL como peso
            dv_book = debt / (debt + book_equity) if (debt + book_equity) > 0 else 0.0
            records.append({
                "ticker": t,
                "market_cap_usd": float(mktcap),
                "total_debt_usd": float(debt),
                "book_equity_usd": float(book_equity),
                "de_ratio": float(de),
                "dv_book": float(dv_book),
            })
        except Exception:
            continue

    df = pd.DataFrame(records) if records else pd.DataFrame(
        columns=["ticker", "market_cap_usd", "total_debt_usd", "de_ratio"]
    )
    _cache_set(key, df)
    return df


def fetch_prm_sp500tr_incremento(prm_df: pd.DataFrame) -> pd.DataFrame:
    """
    Estende a série prm_sp500 da fixture com o ano corrente via ^SP500TR (yfinance).

    Mantém a metodologia ANEEL intacta: mesma fórmula, mesma função calcular_prm —
    apenas amplia a janela móvel com mais um ponto de dados.

    Estratégia:
    - S&P500: ^SP500TR (Total Return, ±4bp vs fixture — validado)
    - rf_tbill: último valor anual conhecido da própria fixture (não puxamos rf de fonte externa
                pois a série Bloomberg/ECB SDW usada pela ANEEL não tem equivalente público
                com aderência suficiente; o valor congela no último despacho, que é o
                comportamento correto enquanto um novo despacho não é publicado)

    Args:
        prm_df: DataFrame de load_prm_sp500() — colunas: data, sp500, rf_tbill

    Returns:
        DataFrame com linhas mensais do ano corrente acrescentadas ao final.
        Se ^SP500TR falhar ou o ano corrente já estiver no df, retorna prm_df original.
    """
    try:
        import yfinance as yf
    except ImportError:
        return prm_df

    ano_corrente = datetime.now().year
    df_base = prm_df.copy()
    df_base["data"] = pd.to_datetime(df_base["data"])

    # Ano corrente já está na fixture (fixture extraída após publicação do despacho)
    if df_base["data"].dt.year.max() >= ano_corrente:
        return df_base

    key = f"sp500tr_incremento_{ano_corrente}"
    cached = _cache_get(key, CACHE_TTL_PRECO_DIAS)
    if cached is not None:
        return pd.concat([df_base, cached], ignore_index=True).sort_values("data")

    try:
        sp_tr = yf.download(
            "^SP500TR",
            start=f"{ano_corrente}-01-01",
            interval="1mo",
            auto_adjust=True,
            progress=False,
        )
        if sp_tr.empty:
            return df_base
        if isinstance(sp_tr.columns, pd.MultiIndex):
            sp_tr = sp_tr["Close"]
        sp_tr.columns = ["sp500_raw"]
        sp_tr = sp_tr.reset_index().rename(columns={"Date": "data", "index": "data"})
        sp_tr["data"] = pd.to_datetime(sp_tr["data"])

        # Rescala ^SP500TR para continuar a série da fixture (mesmo nível de índice)
        ultimo_sp500_fix = float(df_base["sp500"].iloc[-1])
        ultimo_sp500_tr_base = sp_tr["sp500_raw"].iloc[0]
        scale = ultimo_sp500_fix / ultimo_sp500_tr_base
        sp_tr["sp500"] = sp_tr["sp500_raw"] * scale

        # rf_tbill: replica o último valor anual da fixture (série Bloomberg/ECB sem equivalente público)
        rf_ultimo = float(
            df_base[df_base["data"].dt.year == df_base["data"].dt.year.max()]["rf_tbill"].mean()
        )
        sp_tr["rf_tbill"] = rf_ultimo

        incremento = sp_tr[["data", "sp500", "rf_tbill"]].dropna()
        _cache_set(key, incremento)

        return pd.concat([df_base, incremento], ignore_index=True).sort_values("data")

    except Exception as e:
        warnings.warn(f"fetch_prm_sp500tr_incremento falhou: {e} — usando fixture sem extensao")
        return df_base


# ---------------------------------------------------------------------------
# Curva ETTJ NTN-B — ANBIMA
# ---------------------------------------------------------------------------

def fetch_ettj_anbima() -> pd.DataFrame:
    """
    Busca a curva ETTJ de yields reais NTN-B da ANBIMA.

    Returns:
        DataFrame com colunas: prazo_anos, yield_real (decimal)
        Vértices em anos (ex: 1, 2, 3, 5, 7, 10, 20, 30, 40)
    """
    key = "ettj_anbima"
    cached = _cache_get(key, CACHE_TTL_ETTJ_DIAS)
    if cached is not None:
        return cached

    url = "https://www.anbima.com.br/informacoes/est-termo/CZ-down.asp"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        # ANBIMA returns CSV-like text
        from io import StringIO
        lines = [l for l in resp.text.split("\n") if l.strip()]
        # Try to parse; format varies
        df = pd.read_csv(StringIO(resp.text), sep=";", header=None, decimal=",")
        # Assume cols: prazo_du, taxa_spot, taxa_forward, ...
        df = df.dropna()
        if df.shape[1] >= 2:
            df = df.iloc[:, [0, 1]]
            df.columns = ["prazo_du", "yield_real_pct"]
            df["prazo_anos"] = df["prazo_du"].astype(float) / 252.0
            df["yield_real"] = df["yield_real_pct"].astype(float) / 100.0
            df = df[["prazo_anos", "yield_real"]].sort_values("prazo_anos")
            _cache_set(key, df)
            return df
    except Exception as e:
        warnings.warn(f"Falha ao buscar ETTJ da ANBIMA: {e}. Usando aproximação NTN-B.")

    # Fallback: curva estimada a partir das taxas NTN-B ao vivo
    return _ettj_fallback_from_ntnb()


def _anbima_token(client_id: str, client_secret: str) -> str:
    """Obtém access_token ANBIMA via OAuth 2.0 client_credentials."""
    import base64
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    resp = requests.post(
        "https://api.anbima.com.br/oauth/access-token",
        headers={"Authorization": f"Basic {credentials}", "Content-Type": "application/json"},
        json={"grant_type": "client_credentials"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def fetch_debentures_anbima(
    data_ref: Optional[str] = None,
    cache_ttl_h: int = 24,
) -> pd.DataFrame:
    """
    Busca taxas correntes das debêntures de infraestrutura via ANBIMA API.

    Requer ANBIMA_CLIENT_ID e ANBIMA_CLIENT_SECRET como variáveis de ambiente.
    Sem credenciais retorna DataFrame vazio — caller usa fixture.

    Conversões:
        IPCA-indexed: taxa_indicativa já é taxa real (spread sobre IPCA)
        DI-indexed: taxa_real = (1 + DI_anual + spread) / (1 + BEI_ETTJ) − 1
            onde BEI_ETTJ = yield médio da curva ETTJ NTN-B corrente

    Retorna DataFrame com: codigo, indice, taxa_real
    Cache pickle em data/cache/, TTL configurável.
    """
    import os

    client_id = os.environ.get("ANBIMA_CLIENT_ID", "")
    client_secret = os.environ.get("ANBIMA_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return pd.DataFrame()

    if data_ref is None:
        data_ref = datetime.now().strftime("%Y-%m-%d")

    cache_key = f"debentures_anbima_{data_ref}"
    cached = _cache_get(cache_key, cache_ttl_h / 24)
    if cached is not None:
        return cached

    try:
        token = _anbima_token(client_id, client_secret)

        # Dados de mercado secundário
        resp = requests.get(
            "https://api.anbima.com.br/feed/precos-e-indices/v1/debentures/mercado-secundario",
            headers={"Authorization": f"Bearer {token}", "client_id": client_id},
            params={"data": data_ref},
            timeout=60,
        )
        resp.raise_for_status()
        dados = resp.json()
        itens = dados if isinstance(dados, list) else dados.get("debentures", [])

        records = []
        for item in itens:
            codigo = str(item.get("CodigoCETIP", "")).strip()
            indice = str(item.get("Indice", "")).upper()
            taxa = item.get("TaxaIndicativaCompra") or item.get("TaxaIndicativa")
            spread = item.get("Spread")
            perc_di = item.get("Percentual")
            if not codigo or (taxa is None and spread is None):
                continue
            records.append({
                "codigo": codigo,
                "indice": indice,
                "taxa_indicativa": float(taxa) / 100 if taxa is not None else None,
                "spread_di": float(spread) / 100 if spread is not None else None,
                "perc_di": float(perc_di) / 100 if perc_di is not None else None,
            })

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)

        # Converter DI-indexed → taxa real via BEI da ETTJ
        di_mask = df["indice"].str.contains("DI", na=False)
        if di_mask.any():
            try:
                ettj = fetch_ettj_anbima()
                bei = float(ettj["yield_real"].mean()) if not ettj.empty else 0.055
                # Proxy do DI anual: BEI + spread médio histórico (~150bp)
                di_anual = bei + 0.015

                def _to_real(row):
                    if row["spread_di"] is not None:
                        taxa_nom = di_anual + row["spread_di"]
                    elif row["perc_di"] is not None:
                        taxa_nom = di_anual * row["perc_di"]
                    elif row["taxa_indicativa"] is not None:
                        taxa_nom = row["taxa_indicativa"]
                    else:
                        return None
                    return (1 + taxa_nom) / (1 + bei) - 1

                df.loc[di_mask, "taxa_real"] = df[di_mask].apply(_to_real, axis=1)
            except Exception as _e:
                warnings.warn(f"Conversão DI→real falhou: {_e}")
                df.loc[di_mask, "taxa_real"] = df.loc[di_mask, "taxa_indicativa"]

        # IPCA-indexed: taxa indicativa já é real
        ipca_mask = df["indice"].str.contains("IPCA", na=False)
        df.loc[ipca_mask, "taxa_real"] = df.loc[ipca_mask, "taxa_indicativa"]

        result = df[["codigo", "indice", "taxa_real"]].dropna(subset=["taxa_real"])
        _cache_set(cache_key, result)
        return result

    except Exception as e:
        warnings.warn(f"fetch_debentures_anbima falhou: {e}")
        return pd.DataFrame()


def fetch_universo_anbima(
    data_ref: Optional[str] = None,
    fixture_df: Optional[pd.DataFrame] = None,
    cache_ttl_h: int = 24,
    raise_sem_credenciais: bool = False,
) -> pd.DataFrame:
    """
    Retorna o universo completo de debêntures ANBIMA enriquecido com empresa.

    Estratégia:
    1. Busca mercado secundário via fetch_debentures_anbima() → todos os códigos + taxa_real.
    2. Cruza com fixture_df para obter empresa, data_emissao, data_vencimento, area dos
       códigos históricos (sem chamada adicional à API).
    3. Novos códigos não presentes na fixture ficam com empresa=None → o basket inference
       os coloca em categoria X até que o usuário os adicione via override.

    Args:
        data_ref:              Data de referência YYYY-MM-DD (padrão: hoje).
        fixture_df:            Fixture de debêntures (load_debentures()) para enriquecimento.
                               Se None, retorna apenas o que a API devolver sem empresa.
        cache_ttl_h:           TTL do cache pickle (padrão 24h).
        raise_sem_credenciais: Se True, levanta RuntimeError quando ANBIMA_CLIENT_ID /
                               ANBIMA_CLIENT_SECRET não estiverem no ambiente em vez de
                               retornar DataFrame vazio. Passar True no contexto C2.

    Returns:
        DataFrame com colunas: codigo, indice, taxa_real, empresa, data_emissao,
        data_vencimento, area. Linhas apenas dos dados ao vivo (fixture já é mesclada
        em inferir_cesta_transmissao).
        Retorna DataFrame vazio se sem credenciais (ou levanta RuntimeError quando
        raise_sem_credenciais=True) ou em caso de falha de rede.
    """
    import os
    if raise_sem_credenciais and (
        not os.environ.get("ANBIMA_CLIENT_ID")
        or not os.environ.get("ANBIMA_CLIENT_SECRET")
    ):
        raise RuntimeError(
            "fetch_universo_anbima requer ANBIMA_CLIENT_ID e ANBIMA_CLIENT_SECRET no ambiente. "
            "Configure as variáveis antes de chamar no contexto C2."
        )

    secundario = fetch_debentures_anbima(data_ref=data_ref, cache_ttl_h=cache_ttl_h)
    if secundario.empty:
        return pd.DataFrame()

    if fixture_df is None:
        return secundario

    # Cruza com fixture para enriquecer empresa, data_emissao, data_vencimento, area
    fix_cols = ["codigo", "empresa", "data_emissao", "data_vencimento", "area"]
    fix_sub = fixture_df[[c for c in fix_cols if c in fixture_df.columns]].drop_duplicates("codigo")

    result = secundario.merge(fix_sub, on="codigo", how="left")
    return result


def _ettj_fallback_from_ntnb() -> pd.DataFrame:
    """Aproximação da curva ETTJ a partir das taxas NTN-B spot."""
    ntnb = fetch_ntnb_tesouro()
    if ntnb.empty:
        # Retorna uma curva plana de emergência
        prazos = [1, 2, 3, 5, 7, 10, 15, 20, 30, 40]
        default_yield = 0.0514  # último Rf conhecido
        return pd.DataFrame({
            "prazo_anos": prazos,
            "yield_real": [default_yield] * len(prazos),
        })

    hoje = pd.Timestamp.now()
    ntnb = ntnb[ntnb["data"] >= hoje - pd.Timedelta(days=10)]
    if ntnb.empty:
        ntnb = fetch_ntnb_tesouro()

    latest = ntnb.sort_values("data").groupby("vencimento").last().reset_index()
    latest["prazo_anos"] = (latest["vencimento"] - hoje).dt.days / 365.25
    latest = latest[latest["prazo_anos"] > 0]

    return latest[["prazo_anos", "taxa_compra_manha"]].rename(
        columns={"taxa_compra_manha": "yield_real"}
    ).sort_values("prazo_anos").reset_index(drop=True)
