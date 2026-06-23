# Estudo: Python vs. Planilha ANEEL — WACC Regulatório 2026

> Documento de estudo para leitura offline.  
> Produzido em 2026-06-17 a partir dos dados do `Calculadora WACC Regulatório`.  
> Referência: Despacho 675/2026 + Retificação 1174/2026 (Anexo Memória de Cálculo).

---

## 0. Sumário executivo

| # | Parâmetro | C1 Python | Publicado ANEEL | Delta | Status |
|---|---|---|---|---|---|
| 1 | Rf (NTN-B, média 10a) | 5,1377 % | 5,1377 % | 0,0 bp | ✅ |
| 2 | PRM (S&P500 vs US10Y, 5ax acum. 1928) | 6,8481 % | 6,8481 % | 0,0 bp | ✅ |
| 3 | EMBI+ (média 10a) | 2,7649 % | 2,7649 % | 0,0 bp | ✅ |
| 4 | Beta_u (EUA) | 30,2200 % | 30,2200 % | 0,0 bp | ✅ |
| 5 | Beta_l (EUA re-alav.) | 76,9239 % | 76,9239 % | 0,0 bp | ✅ |
| 6 | E/V | 60,2261 % | 60,2261 % | 0,0 bp | ✅ |
| 7 | D/V | 39,7739 % | 39,7739 % | 0,0 bp | ✅ |
| 8 | Kd debêntures | 6,0685 % | 6,0685 % | 0,0 bp | ✅ |
| 9 | Kd custo emissão | 0,5181 % | 0,5181 % | 0,0 bp | ✅ |
|10 | Kd real a.i. | 6,5866 % | 6,5866 % | 0,0 bp | ✅ |
|11 | Ke real d.i. | 10,4055 % | 10,4055 % | 0,0 bp | ✅ |
|12 | WACC real d.i. | 7,9959 % | 7,9959 % | 0,0 bp | ✅ |
|13 | **WACC real a.i.** | **12,1150 %** | **12,1150 %** | **0,0 bp** | ✅ |

**C1 replica o Despacho com delta zero em todos os 13 parâmetros.**  
As seções abaixo documentam o que está correto, onde há discrepâncias metodológicas ocultas, e como o produto pode evoluir.

---

## 1. Taxa Livre de Risco — Rf

### 1.1 O que o Python faz (C1)

Lê o valor pré-calculado de `wacc_aplicacao.csv` → **Rf = 5,1377 %**.  
O fixture foi extraído diretamente da aba "WACC para Aplicação" da planilha ANEEL.

### 1.2 O que o Python calcula do zero (diagnóstico)

Para entender a metodologia, `calcular_rf_historico(ano, ntnb)` computa para cada ano a **média simples das taxas médias por vencimento**:

| Ano | Vencimentos ativos | Rf ano | Prazo médio |
|---|---|---|---|
| 2016 | 7 | 6,2751 % | 15,5 anos |
| 2017 | 7 | 5,4223 % | 14,5 anos |
| 2018 | 6 | 4,9624 % | 15,9 anos |
| 2019 | 6 | 3,4511 % | 14,9 anos |
| 2020 | 9 | 3,4476 % | 16,6 anos |
| 2021 | 8 | 4,2667 % | 17,6 anos |
| 2022 | 9 | 5,8304 % | 16,0 anos |
| 2023 | 9 | 5,8427 % | 15,0 anos |
| 2024 | 9 | 6,3610 % | 14,0 anos |
| 2025 | 9 | 7,5953 % | 17,0 anos |
| **Média simples 10a** | — | **5,3455 %** | — |

### 1.3 O gap de +20,8 bp

`Python_simples = 5,3455 %` vs `ANEEL_publicado = 5,1377 %` → **+20,8 bp**.

**Hipóteses para o gap:**

**H1 — Filtro de prazo:** a ANEEL pode excluir vencimentos curtos (< 2 anos), que estão "embutindo" prêmio de liquidez atípico. Em 2025, o vencimento de Ago/2026 (≈ 1,6 anos) apresentou 9,34 % — muito acima dos demais (7,1–7,7 %). Excluir esse outlier reduz o Rf de 2025 de 7,60 % para ~7,25 %, aproximando a média 10 anos do publicado.

**H2 — Ponderação por volume financeiro:** ANEEL pondera cada vencimento pelo volume negociado, dando mais peso aos títulos mais líquidos (prazos intermediários de 10–20 anos).

**H3 — Data-corte intradía:** o fixture usa taxas até 31/12/2025 com hora de corte específica; nossa série tem observações ligeiramente diferentes.

**H4 — Seleção de vencimentos específicos:** a planilha pode ter uma lista fixa de vencimentos canônicos em vez de todos os ativos.

### 1.4 Como investigar (na planilha ANEEL)

Na aba "WACC para Aplicação" → coluna Rf → clique na célula e rastreie a fórmula.  
Procurar: existe algum `PROCV` para lista de vencimentos? Existe ponderação por volume?  
Isso permitirá replicar a metodologia exata e eliminar o +20,8 bp do cálculo from-scratch.

### 1.5 Rf corrente (C2)

Rf C2 = **7,5953 %** (média de 9 vencimentos ativos em 2025, dados até 2025-12-31).  
Delta vs C1: **+245,8 bp** — reflexo do ciclo de alta de juros reais de 2024–2025.  
Este é o valor mais relevante para projeção do próximo despacho (WACC 2027).

---

## 2. Prêmio de Risco de Mercado — PRM

### 2.1 O que o Python faz (C1 e C2)

- **C1:** fixture `wacc_aplicacao.csv` → PRM = **6,8481 %** (acumulado 1928–2025, 5 médias anuais)
- **C2:** `calcular_prm(ano_publicacao, prm_df)` com fixture `prm_sp500.csv` → PRM = **6,8642 %** (δ = +1,6 bp)

Delta C1 vs C2: **+1,6 bp** — resultado de incluir dados YTD 2026 no acumulado do último ano da janela de 5.

### 2.2 O que a planilha ANEEL faz

A ANEEL calcula o PRM como **média de 5 valores anuais acumulados** [P-5, P-1]:

- Cada valor anual X = média de todos os `PRM_mensal` desde dez/1928 até dez/X
- `PRM_mensal_t = Rm_12m_t − Rf_10y_t/100`, onde:
  - `Rm_12m_t` = retorno S&P500 Total Return nos 12 meses anteriores
  - `Rf_10y_t` = yield US Treasury 10Y no mês t (em %)
- Fontes: S&P500 via Bloomberg `TOT_RETURN_INDEX_GROSS_DVDS`; US 10Y via ECB SDW `FM.M.US.USD.4F.BB.US10YT_RR.YLDA`

A estrutura de dupla média (5 anos × acumulado desde 1928) é análoga ao Rf — mas a janela interna é acumulada, não rolante de 10 anos.

**Valores anuais acumulados confirmados (WACC 2026):**

| Ano acum. | PRM até dez/ano |
|---|---|
| 2021 | 6,8831 % |
| 2022 | 6,7531 % |
| 2023 | 6,7300 % |
| 2024 | 6,9100 % |
| 2025 | 6,9640 % |
| **Média (PRM 2026)** | **6,8481 %** ← delta 0bp ✅ |

### 2.3 Nota sobre escala das séries

O fixture `prm_sp500.csv` usa a série Bloomberg (base S&P500 ≈ 17,66 em 1927). A série yfinance `^SP500TR` tem base ≈ 16.000 em 2026. As escalas são incompatíveis — `pct_change(12)` produz retorno absurdo na borda de junção. **Não fazer merge das séries para cálculo do PRM.** Usar o fixture até que se normalize a série ao vivo (ex: via ECB SDW diretamente).

---

## 3. EMBI+ — Prêmio de Risco Brasil

### 3.1 O que o Python faz

- **C1:** fixture `embi_medias.csv` (pré-calculado pela ANEEL) → EMBI = **2,7649 %** ✅
- **C2:** série diária IPEADATA (código `JPM366_EMBI366`), janela YTD → EMBI = **2,6454 %**

Delta C2 vs C1: **−11,9 bp** — 2026 YTD parcial vs janela completa 2016–2025.

### 3.2 Gap de dados: 2022 e 2023 ausentes

A série IPEADATA no fixture cobre apenas:
2016 (259 obs), 2017 (257), 2018 (257), 2019 (259), 2020 (28!), 2021 (259), 2024 (110), 2025 (261)

**Ausentes: 2022 e 2023** → a média calculada from-scratch seria enviesada.

O fixture `embi_medias.csv` tem o valor consolidado ANEEL (2,7649 %) que presume dados completos de 2022 e 2023 da fonte JPMorgan/BCB. Para replicar completamente from-scratch, precisamos dessas duas séries.

**2020 tem apenas 28 observações** (Nov–Dez), sugerindo que o fixture foi preenchido parcialmente. O C2 live usa `ano_atual` (2017–2026 YTD) e contorna o problema, mas o C1 histórico depende do fixture completo.

### 3.3 Como fechar o gap

Fontes alternativas para 2022–2023:
- **BCB (Banco Central):** SGS série 28763 (EMBI+, daily) — API pública
- **Federal Reserve:** FRED código `JPEMBIBRABD`
- **JP Morgan direto:** requer licença

---

## 4. Beta — Metodologia em detalhe

### 4.1 O que a planilha ANEEL faz

A planilha (aba "Beta") contém:
- Preços Total Return semanais (SPXT + 20+ utilities EUA) de **Set/2008 a Set/2025**
- Para cada janela de 5 anos (Out → Set), calcula **OLS retornos simples semanais** (P_n/P_{n-1}) via `COVARIANCE.S/VAR.S` por empresa vs. SPXT
- Desalavanca com o D/E de **mercado** por empresa (dívida contábil / market cap)
- Pondera as empresas por **D/V contábil** = dívida / (dívida + patrimônio líquido contábil), com cap de 50% por empresa (coluna "Ponderado 50%" na aba Beta, a partir da coluna 87)
- Re-alava com D/E da estrutura de capital do setor elétrico **brasileiro** do ano → beta_l_brasil
- Repete para 13 janelas anuais: 2013, 2014, ..., 2025
- **beta_l final = AVERAGE das 5 janelas mais recentes de beta_l_brasil** (fórmula xlsx: `=AVERAGE('WACC Histórico'!K6:O6)` = anos 2021–2025)

**Resultado 2026:**  
beta_u (janela 2025) = 0,2931 | beta_l_brasil (média 5a) = 0,769239

### 4.2 O que o Python C1 faz

Lê beta_l e beta_u direto de `wacc_aplicacao.csv` e `beta_historico.csv` → ✅ 0,0 bp.

### 4.3 O que o Python C2 faz (ao vivo)

Computa **uma única janela** (Out/2020 → Set/2025, 260 semanas), ponderação **D/V contábil** (metodologia confirmada da ANEEL):

- OLS retornos simples semanais por empresa vs. `^SP500TR`
- Hamada unlever por empresa com D/E de mercado (dívida contábil / market cap)
- Pesos = D/V book = dívida / (dívida + patrimônio líquido contábil), cap 50%

**Resultado C2 atual (jun/2026):**
- beta_u (janela 2025, D/V weighted) = **0,2997** — delta vs ANEEL: **+66bp**
- beta_l (re-alavancado D/E BR) = **0,480** (diagnóstico C2)

**Comprovação da metodologia:** com pesos D/V exatos do xlsx + betas OLS do xlsx → beta_u = 0,293106 (delta 0,0bp). O gap residual de +66bp é inteiramente atribuível a diferenças de dados Bloomberg vs yfinance.

Beta_l publicado (C1) = **0,769** — C2 usa uma única janela recente (menor correlação utilities-S&P500 pós-2021) vs média das 5 janelas históricas da ANEEL.

### 4.4 Causas do gap C1 vs C2 no beta

| Causa | Magnitude estimada | Status |
|---|---|---|
| C2 usa 1 janela vs média de 5 beta_l_brasil ANEEL | Principal — beta_l C2 ≈ 0,48 vs 0,77 publicado | Estrutural |
| Betas individuais yfinance vs Bloomberg | +66bp em beta_u (única janela 2025) | Irredutível sem Bloomberg |
| Datas de balanço diferentes (D/V book) | Incluído nos +66bp acima | Irredutível |
| C2 usa `^SP500TR` (total return, correto) vs ANEEL SPXT | 0bp — ambos são total return | ✅ Resolvido |
| Ponderação por D/V contábil | 0bp — metodologia agora idêntica à ANEEL | ✅ Resolvido (antes +208bp) |

**Progresso da reconciliação do beta_u (janela 2025):**

| Versão | Metodologia de pesos | beta_u C2 | Delta vs ANEEL (0,2931) |
|---|---|---|---|
| Anterior | Market cap | 0,567 | +274bp |
| **Atual** | **D/V contábil (ANEEL)** | **0,2997** | **+66bp** |
| Com dados Bloomberg | D/V contábil + betas Bloomberg | ~0,2931 | ~0bp |

O beta ANEEL de 2026 (0,7692 para beta_l) usa a janela 2025 (Out/2021–Set/2025) com beta_u = 0,2931 — as utilities americanas se correlacionaram pouco com o S&P no ciclo de alta de juros. A média das 5 beta_l_brasil (2021–2025) é o que entra no WACC, não o beta_u individualmente.

### 4.5 Dado faltante: preços históricos por empresa (1997–2025)

A planilha ANEEL contém os preços brutos das 20 utilities na aba "Beta", mas **não foram extraídos como fixture** pelo script `extrair_fixtures.py`. Esse é o principal gap de dados do módulo:

- Sem os preços históricos, não conseguimos replicar as 13 janelas from-scratch
- Só temos o resultado agregado (beta_u por janela) em `beta_historico.csv`
- Para validar se ANEEL usa média simples ou ponderada e qual a seleção exata de empresas, precisamos extrair esses preços

**Ação pendente:** implementar `extrair_beta_prices()` em `scripts/extrair_fixtures.py` (ver plano em `.claude/plans/`).

---

## 5. Custo de Capital de Terceiros — Kd

### 5.1 O que o Python faz (C1)

Lê diretamente do fixture → Kd_deb = 6,0685 %, custo_emissão = 0,5181 %, Kd_ai = 6,5866 % ✅.

### 5.2 O que a planilha ANEEL faz

A aba "Kd" tem uma **amostra de debêntures** do setor elétrico. Para cada debênture:
1. Taxa nominal de emissão (IPCA + spread)
2. Inflação implícita BEI na data de emissão via curva ETTJ (API ANBIMA ou Bloomberg)
3. Taxa real = (1 + nominal) / (1 + BEI) − 1
4. Média ponderada por saldo devedor → Kd_deb

O custo de emissão (0,5181 %) é amortizado sobre o prazo médio da amostra.

### 5.3 Dado faltante: a amostra de debêntures

Não temos a lista de debêntures usada pela ANEEL. O fixture tem apenas o resultado consolidado. Para replicar from-scratch precisaríamos:
- ISIN de cada debênture na amostra
- Séries históricas de ETTJ por data de emissão (ANBIMA)
- Saldo devedor por debênture

**Implicação para C2:** o Kd ao vivo é calculado via regressão `Kd ~ α + β₁×Rf [+ β₂×EMBI]` calibrada sobre o histórico 2013–2025. Com Rf_C2 = 7,60 % → **Kd_ai_C2 = 8,05 %** (+146 bp vs C1). Isso é o principal driver do WACC_ai C2 mais alto.

---

## 6. Fórmulas do WACC — Verificação passo a passo

### 6.1 Custo de capital próprio (Ke)

```
Ke_real_di = Rf + beta_l × PRM
           = 5,1377% + 0,769239 × 6,8481%
           = 5,1377% + 5,2678%
           = 10,4055%   ✅ ref: 10,405%
```

**Nota crítica:** o EMBI **não entra** no numerador do Ke. Essa é a principal diferença da metodologia ANEEL vs formulação acadêmica clássica (Ke = Rf + EMBI + beta × PRM). No ANEEL:
- EMBI está implícito no beta_l via alavancagem americana mais alta
- A fórmula é `Ke = Rf_BR + beta_l_US × PRM_US` sem adição explícita do EMBI

### 6.2 WACC depois de impostos

```
kd_di = Kd_ai × (1 − T) = 6,5866% × 0,66 = 4,3472%

WACC_di = Ke × E/V + Kd_di × D/V
        = 10,4055% × 60,2261% + 4,3472% × 39,7739%
        = 6,2668% + 1,7290%
        = 7,9959%   ✅ ref: 7,996%
```

### 6.3 WACC antes de impostos (resultado final)

```
WACC_ai = WACC_di / (1 − T)
        = 7,9959% / 0,66
        = 12,1150%  ✅ ref: 12,11%
```

**T = 34 %** = IRPJ (15 % + adicional 10 %) + CSLL (9 %). Fixo pela legislação federal.

---

## 7. Comparação C1 (ANEEL) vs C2 (mercado atual)

| Parâmetro | C1 — Despacho 675 | C2 — Live 2026 | Delta | Interpretação |
|---|---|---|---|---|
| Rf | 5,14 % | 7,60 % | +246 bp | NTN-B em máxima histórica; ciclo de alta juros reais |
| PRM | 6,85 % | 6,86 % | +1,6 bp | Fixture Bloomberg acum. 1928; C2 inclui YTD 2026 no 5º ano da janela |
| EMBI+ | 2,76 % | 2,65 % | −12 bp | Compressão YTD 2026 |
| beta_l | 0,769 | 0,511 | −258 bp | 1 janela atual vs 13 históricas; utilities correlação baixa 2021–2025 |
| E/V | 60,2 % | 55,6 % | −47 bp | Alavancagem maior nas utilities (market cap em queda) |
| Kd_ai | 6,59 % | 8,05 % | +146 bp | Regressão: Rf mais alto eleva spread das debêntures |
| Ke | 10,41 % | 10,98 % | +58 bp | Rf alto suplanta ERP menor e beta menor |
| **WACC_ai** | **12,12 %** | **12,82 %** | **+70 bp** | **Sinal: próximo despacho tende a subir** |

**Leitura do sinal C2:** se os parâmetros correntes se mantiverem, o WACC 2027 seria ≈ +70 bp acima do atual. O maior driver de alta é o Rf (+246 bp), parcialmente compensado pela queda do beta (−258 bp) que já começou a entrar nas janelas mais recentes.

---

## 8. Gaps de dados e dependências Bloomberg

### 8.1 Mapa de dependências

| Dataset | Disponível | Fonte alternativa | Impacto |
|---|---|---|---|
| NTN-B diário (2016–2025) | ✅ Tesouro Nacional | — | Rf |
| EMBI+ diário (2016–2021, 2024–2025) | ✅ IPEADATA | — | EMBI |
| EMBI+ 2022–2023 | ❌ **ausente** | BCB/FRED | EMBI (+2 anos) |
| EMBI+ 2020 (só 28 obs) | ⚠️ incompleto | BCB série 28763 | EMBI (Nov–Dez 2020 apenas) |
| Preços Total Return utilities EUA (1997–2025) | ❌ **não extraído** | yfinance (parcial, 2020+) | Beta (13 janelas) |
| D/E histórico por empresa por janela | ❌ Bloomberg | yfinance balance_sheet | Beta (Hamada) |
| Amostra de debêntures ANEEL (IDs, saldos, emissões) | ❌ ANEEL/Bloomberg | — | Kd bottom-up |
| ETTJ por data de emissão das debêntures | ❌ ANBIMA histórico | ANBIMA API (parcial) | Kd bottom-up |
| PRM S&P500 ao vivo (escala compatível com fixture) | ❌ escala incompatível | ECB SDW `FM.M.US.USD.4F.BB.US10YT_RR.YLDA` + yfinance normalizado | PRM C2 live |
| Curva DI futuro (B3) | ❌ sem fetcher | B3 Market Data / Bloomberg | Rf nominal C3 |

### 8.2 Prioridade de resolução

1. **Alta — EMBI 2022–2023:** BCB SGS série 28763 tem API pública gratuita. Fechar esse gap elimina a dependência do fixture para o cálculo from-scratch.
2. **Alta — Preços Total Return utilities:** extrair `beta_prices_aneel.csv` da planilha ANEEL (script já planejado). Permite replicar as 13 janelas do zero e validar metodologia (simples vs ponderada).
3. **Média — D/E histórico por empresa:** yfinance `balance_sheet` retorna 4 anos de dados trimestrais. Para janelas antes de 2021, precisaríamos de dados históricos (Compustat/Bloomberg).
4. **Baixa — Kd bottom-up:** depende de dados proprietários (amostra ANEEL + ETTJ histórico). Dificilmente viável sem acesso à planilha ANEEL completa ou Bloomberg.

---

## 9. Como melhorar o produto (próximos ciclos)

### 9.1 Validação da metodologia Rf (prioridade 1)

**Problema:** gap de +20,8 bp entre Python from-scratch e ANEEL publicado.

**Solução:** inspecionar na planilha ANEEL qual filtro de vencimentos é aplicado:
- Hipótese principal: exclusão de vencimentos < 2 anos (remove o outlier de 2025 que distorce para cima)
- Implementar o filtro em `calcular_rf_historico()` e verificar se o gap fecha

**Como testar na planilha:**
1. Abrir aba "WACC para Aplicação" → célula do Rf → rastrear fórmula
2. Ou abrir aba "NTN-B" (se existir) e verificar quais vencimentos estão incluídos
3. Comparar com os 9 vencimentos que temos no fixture

### 9.2 Extração dos preços de beta (prioridade 1)

Implementar `extrair_beta_prices()` em `scripts/extrair_fixtures.py`:

```python
def extrair_beta_prices():
    """
    Aba "Beta": linha 7 = header, colunas 1–20 = tickers, coluna 23 = SPXT.
    2177 linhas de preços semanais Set/2008 → Set/2025.
    Salva em data/fixtures/beta_prices_aneel.csv
    """
    ws = _wb()["Beta"]
    header = list(ws.iter_rows(min_row=7, max_row=7, values_only=True))[0]
    tickers = [str(header[i]) for i in range(1, 21) if header[i]]
    records = []
    for row in ws.iter_rows(min_row=8, values_only=True):
        if not isinstance(row[0], datetime): continue
        rec = {"data": row[0].date()}
        for i, t in enumerate(tickers, 1):
            rec[t] = float(row[i]) if isinstance(row[i], (int, float)) else None
        rec["SPXT"] = float(row[23]) if isinstance(row[23], (int, float)) else None
        records.append(rec)
    pd.DataFrame(records).to_csv(OUT / "beta_prices_aneel.csv", sep=SEP, index=False)
```

Com esse arquivo:
- Replicar as 13 janelas exatas da ANEEL
- Descobrir se a ponderação é simples ou market cap
- Entender quais 20 empresas exatas são usadas (algumas podem ter sido substituídas ao longo dos anos)
- Estender para 2026 com yfinance e calcular o beta prospectivo

### 9.3 EMBI 2022–2023 via BCB (prioridade 2)

```python
def fetch_embi_bcb(start="2022-01-01", end="2023-12-31") -> pd.DataFrame:
    """
    BCB SGS série 28763 — EMBI+ (Risco-Brasil) diário.
    Endpoint: https://api.bcb.gov.br/dados/serie/bcdata.sgs.28763/dados
    Retorna: DataFrame com colunas data, embi_decimal
    """
    url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.28763/dados"
    params = {"formato": "json", "dataInicial": start, "dataFinal": end}
    resp = requests.get(url, params=params, timeout=30)
    data = resp.json()
    df = pd.DataFrame(data)
    df["data"] = pd.to_datetime(df["data"], dayfirst=True)
    df["embi_decimal"] = pd.to_numeric(df["valor"]) / 100
    return df[["data", "embi_decimal"]]
```

### 9.4 Alinhamento C2 beta com metodologia ANEEL (prioridade 2)

O principal problema do beta C2 é usar **1 janela recente** vs **13 janelas históricas** da ANEEL. Quando o fixture estiver extraído:

```python
def calcular_beta_13_janelas_ao_vivo(prices_aneel_df, prices_recentes_df):
    """
    Concatena preços ANEEL (1997–2025) + yfinance (2025–hoje).
    Para cada janela 2013–ano_atual: OLS 5a, Hamada com D/E por empresa.
    Retorna beta_u_mean das N janelas disponíveis.
    """
    df_full = pd.concat([prices_aneel_df, prices_recentes_df]).drop_duplicates("data")
    resultados = {}
    for ano_fim in range(2013, datetime.now().year + 1):
        start = pd.Timestamp(f"{ano_fim - 5}-10-01")
        end   = pd.Timestamp(f"{ano_fim}-09-30")
        slice_df = df_full[(df_full.index >= start) & (df_full.index <= end)]
        if len(slice_df) < 200: continue
        # OLS por empresa + Hamada
        resultados[ano_fim] = calcular_beta_janela(slice_df, ...)
    return np.mean(list(resultados.values()))
```

### 9.5 Dashboard — melhorias de produto

Com os dados consolidados, o dashboard pode exibir:

**Aba C1 — Replicação:**
- Tabela paramétrica com badge `OK` / `WARN` por parâmetro
- Detalhamento Rf: gráfico de vencimentos vs taxa por ano
- Detalhamento Beta: gráfico de beta_u por janela (2013–2025)

**Aba C2 — Radar de mercado:**
- Gauge "WACC corrente vs publicado" (+70 bp hoje)
- Waterfall: quais parâmetros sobem e quais caem vs C1
- Tabela por empresa: beta_l, R², D/E, peso — com filtro por ticker

**Aba C3 — Vetor 30 anos:**
- Gráfico de linha: WACC_t ao longo de 2026–2055
- Sensibilidade: sliders para Rf, ERP, beta

**Exportação:**
- Botão "Gerar trilha de cálculo" → baixa os 3 CSVs em ZIP
- Botão "Comparar com planilha ANEEL" → diff linha a linha dos parâmetros

---

## 10. Referências e arquivos do módulo

```
engine/Calculadora WACC Regulatório/
├── CLAUDE.md                          ← guia de trabalho do módulo
├── WACC_Regulatorio_Whitepaper.md     ← metodologia completa (v3.0)
├── ENGINE_CONTEXT.md                  ← contexto do produto
├── trilha_calculo_2026.txt            ← trilha texto (passo a passo)
├── memoria_calculo_wacc_2026.csv      ← CSV resumo (58 linhas, 15 colunas)
├── memoria_granular_wacc_2026.csv     ← CSV granular (1.813 linhas)
├── memoria_beta_acoes_wacc_2026.csv   ← CSV retornos ações (4.963 linhas)
│
├── dashboard.py                       ← Streamlit 3 abas
├── scripts/
│   ├── extrair_fixtures.py            ← extrai planilha ANEEL → CSVs
│   ├── trilha_calculo.py              ← gera os 3 CSVs + txt
│   └── test_camadas.py                ← teste integrado C1+C3
│
└── wacc_regulatorio/
    ├── camada1_replicacao.py          ← C1: replica ANEEL exato (0 bp)
    ├── camada2_corrente.py            ← C2: dados ao vivo
    ├── camada3_vetor.py               ← C3: projeção 30 anos
    ├── validator.py                   ← valida C1 vs Despacho
    ├── wacc_calc.py                   ← fórmulas WACC
    ├── config.py                      ← constantes e paths
    ├── params/
    │   ├── rf.py                      ← NTN-B → Rf
    │   ├── erp.py                     ← ERP Damodaran
    │   ├── embi.py                    ← EMBI+ IPEADATA
    │   ├── beta.py                    ← OLS + Hamada + mktcap
    │   └── kd.py                      ← Kd debêntures + regressão
    └── data/
        ├── fixtures/                  ← CSVs extraídos da planilha ANEEL
        │   ├── ntnb_historico.csv
        │   ├── embi_diario.csv
        │   ├── embi_medias.csv
        │   ├── beta_historico.csv     ← beta_u por janela 2013–2026
        │   └── wacc_aplicacao.csv     ← parâmetros publicados por ano
        ├── fetchers.py                ← APIs ao vivo (yfinance, IPEADATA, Damodaran, Tesouro)
        └── cache/                     ← pickles TTL 1d/7d
```

---

## 11. Perguntas para a planilha ANEEL (checklist de estudo)

Ao abrir `anexo-despacho-1174-2026-aneel-2-Anexo_Memoria_de_Calculo_WACC_2026.xlsx`:

**Rf:**
- [ ] Qual aba contém os dados NTN-B? Há filtro de prazo mínimo/máximo?
- [ ] Existe ponderação por volume financeiro ou por prazo?
- [ ] A célula do Rf no WACC para Aplicação referencia média simples ou outra função?

**Beta:**
- [ ] Aba "Beta": quais colunas têm os tickers exatos? Há substituições ao longo das 13 janelas?
- [ ] Como é feita a desalavancagem — usa D/E contábil ou D/E de mercado por empresa?
- [ ] A ponderação final é simples ou por market cap?
- [ ] O benchmark é SPXT (total return) ou SPX (price)?

**Kd:**
- [ ] Qual aba lista as debêntures da amostra? Quantas são?
- [ ] A BEI é calculada por interpol da curva ETTJ ou por outra proxy?
- [ ] O custo de emissão (0,5181 %) tem memória de cálculo? Qual prazo médio?

**EMBI:**
- [ ] A série usada é diária ou mensal?
- [ ] Qual é a fonte exata: JPMorgan, BCB ou outra?
- [ ] Há algum ajuste para feriados ou gaps?

---

*Documento gerado por `scripts/trilha_calculo.py` + contexto da sessão. Próximo passo recomendado: extrair `beta_prices_aneel.csv` e resolver o gap de Rf (+20,8 bp).*
