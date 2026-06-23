# WACC Regulatório — Metodologia e Implementação
## Despacho ANEEL 675/2026 — Transmissão de Energia Elétrica

> **Versão:** 3.0 | **Data:** junho/2026  
> **Referência normativa:** Despacho ANEEL 675/2026 (retificado pelo 1174/2026)  
> **Resultado replicado:** WACC real antes de impostos = **12,11%** (Transmissão) · Delta < 1bp

---

## 1. Contexto Regulatório

A Agência Nacional de Energia Elétrica (ANEEL) atualiza anualmente a Taxa Regulatória de Remuneração do Capital (WACC) por meio de despacho publicado no Diário Oficial. Esse WACC remunera o capital investido em ativos de transmissão e distribuição de energia elétrica, sendo componente direto da Receita Anual Permitida (RAP).

A metodologia é definida pelo módulo 9 do PRORET (Procedimentos de Regulação Tarifária) e segue o modelo CAPM internacionalizado, com parâmetros coletados nos mercados americano e brasileiro.

### 1.1 Estrutura do WACC publicado

| Grandeza | Símbolo | Valor 2026 (Transmissão) |
|----------|---------|--------------------------|
| WACC real depois de impostos | WACC_di | **8,00%** |
| WACC real antes de impostos | WACC_ai | **12,11%** |

A grandeza relevante para o solver BRR × WACC_t é o **WACC_ai**.

### 1.2 Ano base vs. publicação

O WACC publicado em 2026 usa dados coletados até 31/dez/2025. A janela de coleta de cada parâmetro é descrita na seção 2.

---

## 2. Metodologia Detalhada por Parâmetro

### 2.1 Taxa Livre de Risco — Rf

**Resultado 2026:** `Rf = 5,138%`

#### Fonte
Notas do Tesouro Nacional série B (NTN-B), indexadas ao IPCA. Dados: taxa de compra manhã, diária, todos os vencimentos ativos. Série histórica desde 2004; vencimentos de 2006-08-15 até 2060-08-15.

#### Fórmula — 3 etapas (dupla suavização)

A ANEEL aplica **dupla suavização**: primeiro calcula médias rolantes de 10 anos de
rf_spot, depois faz a média das últimas 5 rolantes. Fórmula confirmada na célula K6
da aba "WACC para aplicação": `=AVERAGE('WACC Histórico'!K5:O5)`.

**Etapa 1 — rf_spot anual** (média dos vencimentos, média diária do ano):
$$rf\_spot[k] = \frac{1}{n} \sum_{i=1}^{n} \overline{r_{i,k}}$$

**Etapa 2 — rf_rolling** (média de 10 anos de rf_spot, armazenada em "WACC Histórico"):
$$rf\_rolling[k] = \frac{1}{10} \sum_{j=k-9}^{k} rf\_spot[j]$$

**Etapa 3 — Rf final** (média das 5 rf_rolling consecutivas terminando em P-1):
$$R_f(P) = \frac{1}{5} \sum_{k=P-5}^{P-1} rf\_rolling[k]$$

A janela efetiva resultante é de **~14 anos** com ponderação trapezoidal: os anos
centrais (2019-2020, Rf ≈ 3,45%) têm peso máximo 5/50 e só saem completamente da
janela por volta de **2034**.

#### rf_rolling histórico (médias rolantes 10a — "WACC Histórico")

| Ano rolling (k) | Janela spot | rf_rolling[k] |
|---|---|---|
| 2021 | 2012–2021 | 4,863% |
| 2022 | 2013–2022 | 5,050% |
| 2023 | 2014–2023 | 5,177% |
| 2024 | 2015–2024 | 5,235% |
| 2025 | 2016–2025 | 5,363% |
| **Rf WACC 2026** | **média 2021–2025** | **5,138% ✓** |

#### Rf anual spot (taxa média do ano, sem janela rolante)

| Ano | rf_spot |
|-----|---------|
| 2016 | 6,275% |
| 2017 | 5,422% |
| 2018 | 4,962% |
| 2019 | 3,451% |
| 2020 | 3,448% |
| 2021 | 4,267% |
| 2022 | 5,830% |
| 2023 | 5,843% |
| 2024 | 6,361% |
| 2025 | 7,595% |

A taxa spot 2025 (~7,6%) é significativamente mais alta que a média rolante (5,138%) porque os anos de baixa taxa (2019-2020) ainda estão na janela. À medida que esses anos saem e novos entram, a média rolante sobe — o que explica a trajetória ascendente do WACC nas projeções da Camada 3.

> **Nota de implementação:** A ANEEL inclui na média diária NTN-B com yield real negativo — inclusive títulos próximos ao vencimento como o NTNB 2020-08-15, que registrou taxa negativa durante o COVID (ex: −3,06% em agosto/2020). A função `calcular_rf_anual_10a()` não aplica filtro de piso; remove apenas `NaN` e taxas > 25% (claramente incorretas). Inserir um filtro `>= 0,01` causaria gap de **+3,64bp** na média 2021–2025.

---

### 2.2 Prêmio de Risco de Mercado — PRM

**Resultado 2026 (ANEEL):** `PRM = 6,848%` · delta = **0bp**  
**Corrente (C2, fixture atualizado):** `PRM ≈ 6,864%` · delta = **+1,6bp**

#### Fonte
- **S&P500 Total Return:** Bloomberg `TOT_RETURN_INDEX_GROSS_DVDS` (base ≈ 17,66 em dez/1927)
- **US Treasury 10Y:** ECB SDW `FM.M.US.USD.4F.BB.US10YT_RR.YLDA` (mensal, em %)

Ambas as séries estão no fixture `prm_sp500.csv` extraído da planilha ANEEL (1.200+ observações mensais, 1927–2025).

#### Fórmula — estrutura de dupla média (análoga ao Rf)

**PRM mensal:**
$$\text{PRM}\_{\text{mensal},t} = \frac{S\&P500_t - S\&P500_{t-12}}{S\&P500_{t-12}} - \frac{R_{f,10Y,t}}{100}$$

**PRM acumulado até dez/X:**
$$\text{PRM}\_{\text{acum},X} = \frac{1}{N_X} \sum_{t=\text{jan}/1929}^{\text{dez}/X} \text{PRM}\_{\text{mensal},t}$$

**PRM publicado (P = ano publicação):**
$$\text{PRM}(P) = \frac{1}{5} \sum_{X=P-5}^{P-1} \text{PRM}\_{\text{acum},X}$$

A janela interna é **acumulada desde 1928** (não rolante de 10 anos como no Rf).

**Valores anuais acumulados (WACC 2026):**

| Ano acum. X | PRM acum. até dez/X |
|---|---|
| 2021 | 6,8831 % |
| 2022 | 6,7531 % |
| 2023 | 6,7300 % |
| 2024 | 6,9100 % |
| 2025 | 6,9640 % |
| **Média (WACC 2026)** | **6,8481 %** ✓ |

> **Implementação C1:** Usa o fixture `prm_sp500.csv` (série 1928–2025 extraída da planilha ANEEL), chamando `calcular_prm(2026, prm_df)`. Em C3, o PRM usa o valor do último despacho por default (parâmetro em `params/estruturais.py`).

> **Implementação C2:** `fetch_prm_sp500tr_incremento(prm_df_base)` estende o fixture com o retorno YTD do `^SP500TR` via yfinance usando **incremento percentual** sobre o último valor da série — evitando escalas incompatíveis entre Bloomberg (base ~17,66 em 1928) e yfinance (base ~16.000). Se a busca ao vivo falhar, o fallback usa o fixture até dez/2025 (`erp_fonte = "fixture (fallback)"`). Resultado: PRM C2 ≈ +1,6bp vs C1 (variação esperada com dados YTD do ano corrente).

O PRM histórico é extremamente estável — variação típica < 10bp/ano — e não é sensibilizado em projeções de longo prazo.

---

### 2.3 Prêmio de Risco Brasil — EMBI+

**Resultado 2026 (ANEEL):** `EMBI = 2,765%`  
**Corrente (C2 YTD 2026):** `EMBI ≈ 2,645%`

#### Fonte
Série IPEADATA `JPM366_EMBI366` (JP Morgan Emerging Market Bond Index Plus).

> **Nota de API:** A API IPEADATA retorna valores em bps inteiros (ex: 276 para 2,76%). A conversão correta é `÷ 10000` para decimal — não `÷ 100`.

#### Fórmula

$$\text{EMBI} = \frac{1}{T} \sum_{d \in [\text{ano}-9, \text{ano}]} \text{embi}_d$$

Média aritmética dos spreads diários dos últimos **10 anos** encerrados no ano de referência.

#### Diferença C1 vs C2

| Camada | Janela | EMBI |
|--------|--------|------|
| C1 (ANEEL 2026) | 2016–2025 (completo) | 2,765% |
| C2 (corrente) | 2017–2026 (YTD jun/2026) | ~2,645% |

A janela C2 exclui 2016 (EMBI mais alto: ~4,3%) e inclui 2026 YTD (EMBI mais baixo: ~2,2%), explicando o spread menor.

O EMBI é o principal parâmetro de cenário na Camada 3 (`embi_delta`).

---

### 2.4 Beta Desalavancado e Estrutura de Capital

**Resultados 2026 (ANEEL):**
```
beta_u (desalavancado, D/E americano)  = 0,3022
beta_l (re-alavancado, D/E americano)  = 0,7692
E/V (estrutura regulatória)            = 60,23%
D/V (estrutura regulatória)            = 39,77%
```

**Corrente (C2, yfinance jun/2026):**
```
beta_u (desalavancado, D/E spot)       ≈ 0,30
beta_l (re-alavancado, D/E spot)       ≈ 0,50
E/V (estrutura corrente)               ≈ 57,2%
D/V (estrutura corrente)               ≈ 42,8%
```

#### Amostra
21 utilities americanas do setor elétrico (AEE, AEP, CHG, CNP, ED, EIX, ES, ETR, EXC, FE, IDA, NEE, NWE, OGE, PCG, PEG, POM, PPL, PNW, HE, D). Benchmark: S&P500. CHG foi adquirida em 2012 e não tem dados de preço via yfinance — tratada como ausente.

#### Metodologia ANEEL — 5 passos (C1)

**1. Beta alavancado por empresa (OLS, retornos semanais, janela 5 anos):**

Confirmado na planilha ANEEL, aba Beta: `25/09/2020 A 25/09/2025`. Cada estimativa anual usa 5 anos de retornos semanais contra o S&P500 Total Return (SPXT Bloomberg).

$$\beta_{l,i} = \frac{\text{Cov}(R_i, R_{S\&P500})}{\text{Var}(R_{S\&P500})}$$

**2. D/E de mercado por empresa (book debt / market cap, trimestre mais recente):**

$$D/E_i = \frac{\text{Dívida Contábil}_i}{\text{Market Cap}_i}$$

**3. Desalavancagem Hamada por empresa:**

$$\beta_{u,i} = \frac{\beta_{l,i}}{1 + (1-T) \times D/E_i} \quad T = 34\%$$

**4. Ponderação por D/V contábil (cap 50% por empresa), confirmada na aba Beta do xlsx:**

$$\beta_{u,t} = \sum_i w_{i,t} \cdot \beta_{u,i,t}, \quad w_{i,t} = \min\!\left(\frac{DV\text{book}_{i,t}}{\sum_j DV\text{book}_{j,t}},\, 0{,}50\right) \text{ normalizado}$$

onde $DV\text{book}_i = \dfrac{\text{Dívida Contábil}_i}{\text{Dívida Contábil}_i + \text{Patrimônio Líquido}_i}$ ("Ponderado 50%" na aba Beta, coluna 87+).

$$\beta_{l,BR,t} = \beta_{u,t} \times (1 + (1-T_{BR}) \times D/E_{BR,t})$$

**5. beta_l final = média das 5 beta_l_brasil mais recentes (fórmula ANEEL confirmada):**

$$\beta_l(P) = \frac{1}{5} \sum_{t=P-5}^{P-1} \beta_{l,BR,t}$$

> **Confirmado via fórmula do xlsx:** `=AVERAGE('WACC Histórico'!K6:O6)` = média dos 5 anos 2021–2025 de beta_l_br já re-alavancado por janela. Para 2026: mean(0.758, 0.748, 0.771, 0.776, 0.793) = 0.769239 ≈ 0.769238 publicado (delta 0.01bp). A ponderação por D/V contábil aplicada com os pesos exatos do xlsx → beta_u janela 2025 = 0.293106 (delta 0.0bp vs planilha ANEEL).

**6. Re-alavancagem com D/E brasileiro do ano:**

$$\beta_{l,BR,t} = \beta_{u,t} \times (1 + (1-T_{BR}) \times D/E_{BR,t})$$

O D/E brasileiro (~0,66, D/V = 39,77% publicado) é menor que o americano (~0,33 de D/V das utilities). O gap de alavancagem incorpora implicitamente o risco-país ao beta (ver seção 3.3).

#### Implementação por camada

| Camada | Beta | Fonte |
|--------|------|-------|
| **C1** | `beta_l = 0,7692`, `beta_u = 0,3022` | Fixtures `wacc_aplicacao.csv` + `beta_historico.csv` (valores publicados ANEEL) |
| **C2** | Calculado ao vivo, janela 5 anos Oct-Sep mais recente, ponderação **D/V contábil** (D/(D+book_equity)), cap 50% | `fetch_market_caps()` (retorna `dv_book`) + `calcular_beta_mktcap_window()` via yfinance |
| **C3** | `beta_l` e `E/V` congelados no último publicado | Fixture `wacc_aplicacao.csv` |

---

### 2.5 Custo de Capital de Terceiros — Kd

**Resultado 2026 (Transmissão):**
```
Kd_debêntures   = 6,069%
Custo emissão   = 0,518%
Kd_real_ai      = 6,587%   (antes de impostos)
Kd_real_di      = 4,347%   (depois de impostos = 6,587% × 0,66)
```

#### Fonte
663 debêntures do setor elétrico (266 Transmissão, 397 Distribuição), emissões desde 2003.

#### Fórmula

```
BEI_prazo      = inflação implícita ETTJ ANBIMA para o prazo da debênture
taxa_real_i    = (1 + taxa_nominal_i) / (1 + BEI_prazo) - 1
Kd_deb         = mean(taxa_real_i)            janela rolante 10 anos (média aritmética simples)
custo_emissão  = IPCA+DI agregado (pré-computado pelo ANEEL no xlsx, por janela)
Kd_real_ai     = Kd_deb + custo_emissão
```

> **Nota de implementação — custo de emissão:** A coluna "IPCA+DI" da aba "Custo de Emissao" do xlsx contém um valor **pré-computado pelo ANEEL** (referência absoluta) — não é derivável pela média de `remuneracao_real` das debêntures individuais. Qualquer ponderação (simples, por valor emitido, por prazo, só segmento T ou todos os segmentos) diverge ~+0,8bp. O fixture `custo_emissao_periodos.csv` armazena os 14 valores corretos por janela; `calcular_kd_com_custo_emissao()` usa-o quando `periodos_df` é fornecido (C1). Em C2/C3, o fallback é a média simples de `remuneracao_real` (~+0,8bp acima do valor ANEEL, diferença estrutural documentada).

#### Camada 2 — Basket Inference Engine

A Camada 2 usa a mesma metodologia bottom-up da ANEEL, aplicada ao snapshot corrente de mercado:

1. **Universo**: todas as debêntures negociadas no secundário ANBIMA (via API, quando credenciais disponíveis), enriquecido com os campos `empresa` e `area` do fixture histórico.
2. **Inferência da cesta**: cada debênture recebe uma categoria:
   - `A` — transmissora confirmada (empresa ∈ fixture área=T); forma o cenário **base**
   - `B` — candidata por keyword ("TRANSMISS", "LINHAS DE ENERGIA" etc.); forma o cenário **amplo** (A+B)
   - `C` — override manual do usuário; forma o cenário **custom** (A+C)
   - `X` — excluída (distribuidora, fora da janela, taxa_real ausente)
3. **Cálculo**: `Kd_deb = mean(taxa_real)` por cenário (mesmo mean simples da ANEEL); `Kd_real_ai = Kd_deb + custo_emissão`.
4. **Atualização de yields**: para debêntures ativas, a taxa_real da fixture (emissão histórica) pode ser substituída pelo yield corrente de mercado quando o API ANBIMA estiver disponível.

O cenário **base** tem prioridade A > C — overrides do usuário não alteram a cesta de transmissoras confirmadas, apenas adicionam casos específicos ao cenário custom.

#### Regressão preditiva (Camada 3 apenas)

Calibrada com histórico 2013-2025 (13 observações):

$$K_{d,ai} = 3{,}327\% + 0{,}621 \times R_f \quad (R^2 = 0{,}763)$$

O coeficiente $\beta_1 = 0{,}621$ captura o co-movimento entre a curva NTN-B real e o custo de crédito doméstico. Usada exclusivamente na Camada 3 (projeção forward), onde não existem debêntures futuras a observar.

---

## 3. Montagem do WACC

### 3.1 Fórmula completa

$$K_e^{di} = R_f + \beta_l \cdot \text{PRM}$$

$$K_d^{di} = K_{d,ai} \cdot (1 - T)$$

$$\text{WACC}_{di} = K_e^{di} \cdot \frac{E}{V} + K_d^{di} \cdot \frac{D}{V}$$

$$\text{WACC}_{ai} = \frac{\text{WACC}_{di}}{1 - T}$$

### 3.2 Cálculo numérico — WACC 2026 Transmissão (C1)

```
Ke_di = 5,138% + 0,7692 × 6,848%   (PRM = 6,848%)
      = 5,138% + 5,268%
      = 10,405%

Kd_di = 6,587% × 0,66 = 4,347%

WACC_di = 10,405% × 60,23% + 4,347% × 39,77%
        = 6,267% + 1,729%
        = 7,996%

WACC_ai = 7,996% / 0,66 = 12,115%  ≈  12,11% ✓
```

### 3.3 WACC corrente implícito (C2 — junho/2026)

```
Rf     = 5,248%   (NTN-B 5ax10a, calcular_rf_media_5a(2027, ntnb), +10,9bp vs C1)
PRM    = 6,864%   (fixture prm_sp500.csv, calcular_prm(2027), +1,6bp vs C1)
EMBI   = 2,645%   (IPEADATA média 10a YTD jun/2026)
Beta_l = 0,480    (yfinance D/V contábil weighted, janela out/2020-set/2025; beta_u=0,300)
E/V    = 60,2%    (estrutura regulatória publicada — fixture; D/V = 39,8%)
Kd_ai  = 8,047%   (regressão: 3,327% + 0,621 × Rf_C2_spot)

Ke_di  = 5,248% + 0,480 × 6,864% = 8,543%
WACC_di = 8,543% × 60,2% + 8,047% × 0,66 × 39,8% = 7,254%
WACC_ai = 7,254% / 0,66 ≈ 10,991%
Delta vs publicado: ~−112bp  →  tendência: CAINDO (beta_l menor domina)

Nota: beta_u C2 = 0,300 (+66bp vs ANEEL 0,2931). Gap residual = betas Bloomberg vs yfinance.
```

### 3.4 Sobre o EMBI na fórmula do Ke

A ANEEL não adiciona EMBI explicitamente ao Ke. O risco-país está incorporado via **re-alavancagem com D/E americano** mais alto (~2,35 vs. 0,66 do Brasil):

| Formulação | β_l | Ke | Resultado |
|------------|-----|----|-----------|
| ANEEL (implementada) | 0,769 | Rf + β_l × PRM | **10,405%** |
| Acadêmica equivalente | 0,548 | Rf + β_l × (PRM + EMBI) | **10,405%** |

Ambas convergem para o mesmo Ke. A ANEEL usa a primeira porque a amostra americana já embute o risco de mercado desenvolvido via D/E elevado.

---

## 4. Arquitetura do Módulo

### 4.1 Três camadas funcionais

```
Camada 1 — Replicação histórica
    Entrada: fixtures extraídos da planilha ANEEL (zero chamadas externas)
    Saída:   WACCResult · WACC_ai = 12,115% (delta < 1bp vs. publicado)
    Parâmetros:
        Rf     → wacc_historico.csv (dupla suavização pré-calculada ANEEL)
        PRM    → wacc_aplicacao.csv (publicado no despacho)
        EMBI   → embi_medias_anuais.csv (média 10a pré-calculada ANEEL)
        Beta_l → wacc_aplicacao.csv; Beta_u → beta_historico.csv
        Kd     → fixture debentures + custo_emissao
    Uso:     Validação da metodologia, auditoria regulatória

Camada 2 — WACC corrente implícito
    Entrada: APIs ao vivo + fixtures como fallback
    Saída:   snapshot WACC_ai atual + delta vs. despacho + tendência + cenários Kd
    Parâmetros:
        Rf     → Tesouro Nacional (NTN-B spot YTD)
        PRM    → calcular_prm(fixture prm_sp500.csv) — 5 médias anuais acumuladas desde 1928
        EMBI   → IPEADATA JPM366_EMBI366 (média 10a YTD)
        Beta   → yfinance: OLS 5a + D/V contábil weighted (D/(D+book_equity), cap 50%) + Hamada por empresa
        Kd     → basket inference: cesta A/B/C/X inferida do universo ANBIMA
                   cenário base (A): mean(taxa_real) das transmissoras confirmadas
                   cenário amplo (A+B): inclui candidatas por keyword
                   cenário custom (A+C): base + overrides do usuário
    Uso:     Radar de mercado; antecipação do próximo despacho ANEEL

Camada 3 — Vetor projetado 30 anos
    Entrada: Rf rolling projetado + cenários EMBI + regressão Kd~Rf
    Saída:   DataFrame anual pd.PeriodIndex(freq='Y') — WACC_antes_impostos
    Parâmetros estruturais congelados: ERP, Beta_l, E/V (fotografias de mercado)
    Uso:     Input direto para solver BRR × WACC_t no motor de projeção RAP
```

### 4.2 Relação C1 · C2 · C3

Esta é a chave para interpretar corretamente os três outputs:

| | Rf usado | PRM | Beta_l | Resultado WACC_ai |
|---|---|---|---|---|
| C1 (publicado) | Média de 5 rf_rolling[2021..2025] = 5,138% | 6,848% (fixture) | 0,769 (fixture) | **12,11%** |
| C3 ano 1 | Idem C1 (lê rf_rolling_historico) | 6,848% (fixture) | 0,769 (fixture) | **≈ 12,11%** |
| C2 corrente | 5ax10a YTD ≈ 5,248% | 6,864% (fixture prm_sp500) | 0,480 (yfinance D/V contábil) | **~10,99%** |

**C3 começa em C1 (≈12,11%), não em C2 (≈10,99%).** Isso é correto por design:
- C1 e C3 produzem o mesmo WACC_ai no ano 1 porque ambos leem `rf_rolling_historico[2021..2025]` diretamente do fixture — os valores exatos pré-calculados pela ANEEL
- C2 usa Rf 5ax10a e parâmetros de mercado correntes (beta, PRM, EMBI atualizados); o beta_l menor (~0,48 vs 0,77) é o principal driver do C2 mais baixo
- O gap C3[1] − C2 ≈ +112bp reflete principalmente a diferença de beta (média de 5 janelas históricas vs. 1 janela recente)

**C3 converge para C2**, não para C1. À medida que anos com rf_spot ~7,6% substituem anos com ~3-4% (2019-2020) na janela, a média rolante sobe. A convergência de beta (quando a janela 2021-2025 tiver mais peso) tende a comprimir o WACC.

### 4.3 Rf na Camada 3 — janela rolante projetada

Para cada ano de publicação `P` no horizonte, o Rf é calculado em 2 estágios,
replicando a dupla suavização da planilha ANEEL:

```
# Estágio 1 — rf_rolling para cada um dos 5 anos terminando em P-1:
Para k em [P-1, P-2, P-3, P-4, P-5]:
    se k ≤ 2025:
        rf_rolling[k] = wacc_historico.csv["rf"][k]   # valor exato ANEEL
    se k > 2025:
        rf_rolling[k] = mean(rf_spot[k-9..k])          # extrapolação com rf_spot_projetado

# Estágio 2 — Rf final como média das 5 rf_rolling:
Rf[P] = mean(rf_rolling[P-1], rf_rolling[P-2], ..., rf_rolling[P-5])
```

**Exemplos por horizonte:**

| Ano P | Anos históricos (wacc_historico) | Anos extrapolados | fonte_rf |
|---|---|---|---|
| 2026 | 2021, 2022, 2023, 2024, 2025 | 0 | `"ettj"` |
| 2027 | 2022, 2023, 2024, 2025 | 1 (rolling 2026) | `"ettj"` |
| 2030 | 2025 | 4 (rolling 2026-2029) | `"ettj_extrapol"` |
| 2033+ | — | 5 | `"extrapol_longo"` ⚠️ |

O `rf_spot_projetado` padrão é a média dos yields da curva ETTJ/NTN-B atual (~7,6%). O usuário pode configurar cenários (normalização = 5,5%, persistência = 9%) via dashboard ou via parâmetro `rf_spot_projetado` em `projetar_vetor_wacc()`.

A coluna `fonte_rf` indica a confiabilidade do Rf de cada ano:

| `fonte_rf` | Significado |
|---|---|
| `"ettj"` | Até 3 anos projetados na janela — confiável |
| `"ettj_extrapol"` | 4-7 anos projetados — incerteza crescente |
| `"extrapol_longo"` | 8+ anos projetados — extrapolação pura ⚠️ |

### 4.4 Fluxo de dados

```
Planilha ANEEL (.xlsx)
    └── scripts/extrair_fixtures.py
            ├── ntnb_diario.csv           (43k linhas, 2004-2025)
            ├── prm_sp500.csv             (1,2k linhas, 1927-2025)
            ├── embi_diario.csv           (3,7k linhas, 2008-2025)
            ├── embi_medias_anuais.csv    (médias pré-calculadas ANEEL)
            ├── debentures.csv            (663 debêntures D+T)
            ├── custo_emissao.csv         (106 títulos)
            ├── custo_emissao_periodos.csv (14 períodos → IPCA+DI agregado ANEEL)
            ├── wacc_historico.csv        (parâmetros 2013-2025)
            ├── wacc_aplicacao.csv        (valores oficiais 2018-2026)
            ├── beta_historico.csv        (beta_u_eua publicado 2013-2026)
            ├── beta_prices_aneel.csv     (preços semanais 21 utilities + SPXT)
            └── beta_janelas_aneel.csv    (beta_u/beta_l por ticker por janela)

APIs ao vivo (Camada 2)
    ├── Tesouro Nacional  → NTN-B spot (taxas de compra manhã)
    ├── IPEADATA          → EMBI+ série diária (bps, ÷10000 para decimal)
    ├── yfinance          → preços semanais utilities + S&P500; market cap; balanço
    └── ANBIMA            → curva ETTJ (fallback: NTN-B spot dos fixtures)
```

---

## 5. Dashboard Interativo

### 5.1 Estrutura

O dashboard (`dashboard.py`, Streamlit) expõe as três camadas em abas:

**Aba 1 — Validação ANEEL (C1)**
- Gráfico waterfall de decomposição do WACC: Rf×E/V → β×ERP×E/V → Ke×E/V → Kd_di×D/V → WACC_di → ÷(1-T) → WACC_ai
- Tabela completa com delta em bps vs. referência para cada parâmetro
- Badge PASS/FAIL (tolerância ±0,1bp no WACC_ai)

**Aba 2 — WACC Corrente (C2)**
- Métricas ao vivo: WACC_ai, Rf, EMBI+, tendência (↑/→/↓)
- Barras agrupadas: publicado vs. corrente para cada parâmetro
- Build-up waterfall do WACC corrente
- Botão "Atualizar dados" (TTL cache 1h)
- Fonte indicada para cada parâmetro: `[Damodaran]`, `[live-mktcap]`, `[fixture]`

**Aba 3 — Vetor 30 anos (C3)**
- Gráfico de linha com coloração por `fonte_rf` (verde/laranja/vermelho)
- Painel de convergência: C1 | C3 ano 1 | C2 corrente | Gap represado | Ano de convergência
- Anotação no gráfico marcando o ponto de convergência C3 → C2
- Painel inferior: Rf rolling, EMBI, Kd ao longo do tempo, com linha horizontal Rf C2

### 5.2 Controles (sidebar)

| Controle | Parâmetro | Padrão |
|----------|-----------|--------|
| Horizonte | `horizonte_anos` | 30 anos |
| Rf spot projetado | `rf_spot_projetado` | 7,6% (nível ETTJ atual) |
| Choque EMBI | `embi_delta` | desativado |
| Especificação Kd | `kd_spec` | `"simples"` (Kd~Rf) |

---

## 6. Guia de Uso Programático

### 6.1 Setup

```bash
pip install pandas numpy scipy requests yfinance openpyxl streamlit plotly
python scripts/extrair_fixtures.py  # uma vez, com a planilha ANEEL na raiz
```

### 6.2 Camada 1 — Replicação

```python
from wacc_regulatorio.camada1_replicacao import executar_camada1
from wacc_regulatorio.validator import validar

result = executar_camada1(segmento="transmissao")
validar(result)
# → PASS — WACC_ai = 12.115%  (todos os parâmetros ±0,1bp)
```

### 6.3 Camada 2 — Snapshot corrente

```python
from wacc_regulatorio.camada2_corrente import executar_camada2

c2 = executar_camada2()
print(c2)
# WACC atual, delta vs. despacho, tendência (subindo/caindo/estável)
# ERP via Damodaran; Beta via yfinance market cap weighted; EMBI via IPEADATA
```

### 6.4 Camada 3 — Vetor 30 anos

```python
from wacc_regulatorio.camada3_vetor import projetar_vetor_wacc

# Cenário base (taxas ficam flat em 7,6%)
df = projetar_vetor_wacc(horizonte_anos=30)

# Cenário otimista: normalização para 5,5%
df_norm = projetar_vetor_wacc(
    horizonte_anos=30,
    rf_spot_projetado=0.055,
)

# Cenário estresse: choque de crédito + taxas elevadas
df_stress = projetar_vetor_wacc(
    horizonte_anos=30,
    rf_spot_projetado=0.090,
    embi_delta={2027: +0.015, 2028: +0.008},
    kd_spec="embi",
)

# Coluna para o solver BRR × WACC_t
wacc_t = df["WACC_antes_impostos"]
```

**Schema do DataFrame retornado:**

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `WACC_antes_impostos` | float | Input direto para solver BRR |
| `WACC_depois_impostos` | float | Para fluxo de caixa |
| `Rf` | float | Taxa livre de risco (rolling) |
| `ERP` | float | Prêmio de risco (fixture ANEEL) |
| `EMBI` | float | Prêmio risco Brasil (+ delta cenário) |
| `Beta_l` | float | Beta alavancado (fixture ANEEL) |
| `Ke_real_di` | float | Custo equity depois de impostos |
| `Kd_real_ai` | float | Custo dívida antes de impostos |
| `fonte_rf` | str | `"ettj"` / `"ettj_extrapol"` / `"extrapol_longo"` |

Index: `pd.PeriodIndex(freq='Y')` compatível com o motor de projeção RAP.

---

## 7. Limitações e Notas de Cautela

### 7.1 Janela rolante e incerteza crescente

Para um horizonte de 30 anos a partir de 2026:
- Anos 2026-2028: janela quase toda histórica → `"ettj"` (verde)
- Anos 2029-2032: ~4-7 anos projetados → `"ettj_extrapol"` (laranja)
- Anos 2033+: mais da metade projetada → `"extrapol_longo"` (vermelho) ⚠️

O vetor deve ser interpretado como cenário de referência para anos distantes, não como previsão pontual.

### 7.2 rf_spot_projetado é um parâmetro de cenário

O `rf_spot_projetado` (default ≈ 7,6%) assume que as taxas NTN-B ficarão flat no nível atual. Se as taxas normalizarem para ~5,5% nos próximos anos, use `rf_spot_projetado=0.055`. O dashboard permite explorar esses cenários interativamente.

### 7.3 PRM — variação C1 vs C2

O PRM em C1 e C3 é o valor publicado pelo ANEEL (6,8481%, calculado com dados até dez/2025). O PRM em C2 usa `calcular_prm(ano_publicacao_corrente, prm_df)` com o mesmo fixture, mas inclui dados YTD 2026 no 5º ano da janela → PRM ≈ 6,864% (+1,6bp). A variação é pequena e esperada. O PRM histórico varia menos de 10bp/ano — não é sensibilizado em projeções de longo prazo.

### 7.4 Beta C2 — janela única vs. média de 5 janelas ANEEL

A ANEEL calcula beta_l como **média das 5 beta_l_brasil mais recentes** (2021–2025), onde cada beta_l_brasil é o beta_u da janela (5 anos OLS, ponderado por **D/V contábil**) re-alavancado com o D/E brasileiro daquele ano. A C2 usa apenas a **janela mais recente** (out/2020–set/2025) com balanços correntes do yfinance.

O gap residual em C2 (+66bp, beta_u ≈ 0,30 vs ANEEL 0,2931) decorre de diferenças Bloomberg vs yfinance nos betas individuais de cada empresa — não da metodologia de ponderação (que já está correta: D/V contábil, 0.0bp comprovado com pesos do xlsx). O beta_l C2 (~0,50) é menor que o ANEEL (~0,77) principalmente porque usa uma única janela recente (menor correlação utilities-S&P500 pós-2021) em vez da média rolante de 5 janelas históricas.

### 7.5 Escopo atual

Apenas **Transmissão** está implementado e validado. Distribuição é suportada estruturalmente (`segmento="distribuicao"`) mas sem valores de referência no `validator.py`.

---

## 8. Referências

1. ANEEL — **Despacho nº 675/2026**, Memória de Cálculo da Taxa Regulatória de Remuneração do Capital.
2. ANEEL — **Despacho nº 1174/2026** (Retificação do Despacho 675/2026).
3. ANEEL — **PRORET Módulo 9** — Remuneração do Capital.
4. ECB Statistical Data Warehouse — Série `FM.M.US.USD.4F.BB.US10YT_RR.YLDA` — US Treasury 10Y yield (mensal). Disponível em: `sdw.ecb.europa.eu`
5. Bloomberg — S&P500 Total Return Index (`TOT_RETURN_INDEX_GROSS_DVDS`), série mensal desde dez/1927. Fixture extraído da planilha ANEEL em `prm_sp500.csv`.
6. Hamada, R. S. (1972). The Effect of the Firm's Capital Structure on the Systematic Risk of Common Stocks. *Journal of Finance*, 27(2), 435–452.
7. ANBIMA — Estrutura a Termo das Taxas de Juros (ETTJ) — Curva NTN-B implícita.
8. IPEADATA — Série `JPM366_EMBI366` — EMBI+ Risco Brasil (JPMorgan). Valores em bps (÷10000 para decimal).
9. Tesouro Nacional — Portal Tesouro Transparente — Taxas NTN-B históricas.

---

*Documento gerado com base na análise da planilha oficial ANEEL e no módulo `wacc_regulatorio/` implementado e validado. Para dúvidas metodológicas, consultar a Nota Técnica do Despacho 675/2026 e o PRORET Módulo 9.*
