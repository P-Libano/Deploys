"""
Coleta de expectativas de SELIC por reunião COPOM via Boletim Focus (BCB).

O endpoint ExpectativasMercadoSelic retorna a mediana das expectativas de mercado
para a taxa SELIC ao final de cada reunião do COPOM, identificada como "R{n}/{ano}".
Isso é o equivalente survey da curva DI futuro: em vez de preços negociados em bolsa,
usa o consenso semanal de ~150 instituições financeiras.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from config import CACHE_DIR

_CACHE_FILE = CACHE_DIR / "focus_selic_curve.parquet"
_CACHE_TTL_DAYS = 7  # Focus é semanal

# Calendário COPOM 2026 (datas oficiais BCB — último dia da reunião)
_COPOM_2026: dict[int, date] = {
    1: date(2026, 1, 29),
    2: date(2026, 3, 19),
    3: date(2026, 5,  7),
    4: date(2026, 6, 18),
    5: date(2026, 7, 30),
    6: date(2026, 9, 17),
    7: date(2026, 11, 5),
    8: date(2026, 12, 10),
}

# Para anos além de 2026: spacing uniforme de ~45 dias (360/8)
_MEETING_MONTH_APPROX = {
    1: (1, 29), 2: (3, 19), 3: (5, 7),  4: (6, 18),
    5: (7, 30), 6: (9, 17), 7: (11, 5), 8: (12, 10),
}


def fetch_selic_curve(force_refresh: bool = False) -> pd.DataFrame:
    """
    Retorna expectativas de SELIC por reunião COPOM da pesquisa mais recente.

    Colunas do DataFrame:
        reuniao      (str)   — "R4/2026"
        data_reuniao (date)  — data estimada da reunião
        anos_ahead   (float) — anos a partir de hoje até a reunião
        du_ahead     (int)   — dias úteis aproximados até a reunião
        mediana      (float) — SELIC esperada (% a.a.)
        media        (float)
        minimo       (float)
        maximo       (float)
        n_respondentes (int)
        data_survey  (date)  — data da pesquisa Focus
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if not force_refresh and _cache_fresh():
        try:
            return pd.read_parquet(_CACHE_FILE)
        except Exception:
            pass

    df = _fetch_from_focus()
    df.to_parquet(_CACHE_FILE, index=False, engine="pyarrow")
    _log_fetch(df)
    return df


def _fetch_from_focus() -> pd.DataFrame:
    from bcb import Expectativas
    em = Expectativas()
    ep = em.get_endpoint("ExpectativasMercadoSelic")

    raw = (
        ep.query()
        .filter(ep.baseCalculo == 0)
        .collect()
    )

    # Manter apenas a última data de survey
    latest_date = raw["Data"].max()
    raw = raw[raw["Data"] == latest_date].copy()

    today = date.today()

    rows = []
    for _, row in raw.iterrows():
        reuniao = str(row["Reuniao"])
        data_reuniao = _reuniao_to_date(reuniao)
        if data_reuniao is None or data_reuniao <= today:
            continue

        delta_days = (data_reuniao - today).days
        anos_ahead = delta_days / 365.25
        du_ahead = max(1, round(delta_days * 252 / 365))

        rows.append({
            "reuniao":       reuniao,
            "data_reuniao":  data_reuniao,
            "anos_ahead":    round(anos_ahead, 4),
            "du_ahead":      du_ahead,
            "mediana":       float(row["Mediana"]),
            "media":         float(row["Media"]),
            "minimo":        float(row["Minimo"]),
            "maximo":        float(row["Maximo"]),
            "n_respondentes": int(row["numeroRespondentes"]),
            "data_survey":   pd.Timestamp(latest_date).date(),
        })

    df = pd.DataFrame(rows).sort_values("data_reuniao").reset_index(drop=True)
    return df


def _reuniao_to_date(reuniao: str) -> date | None:
    """Converte 'R3/2026' → data estimada da reunião."""
    try:
        partes = reuniao.split("/")
        n    = int(partes[0][1:])   # número da reunião
        year = int(partes[1])

        if year == 2026 and n in _COPOM_2026:
            return _COPOM_2026[n]

        if n in _MEETING_MONTH_APPROX:
            month, day = _MEETING_MONTH_APPROX[n]
            return date(year, month, min(day, 28))

        return None
    except Exception:
        return None


def _cache_fresh() -> bool:
    if not _CACHE_FILE.exists():
        return False
    age = datetime.now() - datetime.fromtimestamp(_CACHE_FILE.stat().st_mtime)
    return age.days < _CACHE_TTL_DAYS


def _log_fetch(df: pd.DataFrame) -> None:
    try:
        from data.update_log import append_event
        n = len(df)
        survey = str(df["data_survey"].iloc[0]) if not df.empty else "?"
        append_event(
            "SELIC Focus",
            "fetch_focus",
            last_period=survey,
            previous_period=None,
            n_new_records=n,
            source="Boletim Focus/BCB — ExpectativasMercadoSelic",
        )
    except Exception:
        pass
