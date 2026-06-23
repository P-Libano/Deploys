# Calculadora WACC Regulatório ANEEL

Módulo Python para cálculo, monitoramento e projeção do WACC regulatório do setor elétrico brasileiro, seguindo a metodologia do **Despacho ANEEL 675/2026** (retificado pelo 1174/2026).

**Resultado validado:** WACC real antes de impostos = **12,11%** (Transmissão) · Delta < 1bp vs. publicado.

---

## Início rápido

```bash
# 1. Instalar dependências
pip install pandas numpy scipy requests yfinance openpyxl streamlit plotly

# 2. Extrair fixtures da planilha ANEEL (executar uma vez)
python scripts/extrair_fixtures.py

# 3. Abrir o dashboard interativo
streamlit run dashboard.py
```

> A planilha `anexo-despacho-1174-2026-aneel-2-Anexo_Memoria_de_Calculo_WACC_2026.xlsx`
> deve estar na raiz do projeto antes de executar o passo 2.

---

## As três camadas

| Camada | Descrição | Input | Output |
|--------|-----------|-------|--------|
| **C1 — Replicação** | Replica o Despacho 675/2026 com dados da planilha oficial | Fixtures ANEEL | WACC = 12,11% ± 1bp |
| **C2 — Corrente** | WACC implícito de mercado hoje (radar regulatório) | APIs ao vivo | Snapshot + delta + tendência |
| **C3 — Vetor 30a** | Projeção anual para o solver BRR × WACC_t | ETTJ + cenários | DataFrame 30 linhas |

### Por que C3 começa diferente de C2?

C3 inicia no mesmo valor de C1 (~12,1%) porque usa a **média histórica rolante de 10 anos de Rf** (idêntica à metodologia ANEEL). C2 usa a taxa spot YTD (~7,6%) e é mais alta (~14,9%). O gap (~260bp) é a elevação regulatória já represada na janela rolante: à medida que anos com taxas altas entram e anos com taxas baixas (2019-2020) saem, C3 converge para C2 em ~8-10 anos.

---

## Dashboard

```bash
streamlit run dashboard.py
```

Três abas:

- **Validação ANEEL (C1)** — waterfall de decomposição do WACC, tabela parâmetros vs. referência, badge PASS/FAIL
- **WACC Corrente (C2)** — snapshot ao vivo, barras comparativas publicado vs. corrente, build-up waterfall
- **Vetor 30 anos (C3)** — gráfico interativo com zonas de confiabilidade, painel de convergência C1→C2→C3, cenários via sidebar

Controles no sidebar: horizonte (5-30a), Rf spot projetado (cenário de normalização vs. persistência de juros), choque EMBI por ano, especificação Kd.

---

## Uso programático

```python
# Camada 1 — replicação
from wacc_regulatorio.camada1_replicacao import executar_camada1
from wacc_regulatorio.validator import validar

result = executar_camada1()
validar(result)  # → PASS  WACC_ai = 12.115%

# Camada 2 — snapshot mercado
from wacc_regulatorio.camada2_corrente import executar_camada2

c2 = executar_camada2()
print(c2)  # → WACC atual, delta vs despacho, tendência

# Camada 3 — vetor para solver RAP
from wacc_regulatorio.camada3_vetor import projetar_vetor_wacc

df = projetar_vetor_wacc(
    horizonte_anos=30,
    rf_spot_projetado=0.076,        # cenário Rf futuro (None = usa ETTJ médio)
    embi_delta={2027: +0.015},      # choque EMBI opcional
)
wacc_t = df["WACC_antes_impostos"]  # vetor para o solver BRR × WACC_t
```

---

## Estrutura do projeto

```
├── dashboard.py                    # Dashboard Streamlit (3 abas)
├── scripts/
│   └── extrair_fixtures.py         # Lê planilha ANEEL → gera CSVs (executar 1x)
├── wacc_regulatorio/
│   ├── config.py                   # Parâmetros, tickers, TTL cache
│   ├── wacc_calc.py                # WACCResult + calcular_wacc()
│   ├── validator.py                # Validação vs. Despacho 675/2026
│   ├── camada1_replicacao.py
│   ├── camada2_corrente.py
│   ├── camada3_vetor.py
│   ├── data/
│   │   ├── fixtures.py             # Carrega CSVs extraídos
│   │   ├── fetchers.py             # APIs ao vivo com cache pickle
│   │   └── fixtures/               # CSVs gerados pelo script (não versionar)
│   │       ├── ntnb_diario.csv     # NTN-B 2004-2025 (43k linhas)
│   │       ├── prm_sp500.csv       # S&P500 + Treasury 1927-2025
│   │       ├── embi_diario.csv     # EMBI+ 2008-2025
│   │       ├── wacc_aplicacao.csv  # Valores oficiais 2018-2026
│   │       └── ...
│   └── params/
│       ├── rf.py                   # NTN-B yield (histórico + rolling + ETTJ)
│       ├── erp.py                  # ERP geométrico S&P500
│       ├── embi.py                 # IPEADATA JPM366_EMBI366
│       ├── beta.py                 # OLS utilities americanas + Hamada
│       └── kd.py                   # Debêntures + regressão Kd~Rf
└── WACC_Regulatorio_Whitepaper.md  # Metodologia completa
```

---

## Parâmetros WACC 2026 — Transmissão

| Parâmetro | Símbolo | Valor | Fonte |
|-----------|---------|-------|-------|
| Taxa livre de risco | Rf | 5,138% | NTN-B média rolante 10a (2016-2025) |
| Prêmio de risco mercado | ERP | 6,848% | S&P500 geométrico vs. T-Bill desde 1928 |
| Prêmio risco Brasil | EMBI | 2,765% | IPEADATA média rolante 10a (2016-2025) |
| Beta alavancado | β_l | 0,7692 | 21 utilities EUA, D/E americano |
| Estrutura capital | E/V | 60,23% | Market cap ponderado, mesma amostra |
| Custo dívida | Kd_ai | 6,587% | Debêntures setor elétrico + emissão |
| Alíquota | T | 34,0% | IRPJ + CSLL composita |
| **WACC real a.i.** | **WACC_ai** | **12,11%** | |

---

## Notas técnicas

- **ERP (Camada 2)**: congelado no último valor publicado (6,848%). A série histórica `rf_10y` do fixture contém yield do T-Bond 10Y, enquanto ANEEL usa T-Bills (~3,3% de média histórica) — sem a série correta, o cálculo bottom-up não converge para 6,848%.
- **Rf (Camada 3)**: usa janela rolante de 10 anos de `rf_spot` anuais, projetando anos futuros com o parâmetro `rf_spot_projetado` (default = média da curva ETTJ ≈ nível atual de mercado).
- **Ke sem EMBI explícito**: ANEEL usa `Ke = Rf + β_l × ERP` (sem EMBI no Ke). O risco-país está implícito via re-alavancagem com D/E americano maior. Numericamente equivalente à formulação com EMBI e β_l menor.
- **Distribuição**: estruturalmente suportada via `segmento="distribuicao"` mas sem valores de referência no validator — a ser implementado em iteração futura.

---

## Referências normativas

- ANEEL — Despacho 675/2026 e Retificação 1174/2026
- ANEEL — PRORET Módulo 9 (Remuneração do Capital)
- Damodaran, A. (2024). *Equity Risk Premiums*. Stern NYU.
- Hamada, R.S. (1972). *Journal of Finance* 27(2).
