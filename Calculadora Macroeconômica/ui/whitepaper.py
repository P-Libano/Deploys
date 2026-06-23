"""Aba de documentação e guia de uso da Calculadora Macroeconômica."""
import streamlit as st
from datetime import datetime


def render_whitepaper_tab() -> None:
    st.header("Documentação")

    tab_eli5, tab_tech, tab_data = st.tabs([
        "📘 Guia para não-economistas",
        "⚙️ Metodologia técnica",
        "🗄️ Fontes e base de dados",
    ])

    with tab_eli5:
        _render_eli5()

    with tab_tech:
        _render_methodology()

    with tab_data:
        _render_data_sources()


# ---------------------------------------------------------------------------
# ELI5 — Guia para não-economistas
# ---------------------------------------------------------------------------

def _render_eli5() -> None:
    st.subheader("O que é inflação — explicação simples")

    st.markdown("""
Imagine que em 2010 você comprava um almoço por **R\$ 15,00**. Hoje o mesmo almoço custa
**R\$ 38,00**. O almoço não ficou melhor — o **dinheiro ficou mais fraco**.
Isso é inflação: a perda gradual do poder de compra da moeda ao longo do tempo.

O IPCA (Índice de Preços ao Consumidor Amplo) mede, mês a mês, quanto os
preços subiram em média para as famílias brasileiras. Se o IPCA de janeiro foi 0,42%,
significa que uma cesta de produtos que custava R\$ 1.000,00 em dezembro passou a custar
R\$ 1.004,20 em janeiro.

---
""")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
#### 🔙 Deflacionar
*"Quanto valia esse dinheiro do passado em reais de hoje?"*

Você encontrou uma nota fiscal de 2010: equipamento comprado por **R\$ 200.000**.
Para saber o equivalente hoje, você **deflaciona** — divide pelo fator de inflação do
período. Isso mostra o **poder de compra real** daquele investimento.

> Deflacionar = dividir pelo fator acumulado
> `Valor_hoje = Valor_antigo ÷ Fator`
""")

    with col2:
        st.markdown("""
#### 🔜 Inflacionar
*"Quanto vai custar lá na frente?"*

Você tem um orçamento de **R\$ 500.000** para um projeto em 2025 e precisa saber
quanto reservar para executá-lo em 2027. Você **inflaciona** — multiplica pelo fator
projetado de inflação. Isso dá o **custo futuro estimado**.

> Inflacionar = multiplicar pelo fator acumulado
> `Valor_futuro = Valor_atual × Fator`
""")

    st.divider()
    st.subheader("Exemplo prático — CAPEX de equipamento antigo")

    st.markdown("""
**Contexto:** Uma indústria comprou um compressor em **março de 2018** por **R\$ 500.000**.
O time de engenharia quer saber:

1. Qual o custo de reposição hoje? *(inflacionar o preço de 2018 para hoje)*
2. Se recomprar em 2027, quanto deve provisionar?
3. O fornecedor enviou orçamento de R\$ 1.000.000 — quanto disso é inflação e quanto é aumento real?

**Passo 1 — Inflacionar o preço de 2018 para hoje:**
""")

    st.info("""
IPCA acumulado de Mar/2018 até hoje ≈ **+65%** → Fator ≈ 1,65

```
R$ 500.000 × 1,65 = R$ 825.000   ← custo de reposição equivalente hoje
```

> Interpretar o preço original como "dinheiro de hoje" sem corrigir seria
> comparar laranjas com maçãs: R$ 500k de 2018 ≠ R$ 500k de hoje.
""")

    st.markdown("**Passo 2 — Inflacionar até 2027 (usando projeção Focus ou ETTJ BEI):**")

    st.info("""
IPCA projetado de hoje até Dez/2027 ≈ **+10%** → Fator ≈ 1,10

```
R$ 825.000 × 1,10 = R$ 907.500   ← provisão necessária para 2027
```
""")

    st.markdown("**Passo 3 — Deflacionar um orçamento recebido para comparar com o preço original:**")

    st.info("""
O fornecedor enviou um orçamento hoje de **R\$ 1.000.000** para o mesmo compressor.
Parece que o preço dobrou — mas quanto disso é inflação e quanto é aumento real?

Deflacione o orçamento de volta a Mar/2018 para comparar na mesma base:

```
R$ 1.000.000 ÷ 1,65 = R$ 606.000   ← orçamento atual em "reais de Mar/2018"
```

Comparando com o preço original de R\$ 500.000:
```
(606.000 - 500.000) / 500.000 = +21%   ← aumento REAL acima da inflação
```

> Sem deflacionar, a conclusão errada seria "o preço subiu 100%".
> Deflacionando, a conclusão correta é "subiu 21% acima da inflação" —
> o restante (+65%) é apenas a inflação do período.
""")

    st.divider()
    st.subheader("Uso em modelos financeiros — fluxos de caixa")

    st.markdown("""
Suponha que você tem um modelo de DCF (Fluxo de Caixa Descontado) com custos
históricos e projetados misturados. Para **comparar todos na mesma base**,
você precisa de um **vetor de inflação**.

**Como funciona:**
""")

    exemplo_df = {
        "Período": ["Jan/2020", "Jan/2021", "Jan/2022", "Jan/2023", "Jan/2024", "Jan/2025 (proj.)", "Jan/2026 (proj.)"],
        "OPEX histórico (R$)": ["80.000", "84.000", "91.000", "98.000", "107.000", "—", "—"],
        "Fator (base Jan/2024)": ["0,7312", "0,7843", "0,8521", "0,9201", "1,0000", "1,0414", "1,0852"],
        "OPEX em R$ Jan/2024": ["109.400", "107.110", "106.800", "106.500", "107.000", "—", "—"],
        "OPEX projetado (R$)": ["—", "—", "—", "—", "107.000", "111.430", "116.116"],
    }

    import pandas as pd
    st.dataframe(pd.DataFrame(exemplo_df), use_container_width=True, hide_index=True)

    st.markdown("""
**Regras práticas:**

| Operação | Quando usar | Fórmula |
|---|---|---|
| Deflacionar histórico | Comparar custos de anos diferentes na mesma base | `÷ Fator` |
| Inflacionar para futuro | Projetar orçamento / provisionar CAPEX | `× Fator` |
| Homogeneizar série | Análise de tendência real (descontando inflação) | `÷ Fator` de cada período |

> **Dica:** use a aba **Vetor de Correção** para gerar a coluna de fatores pronta
> para colar no seu modelo. Escolha a data base como o período de referência
> do seu modelo (ex: data do orçamento aprovado).
""")

    st.divider()
    st.subheader("Por que os índices diferem?")

    st.markdown("""
| Índice | Mede | Aplicação típica |
|---|---|---|
| **IPCA** | Inflação das famílias (IBGE) | Reajuste de salários, contratos de consumo, benchmark oficial BCB |
| **IGP-M** | Preços no atacado + construção + consumidor (FGV) | Contratos de aluguel, energia elétrica |
| **IPCA-15** | Prévia do IPCA, divulgada dia 15 | Expectativa do mercado, antecipação do IPCA cheio |
| **INPC** | Famílias de menor renda (IBGE) | Reajuste do salário mínimo, benefícios sociais |
| **INCC** | Custo de construção civil (FGV) | Contratos imobiliários na planta, financiamentos habitacionais |
| **SELIC** | Taxa básica de juros (BCB) | Custo de carregamento, benchmark de renda fixa |
| **CDI** | Taxa interbancária diária (B3) | Benchmark de fundos de investimento, FIDCs, debêntures |

Para correção de ativos industriais e CAPEX, o **IPCA** é o mais usado por ser o
índice-meta da política monetária brasileira.

> **SELIC e CDI** não são índices de inflação — são taxas de juros nominais.
> Por isso aparecem apenas na aba **Vetor de Correção** e não na calculadora de correção monetária.
""")

    st.divider()
    st.subheader("O que é a Inflação Implícita (ETTJ BEI)?")

    st.markdown("""
O mercado de títulos públicos revela implicitamente **quanto os investidores esperam de inflação**
nos próximos anos. Essa leitura é chamada de **Break-Even Inflation (BEI)** — ou
**Inflação Implícita** — e é calculada a partir da Estrutura a Termo da Taxa de Juros (ETTJ).

### Como funciona

Existem dois tipos de título público que permitem a comparação:

- **NTN-B (IPCA+)**: paga uma taxa **real** fixada na emissão + correção pelo IPCA.
  Quem compra sabe a rentabilidade real, mas não a rentabilidade nominal.

- **LTN / NTN-F (PRE)**: paga uma taxa **nominal** fixada. O investidor sabe exatamente
  o valor nominal no vencimento, mas não sabe quanto isso vai comprar em termos reais.

Se esses dois títulos têm vencimento igual, a diferença entre suas taxas revela quanto
o mercado **aposta que a inflação será**:

```
BEI = (1 + Taxa PRE) / (1 + Taxa IPCA+) − 1   ≈   Taxa PRE − Taxa IPCA+
```

Exemplo com vértice de 5 anos:
```
PRE 5a = 14,14% a.a.
IPCA+ 5a = 8,03% a.a.

BEI ≈ 14,14% − 8,03% = 5,65% a.a.
```

Isso significa: o mercado espera que a inflação (IPCA) média nos próximos 5 anos
seja de aproximadamente **5,65% a.a.** Se a inflação ficar abaixo disso, quem comprou
LTN teria saído melhor; se ficar acima, quem comprou NTN-B teria saído melhor.

### Diferença em relação ao Focus

| Fonte | Quem produz | Tipo | Horizonte |
|---|---|---|---|
| **Boletim Focus (BCB)** | Economistas de bancos e gestoras | Previsão explícita | Até ~5 anos |
| **ETTJ BEI (ANBIMA)** | Precificação do mercado (compra/venda de títulos) | Implícita no preço | Até 33 anos |

A vantagem do BEI é que é **atualizado em tempo real** conforme os preços dos títulos mudam,
capturando reações instantâneas a notícias (dados de inflação, decisões do Copom, câmbio).
A desvantagem é que inclui um **prêmio de risco de inflação** — investidores exigem uma
gordura para se proteger de surpresas inflacionárias, então o BEI tende a ser ligeiramente
maior que a inflação efetivamente esperada.

> **Quando usar o BEI como projeção:** ao fazer análises de longo prazo (5+ anos),
> quando o horizonte Focus já se esgotou, ou quando se quer capturar a visão de mercado
> em vez do consenso de economistas.
""")


# ---------------------------------------------------------------------------
# Metodologia técnica
# ---------------------------------------------------------------------------

def _render_methodology() -> None:
    st.subheader("Arquitetura e metodologia de cálculo")

    st.markdown("""
### Base de dados: cache local com TTL

A aplicação **não chama a API a cada cálculo**. Os dados são baixados uma vez
e armazenados em arquivos Parquet locais:

| Dado | Arquivo | TTL | Motivo |
|---|---|---|---|
| Séries realizadas | `data/cache/series_IPCA.parquet` | 1 dia | IPCA divulgado ~dia 9 de cada mês |
| Boletim Focus | `data/cache/focus_annual_IPCA.parquet` | 7 dias | Focus publicado toda sexta-feira |
| ETTJ ANBIMA | `data/cache/ettj_YYYYMMDD.parquet` | 1 dia útil | ANBIMA atualiza diariamente |

O botão **"Atualizar dados agora"** na sidebar força o re-fetch imediato das séries e Focus.
Na aba ETTJ há um botão "🔄 Atualizar" independente.

---

### Fluxo do cálculo de correção monetária
""")

    st.code("""
corrigir_valor(valor, data_origem, data_destino, indice, projecao="focus")

1. Carrega série realizada do Parquet local (ou API se expirado)
   IPCA: Jul/1994 → mês mais recente (~380 registros mensais)

2. Se data_destino > último mês realizado:

   ── projecao="focus" (padrão) ──────────────────────────────
   Lê Focus anual (Boletim Focus / BCB)
   Distribui taxa anual em parcelas mensais iguais:
     taxa_mensal = (1 + anual/100)^(1/12) - 1

   Para o ano corrente (meses parcialmente realizados):
     fator_residual = expectativa_anual / acumulado_já_realizado
     taxa_restante  = fator_residual^(1/n_meses_restantes) - 1

   Para anos além do horizonte Focus (~5 anos):
     Replica a última taxa anual Focus disponível como premissa

   ── projecao="ettj" (só IPCA) ──────────────────────────────
   Busca curva BEI spot da ANBIMA (cache Parquet)
   Constrói curva de taxas forward implícitas entre vértices:
     forward(v_i → v_{i+1}) =
       [(1+bei_{i+1}/100)^anos_{i+1} / (1+bei_i/100)^anos_i]^(1/Δanos) − 1

   Para cada mês futuro t:
     du_t   = t × 21 du
     fwd_t  = forward do intervalo que contém du_t
     taxa_t = (1 + fwd_t/100)^(1/12) − 1

3. Série unificada: realizados + projetados

4. Fator acumulado (intervalo inclusivo nos dois extremos):
   fator = ∏ (1 + taxa_i / 100)   para i de data_origem até data_destino

5. valor_corrigido = valor × fator
""", language="python")

    st.markdown("""
---

### Semântica do intervalo — compatibilidade com Calculadora do Cidadão BCB

A correção usa **intervalo inclusivo**: ao corrigir de Janeiro a Março,
o cálculo multiplica as taxas de Janeiro, Fevereiro **e** Março.

```
Exemplo: Jan=1%, Fev=2%, Mar=3%
Fator = 1,01 × 1,02 × 1,03 = 1,061106  (+6,11%)
```

Este comportamento é idêntico à
[Calculadora do Cidadão do BCB](https://www3.bcb.gov.br/CALCIDADAO/publico/corrigirPorIndice.do).

---

### Projeção Focus — metodologia de distribuição

O Boletim Focus divulga **expectativas anuais** (ex: IPCA 2026 = 5,09%).
Para obter taxas mensais, a aplicação usa **taxa composta uniforme**:

```
taxa_mensal = (1 + 5,09/100)^(1/12) - 1  ≈  0,414% ao mês
```

Essa taxa é **igual em todos os 12 meses** do ano projetado — premissa de
distribuição neutra, sem sazonalidade. Para o ano corrente, a taxa dos
meses restantes é ajustada para fechar exatamente a expectativa anual
descontando o que já foi realizado.

> **Por que não usar o Focus mensal?** O Focus também divulga expectativas
> mês a mês. Optamos pela distribuição plana do anual para manter consistência
> com o dado mais amplamente divulgado, auditável e comparável entre analistas.

---

### ETTJ — Estrutura a Termo da Taxa de Juros

A ETTJ descreve como as taxas de juros variam com o prazo. A ANBIMA calcula
diariamente curvas **zero-coupon** (CZ) para três mercados:

| Curva | Instrumento | Natureza | Disponibilidade |
|---|---|---|---|
| **PRE** | DI futuro + LTN + NTN-F | Nominal | Vértices de 6m a ~10 anos |
| **IPCA+** | NTN-B | Real | Vértices de 6m a ~33 anos |
| **Inflação Implícita (BEI)** | PRE − IPCA+ | Expectativa de mercado | Onde ambas existem |

**Zero-coupon** significa que a taxa é para um único pagamento no vencimento
(sem cupons intermediários). É a taxa "pura" de cada prazo, calculada por
bootstrapping a partir dos preços de mercado dos títulos.

**Cálculo do BEI spot pela ANBIMA:**

```
BEI_spot(v) = [(1 + PRE(v)/100) / (1 + IPCA+(v)/100)] − 1  × 100
```

O BEI spot no vértice `v` representa a inflação **média acumulada** esperada
do presente até o prazo `v` — não a inflação esperada especificamente em `v`.

---

### Projeção ETTJ BEI — taxas forward implícitas

#### Por que usar forwards em vez do spot?

O BEI spot a 5 anos (ex: 5,65% a.a.) diz "a inflação média dos próximos 5 anos
deve ser 5,65%". Mas para projetar o mês 60 especificamente, o dado relevante
é a inflação esperada **entre o ano 4 e o ano 5** — chamada de taxa **forward**.

Usar o spot de 5 anos para o mês 60 subestima ou superestima conforme a inclinação
da curva. Com a curva atual (ascendente), a abordagem spot subestima a inflação
de longo prazo em até ~0,5 p.p.

#### Cálculo do forward entre dois vértices

Dados dois vértices consecutivos com BEI spot (v₁, bei₁) e (v₂, bei₂):

```
f₁ = (1 + bei₁/100) ^ (v₁/252)   ← fator acumulado até v₁
f₂ = (1 + bei₂/100) ^ (v₂/252)   ← fator acumulado até v₂
Δanos = (v₂ - v₁) / 252

forward(v₁ → v₂) = (f₂ / f₁) ^ (1/Δanos) − 1   [% a.a.]
```

#### Exemplo com dados reais (Jun/2026)

| Vértice | BEI spot | Forward implícito |
|---|---|---|
| 0,5a (126 du) | 4,88% | 4,88% (sem prior, = spot) |
| 1,0a (252 du) | 5,49% | ~6,10% (inflação esp. no 2º semestre) |
| 2,0a (504 du) | 5,53% | ~5,57% |
| 5,0a (1260 du) | 5,66% | ~5,79% |
| 10,5a (2646 du) | 6,12% | ~6,55% |

O mercado precifica **inflação crescente ao longo do tempo** — algo que a abordagem
spot não captura.

#### Âncora temporal: ETTJ vs. Focus

Ambos usam **% a.a. compostos**, portanto a conversão para mensal é idêntica:
`(1 + r/100)^(1/12) − 1`. A diferença é o **ponto de referência**:

| Fonte | Referência | Exemplo |
|---|---|---|
| **Focus anual** | Ano calendário (Jan–Dez) | "IPCA 2027 = 4,80%" cobre Jan–Dez/2027 |
| **ETTJ forward** | Rolling a partir de hoje | Forward 12m→24m cobre Jun/2027–Jun/2028 |

O descompasso máximo é de ~6 meses (offset do ponto atual no ano). Para a maioria
das análises financeiras isso é tolerável; para cálculos que exigem ancoragem exata
em ano calendário, o Focus é mais preciso.

#### Construção prática da projeção

```
Para cada mês futuro t (t = 1, 2, 3, ... meses à frente):
  du_t = t × 21 du

  Segmento: encontra (v_i, v_{i+1}) tal que v_i ≤ du_t < v_{i+1}
  forward_t = taxa forward desse segmento (% a.a.)
  taxa_t    = (1 + forward_t/100)^(1/12) − 1

Casos especiais:
  du_t < v_primeiro  → usa BEI spot do 1º vértice (sem referência anterior)
  du_t > v_último    → mantém o último forward disponível (extrapolação plana)
```

#### Limitações do BEI como projeção

1. **Prêmio de risco**: o BEI embute um prêmio pela incerteza inflacionária
   (~0,3 a 0,8 p.p. no Brasil), logo tende a superar a inflação realizada sistematicamente.

2. **Liquidez**: vértices longos (>5 anos) têm menos negócios; a taxa reflete mais
   precificação indicativa da ANBIMA do que consenso de mercado.

3. **Ponto no tempo**: o BEI muda ao longo do dia com as negociações. A ANBIMA
   publica a taxa de fechamento — diferente do Focus (mediana semanal de respostas).
""")


# ---------------------------------------------------------------------------
# Fontes
# ---------------------------------------------------------------------------

def _render_data_sources() -> None:
    st.subheader("Fontes de dados")

    st.markdown("""
### Dados realizados — API SGS / Banco Central

Endpoint base:
```
https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json
```

| Índice | Série SGS | Cobertura | Divulgação |
|---|---|---|---|
| IPCA | 433 | Jul/1994 – presente | ~dia 9 do mês seguinte (IBGE) |
| IGP-M | 189 | Jan/1940 – presente | Último dia útil do mês (FGV) |
| IPCA-15 | 7478 | Fev/1999 – presente | ~dia 15 do mês (IBGE) |
| INPC | 188 | Jan/1979 – presente | ~dia 9 do mês seguinte (IBGE) |
| INCC | 192 | Jan/1985 – presente | Última semana do mês (FGV) |
| SELIC | 4390 | Jun/1986 – presente | Diário (BCB) |
| CDI | 4391 | Jun/1986 – presente | Diário (B3 / BCB) |

Retorno da API: lista de `{"data": "dd/MM/yyyy", "valor": "float"}`.

---

### Projeções — Boletim Focus / BCB

Coletado via biblioteca `python-bcb` (pacote `bcb`):

```python
from bcb import Expectativas
em  = Expectativas()
ep  = em.get_endpoint("ExpectativasMercadoAnuais")
df  = ep.query().filter(ep.Indicador == "IPCA", ep.baseCalculo == 0).collect()
```

- **`baseCalculo == 0`**: expectativas padrão (não de comparação com ano-base)
- Cada linha representa uma pesquisa semanal com mediana, média, mín, máx e nº de respondentes
- A aplicação utiliza apenas a pesquisa **mais recente** por ano de referência
- Disponível para: IPCA, IGP-M, IPCA-15, INPC

---

### ETTJ — ANBIMA (Curvas Zero-Coupon)

**Fonte:** página pública da ANBIMA, atualizada diariamente após o fechamento do mercado.

```
https://www.anbima.com.br/informacoes/est-termo/CZ.asp
```

**Coleta:** scraping do HTML da página via `requests` + `pandas.read_html`.
A página usa encoding **ISO-8859-1** e inclui declaração XML — ambas tratadas
no coletor antes do parse.

**Curvas disponíveis:**

| Curva | Natureza | Vértices típicos | Instrumento base |
|---|---|---|---|
| IPCA+ | Taxa real | 126 du a 8.442 du (~0,5 a 33,5 anos) | NTN-B |
| PRE | Taxa nominal | 126 du a 2.646 du (~0,5 a 10,5 anos) | DI futuro / LTN / NTN-F |
| Inflação Implícita | Break-even | Onde PRE e IPCA+ coexistem | Calculado pela ANBIMA |

**Caching:** arquivo Parquet por data de referência em `data/cache/ettj_YYYYMMDD.parquet`.
O app re-fetcha automaticamente se o cache for anterior ao último dia útil.

---

### Validação

Os resultados foram validados contra a
[Calculadora do Cidadão do BCB](https://www3.bcb.gov.br/CALCIDADAO/publico/corrigirPorIndice.do)
para múltiplos períodos com tolerância de **0,1%** no fator acumulado.

Para rodar os testes de validação:
```bash
pytest tests/ -m integration
```

*(requer conexão com a internet para buscar os dados do BCB)*
""")

    st.divider()
    st.caption(
        f"Documentação gerada em {datetime.today().strftime('%d/%m/%Y')}. "
        "Os TTLs e parâmetros técnicos estão em `config.py`."
    )
