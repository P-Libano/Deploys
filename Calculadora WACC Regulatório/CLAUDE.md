# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Contexto

Módulo Python de validação do **WACC Regulatório ANEEL** (Despacho 675/2026, retificado pelo 1174/2026). Não é entregável de produção — é um protótipo de engine para validar a lógica de cálculo contra a planilha Excel da ANEEL antes de portar para o backend. Ver `ENGINE_CONTEXT.md` e `WACC_Regulatorio_Whitepaper.md` para metodologia completa.

**Resultado validado:** WACC real antes de impostos = 12,11% (Transmissão), delta < 1bp vs. publicado.

**Status:** versão final de validação para apresentação (2026-06-22). Scope freeze — sem novas features até decisão pós-apresentação. Gate obrigatório antes de qualquer alteração (ver seção abaixo).

## Comandos

```bash
# Instalar dependências (Python 3.11+)
pip install pandas numpy scipy requests yfinance openpyxl streamlit plotly

# Extrair fixtures da planilha ANEEL — executar uma vez antes de qualquer coisa
python scripts/extrair_fixtures.py

# Dashboard interativo (3 abas: C1/C2/C3)
streamlit run dashboard.py --server.fileWatcherType none --server.runOnSave false

# Validar Camada 1 diretamente
python -m wacc_regulatorio.validator

# Teste integrado Camadas 1 + 3
python scripts/test_camadas.py

# Rodar uma camada individualmente
python -m wacc_regulatorio.camada1_replicacao
python -m wacc_regulatorio.camada2_corrente
```

## Arquitetura das três camadas

| Camada | Arquivo | Input | Propósito |
|--------|---------|-------|-----------|
| **C1 — Replicação** | `camada1_replicacao.py` | Fixtures CSV Bloomberg (zero APIs) | Replica Despacho 675/2026; WACC_ai = 12,11% ± 1bp |
| **C2 — Corrente** | `camada2_corrente.py` | APIs ao vivo (yfinance, IPEADATA, ANBIMA) | Snapshot do WACC implícito de mercado hoje (YTD) |
| **C3 — Vetor 30a** | `camada3_vetor.py` | ETTJ/DI + cenários estruturais | Vetor anual para solver BRR × WACC_t |

### Trilhas de cálculo e isolamento de limitações de base de dados

O comparativo entre C1 e C2 mistura dois efeitos distintos. Para separá-los, usamos três trilhas:

| Trilha | Janela de dados | Fontes | Propósito |
|--------|----------------|--------|-----------|
| **C1 ANEEL** | 2016–2025 (histórica) | Bloomberg (fixture pré-computado) | Referência de validação — 0bp de delta |
| **C1 Público** | 2016–2025 (histórica) | yfinance + ANBIMA pública + IPEADATA | Isola gap de base de dados (Bloomberg vs público) |
| **C2 YTD** | Até hoje (live) | yfinance + ANBIMA pública + IPEADATA | Sinal de mercado — incorpora movimentos YTD |

**Resultado do comparativo (Despacho 675/2026, baseline 2026-06-22):**

| Parâmetro | C1 ANEEL | C1 Público | gap BD | C2 YTD | mvmt mercado |
|-----------|:--------:|:----------:|:------:|:------:|:------------:|
| Rf | 5,1377% | 5,1362% | −0,1 bp | 5,2132% | +7,7 bp |
| ERP | 6,8481% | 6,8481% | 0,0 bp | 6,8738% | +2,6 bp |
| EMBI | 2,765% | 2,7649% | 0,0 bp | 2,6454% | −11,9 bp |
| β_u | 0,5030 | 0,4962 | **−6,7 bp** | 0,4447 | −51,5 bp |
| β_l | 0,7692 | 0,7596 | **−9,6 bp** | 0,6675 | −92,1 bp |
| Kd_ai | 6,587% | 6,587% | 0,0 bp | 6,650% | +6,4 bp |
| **WACC_ai** | **12,115%** | **12,053%** | **−6,2 bp** | **11,312%** | **−74,1 bp** |

**Metodologia C1 Público — 4+1 híbrido:**
- Beta: 4 janelas Bloomberg (2021–2024) diretamente do `beta_historico.csv` (fixture xlsx ANEEL) + 1 janela yfinance Oct2024–Set2025. Mesma lógica do 4+1 de C2, mas referenciada à janela histórica (2021–2025) em vez da janela corrente (2022–2026). Gap de BD isolado apenas na janela 2025 = −48bp por janela / 5 janelas = **−9,6bp no WACC**.
- Todos os demais parâmetros: fontes públicas (NTN-B ANBIMA, IPEADATA, ^SP500TR via yfinance).

**Conclusão:** com o xlsx ANEEL como fixture para β_l histórico + yfinance apenas para a janela corrente, o gap de BD cai para **−6bp no WACC_ai** (antes: −202bp). O único gap residual vem da janela 2025 onde yfinance diverge −48bp de Bloomberg para o basket de utilities.

Script de comparativo: `scripts/comparativo_trilhas.py`

**Fluxo de dados:**
```
extrair_fixtures.py  →  data/fixtures/*.csv
                              ↓
data/fixtures.py  (carregadores)  +  data/fetchers.py (APIs com cache pickle)
                              ↓
params/rf.py · erp.py · embi.py · beta.py · estruturais.py · kd.py · kd_cesta.py
                              ↓
wacc_calc.py → WACCResult
                              ↓
validator.py  (tolerância ±1bp no WACC_ai)
```

**Kd na Camada 2 — Basket Inference Engine (`params/kd_cesta.py`):**
```
fetch_universo_anbima()  →  universo {codigo, indice, taxa_real, empresa}
        +  fixture debentures.csv (âncora classificação)
                              ↓
inferir_cesta_transmissao()  →  df com coluna 'categoria':
    A = transmissora confirmada (empresa ∈ fixture área=T)  ← cenário base (WACC)
    B = candidata por keyword ("TRANSMISS", "LT " etc.)     ← cenário amplo
    C = override manual do usuário                          ← cenário custom
    X = excluída (distribuidora, fora da janela, sem taxa)
                              ↓
executar_kd_sensibilidade()  →  {base: KdResult, amplo: KdResult, custom: KdResult}
```

Prioridade de classificação: **A > C > B > X** — o cenário base nunca muda com overrides do usuário.

## Invariantes críticos de negócio

- **Fórmula Ke sem EMBI explícito:** `ke_di = Rf + beta_l_us × ERP`. O EMBI está implícito na re-alavancagem com D/E americano (≈2,35×). Não adicionar EMBI no Ke — seria double-counting.
- **ERP em C2 via extensão incremental, não congelado:** `camada2_corrente.py` chama `fetch_prm_sp500tr_incremento(prm_df_base)` que estende a série da fixture com o ano corrente via `^SP500TR` (yfinance). Mesma função `calcular_prm()`, janela ampliada. Se `^SP500TR` falhar, cai no fallback `erp_fonte = "fixture (fallback)"`. Em C3, o ERP usa o valor do último despacho por default (parâmetro `erp` em `params/estruturais.py`). A série histórica 1928–1987 só existe na planilha ANEEL (originalmente Bloomberg) — `extrair_fixtures.py` é a única fonte; não replicável publicamente com delta=0.
- **C3 começa em ~12,1%, não em ~14,9% (C2):** C3 usa a média de 5 médias rolantes consecutivas de 10 anos de Rf, igual à planilha ANEEL. C2 usa taxa spot YTD. O gap (~260bp) é estrutural — não é bug.
- **Parâmetros estruturais da C3 são cenários:** `Beta_l`, `Beta_u`, `ERP` e `E/V-D/V` podem usar `valor_atual`, `media_5a`, `media_10a`, `regressao_5a` ou `regressao_10a` via `params/estruturais.py`. Isso não altera C1 nem a referência ANEEL.
- **DI futuro é nominal:** `rf_source="di_futuro"` só alimenta o WACC real se houver `ipca_deflator`; sem deflator, DI entra como diagnóstico e a âncora real continua ETTJ/NTN-B. Nunca usar DI nominal diretamente como Rf real.
- **`segmento="distribuicao"`** está estruturalmente suportado no código mas sem valores de referência no `validator.py` — não implementar sem os parâmetros ANEEL oficiais.
- **Basket inference — A tem prioridade sobre C:** o override manual nunca retira debêntures do cenário base. Transmissoras confirmadas (área=T no fixture) sempre ficam em A. O cenário `kd_base` (usado no WACC) é estável independente dos overrides.
- **Regressão Kd apenas em C3:** a regressão `Kd ~ 3,327% + 0,621 × Rf` (R²=76%) ficou em `camada3_vetor.py` para projeção forward. C2 usa exclusivamente bottom-up via basket inference — sem fallback para regressão.
- **Kd C2 — dois caminhos, sem colapso em C1:** se `ANBIMA_CLIENT_ID`/`ANBIMA_CLIENT_SECRET` estiverem no ambiente, `executar_camada2()` usa basket inference ANBIMA live (`kd_fonte = "anbima_live"`). Sem credenciais, cai no Kd-mid (`kd_fonte = "ettj_atualizado"`): mesmos títulos do fixture ANEEL + BEI atualizado via ETTJ ao vivo. O Kd-mid captura o efeito das taxas de mercado sobre os mesmos títulos sem depender de credenciais — o gap vs C1 é estrutural (BEI atual ≠ BEI na emissão). O campo `kd_fonte` distingue os dois caminhos no snapshot. Em produção com ANBIMA o cenário de base é sempre `"anbima_live"`.
- **Metodologia Beta — média móvel 5a de beta_l_brasil (confirmada no xlsx):** A fórmula do xlsx é `=AVERAGE('WACC Histórico'!K6:O6)` = média das 5 janelas mais recentes de beta_l já re-alavancado com D/E brasileiro. Para 2026: mean(beta_l_brasil de 2021..2025) = 0.769239 ≈ 0.769238 publicado (delta 0.01bp). **NÃO** é média de 13 janelas de beta_u_us re-alavancado em bloco. O código correto está em `calcular_beta_from_historico()` em `params/beta.py`. `JANELA_BETA_ANOS = 5` em `config.py` refere-se à janela OLS de retornos (Oct-Sep) — separada da média móvel de 5 anos de beta_l_brasil.
- **Beta 4+1 híbrido em C2 (já implementado em `executar_camada2()`):** C2 usa 4 janelas Bloomberg do fixture (anos 2022–2025) + 1 janela yfinance ao vivo (ano corrente = 2026), depois aplica `calcular_beta_from_historico()` = média das 5 β_l_brasil. Resultado: β_l = 0.6675 (vs ANEEL 0.769). Scripts que bypassam `executar_camada2()` e chamam `calcular_beta_mktcap_window()` diretamente para C2 produzem β_l errado. Sempre usar `executar_camada2()` para a coluna C2 no comparativo.
- **Beta 4+1 híbrido em C1 Público (`comparativo_trilhas.py` e `dashboard.py`):** C1 Público usa 4 janelas Bloomberg do fixture (anos 2021–2024) + 1 janela `calcular_beta_janelas_anuais(..., anos=[2025])` via yfinance. Fórmula: `mean([bl_2021, bl_2022, bl_2023, bl_2024, bl_2025_yf])`. Gap BD isolado apenas na janela 2025 = −48bp ÷ 5 = **−9.6bp em β_l, −6bp no WACC_ai**. Não usar `calcular_beta_mktcap_window()` para C1 Público — produziria gap de −324bp (5 janelas yfinance puras). Implementado via `_hist_2021_2024 = beta_hist_df[ano.isin([2021..2024])]` + `calcular_beta_janelas_anuais(..., anos=[2025])` diretamente no script/dashboard.
- **Ponderação D/V contábil para beta_u em C2 (confirmada no xlsx):** ANEEL pondera empresas pelo **D/V book** = dívida contábil / (dívida + patrimônio líquido contábil), NÃO por market cap. Fórmula: `peso_i = dv_book_i / Σ(dv_book_j)`, com cap de 50% por empresa ("Ponderado 50%" na aba Beta do xlsx, coluna 87+). Prova: aplicando pesos D/V exatos do xlsx + betas exatos do xlsx → beta_u_janela = 0.293106 (delta 0.0bp). Implementado em `calcular_beta_mktcap_window()` em `params/beta.py`, que agora usa `dv_book` de `fetch_market_caps()`. Gap residual em C2 (+66bp vs ANEEL 0.2931): betas individuais yfinance vs Bloomberg + datas de balanço diferentes.
- **Tolerâncias do validator:** parâmetros intermediários ±1bp; WACC final ±5bp. `beta_u` tem tolerância de ±50bp (valor diagnóstico — não entra no WACC; nosso cálculo exibe a média dos 5 beta_u_eua das janelas mais recentes = 0.5029, não a referência histórica de 0.302).
- **Rf não filtra taxas negativas:** `calcular_rf_anual_10a()` em `params/rf.py` filtra apenas `> 0.25` e `notna()`. A ANEEL inclui NTN-B com yield real negativo (ex: 2020-08-15 com -3.06% durante o COVID). Não restaurar filtro `>= 0.01` — causaria gap de +3.64bp.
- **Custo emissão IPCA+DI congelado por Res. CVM 160 (jul/2022):** `calcular_kd_com_custo_emissao()` usa o agregado da fixture `custo_emissao_periodos.csv` quando `periodos_df` é fornecido. Não tentar derivar esse valor da média de `remuneracao_real` individual — nenhuma ponderação reproduz o valor ANEEL (diferença estrutural ~+0.8bp). O fixture extrai a coluna "IPCA+DI" diretamente do xlsx via `extrair_fixtures.py`. C2 (path Kd-mid) agora também passa `periodos_df` — custo = 0.5181% em todas as trilhas. Quando o período exato não existe no fixture (ex: `"2017-2026"` em C2 YTD), o código cai no período mais recente disponível (CVM 160 congela o valor).
- **D/V é parâmetro regulatório endógeno (circularidade WACC ↔ D/V):** na aba "WACC Histórico" do xlsx, célula AD4 = D/V colado (para evitar referência circular). A fórmula AD10 que calcula D/V é: `EBITDA = (taxa_deprec_reg + WACC_ai) × Ativos`, `D/V = 3 × (0.0307 + WACC_ai)`, onde taxa_deprec_reg=0.0307 e 3=Dívida/EBITDA× (constantes regulatórias). O EBITDA depende de O22 (WACC do mesmo período) — gerando circularidade WACC→EBITDA→D/V→WACC. Implementado como solver de ponto fixo em `resolver_dv_wacc_iterativo()` em `params/estruturais.py`. C2 usa o solver para D/V dinâmico; C1 usa o valor colado do fixture (0.3977 para 2026). Validação: D/V_2025=0.3977 implica WACC_2025≈10.19% (diferente do WACC_2026=12.115% que usa D/V_2025 como input fixo).
- **`inflacao_implicita` em `debentures.csv` é o BEI histórico:** coluna contém o BEI interpolado da ETTJ ANBIMA na data de emissão de cada debênture (pré-computado no xlsx ANEEL). Permite replicar `taxa_real` bottom-up: `taxa_real = (1 + taxa_nominal_pct/100) / (1 + inflacao_implicita) - 1`. O Kd-mid usa ETTJ *atual* — gap +6bp vs C1 é estrutural (BEI atual ≠ BEI na emissão). A função `calcular_kd_fixture_bottomup()` em `params/kd.py` usa `inflacao_implicita` para demonstrar replicabilidade bottom-up, mas o `comparativo_trilhas.py` usa `calcular_kd_com_custo_emissao()` para C1pub (0bp gap, mesma fonte taxa_real).

## Gate obrigatório após qualquer alteração

**Toda alteração em qualquer arquivo deste módulo deve ser seguida de:**

```bash
# 1. Validar C1 — deve continuar PASS (tolerância ±5bp no WACC_ai)
python -m wacc_regulatorio.validator

# 2. Emitir quadro comparativo das três trilhas
python scripts/comparativo_trilhas.py
```

O quadro abaixo é a baseline de referência (2026-06-22). Qualquer alteração deve produzir resultado comparável ou melhor (menor gap C1 ANEEL vs C1 Público, sem regressão em C2):

```
Parametro                         C1 ANEEL      C1 Pub    dif bp      C2 YTD  vs C1 bp      C2 YTD  vs C1pub
                                 Bloomberg    Pub/hist    BD gap    Pub/live     total    Pub/live  mkt mvmt
------------------------------------------------------------------------
Rf -- Taxa Livre de Risco          5.1377%     5.1362%      -0.1     5.2132%      +7.5     5.2132%      +7.7
ERP -- Premio de Risco             6.8481%     6.8481%      -0.0     6.8738%      +2.6     6.8738%      +2.6
EMBI -- Risco Brasil               2.7650%     2.7649%      -0.0     2.6454%     -12.0     2.6454%     -11.9
Bu -- Beta Desalavancado            0.5030      0.4962     -67.2      0.4447    -582.4      0.4447    -515.2
Bl -- Beta Alavancado (BR)          0.7692      0.7596     -96.5      0.6675   -1017.9      0.6675    -921.4
E/V                               60.2261%    60.2261%      -0.0    56.8535%    -337.3    56.8535%    -337.3
D/V                               39.7739%    39.7739%      +0.0    43.1465%    +337.3    43.1465%    +337.3
Ke_di -- Custo Equity             10.4055%    10.3379%      -6.8     9.8011%     -60.4     9.8011%     -53.7
Kd_deb -- Debentures               6.0685%     6.0685%      +0.0     6.1321%      +6.4     6.1321%      +6.4
Custo de emissao                   0.5181%     0.5181%      +0.0     0.5181%      +0.0     0.5181%      +0.0
Kd_ai -- Custo Divida AI           6.5866%     6.5866%      +0.0     6.6502%      +6.4     6.6502%      +6.4
WACC_di -- Real DI                 7.9959%     7.9552%      -4.1     7.4660%     -53.0     7.4660%     -48.9
------------------------------------------------------------------------
WACC_ai -- Real AI                12.1150%    12.0533%      -6.2    11.3122%     -80.3    11.3122%     -74.1
------------------------------------------------------------------------
```

**Leitura:** `dif bp` = gap de base de dados (Bloomberg vs público, mesma janela). `vs C1pub` = movimento puro de mercado (YTD vs histórico). C1 Público usa 4 janelas Bloomberg do fixture ANEEL (2021–2024) + 1 janela yfinance (2025). Gap total de BD = −6bp no WACC_ai.

**Critérios de aprovação:**
- `python -m wacc_regulatorio.validator` → Status: PASS
- WACC_ai C1 ANEEL = 12.115% ± 5bp
- WACC_ai C1 Público gap BD (dif bp) ≤ 10bp (baseline: −6.2bp)
- Kd_ai gap BD ≤ 1bp (custo emissão congelado — nunca deve regredir)
- Rf gap BD ≤ 1bp

## Problemas conhecidos — ler antes de qualquer sessão

Estado verificado em 2026-06-22 contra o código real (não contra descrições de sessão).

### ~~P1~~ — RESOLVIDO (2026-06-19): `fetch_sp500_treasury` removida
Função morta removida de `data/fetchers.py`. C1 validator continua PASS ±0bp.

### ~~P2~~ — RESOLVIDO (2026-06-19): Invariante ERP atualizado
Seção "Invariantes críticos de negócio" atualizada: ERP não é congelado em C2 —
usa `fetch_prm_sp500tr_incremento` para estender a série PRM com o ano corrente via `^SP500TR`.

### ~~P3~~ — RESOLVIDO (2026-06-19 / atualizado 2026-06-19): Kd-mid como fallback C2
`fetch_universo_anbima` recebeu parâmetro `raise_sem_credenciais: bool = False`.
`camada2_corrente.py` verifica credenciais via `tem_anbima = bool(ANBIMA_CLIENT_ID and ANBIMA_CLIENT_SECRET)`:
- Com credenciais → basket inference ANBIMA live (caminho C2 completo)
- Sem credenciais → `calcular_kd_ettj_atualizado()` via ETTJ ao vivo (Kd-mid, `kd_fonte = "ettj_atualizado"`)
Dashboard trata `RuntimeError` separadamente (ainda útil para falhas de conectividade).
`fetch_debentures_anbima` mantém retorno vazio silencioso (é utilitária — só C2 requer explicitação).
`calcular_taxa_real_ettj()` e `calcular_kd_ettj_atualizado()` adicionados em `params/kd.py`.
Kd-mid: mesmos 192 títulos (janela 10a transmissão), BEI atual interpolado da ETTJ. Delta vs C1 ≈ +14bp (BEI plano de emergência — ETTJ ANBIMA ou Tesouro ao vivo dará resultado mais preciso).

### ~~P8~~ — RESOLVIDO (2026-06-19): Beta FIXME removido — metodologia ANEEL confirmada
`camada1_replicacao.py` usava `calcular_beta_from_fixture()` (lia beta_l diretamente de `wacc_aplicacao.csv`) como workaround porque `calcular_beta_from_historico()` retornava 0.4126×relever_br = 0.59 (errado).
Raiz do erro (via leitura de fórmulas sem data_only=True): o xlsx computa beta_l 2026 como
`=AVERAGE('WACC Histórico'!K6:O6)` = média das 5 janelas mais recentes (2021-2025) de beta_l_br (não de 13 janelas de beta_u_us). Correção em duas partes:
1. `calcular_beta_from_historico()` em `params/beta.py`: `tail(5)["beta_l_brasil"].mean()` → 0.769239
2. `camada1_replicacao.py`: substituído `calcular_beta_from_fixture` por `calcular_beta_from_historico`; removida dependência de `load_wacc_aplicacao`
Validator C1: beta_l delta = 0.00bp; WACC_ai delta = -0.1bp — PASS.

### P4 — Basket inference NUNCA testado com credenciais ANBIMA reais
Toda validação da lógica A/B/C/X (`params/kd_cesta.py`) foi feita contra a fixture (663 debêntures).
O universo ANBIMA real via `/mercado-secundario` tem tamanho desconhecido.
Comportamento do basket inference com dados ao vivo é **heurística não validada**.
Scope freeze (2026-06-22): validação de apresentação amanhã — não implementar até decisão explícita.

### ~~P5~~ — RESOLVIDO (2026-06-19): Coluna renomeada `rf_10y` → `rf_tbill`
`prm_sp500.csv`, `extrair_fixtures.py`, `fetchers.py`, `params/erp.py` e `data/fixtures.py` atualizados.
A série histórica 1928–1987 usa T-Bills 3M (Damodaran) — nome `rf_tbill` agora reflete a fonte real.
Coluna derivada interna `rf_10y_dec` renomeada para `rf_tbill_dec` em `params/erp.py`.
Validator C1 continua PASS ±0bp após o rename.

### ~~P6~~ — RESOLVIDO (2026-06-19): Rf gap +3.64bp por filtro de taxa negativa
`params/rf.py`: `calcular_rf_anual_10a()` filtrava `taxa_compra_manha >= 0.01`, excluindo a NTN-B 2020-08-15 que teve yield real negativo durante o COVID. A ANEEL inclui essas taxas. Removido o limite inferior do filtro (mantido apenas `<= 0.25` e `notna()`). Resultado: delta Rf = -0.15bp (mean de 5 anos). 2021–2024 agora batem com a ANEEL em 0.00bp; 2025 tem -0.75bp residual por diferença de vencimentos disponíveis.

### ~~P7~~ — RESOLVIDO (2026-06-19): Custo emissão IPCA+DI +0.82bp
`params/kd.py`: `calcular_kd_com_custo_emissao()` calculava custo de emissão como `remuneracao_real.mean()` das debêntures individuais (0.5262%). A ANEEL usa um agregado pré-computado no xlsx (coluna IPCA+DI, valor 0.5181024% para o período 2016–2025). Solução: novo fixture `data/fixtures/custo_emissao_periodos.csv` (14 períodos → IPCA+DI); novo loader `load_custo_emissao_periodos()` em `data/fixtures.py`; parâmetro opcional `periodos_df` adicionado a `calcular_kd_com_custo_emissao()` — quando fornecido, usa o agregado ANEEL; quando ausente, mantém fallback `remuneracao_real.mean()` (para C2/C3). `camada1_replicacao.py` passa `periodos_df`. Resultado: Kd custo emissão = 0.5181% exato, WACC_ai delta = -0.1bp.

---

## Dados e fixtures

- `scripts/extrair_fixtures.py` lê `anexo-despacho-1174-2026-aneel-2-Anexo_Memoria_de_Calculo_WACC_2026.xlsx` e gera os CSVs em `wacc_regulatorio/data/fixtures/`. Deve ser executado antes de qualquer outra coisa.
- `data/fetchers.py` faz cache em pickle em `data/cache/` com TTL configurável em `config.py` (1 dia para preços/EMBI, 7 dias para ETTJ ANBIMA).
- Seis dos 18 datasets do datalake completo dependem de Bloomberg Terminal. Para operação sem Bloomberg, C1 usa apenas fixtures CSV. Ver seção "Dependências Bloomberg" no README para detalhes por dataset.
- `data/kd_regressao.json` contém os coeficientes calibrados da regressão `Kd ~ alpha + beta1×Rf [+ beta2×EMBI]` (histórico 2013–2025).
- Curva DI futura ainda não tem fetcher público implementado. A C3 aceita `curva_di_df` local com `prazo_anos`/`taxa_nominal` ou `vencimento`/`taxa_nominal`; fonte externa futura esperada: B3 Market Data ou Bloomberg `IRZ+ Comdty`.
