"""Coleta da ETTJ (Estrutura a Termo da Taxa de Juros) via scraping da ANBIMA."""
import io
import re
from datetime import date, datetime

import pandas as pd
import requests

from config import CACHE_DIR

ANBIMA_CZ_URL = "https://www.anbima.com.br/informacoes/est-termo/CZ.asp"
_CACHE_PREFIX = "ettj_"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Referer": "https://www.anbima.com.br/",
}


class AnbimaETTJError(Exception):
    """Levantada quando a coleta ou parse da ETTJ ANBIMA falha."""
    pass


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def fetch_ettj(force_refresh: bool = False) -> tuple[pd.DataFrame, date]:
    """
    Retorna (df, reference_date) com a ETTJ mais recente disponível.

    DataFrame com colunas:
      vertice_du   (int)   — dias úteis
      vertice_anos (float) — du / 252
      ipca_pct     (float) — ETTJ real IPCA+ (% a.a.)
      pre_pct      (float) — ETTJ pré-fixada / CDI implícito (% a.a.), NaN nos vértices longos
      bei_pct      (float) — inflação implícita break-even (% a.a.), NaN nos vértices longos
      data_ref     (date)

    Levanta AnbimaETTJError se a ANBIMA estiver inacessível e não houver cache.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if not force_refresh:
        cached = _load_latest_cache()
        if cached is not None:
            df, ref_date = cached
            if ref_date >= _last_business_day():
                _log("ETTJ", "cache_hit",
                     last_period=ref_date.strftime("%d/%m/%Y"), previous_period=None)
                return df, ref_date

    try:
        df, ref_date = _fetch_from_anbima()
        _save_cache(df, ref_date)
        _log("ETTJ", "fetch_ettj",
             last_period=ref_date.strftime("%d/%m/%Y"), previous_period=None,
             n_new_records=len(df), source="ANBIMA ETTJ CZ")
        return df, ref_date
    except AnbimaETTJError as e:
        cached = _load_latest_cache()
        if cached is not None:
            df, ref_date = cached
            _log("ETTJ", "fetch_ettj",
                 last_period=ref_date.strftime("%d/%m/%Y"), previous_period=None,
                 note=f"ANBIMA indisponível — usando cache: {e}")
            return df, ref_date
        raise


# ---------------------------------------------------------------------------
# Log helper (import opcional — não deve quebrar o coletor se falhar)
# ---------------------------------------------------------------------------

try:
    from data.update_log import append_event as _log_event
    def _log(series, event_type, **kw):
        _log_event(series, event_type, **kw)
except Exception:
    def _log(*a, **kw):
        pass


# ---------------------------------------------------------------------------
# Coleta e parse
# ---------------------------------------------------------------------------

def _fetch_from_anbima() -> tuple[pd.DataFrame, date]:
    try:
        resp = requests.get(ANBIMA_CZ_URL, headers=_HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise AnbimaETTJError(f"Falha ao conectar à ANBIMA: {e}") from e

    # O site usa ISO-8859-1; decodificar explicitamente para evitar mojibake
    html = resp.content.decode("iso-8859-1", errors="replace")
    ref_date = _extract_reference_date(html)

    # lxml rejeita declarações <?xml ...?> em strings unicode — remover antes de parsear
    html_clean = re.sub(r"<\?xml\b[^>]*\?>", "", html, count=1)

    try:
        tables = pd.read_html(io.StringIO(html_clean), decimal=",", thousands=".", flavor="lxml")
    except Exception as e:
        raise AnbimaETTJError(f"Falha ao parsear HTML da ANBIMA: {e}") from e

    ettj_raw = _find_ettj_table(tables)
    if ettj_raw is None:
        raise AnbimaETTJError("Tabela ETTJ não encontrada no HTML da ANBIMA.")

    df = _clean_ettj_table(ettj_raw, ref_date)
    if df.empty:
        raise AnbimaETTJError("Tabela ETTJ vazia após limpeza.")

    return df, ref_date


def _extract_reference_date(html: str) -> date:
    """Extrai a primeira data DD/MM/YYYY encontrada no HTML."""
    match = re.search(r"(\d{2}/\d{2}/\d{4})", html)
    if match:
        try:
            return datetime.strptime(match.group(1), "%d/%m/%Y").date()
        except ValueError:
            pass
    return date.today()


def _find_ettj_table(tables: list[pd.DataFrame]) -> pd.DataFrame | None:
    """
    Identifica a tabela ETTJ dentre as tabelas do HTML.
    A tabela ANBIMA tem MultiIndex com colunas IPCA, PRE e Implícita
    e primeira coluna de vértices numéricos ≥ 100.
    """
    for table in tables:
        # Extrair todos os nomes de colunas, suportando MultiIndex
        if isinstance(table.columns, pd.MultiIndex):
            all_names = " ".join(
                str(v).lower()
                for level in range(table.columns.nlevels)
                for v in table.columns.get_level_values(level)
            )
        else:
            all_names = " ".join(str(c).lower() for c in table.columns)

        has_ipca = "ipca" in all_names
        has_pre = "pré" in all_names or "pre" in all_names
        has_bei = "impl" in all_names

        if not (has_ipca and has_pre):
            continue
        if len(table.columns) < 3:
            continue

        # Confirmar que primeira coluna contém vértices numéricos ≥ 100
        try:
            first_col = (
                table.iloc[:, 0]
                .astype(str)
                .str.replace(".", "", regex=False)
                .str.strip()
            )
            numeric = pd.to_numeric(first_col, errors="coerce").dropna()
            if len(numeric) >= 5 and numeric.min() >= 100:
                return table
        except Exception:
            continue

    return None


def _clean_ettj_table(df: pd.DataFrame, ref_date: date) -> pd.DataFrame:
    """
    Normaliza a tabela bruta.
    Espera colunas na ordem: Vértices, ETTJ IPCA, ETTJ PRE, Inflação Implícita
    (posição 0, 1, 2, 3 — nomes reais podem variar, inclusive MultiIndex).
    """
    df = df.copy()

    # Achatar MultiIndex: usar apenas o último nível de cada coluna
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [str(col[-1]) for col in df.columns]

    # Renomear pelas posições (estrutura da ANBIMA é estável)
    col_map = {df.columns[0]: "vertice_du"}
    if len(df.columns) > 1:
        col_map[df.columns[1]] = "ipca_pct"
    if len(df.columns) > 2:
        col_map[df.columns[2]] = "pre_pct"
    if len(df.columns) > 3:
        col_map[df.columns[3]] = "bei_pct"
    df = df.rename(columns=col_map)

    # Limpar vértices: remover separador de milhar, manter apenas linhas numéricas
    df["vertice_du"] = (
        df["vertice_du"]
        .astype(str)
        .str.replace(".", "", regex=False)
        .str.strip()
    )
    df = df[df["vertice_du"].str.match(r"^\d+$", na=False)].copy()
    df["vertice_du"] = df["vertice_du"].astype(int)

    # Converter taxas: vírgula → ponto, traço/vazio → NaN
    _DASH = {"—", "-", "", "nan", "None"}
    for col in ["ipca_pct", "pre_pct", "bei_pct"]:
        if col not in df.columns:
            df[col] = float("nan")
            continue
        cleaned = (
            df[col]
            .astype(str)
            .str.replace(",", ".", regex=False)
            .str.replace("\xa0", "", regex=False)
            .str.strip()
        )
        cleaned = cleaned.where(~cleaned.isin(_DASH), other=None)
        df[col] = pd.to_numeric(cleaned, errors="coerce")

    df["vertice_anos"] = (df["vertice_du"] / 252).round(4)
    df["data_ref"] = ref_date

    df = df.sort_values("vertice_du").reset_index(drop=True)
    return df[["vertice_du", "vertice_anos", "ipca_pct", "pre_pct", "bei_pct", "data_ref"]]


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def _save_cache(df: pd.DataFrame, ref_date: date) -> None:
    path = CACHE_DIR / f"{_CACHE_PREFIX}{ref_date.strftime('%Y%m%d')}.parquet"
    df.to_parquet(path, index=False, engine="pyarrow")


def _load_latest_cache() -> tuple[pd.DataFrame, date] | None:
    files = sorted(CACHE_DIR.glob(f"{_CACHE_PREFIX}*.parquet"), reverse=True)
    if not files:
        return None
    try:
        df = pd.read_parquet(files[0], engine="pyarrow")
        date_str = files[0].stem.replace(_CACHE_PREFIX, "")
        ref_date = datetime.strptime(date_str, "%Y%m%d").date()
        return df, ref_date
    except Exception:
        return None


def _last_business_day() -> date:
    """Último dia útil aproximado (sem considerar feriados)."""
    today = date.today()
    wd = today.weekday()
    if wd == 5:
        return date(today.year, today.month, today.day - 1)
    if wd == 6:
        return date(today.year, today.month, today.day - 2)
    return today
