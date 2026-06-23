"""Coleta de séries temporais via API SGS do Banco Central do Brasil."""
import time
import requests
import pandas as pd
from config import SGS_URL, SERIES


class BCBAPIError(Exception):
    """Levantada quando a API SGS do BCB é inacessível ou retorna erro."""
    pass


def fetch_series(
    series_key: str,
    start_date: str | None = None,
    end_date: str | None = None,
    timeout: int = 30,
) -> pd.Series:
    """
    Retorna pd.Series com PeriodIndex mensal ('M') e valores em % (float).

    Args:
        series_key: chave do SERIES dict (ex: "IPCA", "IGPM")
        start_date: "MM/YYYY" — None usa o início da série
        end_date: "MM/YYYY" — None usa hoje
        timeout: timeout HTTP em segundos

    Raises:
        KeyError: series_key inválida
        BCBAPIError: falha na requisição HTTP
    """
    if series_key not in SERIES:
        raise KeyError(f"Série '{series_key}' não encontrada. Opções: {list(SERIES)}")

    code = SERIES[series_key]["sgs_id"]
    url = SGS_URL.format(code=code)
    params = {"formato": "json"}
    if start_date:
        params["dataInicial"] = _mmyyyy_to_ddmmyyyy(start_date)
    if end_date:
        params["dataFinal"] = _mmyyyy_to_ddmmyyyy(end_date)

    try:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        raw = resp.json()
    except requests.exceptions.HTTPError as e:
        raise BCBAPIError(f"Erro HTTP ao buscar série {series_key} (SGS {code}): {e}") from e
    except requests.exceptions.RequestException as e:
        raise BCBAPIError(f"Falha de conexão ao buscar série {series_key}: {e}") from e

    if not raw:
        raise BCBAPIError(f"API retornou lista vazia para série {series_key} (SGS {code})")

    return _parse_response(raw)


def fetch_all_series(
    series_keys: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    sleep_between: float = 0.5,
) -> dict[str, pd.Series]:
    """
    Faz fetch de múltiplas séries com pausa entre requisições para evitar rate limit.
    Retorna dict {series_key: pd.Series}.
    """
    if series_keys is None:
        series_keys = list(SERIES.keys())

    result = {}
    for key in series_keys:
        result[key] = fetch_series(key, start_date=start_date, end_date=end_date)
        if key != series_keys[-1]:
            time.sleep(sleep_between)
    return result


def _parse_response(raw: list[dict]) -> pd.Series:
    """
    Converte [{"data": "01/07/1994", "valor": "0.42"}, ...] em pd.Series.
    Index: pd.PeriodIndex com freq='M'.
    Valores: float (% mensal). Entradas nulas/vazias viram NaN.
    """
    records = []
    for item in raw:
        date_str = item.get("data", "")
        valor_str = item.get("valor", "")

        try:
            dt = pd.to_datetime(date_str, format="%d/%m/%Y")
            period = pd.Period(dt, freq="M")
        except (ValueError, TypeError):
            continue

        if valor_str in (None, "", "null"):
            valor = float("nan")
        else:
            try:
                valor = float(str(valor_str).replace(",", "."))
            except (ValueError, TypeError):
                valor = float("nan")

        records.append((period, valor))

    if not records:
        raise BCBAPIError("Nenhum registro válido encontrado na resposta da API")

    periods, values = zip(*records)
    series = pd.Series(values, index=pd.PeriodIndex(periods, freq="M"), dtype=float)
    series = series.sort_index()
    series = series[~series.index.duplicated(keep="last")]
    return series


def _mmyyyy_to_ddmmyyyy(date_str: str) -> str:
    """Converte "MM/YYYY" para "dd/MM/YYYY" (dia 01) exigido pela API SGS."""
    parts = date_str.strip().split("/")
    if len(parts) != 2:
        raise ValueError(f"Formato de data inválido: '{date_str}'. Esperado: 'MM/YYYY'")
    mm, yyyy = parts
    return f"01/{mm.zfill(2)}/{yyyy}"
