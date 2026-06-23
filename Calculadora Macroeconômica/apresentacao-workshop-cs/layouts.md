# Layouts: Workshop CS | Calculadora Macroeconômica

Capa: \amcover (estilo full, tema dark), \coverimagedark{covers/tecnologia.jpg}. Sem
\confidencial. Cliente: "Workshop CS". Título: "Calculadora Macroeconômica: de
repositório a apresentação". Nota de rodapé da capa (texto pequeno, alinhado à
régua inferior): "Criado com apresentacao-rapida-am".

Sem agenda: deck tem só 2 capítulos, abaixo do limiar de 4 que exige `\amagenda`.

Sequência de composições do deck (conferida para não repetir em slides
consecutivos): texto em 2 colunas com destaques numerados (1.1) → split 60/40
(1.2) → full-width + nota (1.3) → [separador dark] → cards paralelos +
statstrip (2.1) → split 60/40 (2.2) → full-width + nota (2.3).

## Separador Capítulo 1: "Da dor ao deck em minutos" [dark]
- `\amsection[dark]{Da dor ao deck em minutos}`
- Sem foto lateral: manter o divisor limpo, só o número de capítulo e o título.

## Slide 1.1: Objetivos deste workshop
- Composição: texto em 2 colunas com destaques numerados
- Região A (esquerda, 0.5): 3 destaques numerados (01, 02, 03) a partir do
  Bloco 1 "O que você vai ver": 01 leitura automática do projeto; 02 validação
  cruzada entre agentes a cada etapa; 03 este deck como prova viva
- Região B (direita, 0.5): \amkpi{7 etapas}{do roteiro ao PDF final} no topo;
  abaixo, parágrafo curto do Bloco 2 "Por que isso interessa ao CS" (2 frases)
- Ícones: I1, um por destaque numerado da Região A (search, shield-check,
  file-text; slate), ao lado de cada número
- Alinhamento: topos nivelados entre as duas colunas; take away no rodapé
- Racional: a persona quer saber em 5 segundos o que vai ganhar com o tempo
  investido; números frente e centro, contexto do CS como reforço, não abertura

## Slide 1.2: A dor: dados prontos, apresentação represada
- Composição: split 60/40
- Região A (esquerda, 0.58): subtítulo "Sintomas comuns" + os 4 bullets do
  Bloco 1, cada um em frase completa com a consequência
- Região B (direita, 0.38): \amhighlight{8--12} {slides por proposta A\&M,
  hoje gastos em formatação} no topo; \begin{amcard} "Custo real" com o texto
  do Bloco 2 \end{amcard} abaixo
- Alinhamento: topos nivelados; highlight alinhado ao topo da lista de sintomas
- Racional: a lista de sintomas precisa de espaço para respirar (são 4 itens
  concretos); o destaque numérico ancora o custo antes do card explicar a causa

## Slide 1.3: Como funciona o apresentacao-rapida-am
- Composição: full-width + nota
- Região A (full-width, topo, ~60% da altura): diagrama D1, fluxo horizontal
  com os 7 nós numerados (Roteiro, Avaliação, Layout, Gráficos, Decoração,
  Código, QA), setas finas entre eles
- Região B (full-width, rodapé, ~40% da altura, 2 colunas): coluna esquerda
  "O que isso garante" com o resumo do Bloco 1 condensado em 1 frase; coluna
  direita "O que isso elimina" com os 2 bullets do Bloco 2
- Decoração: D1 (ver acima)
- Alinhamento: diagrama centrado no eixo horizontal do slide; régua entre
  Região A e B
- Racional: o fluxo de 7 etapas é a informação central deste slide e precisa
  do espaço da largura toda para não comprimir os nós; a leitura embaixo fecha
  o raciocínio sem competir visualmente com o diagrama

## Separador Capítulo 2: "Estudo de caso ao vivo: Calculadora Macroeconômica" [light]
- `\amsection{Estudo de caso ao vivo: Calculadora Macroeconômica}`

## Slide 2.1: Por dentro do projeto: de coletores a interface
- Composição: cards paralelos (3 colunas) + statstrip
- Região A (full-width, topo, 3 colunas de 0.32\textwidth): \begin{amcard}
  "Coletores" com os 5 itens do Bloco 1 (BCB SGS, Focus, ANBIMA ETTJ, B3 DI1,
  IBGE Sidra) condensados em lista curta; \begin{amcard} "Motor" com os 4
  módulos (deflator, index\_builder, projector, vector); \begin{amcard}
  "Interface" com as 6 abas do app Streamlit
- Região B (full-width, rodapé): \amstatstrip{7/índices suportados, 4/fontes
  de dados, 1--7 dias/ciclo de cache}, seguido do Bloco 2 "Por que isso
  facilita gerar um deck" como nota de 1 a 2 frases abaixo do statstrip
- Ícones: I2, um por card (database para Coletores, cog para Motor, monitor
  para Interface; navy), no topo de cada card ao lado do título
- Alinhamento: 3 cards com gutters iguais, topos nivelados; statstrip alinhado
  à margem inferior dos cards com respiro de 4mm
- Racional: três camadas paralelas pedem três blocos paralelos; o statstrip
  fecha com os números que provam a abrangência do projeto antes da
  metodologia entrar em detalhe no próximo slide

## Slide 2.2: A metodologia que sustenta cada número
- Composição: split 60/40
- Região A (esquerda, 0.58): tabela listrada com os 7 índices (coluna Índice,
  Fonte SGS, Início da série, Projeção Focus/ETTJ), dados do Bloco 2
- Região B (direita, 0.38): bloco "Como o fator é calculado" do Bloco 1, com a
  fórmula do fator acumulado em destaque (`\bfseries\color{amSignal}`) e 1
  frase por tipo de projeção (Realizado, Focus, ETTJ)
- Alinhamento: topos nivelados; tabela ocupando toda a altura útil da Região A
- Racional: a tabela é a evidência (a persona técnica vai conferir os números
  primeiro); a fórmula ao lado sustenta como aquele número nasce, sem disputar
  espaço com a tabela

## Slide 2.3: Recapitulando e como usar a ferramenta
- Composição: full-width + nota
- Região A (full-width, topo): 3 destaques numerados em linha única (não
  cards) resumindo o Bloco 1 "O que vimos": 01 leitura do projeto, 02 validação
  por agente em cada etapa, 03 estudo de caso ao vivo
- Região B (full-width, rodapé, split 55/45): coluna esquerda "Próximos
  passos" com os 2 bullets do Bloco 2; coluna direita: QR code (gerado via
  pacote LaTeX `qrcode`, vetorial, sem imagem externa) apontando para
  cortex.enpower.com.br/plugins/apresentacao-rapida-am, com o texto "Criado
  com apresentacao-rapida-am" abaixo do QR
- Ícones: I3, rocket ao lado do subtítulo "Próximos passos" (navy)
- Alinhamento: QR code alinhado à margem direita (3.2mm), tamanho 18mm
- Racional: fechamento precisa do call-to-action visualmente isolado (QR à
  direita) sem se misturar com a recapitulação; a persona age se o caminho
  estiver à vista, não enterrado em texto

## Manifesto de decoração (entrada para `decorar`)
- D1: diagrama de fluxo horizontal, 7 nós numerados, slide 1.3, ~150mm x 30mm,
  nós navy/branco conectados por setas cinza finas — explica a pipeline sem
  texto corrido
- I1: ícones search, shield-check, file-text (slate, 5mm), slide 1.1, ao lado
  dos 3 destaques numerados — reforça a leitura rápida dos 3 pontos
- I2: ícones database, cog, monitor (navy, 5mm), slide 2.1, no topo de cada
  card — identifica a camada do projeto à primeira vista
- I3: ícone rocket (navy, 5mm), slide 2.3, ao lado de "Próximos passos" —
  marca visualmente o call-to-action final

Nota para `codar-latex`: o QR code do slide 2.3 não é um asset de `decorar`
(não é ícone do catálogo nem foto); gerar diretamente em LaTeX com o pacote
`qrcode` (`\qrcode[height=18mm]{https://cortex.enpower.com.br/plugins/apresentacao-rapida-am}`),
vetorial e sem dependência de imagem externa.

## Auto-revisão de prancheta
- Composições em sequência (sem repetição consecutiva): confirmado acima.
- Densidade: todo slide de conteúdo usa ao menos 2 regiões com substância
  própria (tabela, cards, diagrama ou lista desenvolvida); nenhum slide só com
  bullets soltos.
- Cards paralelos aparece 1 vez em 6 slides de conteúdo (abaixo do limite de
  25%).
- Momentos de impacto (o "7 etapas" da pipeline e os "7 índices" do motor)
  recebem destaque numérico (\amkpi, statstrip) em vez de ficarem perdidos em
  texto corrido.
