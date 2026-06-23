"""Coleta de IPCA via API SIDRA do IBGE (backup e validação cruzada)."""
import requests
import pandas as pd
from config import SIDRA_URL


class SIDRAAPIError(Exception):
    pass


def fetch_ipca_sidra(
    start_yearmonth: str,
    end_yearmonth: str,
    timeout: int = 30,
) -> pd.Series:
    """
    Retorna pd.Series IPCA com PeriodIndex mensal ('M') e valores em %.

    Args:
        start_yearmonth: "YYYYMM" ex: "201001"
        end_yearmonth: "YYYYMM" ex: "202412"
    """
    periods_param = f"{start_yearmonth}-{end_yearmonth}"
    url = SIDRA_URL.format(periods=periods_param)

    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.HTTPError as e:
        raise SIDRAAPIError(f"Erro HTTP ao buscar IPCA SIDRA: {e}") from e
    except requests.exceptions.RequestException as e:
        raise SIDRAAPIError(f"Falha de conexão SIDRA: {e}") from e

    return _parse_sidra_response(data)


def _parse_sidra_response(data: list) -> pd.Series:
    """
    Navega na estrutura SIDRA:
    data[0]["resultados"][0]["series"][0]["serie"] -> {"YYYYMM": "valor", ...}
    """
    try:
        serie_dict = data[0]["resultados"][0]["series"][0]["serie"]
    except (IndexError, KeyError, TypeError) as e:
        raise SIDRAAPIError(f"Estrutura de resposta SIDRA inesperada: {e}") from e

    records = []
    for period_str, valor_str in serie_dict.items():
        try:
            period = pd.Period(
                f"{period_str[:4]}-{period_str[4:6]}", freq="M"
            )
            valor = float(str(valor_str).replace(",", ".")) if valor_str not in (None, "") else float("nan")
            records.append((period, valor))
        except (ValueError, TypeError):
            continue

    if not records:
        raise SIDRAAPIError("Nenhum registro válido na resposta SIDRA")

    periods, values = zip(*records)
    series = pd.Series(values, index=pd.PeriodIndex(periods, freq="M"), dtype=float)
    return series.sort_index()
