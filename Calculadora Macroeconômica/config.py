from pathlib import Path
from datetime import timedelta

SERIES = {
    "IPCA": {
        "sgs_id": 433,
        "start": "07/1994",
        "focus_name": "IPCA",
        "label": "IPCA",
    },
    "IGPM": {
        "sgs_id": 189,
        "start": "01/1940",
        "focus_name": "IGP-M",
        "label": "IGP-M",
    },
    "IPCA15": {
        "sgs_id": 7478,
        "start": "02/1999",
        "focus_name": "IPCA-15",
        "label": "IPCA-15",
    },
    "INPC": {
        "sgs_id": 188,
        "start": "01/1979",
        "focus_name": "INPC",
        "label": "INPC",
    },
    "INCC": {
        "sgs_id": 192,
        "start": "01/1985",
        "focus_name": None,
        "label": "INCC",
    },
    "SELIC": {
        "sgs_id": 4390,
        "start": "06/1986",
        "focus_name": None,
        "label": "SELIC",
    },
    "CDI": {
        "sgs_id": 4391,
        "start": "06/1986",
        "focus_name": None,
        "label": "CDI",
    },
}

SGS_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"

PLANO_REAL_START = "07/1994"
MAX_FUTURE_MONTHS = 120
SEASONAL_YEARS = 5

# Índices exibidos na calculadora de correção monetária (exclui taxas de juros)
CALCULATOR_INDICES = ["IPCA", "IGPM", "IPCA15", "INPC", "INCC"]

CACHE_DIR = Path(__file__).parent / "data" / "cache"
CACHE_TTL_REALIZED = timedelta(days=1)
CACHE_TTL_FOCUS = timedelta(days=7)

FOCUS_INDICATOR_MAP = {key: meta["focus_name"] for key, meta in SERIES.items()}

# SIDRA backup for IPCA
SIDRA_URL = (
    "https://servicodados.ibge.gov.br/api/v3/agregados/1737"
    "/periodos/{periods}/variaveis/63?localidades=N1[all]"
)
