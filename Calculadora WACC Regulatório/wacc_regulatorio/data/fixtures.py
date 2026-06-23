"""
Carrega os CSVs extraídos da planilha ANEEL para validação (Camada 1).
Execute scripts/extrair_fixtures.py antes de usar este módulo.
"""
from pathlib import Path
import pandas as pd

_FIX = Path(__file__).parent / "fixtures"


def _path(name: str) -> Path:
    p = _FIX / name
    if not p.exists():
        raise FileNotFoundError(
            f"Fixture '{name}' não encontrado. Execute primeiro:\n"
            "    python scripts/extrair_fixtures.py"
        )
    return p


def load_ntnb() -> pd.DataFrame:
    """NTN-B: data, vencimento, taxa_compra_manha, taxa_venda_manha (decimal, e.g. 0.0514)."""
    df = pd.read_csv(_path("ntnb_diario.csv"), sep=";", parse_dates=["data", "vencimento"])
    return df


def load_prm_sp500() -> pd.DataFrame:
    """S&P500 mensal + T-Bill 3M (1928–1987) / ECB SDW 10Y (pós-1987): data, sp500, rf_tbill (%)."""
    df = pd.read_csv(_path("prm_sp500.csv"), sep=";", parse_dates=["data"])
    return df


def load_embi_diario() -> pd.DataFrame:
    """EMBI diário: data, embi_bps, embi_decimal."""
    df = pd.read_csv(_path("embi_diario.csv"), sep=";", parse_dates=["data"])
    return df


def load_embi_medias() -> pd.DataFrame:
    """Médias anuais EMBI pré-calculadas pelo ANEEL: ano_wacc, janela, embi_media_10a."""
    df = pd.read_csv(_path("embi_medias_anuais.csv"), sep=";")
    return df


def load_debentures() -> pd.DataFrame:
    """Amostra de debêntures do setor elétrico: area (D/T), taxa_real, etc."""
    df = pd.read_csv(
        _path("debentures.csv"), sep=";",
        parse_dates=["data_emissao", "data_vencimento"]
    )
    return df


def load_custo_emissao() -> pd.DataFrame:
    """Custos de emissão das debêntures."""
    df = pd.read_csv(
        _path("custo_emissao.csv"), sep=";",
        parse_dates=["data_emissao", "data_vencimento"]
    )
    return df


def load_custo_emissao_periodos() -> pd.DataFrame:
    """Custo agregado da cesta por janela — pré-computado pelo ANEEL no xlsx.
    Colunas: periodo (str, ex: '2016-2025'), custo_emissao_agregado (decimal).
    Use este valor em calcular_kd_com_custo_emissao() para C1.
    """
    df = pd.read_csv(_path("custo_emissao_periodos.csv"), sep=";")
    return df


def load_wacc_historico() -> pd.DataFrame:
    """Parâmetros WACC anuais 2013-2025 (Transmissão) — calculados pelo ANEEL."""
    df = pd.read_csv(_path("wacc_historico.csv"), sep=";")
    return df


def load_wacc_aplicacao() -> pd.DataFrame:
    """Parâmetros WACC anuais 2018-2026 (Transmissão) — valores oficiais do Despacho."""
    df = pd.read_csv(_path("wacc_aplicacao.csv"), sep=";")
    return df


def load_beta_historico() -> pd.DataFrame:
    """Beta desalavancado EUA e estrutura de capital brasileira: ano, beta_u_eua, dv_brasil, etc."""
    df = pd.read_csv(_path("beta_historico.csv"), sep=";")
    return df
