"""
Parâmetros fixos e configuráveis do módulo WACC Regulatório (ANEEL PRORET).

Nota sobre a fórmula do Ke:
    A planilha ANEEL (Despacho 675/2026) implementa:
        ke_di = rf + beta_l_us * erp
    onde beta_l_us é o beta re-alavancado com a estrutura de capital americana
    (D_us/E_us ≈ 2.35), NOT com a estrutura brasileira.
    O risco-país (EMBI) está implicitamente incorporado na re-alavancagem com
    a estrutura americana de maior leverage. O valor de EMBI é mantido no
    módulo para transparência regulatória e uso nas projeções de Kd (Camada 3).
"""
from pathlib import Path

# Diretórios
BASE_DIR = Path(__file__).parent
FIXTURES_DIR = BASE_DIR / "data" / "fixtures"
CACHE_DIR = BASE_DIR / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Parâmetros regulatórios fixos
T_IRPJ_CSLL = 0.34       # Alíquota composita IRPJ + CSLL
JANELA_ANOS = 10          # Janela rolante EMBI e Kd (anos) — Rf usa esta mesma janela por etapa
JANELA_BETA_ANOS = 5      # Janela OLS do beta (5 anos de retornos semanais, per ANEEL)

# Tickers das 21 utilities americanas da amostra ANEEL
TICKERS_UTILITIES_ANEEL = [
    "AEE", "AEP", "CHG", "CNP", "ED", "EIX", "ES", "ETR", "EXC",
    "FE", "IDA", "NEE", "NWE", "OGE", "PCG", "PEG", "POM", "PPL",
    "PNW", "HE", "D",
]
TICKER_SP500 = "^SP500TR"  # S&P500 Total Return via yfinance (SPXT Bloomberg = ^SP500TR yfinance)
TICKER_SP500_TR = "SPXT"   # S&P500 Total Return (Bloomberg, usado nas fixtures PRM)

# Parâmetros de cache
CACHE_TTL_PRECO_DIAS = 1   # Preços e EMBI: cache de 1 dia
CACHE_TTL_ETTJ_DIAS = 7    # Curva ETTJ ANBIMA: cache de 7 dias

# URLs de dados externos
URL_IPEADATA_EMBI = (
    "http://www.ipeadata.gov.br/api/odata4/ValoresSerie"
    "(SERCODIGO='JPM366_EMBI366')"
)
URL_TESOURO_NTNB = "https://sisweb.tesouro.gov.br/apex/f?p=2031:2:0"

# Índice IPEADATA para EMBI
IPEADATA_EMBI_CODE = "JPM366_EMBI366"

# Arquivo de coeficientes calibrados da regressão Kd
KD_REGRESSAO_JSON = BASE_DIR / "data" / "kd_regressao.json"

PREMISSAS = {
    "automaticos": {
        "rf": "NTN-B yield real — média das taxas diárias por vencimento, depois média dos vencimentos",
        "bei_kd": "Inflação implícita para cálculo Kd — curva ETTJ ANBIMA via engine",
        "ipca": "IPCA projetado — Focus BCB ou ETTJ BEI (configurável via cenario_ipca)",
    },
    "estruturais_congelados": {
        "erp": "ERP geométrico histórico S&P500 desde jan/1928 — estável, varia <10bp/ano",
        "beta_l": (
            "Beta alavancado das utilities americanas — OLS semanal janela 5 anos por estimativa, "
            "13 estimativas (2013-2025) ponderadas por market cap (cap 50%). "
            "Re-alavancado com D/E americano (book debt / market cap). "
            "Atualizado quando Camada 2 é re-executada com dados mais recentes."
        ),
        "ev_dv": "Estrutura de capital regulatória — 13 janelas anuais 2013-2025, utilities EUA ponderadas por market cap",
    },
    "cenario": {
        "embi": (
            "EMBI+ médio 10 anos como base — média aritmética simples dos spreads diários. "
            "Sensibilizável por ano via embi_delta: {ano: delta_decimal}. "
            "Exemplo choque crédito 2027: embi_delta={2027: +0.015, 2028: +0.008}"
        ),
        "kd_spread": (
            "Projetado via regressão Kd ~ alpha + beta1*Rf [+ beta2*EMBI] — "
            "coeficientes calibrados com histórico 2013-2025 (wacc_historico.csv)"
        ),
    },
    "nota_horizonte": (
        "Para concessões com prazo de 30 anos: beta e E/V são fotografias do mercado "
        "atual e não refletem mudanças estruturais futuras. O WACC projetado é mais "
        "confiável nos primeiros 5-7 anos do horizonte, onde a curva ETTJ tem liquidez. "
        "Para anos distantes (fonte_rf='ettj_extrapol' ou 'extrapol_longo'), o vetor "
        "deve ser interpretado como cenário de referência, não como previsão pontual."
    ),
    "nota_formula_ke": (
        "A fórmula implementada ke_di = Rf + beta_l_us * ERP segue a planilha ANEEL. "
        "O risco-país (EMBI) está incorporado no beta_l via re-alavancagem com D/E "
        "americano mais alto — efeito equivalente a usar ke_di = Rf + beta_l_br * (ERP + EMBI) "
        "com estrutura de capital brasileira."
    ),
}
