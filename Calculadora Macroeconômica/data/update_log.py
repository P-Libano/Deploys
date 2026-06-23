"""
Sistema de log de atualizações dos dados.
Persiste um arquivo JSON com o histórico de fetches e novos dados detectados.
"""
import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd

LOG_PATH = Path(__file__).parent / "update_log.json"
FALLBACK_LOG_PATH = (
    Path(os.environ.get("LOCALAPPDATA", Path.home()))
    / "CalculadoraMacroeconomica"
    / "update_log.json"
)


def append_event(
    series_key: str,
    event_type: str,              # "fetch_realized" | "fetch_focus" | "new_data"
    last_period: str | None,      # "MM/YYYY" do último dado disponível
    previous_period: str | None,  # "MM/YYYY" do último dado antes da atualização
    n_new_records: int = 0,
    source: str = "API BCB SGS",
    note: str = "",
) -> None:
    """
    Registra um evento no log. Detecta automaticamente se novos dados chegaram.
    """
    events = _load()

    is_new_data = (
        event_type == "fetch_realized"
        and previous_period is not None
        and last_period is not None
        and last_period != previous_period
    )

    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "series": series_key,
        "event_type": "new_data" if is_new_data else event_type,
        "last_period": last_period,
        "previous_period": previous_period,
        "n_new_records": n_new_records,
        "source": source,
        "note": note,
        "is_new_data": is_new_data,
    }

    events.append(entry)
    _save(events)


def get_events(limit: int = 200) -> list[dict]:
    """Retorna os últimos `limit` eventos, mais recentes primeiro."""
    return list(reversed(_load()))[:limit]


def get_last_period(series_key: str) -> str | None:
    """Retorna o último período conhecido para uma série (do cache do log)."""
    for ev in reversed(_load()):
        if ev.get("series") == series_key and ev.get("last_period"):
            return ev["last_period"]
    return None


def to_dataframe(limit: int = 200) -> pd.DataFrame:
    """Converte o log em DataFrame para exibição na UI."""
    events = get_events(limit)
    if not events:
        return pd.DataFrame(columns=["Horário", "Série", "Evento", "Último período", "Novos registros", "Nota"])

    rows = []
    for ev in events:
        rows.append({
            "Horário": ev.get("timestamp", ""),
            "Série": ev.get("series", ""),
            "Evento": _label(ev),
            "Último período": ev.get("last_period", ""),
            "Novos registros": ev.get("n_new_records", 0),
            "Nota": ev.get("note", ""),
        })
    return pd.DataFrame(rows)


def _label(ev: dict) -> str:
    if ev.get("is_new_data"):
        prev = ev.get("previous_period", "?")
        curr = ev.get("last_period", "?")
        return f"🆕 Novo dado ({prev} → {curr})"
    etype = ev.get("event_type", "")
    if etype == "fetch_realized":
        return "🔄 Atualização (sem novos dados)"
    if etype == "fetch_focus":
        return "📊 Focus atualizado"
    if etype == "fetch_ettj":
        return "📉 ETTJ ANBIMA atualizada"
    if etype == "cache_hit":
        return "💾 Cache (sem fetch)"
    return etype


def _load() -> list[dict]:
    for path in (LOG_PATH, FALLBACK_LOG_PATH):
        if not path.exists():
            continue
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
    return []


def _save(events: list[dict]) -> None:
    payload = json.dumps(events, ensure_ascii=False, indent=2)
    for path in (FALLBACK_LOG_PATH, LOG_PATH):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(payload, encoding="utf-8")
            return
        except PermissionError:
            continue
