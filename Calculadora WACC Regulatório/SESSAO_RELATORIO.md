# Relatório de Sessão — WACC Regulatório ANEEL
*Estado verificado: 2026-06-19 · Validator C1: PASS ±0bp*

---

## 1. O que foi feito

### P1 — Remoção da função morta `fetch_sp500_treasury`
**Arquivo:** `wacc_regulatorio/data/fetchers.py`

Função de ~50 linhas que buscava dados do Tesouro americano via Yahoo Finance foi removida. Não era chamada em nenhum lugar do código; existia como resquício de uma versão anterior do cálculo de ERP que foi substituída pela série Bloomberg `prm_sp500.csv`. Remoção limpa, sem quebras. C1 PASS ±0bp confirmado.

---

### P2 — Invariante ERP atualizado no CLAUDE.md
**Arquivo:** `CLAUDE.md`

A seção de invariantes dizia que "ERP em C2 é congelado". Isso estava desatualizado: o código já usava `fetch_prm_sp500tr_incremento()` para estender a série histórica com o ano corrente via `^SP500TR`. O invariante foi atualizado para refletir o comportamento real — a linha de código não mudou.

---

### P3 → Kd-mid como fallback C2 (evolução do plano original)
**Arquivos:** `data/fetchers.py`, `params/kd.py`, `camada2_corrente.py`, `dashboard.py`

**Versão original (P3 inicial):** `fetch_universo_anbima` recebeu parâmetro `raise_sem_credenciais: bool = False`. C2 chamava com `raise_sem_credenciais=True` → levantava `RuntimeError` explícito sem credenciais ANBIMA. Dashboard capturava o RuntimeError com instrução de configuração de env vars.

**Evolução nesta sessão (Kd-mid):** o `RuntimeError` como resposta final foi substituído por um fallback útil. C2 agora verifica a presença de credenciais (`tem_anbima = bool(ANBIMA_CLIENT_ID and ANBIMA_CLIENT_SECRET)`) e toma dois caminhos:

| Caminho | Trigger | Kd_fonte | Descrição |
|---------|---------|----------|-----------|
| C2 completo | `ANBIMA_CLIENT_ID` + `ANBIMA_CLIENT_SECRET` no ambiente | `"anbima_live"` | Basket inference com universo ANBIMA ao vivo |
| **Kd-mid** | sem credenciais | `"ettj_atualizado"` | Mesmos 192 títulos ANEEL + BEI atual via ETTJ |

**Invariante preservado:** C2 sem credenciais NÃO colapsa em C1. O Kd-mid usa os mesmos títulos do fixture ANEEL mas recalcula `taxa_real` com o BEI atual da curva ETTJ — capturando o movimento de mercado nas taxas reais dos títulos existentes.

---

### P4 — Basket inference NUNCA testado com credenciais reais
**Status: ABERTO**

`params/kd_cesta.py` foi validado contra o fixture de 663 debêntures mas nunca contra o endpoint ANBIMA real (`/mercado-secundario`). Tamanho do universo real e comportamento das heurísticas A/B/C/X são desconhecidos. Não há plano de resolução sem credenciais de parceiro ANBIMA.

---

### P5 — Renomeação `rf_10y` → `rf_tbill`
**Arquivos:** `data/fixtures/prm_sp500.csv`, `scripts/extrair_fixtures.py`, `data/fetchers.py`, `params/erp.py`, `data/fixtures.py`

O nome `rf_10y` era impreciso: a série histórica 1928–1987 usa T-Bills de 3 meses (Damodaran), não yields de 10 anos. A partir de 1987 a série usa ECB SDW 10Y. O rename para `rf_tbill` comunica a fonte correta.

Colunas afetadas: header do CSV, todas as referências `.csv`, `df["rf_10y"]` → `df["rf_tbill"]`, coluna derivada `rf_10y_dec` → `rf_tbill_dec` em `params/erp.py`. C1 PASS ±0bp após o rename.

---

### Kd-mid — Implementação dos helpers (Blocos 2 e 3)
**Arquivo:** `wacc_regulatorio/params/kd.py`

#### `calcular_taxa_real_ettj(taxa_nominal, prazo_anos, ettj_df) → float`

Helper de conversão nominal → real usando BEI interpolado da curva ETTJ atual:

```
taxa_real = (1 + taxa_nominal) / (1 + BEI_prazo) - 1
BEI_prazo = np.interp(prazo_anos, ettj_df["prazo_anos"], ettj_df["yield_real"])
```

- `taxa_nominal`: decimal (ex: 0.1447 para 14,47%)
- `prazo_anos` é clampado ao range da curva ETTJ disponível (extrapola via valor do extremo, não `nan`)

#### `calcular_kd_ettj_atualizado(ano, deb_df, custo_df, ettj_df, ...) → KdResult`

Lógica por tipo de indexador (verificada contra os 266 títulos T com `taxa_real`):

| Tipo | Condição | Tratamento |
|------|----------|------------|
| DI (248/266) | `taxa_nominal_pct notna` | Recalcula via `calcular_taxa_real_ettj` |
| IPCA (11 de 18) | `taxa_nominal_pct null` | Mantém `taxa_real` da fixture (já é spread real) |
| IPCA (7 de 18) | `taxa_nominal_pct notna` | Recalcula via `calcular_taxa_real_ettj` (caso misto) |

Custo de emissão: mantém valor histórico da fixture (não varia com mercado).

**Verificação de fórmula** contra fixture:
```
CMGT11 (DI, emissão 2006): taxa_nominal_pct=14.47%, inflacao_implicita=4.032%
  calculado: (1.1447)/(1.04032) - 1 = 10.0335%
  fixture:   taxa_real = 10.0335%
  delta: 0.00bp ✓
```

**Resultado do teste Kd-mid vs C1 (ETTJ emergência plana = 5.14%):**
```
Kd-C1 (BEI fixture ANEEL):  kd_deb=6.0685%  kd_ai=6.5947%  n=192
Kd-mid (BEI atual 5.14%):   kd_deb=6.2093%  kd_ai=6.7356%  n=192
Delta Kd-mid vs C1: +14.1bp
```

O +14.1bp reflete a substituição do BEI histórico por uma curva plana de emergência (5.14%). Com a ETTJ ANBIMA real ou NTN-B ao vivo com dados frescos, o resultado será diferente.

---

## 2. O plano (Blocos 1–5)

### Bloco 1 — Inspeção do xlsx (ABERTO, depende de ação do usuário)
Abrir aba **"Debentures "** no xlsx ANEEL e verificar:
1. Fórmula da coluna `inflacao_implicita`: referencia aba de curva ETTJ embutida ou valor fixo por emissão?
2. Confirmar `taxa_real = (1 + taxa_nominal_pct/100) / (1 + inflacao_implicita) - 1`
3. Há sub-aba com curva ETTJ histórica por data de emissão?

**Status:** fórmula confirmada via verificação computacional (delta 0.00bp). A fonte da `inflacao_implicita` (ETTJ em data de emissão via API ANBIMA ou tabela embutida) ainda não foi inspecionada no xlsx.

### Bloco 2 — `calcular_taxa_real_ettj()` ✓ CONCLUÍDO
Implementado em `params/kd.py`. 10 linhas com `np.clip` para evitar extrapolação.

### Bloco 3 — `calcular_kd_ettj_atualizado()` ✓ CONCLUÍDO
Implementado em `params/kd.py`. Lida com DI/IPCA, mantém janela e custo de emissão de C1.

### Bloco 4 — Integração Kd-mid em C2 ✓ CONCLUÍDO
`camada2_corrente.py` reestruturado: bifurcação `tem_anbima` substitui `RuntimeError` hard.

### Bloco 5 — Validação fallback ETTJ ✓ VALIDADO (com ressalva)
`_ettj_fallback_from_ntnb()` produz curva cobrindo prazos 1–40 anos.
**Ressalva:** quando `fetch_ntnb_tesouro()` retorna dados mas sem entradas recentes (cache vazio > 10 dias), cai na curva plana de emergência `yield_real = 5.14%` para todos os prazos. Com dados ao vivo do Tesouro, a curva será escalonada por prazo (NTN-B 2030, 2035, 2040, 2045, 2055, 2060).

**Gate C1 após todos os blocos:** PASS ±0bp ✓

---

## 3. Gap da Planilha ANEEL — Mapa exaustivo

Esta seção documenta **cada divergência** entre a replicação Python e a planilha ANEEL, para cada parâmetro do WACC.

### 3.1 Taxa Livre de Risco (Rf)

**Metodologia ANEEL:**  
Média das 5 médias anuais consecutivas de rolling 10 anos de taxas NTN-B diárias (compra + venda / 2), para todos os vencimentos, do ano P-5 ao P-1 (P = ano de publicação).

**Status C1:** `Rf = 5.1377%` → 0bp delta vs publicado ✓

**Gap C2 (from-scratch):**  
`calcular_rf_media_5a(P, ntnb_all)` replica a estrutura mas diverge em ~+20.8bp porque a planilha ANEEL aplica um **filtro de prazo mínimo desconhecido** sobre os vencimentos NTN-B. A planilha provavelmente exclui NTN-B com prazo residual < X anos da média diária. O valor de X não está documentado no Despacho — precisa de inspeção da aba Rf no xlsx.

**O que falta para C2 Rf = 0bp from-scratch:**  
Identificar o filtro de prazo mínimo na aba "Rf" ou "NTN-B" do xlsx ANEEL e implementar em `params/rf.py → calcular_rf_anual_10a()`.

---

### 3.2 Prêmio de Risco de Mercado (ERP/PRM)

**Metodologia ANEEL:**  
PRM = média geométrica acumulada de (S&P500 retorno anual − T-Bill 3M) desde 1928, calculada 5 vezes (anos P-5 a P-1), depois média aritmética dessas 5 médias.

**Status C1:** `ERP = 6.8481%` → 0bp delta ✓ (usa fixture `prm_sp500.csv`)

**Gap estrutural:**  
A série histórica S&P500 1928–1987 em `prm_sp500.csv` é de fonte Bloomberg Terminal (via planilha ANEEL) e não é reprodutível publicamente com delta=0. O nível base do índice em 1928 (~17.66) difere de qualquer série pública disponível (Yahoo Finance, FRED, Shiller).

**C2 com extensão incremental:**  
`fetch_prm_sp500tr_incremento()` estende a série com `^SP500TR` (yfinance) a partir de 2025. O PRM calculado com a série estendida pode diferir do publicado porque a série Bloomberg de base e a série pública de extensão usam metodologias de retorno total diferentes. O `rf_tbill` do ano corrente é congelado no último valor da fixture (não há substituto público exato).

**O que falta:**  
Bloomberg Terminal ou aceitação de um delta estrutural no ERP de C2.

---

### 3.3 EMBI+

**Metodologia ANEEL:**  
Média simples de 10 anos de EMBI diário (JPM/IPEADATA), janela P-10 a P-1, incluindo dias úteis e não-úteis. Fonte: IPEADATA série `JPM366_EMBI366`.

**Status C1:** `EMBI = 2.7649%` → 0bp delta ✓ (usa fixture `embi_diario.csv`)

**Gap C2:**  
Os anos 2022 e 2023 estão ausentes da série pública IPEADATA (`JPM366_EMBI366`) — há um hiato de dados que a ANEEL certamente tem via Bloomberg ou feed direto JPMorgan. Impacto: a janela de 10 anos calculada em C2 via `fetch_embi_ipeadata()` exclui esses 2 anos, distorcendo a média.

**O que falta para C2:**  
- **BCB SGS 28763** (`api.bcb.gov.br/dados/serie/bcdata.sgs.28763`) como fonte alternativa de EMBI — pode cobrir 2022-2023
- Ou Bloomberg `JPEMBI Index`

---

### 3.4 Beta

**Metodologia ANEEL:**  
13 janelas consecutivas de 5 anos cada (semanais), ponderadas por market cap médio na janela, usando OLS de cada empresa americana do setor de utilities vs S&P500. Beta alavancado EUA → Beta desalavancado EUA via Hamada com D/E americano. Re-alavancagem com D/E brasileiro (estrutura de capital da amostra transmissoras BR).

**Status C1:** `Beta_l = 0.7692` → 0bp delta ✓ (usa fixture `beta_historico.csv`)

**Gap C2 (estimado: ~475bp no Beta_u):**

| Componente | ANEEL | Python C2 atual | Delta |
|------------|-------|-----------------|-------|
| Janelas | 13 × 5 anos rolling | 1 janela 5 anos spot | Grande |
| Ponderação | Market cap médio da janela (13 valores) | Market cap atual (1 valor) | Significativo |
| Empresas | Lista fixa ANEEL (não publicada) | `TICKERS_UTILITIES_ANEEL` em `config.py` | Desconhecido |
| Data de corte | 25/09/2025 (5a: 25/09/2020-25/09/2025) | YTD | Pequeno |

**Gap estrutural adicional:**  
O `Beta_u` do validator mostra divergência de **+2335bp** entre o valor publicado (0.302) e o calculado em C2 (0.5357). Isso porque a ANEEL usa D/E americano para calcular Beta_u (Hamada EUA), mas o validator reporta o Beta_u "implícito brasileiro" (com D/E BR). O validator emite WARN para esse parâmetro mas PASS no WACC_ai.

**O que falta para C2 Beta from-scratch:**  
- `calcular_beta_13_janelas()` com 13 janelas rolantes de 5 anos de retornos semanais
- Identificar lista exata de empresas americanas usada pela ANEEL
- `extrair_beta_prices()` para baixar série histórica necessária (6+ anos de retornos semanais)

---

### 3.5 Kd (Custo de Capital de Terceiros)

**Metodologia ANEEL:**  
Média aritmética simples da `taxa_real` de debêntures do setor elétrico (transmissão), janela de emissão de 10 anos. `taxa_real` calculada na data de emissão via BEI (Break-Even Inflation) interpolado da curva ETTJ NTN-B para o prazo original de cada título.

**Status C1:** `Kd_deb = 6.0685%` → 0bp delta ✓ (usa `taxa_real` pré-calculada pela ANEEL)

**Três camadas de Kd — estado atual:**

| ID | Nome | Onde? | Status |
|----|------|-------|--------|
| **Kd-C1** | Histórico ANEEL | `calcular_kd_historico()` em `params/kd.py` | ✓ 0bp delta |
| **Kd-mid** | BEI atualizado | `calcular_kd_ettj_atualizado()` em `params/kd.py` | ✓ implementado, +14.1bp vs C1 (ETTJ emergência) |
| **Kd-C2** | Universo vivo ANBIMA | `params/kd_cesta.py` + basket inference | ⚠ nunca testado com credenciais reais (P4) |

**Gap Kd-mid vs C1 — decomposição:**

O delta de +14.1bp no teste atual é artificial (ETTJ plana em 5.14%). Com a ETTJ real:
- DI bonds com BEI de emissão histórico (2009–2015) entre 4–6% → BEI atual (≈5%) provavelmente próximo → delta pequeno
- O delta real do Kd-mid vs C1 reflete a diferença entre as expectativas de inflação implícita no momento da emissão vs hoje

**Dependência da fonte ETTJ:**
1. `fetch_ettj_anbima()` → endpoint `CZ-down.asp` (sem credenciais, scraping): incerto
2. `_ettj_fallback_from_ntnb()` → NTN-B spot via Tesouro Transparente: funciona quando API responde
3. Curva plana 5.14%: fallback de emergência quando Tesouro também falha

**Coluna `inflacao_implicita` no fixture:**  
Armazena o BEI histórico por título (na data de emissão). Para Kd-mid, esse valor é substituído pelo BEI atual da ETTJ ao prazo original do título.

**O que falta para Kd-C2:**  
- Credenciais ANBIMA (`ANBIMA_CLIENT_ID`, `ANBIMA_CLIENT_SECRET`)
- Validação do basket inference A/B/C/X com universo real (P4 aberto)

---

### 3.6 Estrutura de Capital (E/V, D/V)

**Metodologia ANEEL:**  
Ponderação por market cap das transmissoras brasileiras listadas. Valores 2026: E/V = 60,23%, D/V = 39,77%.

**Status C1:** 0bp delta ✓ (usa fixture `wacc_aplicacao.csv`)

**Gap C2:**  
`fetch_market_caps()` busca via yfinance. Os tickers das transmissoras BR (`TRPL3`, `TAEE11`, `ENGI11`, etc.) têm liquidez variável e o market cap varia diariamente. A ANEEL usa uma data de corte específica ou média do período — não documentado. Delta esperado: pequeno a moderado.

---

### 3.7 Fórmula WACC

**Fórmula ANEEL (Ke, sem EMBI explícito):**
```
Ke_DI = Rf + Beta_l_EUA × PRM
Ke_real_DI = (1 + Ke_DI) / (1 + EMBI) − 1   ← EMBI deflaciona o Ke dollar
WACC_real_DI  = E/V × Ke_real_DI + D/V × Kd_real_DI
WACC_real_AI  = WACC_real_DI / (1 − T)
```

O EMBI **não entra no Ke** — está implícito porque o Beta é calculado com D/E americano (≈2.35× o D/E brasileiro), que já captura o prêmio de risco-país via a diferença de alavancagem. Adicionar EMBI explicitamente no Ke seria double-counting.

**Status C1:** WACC_ai = 12.1150% → 0bp delta ✓

---

## 4. Mapa de GAPs — Prioridades para completar C2

| Parâmetro | Gap atual | Fonte necessária | Complexidade |
|-----------|-----------|-----------------|--------------|
| **Rf** | ~+20bp (filtro prazo desconhecido) | Inspecionar aba Rf no xlsx | Baixa |
| **ERP** | Série Bloomberg 1928-1987 não replicável | Bloomberg Terminal | Alta (depende de licença) |
| **EMBI** | Hiato 2022-2023 na série pública | BCB SGS 28763 ou Bloomberg | Média |
| **Beta** | 1 janela vs 13 janelas rolantes | 6+ anos preços semanais yfinance | Média |
| **Kd-mid** | ETTJ plana (fallback) | Tesouro ao vivo ou ETTJ ANBIMA | Baixa (dados disponíveis) |
| **Kd-C2** | Basket inference não validado | Credenciais ANBIMA | Alta (depende de acesso) |
| **E/V, D/V** | Data de corte desconhecida | Convenção ANEEL | Baixa |

---

## 5. Invariante arquitetural das três camadas

```
C1 (0bp delta)  ← usa outputs pré-calculados pela ANEEL como fixtures
                   NÃO é replicação from-scratch; é verificação de consistência

C2 (Kd-mid)    ← mesmos títulos ANEEL + BEI atual via ETTJ
                   Kd_fonte = "ettj_atualizado"
                   Sem credenciais ANBIMA: este é o caminho de projeção T-1

C2 (ANBIMA)    ← universo ao vivo ANBIMA + basket inference A/B/C/X
                   Kd_fonte = "anbima_live"
                   Requer credenciais; basket inference não validado (P4)

C3              ← vetor 30 anos com ETTJ/DI projetado + parâmetros estruturais
```

O gap entre C1 e C2 **não é um bug** — é informação. Cada divergência revela um efeito de mercado em movimento relativo ao último despacho publicado.

---

## 6. Arquivos modificados nesta sessão

| Arquivo | Mudança |
|---------|---------|
| `wacc_regulatorio/data/fetchers.py` | Remove `fetch_sp500_treasury`; adiciona `raise_sem_credenciais` em `fetch_universo_anbima`; renomeia `rf_10y` → `rf_tbill` em `fetch_prm_sp500tr_incremento` |
| `wacc_regulatorio/data/fixtures/prm_sp500.csv` | Header `rf_10y` → `rf_tbill` |
| `scripts/extrair_fixtures.py` | Key `"rf_10y"` → `"rf_tbill"` em `extrair_debentures` |
| `wacc_regulatorio/data/fixtures.py` | Docstring `load_prm_sp500()` atualizado |
| `wacc_regulatorio/params/erp.py` | `rf_10y_dec` → `rf_tbill_dec`; `df["rf_10y"]` → `df["rf_tbill"]` |
| `wacc_regulatorio/params/kd.py` | **Adicionado:** `calcular_taxa_real_ettj()` e `calcular_kd_ettj_atualizado()` (Bloco C — Kd-mid) |
| `wacc_regulatorio/camada2_corrente.py` | Bifurcação `tem_anbima`: ANBIMA live OU Kd-mid fallback; importa `fetch_ettj_anbima` e `calcular_kd_ettj_atualizado`; `kd_n_A/B/C` protegidos contra `df_cesta = None` |
| `dashboard.py` | Handler `RuntimeError` separado para erro ANBIMA com instrução de env vars |
| `CLAUDE.md` | P1-P3-P5 marcados resolvidos; invariante Kd C2 atualizado; P3 expandido com Kd-mid |

---

## 7. Próximas sessões — backlog priorizado

### Alta prioridade
1. **Rf filter**: inspecionar aba "NTN-B" no xlsx → identificar critério de filtro de prazo → implementar em `calcular_rf_anual_10a()` → meta: C2 Rf ±0bp from-scratch
2. **EMBI 2022-2023**: testar BCB SGS 28763 como fonte alternativa → fechar o hiato de série

### Média prioridade
3. **Beta 13 janelas**: implementar `calcular_beta_13_janelas()` + `extrair_beta_prices()` — janela 2008-2025 de retornos semanais de utilities americanas
4. **ETTJ ao vivo**: forçar refresh do cache da curva NTN-B e verificar se `_ettj_fallback_from_ntnb()` produz curva escalonada real (não plana)

### Baixa prioridade
5. **P4**: aguarda credenciais ANBIMA para validar basket inference com universo real
6. **ERP**: depende de Bloomberg Terminal — delta estrutural a ser documentado e aceito

---

*C1 gate: `python -m wacc_regulatorio.validator` → PASS ±0bp (verificado 2026-06-19)*
