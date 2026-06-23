"""
Coleta da curva DI Futuro (contratos DI1) da B3.

Cadeia de fallback:
  1. Cache local Parquet (evita requisições repetidas no mesmo dia)
  2. API intraday B3 (cotacao.b3.com.br) — funciona sem autenticação
  3. Dataset histórico pyield (GitHub Releases) — sem passar pela rede B3
  Levanta B3DI1Unavailable se todas falharem.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from config import CACHE_DIR

_CACHE_FILE  = CACHE_DIR / "b3_di1_curve.parquet"
_CACHE_TTL_H = 4  # horas (dados intraday mudam ao longo do dia)

_INTRADAY_URL = "https://cotacao.b3.com.br/mds/api/v1/DerivativeQuotation/DI1"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0",
    "Accept": "application/json",
    "Referer": "https://www.b3.com.br/",
}


class B3DI1Unavailable(Exception):
    """Levantada quando nenhuma fonte de dados DI1 está acessível."""


def fetch_di1_curve(force_refresh: bool = False) -> tuple[pd.DataFrame, date, str]:
    """
    Retorna (df, data_ref, fonte) com a curva DI1 mais recente disponível.

    DataFrame com colunas:
        symb            (str)   — código do contrato (ex: "DI1J30")
        expiration_date (date)  — vencimento
        du              (int)   — dias úteis até vencimento
        anos            (float) — du / 252
        taxa_aa         (float) — taxa de ajuste (% a.a.)
        open_contracts  (int)   — contratos em aberto (indicador de liquidez)
        data_ref        (date)
        fonte           (str)   — "intraday" | "historico_pyield"

    Levanta B3DI1Unavailable se todas as fontes falharem.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if not force_refresh and _cache_fresh():
        try:
            df = pd.read_parquet(_CACHE_FILE)
            data_ref = pd.to_datetime(df["data_ref"].iloc[0]).date()
            fonte = str(df["fonte"].iloc[0])
            return df, data_ref, fonte
        except Exception:
            pass

    # Fonte 1: API intraday B3
    df = _try_intraday()
    if df is not None:
        df["data_ref"] = date.today()
        df["fonte"]    = "intraday"
        _save_cache(df)
        _log("intraday")
        return df, date.today(), "intraday"

    # Fonte 2: dataset histórico pyield (GitHub Releases)
    df = _try_cached_dataset()
    if df is not None:
        data_ref = df["data_ref"].iloc[0]
        df["fonte"] = "historico_pyield"
        _save_cache(df)
        _log("historico_pyield")
        return df, data_ref, "historico_pyield"

    raise B3DI1Unavailable(
        "Dados DI1 indisponíveis: API intraday B3 inacessível e dataset histórico não retornou dados."
    )


# ---------------------------------------------------------------------------
# Fontes
# ---------------------------------------------------------------------------

def _try_intraday() -> pd.DataFrame | None:
    """GET cotacao.b3.com.br — retorna curva DI1 intraday ou None se falhar."""
    try:
        resp = requests.get(_INTRADAY_URL, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None

    items = data.get("Scty", [])
    if not items:
        return None

    today = date.today()
    rows = []
    for item in items:
        try:
            mty_str = item["asset"]["AsstSummry"]["mtrtyCode"]
            exp_date = datetime.strptime(mty_str, "%Y-%m-%d").date()
            if exp_date <= today:
                continue

            taxa = float(item["SctyQtn"]["prvsDayAdjstmntPric"])
            open_c = int(item["asset"]["AsstSummry"].get("opnCtrcts", 0))

            du   = _calc_du(today, exp_date)
            anos = du / 252

            rows.append({
                "symb":            item.get("symb", ""),
                "expiration_date": exp_date,
                "du":              du,
                "anos":            round(anos, 4),
                "taxa_aa":         taxa,
                "open_contracts":  open_c,
            })
        except Exception:
            continue

    if not rows:
        return None

    df = (
        pd.DataFrame(rows)
        .query("open_contracts >= 100")     # remove vencimentos ilíquidos
        .sort_values("expiration_date")
        .reset_index(drop=True)
    )
    return df if not df.empty else None


def _try_cached_dataset() -> pd.DataFrame | None:
    """Dataset histórico pyield (b3_di.parquet do GitHub Releases)."""
    try:
        import pyield as py
        raw = py.di1.get_cached_dataset("di1")  # polars DataFrame
        if raw is None or (hasattr(raw, "__len__") and len(raw) == 0):
            return None

        # Converter para pandas
        if hasattr(raw, "to_pandas"):
            raw = raw.to_pandas()

        # Encontrar colunas de data e taxa (nomes podem variar entre versões)
        date_col = _find_col(raw, ["trade_date", "TradeDate", "date", "Date", "data"])
        taxa_col = _find_col(raw, ["rate", "Rate", "SettlementRate", "settlement_rate", "taxa"])
        mty_col  = _find_col(raw, ["maturity_date", "MaturityDate", "ExpirationDate", "expiration_date"])
        du_col   = _find_col(raw, ["du", "DU", "BDtoExp", "bd_to_exp", "business_days"])

        if not (date_col and taxa_col and mty_col):
            return None

        # Filtrar pela data mais recente
        latest = raw[date_col].max()
        df = raw[raw[date_col] == latest].copy()

        today = date.today()
        result_rows = []
        for _, row in df.iterrows():
            try:
                exp_date = pd.Timestamp(row[mty_col]).date()
                if exp_date <= today:
                    continue
                taxa = float(row[taxa_col])
                du   = int(row[du_col]) if du_col else _calc_du(today, exp_date)
                result_rows.append({
                    "symb":            "",
                    "expiration_date": exp_date,
                    "du":              du,
                    "anos":            round(du / 252, 4),
                    "taxa_aa":         taxa,
                    "open_contracts":  0,
                    "data_ref":        pd.Timestamp(latest).date(),
                })
            except Exception:
                continue

        if not result_rows:
            return None
        return pd.DataFrame(result_rows).sort_values("expiration_date").reset_index(drop=True)

    except Exception:
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _calc_du(start: date, end: date) -> int:
    """Calcula dias úteis aproximados entre duas datas (sem feriados)."""
    days = (end - start).days
    weeks, remainder = divmod(days, 7)
    du = weeks * 5
    start_wd = start.weekday()
    for i in range(remainder):
        wd = (start_wd + i) % 7
        if wd < 5:
            du += 1
    return max(1, du)


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _cache_fresh() -> bool:
    if not _CACHE_FILE.exists():
        return False
    age_hours = (datetime.now() - datetime.fromtimestamp(
        _CACHE_FILE.stat().st_mtime)).total_seconds() / 3600
    return age_hours < _CACHE_TTL_H


def _save_cache(df: pd.DataFrame) -> None:
    df_save = df.copy()
    for col in ["expiration_date", "data_ref"]:
        if col in df_save.columns:
            df_save[col] = df_save[col].astype(str)
    df_save.to_parquet(_CACHE_FILE, index=False, engine="pyarrow")


def _log(fonte: str) -> None:
    try:
        from data.update_log import append_event
        append_event("DI1 B3", "fetch_ettj",
                     last_period=date.today().strftime("%d/%m/%Y"),
                     previous_period=None,
                     source=f"B3 DI Futuro ({fonte})")
    except Exception:
        pass
