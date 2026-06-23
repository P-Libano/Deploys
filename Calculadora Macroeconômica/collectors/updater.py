"""Cache Parquet local com TTL para séries realizadas e Focus."""
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

import config
from collectors.bcb_sgs import BCBAPIError, fetch_series
from collectors.focus import FocusAPIError, fetch_focus_annual, fetch_focus_monthly

logger = logging.getLogger(__name__)

# Import opcional do log — não deve quebrar o cálculo se falhar
try:
    from data.update_log import append_event as _log_event, get_last_period as _log_last_period
    _LOG_AVAILABLE = True
except Exception:
    _LOG_AVAILABLE = False
    def _log_event(*a, **kw): pass
    def _log_last_period(*a, **kw): return None


class NoCacheError(Exception):
    """Levantada quando não há cache local E a API está inacessível."""
    pass


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def get_realized_series(
    series_key: str,
    force_refresh: bool = False,
) -> tuple[pd.Series, bool, str | None]:
    """
    Retorna (series, from_cache, warning_message).

    - from_cache=True se o dado veio do Parquet local (sem chamada API).
    - warning_message é preenchido se a API falhou e o dado é do cache antigo.
    - Levanta NoCacheError se não há cache E a API está inacessível.
    """
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = config.CACHE_DIR / f"series_{series_key}.parquet"

    fresh = not force_refresh and _cache_is_fresh(path, config.CACHE_TTL_REALIZED)

    if fresh:
        _log_event(series_key, "cache_hit", _log_last_period(series_key), None)
        return _load_series(path), True, None

    # Guardar último período antes de atualizar
    previous_period: str | None = None
    if path.exists():
        try:
            prev_series = _load_series(path)
            previous_period = prev_series.index.max().strftime("%m/%Y")
        except Exception:
            pass

    try:
        series = fetch_series(
            series_key,
            start_date=config.SERIES[series_key]["start"],
        )
        _save_series(series, path)

        last_period = series.index.max().strftime("%m/%Y")
        n_new = 0
        if previous_period:
            try:
                prev_p = pd.Period(f"{previous_period[-4:]}-{previous_period[:2]}", freq="M")
                n_new = max(0, int(series.index.max().ordinal - prev_p.ordinal))
            except Exception:
                pass

        _log_event(
            series_key, "fetch_realized",
            last_period=last_period,
            previous_period=previous_period,
            n_new_records=n_new,
            source="API SGS/BCB",
        )
        return series, False, None
    except BCBAPIError as e:
        if path.exists():
            logger.warning("API BCB inacessível; usando cache local. Erro: %s", e)
            age = _cache_age_str(path)
            warn = f"API BCB indisponível. Dados do cache ({age})."
            _log_event(series_key, "fetch_realized", previous_period, previous_period,
                       note=f"API indisponível: {e}")
            return _load_series(path), True, warn
        raise NoCacheError(
            f"API BCB inacessível e nenhum cache local para '{series_key}'."
        ) from e


def get_focus_projections(
    series_key: str,
    force_refresh: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Retorna (focus_monthly_df, focus_annual_df).
    Aplica CACHE_TTL_FOCUS (7 dias).
    Retorna DataFrames vazios (não levanta erro) se Focus indisponível e sem cache.
    """
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path_m = config.CACHE_DIR / f"focus_monthly_{series_key}.parquet"
    path_a = config.CACHE_DIR / f"focus_annual_{series_key}.parquet"

    fresh = not force_refresh and (
        _cache_is_fresh(path_m, config.CACHE_TTL_FOCUS)
        and _cache_is_fresh(path_a, config.CACHE_TTL_FOCUS)
    )

    if fresh:
        return _load_df(path_m), _load_df(path_a)

    try:
        df_m = fetch_focus_monthly(series_key)
        df_a = fetch_focus_annual(series_key)
        _save_df(df_m, path_m)
        _save_df(df_a, path_a)
        _log_event(series_key, "fetch_focus", source="Boletim Focus/BCB",
                   last_period=None, previous_period=None,
                   n_new_records=len(df_m))
        return df_m, df_a
    except Exception as e:
        logger.warning("Focus inacessível para %s; tentando cache. Erro: %s", series_key, e)
        _log_event(series_key, "fetch_focus", source="Boletim Focus/BCB",
                   last_period=None, previous_period=None,
                   note=f"Focus indisponível: {e}")
        df_m = _load_df(path_m) if path_m.exists() else pd.DataFrame()
        df_a = _load_df(path_a) if path_a.exists() else pd.DataFrame()
        return df_m, df_a


def force_update_all() -> dict[str, str | None]:
    """
    Atualiza todas as séries, o Focus e a ETTJ ANBIMA em modo forçado.
    Retorna dict {series_key: warning_message | None}.
    """
    warnings_map: dict[str, str | None] = {}
    for key in config.SERIES:
        _, _, warn = get_realized_series(key, force_refresh=True)
        warnings_map[key] = warn
        get_focus_projections(key, force_refresh=True)

    # Atualiza ETTJ ANBIMA
    try:
        from collectors.anbima_ettj import fetch_ettj
        fetch_ettj(force_refresh=True)
        warnings_map["ETTJ"] = None
    except Exception as e:
        warnings_map["ETTJ"] = f"ETTJ indisponível: {e}"

    return warnings_map


def get_cache_status() -> dict[str, dict]:
    """Retorna metadados do cache: última atualização por série e ETTJ."""
    status = {}
    for key in config.SERIES:
        path = config.CACHE_DIR / f"series_{key}.parquet"
        focus_path = config.CACHE_DIR / f"focus_monthly_{key}.parquet"
        status[key] = {
            "realized_updated_at": _file_mtime_str(path),
            "focus_updated_at": _file_mtime_str(focus_path),
        }

    # ETTJ: arquivo mais recente na pasta de cache
    ettj_files = sorted(config.CACHE_DIR.glob("ettj_*.parquet"), reverse=True)
    status["ETTJ"] = {
        "realized_updated_at": _file_mtime_str(ettj_files[0]) if ettj_files else None,
        "focus_updated_at": None,
    }

    return status


# ---------------------------------------------------------------------------
# Parquet — serialização com PeriodIndex
# ---------------------------------------------------------------------------

def _save_series(series: pd.Series, path: Path) -> None:
    """Salva pd.Series com PeriodIndex mensal como Parquet (index como string "YYYY-MM")."""
    df = pd.DataFrame({"period": series.index.strftime("%Y-%m"), "valor": series.values})
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, path)


def _load_series(path: Path) -> pd.Series:
    """Carrega Parquet e reconstrói pd.Series com PeriodIndex mensal."""
    df = pd.read_parquet(path)
    index = pd.PeriodIndex(df["period"], freq="M")
    return pd.Series(df["valor"].values, index=index, dtype=float, name="valor")


def _save_df(df: pd.DataFrame, path: Path) -> None:
    """Salva DataFrame convertendo colunas Period para string."""
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_extension_array_dtype(df[col]) and hasattr(df[col].dtype, "freq"):
            df[col] = df[col].astype(str)
        elif df[col].dtype == object:
            sample = df[col].dropna().iloc[0] if len(df[col].dropna()) > 0 else None
            if isinstance(sample, pd.Period):
                df[col] = df[col].astype(str)
    df.to_parquet(path, engine="pyarrow", index=False)


def _load_df(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path)


# ---------------------------------------------------------------------------
# Helpers de TTL e metadados
# ---------------------------------------------------------------------------

def _cache_is_fresh(path: Path, ttl) -> bool:
    if not path.exists():
        return False
    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    return age < ttl


def _cache_age_str(path: Path) -> str:
    if not path.exists():
        return "desconhecido"
    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    hours = int(age.total_seconds() // 3600)
    if hours < 1:
        return "menos de 1 hora atrás"
    if hours < 24:
        return f"{hours}h atrás"
    days = hours // 24
    return f"{days}d atrás"


def _file_mtime_str(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
