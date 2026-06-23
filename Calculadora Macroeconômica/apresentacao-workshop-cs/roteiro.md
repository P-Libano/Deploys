# Roteiro: Workshop CS | Calculadora Macroeconômica

## Metadados
- Tipo: educativa
- Cliente/instituição: Workshop CS
- Público-alvo: time de Capital Strategy, já familiarizado com IPCA, SELIC e curvas de juros, mas não com a pipeline de geração de apresentações
- Objetivo: que o time entenda a agilidade do apresentacao-rapida-am em transformar um repositório de dados/código em deck pronto, e veja como aplicar isso às próprias dores de dados
- Idioma: pt-BR
- Capa: tema dark; estilo full; foto: tecnologia
- Total estimado de slides: 7 (capa + 6 slides de conteúdo)
- Observação para etapas seguintes (decorar/codar-latex): incluir, em algum elemento de marca recorrente do deck (rodapé da capa ou do slide final), o texto "Criado com apresentacao-rapida-am" e, no slide final, um QR code apontando para https://cortex.enpower.com.br/plugins/apresentacao-rapida-am

## Capítulo 1: Da dor ao deck em minutos [separador: dark]

### Slide 1.1: Objetivos deste workshop
- Mensagem (takeaway): Ao final deste workshop, o time de Capital Strategy entende como transformar um repositório de código e dados em uma apresentação pronta, sem depender de designer ou de horas de formatação manual.
- Bloco 1: O que você vai ver
  - Como a pipeline lê um projeto real (código, dados, documentação) e gera um roteiro estruturado
  - Como cada etapa (roteiro, layout, gráficos, decoração, código, QA) é revisada por um agente especialista antes de avançar
  - Este próprio deck como prova: foi gerado a partir da pasta do projeto Calculadora Macroeconômica
- Bloco 2: Por que isso interessa ao CS
  - Propostas e relatórios de Capital Strategy nascem de planilhas, modelos e memos densos
  - Hoje, tempo de formatação compete com tempo de análise
- Dados: pipeline em 7 etapas, do roteiro ao PDF final
- Layout sugerido: texto corrido com 3 destaques numerados à esquerda, diagrama simples de engrenagens/fluxo à direita
- Fonte:

### Slide 1.2: A dor: dados prontos, apresentação represada
- Mensagem (takeaway): O gargalo de uma apresentação raramente é a análise, é transformar a análise em slides consistentes e bem desenhados na velocidade que o negócio pede.
- Bloco 1: Sintomas comuns
  - Horas redistribuindo a mesma tabela em formatos diferentes a cada apresentação
  - Gráficos refeitos manualmente sempre que um dado é atualizado
  - Identidade visual inconsistente entre decks do mesmo projeto
  - Revisão de conteúdo e revisão de design acontecendo nas mesmas idas e voltas
- Bloco 2: Custo real
  - Cada deck consome ciclos de analista sênior em tarefa de formatação, não de julgamento
  - Decks de proposta levam, em média, de 8 a 12 slides para amarrar contexto, escopo e investimento
- Dados: 8 a 12 slides é o padrão de uma proposta A&M completa
- Layout sugerido: 60/40, lista de sintomas à esquerda, número de destaque em card à direita
- Fonte: referência interna A&M, estrutura-deck.md

### Slide 1.3: Como funciona o apresentacao-rapida-am
- Mensagem (takeaway): Dividir a criação do deck em sete etapas com validação cruzada entre agentes é o que permite trocar reunião de design por revisão automática, sem perder rigor.
- Bloco 1: As sete etapas
  - 1. Roteiro: conteúdo bruto vira estrutura de slides com takeaways
  - 2. Avaliação do roteiro: persona do público critica antes de seguir
  - 3. Layout: diretor de arte projeta a composição de cada slide
  - 4. Gráficos e 5. Decoração: dados e ícones/diagramas ganham forma visual
  - 6. Código LaTeX: tudo compila em PDF com a marca A&M
  - 7. QA visual: revisão crítica slide a slide antes da entrega
- Bloco 2: O que isso elimina
  - Retrabalho manual de formatação e diagramação
  - Inconsistência visual entre seções do mesmo deck
- Dados: 7 etapas, cada uma com validação própria antes de avançar para a próxima
- Layout sugerido: diagrama de fluxo horizontal com as 7 etapas numeradas
- Fonte:

## Capítulo 2: Estudo de caso ao vivo: Calculadora Macroeconômica [separador: light]

### Slide 2.1: Por dentro do projeto: de coletores a interface
- Mensagem (takeaway): A Calculadora Macroeconômica organiza a correção monetária em três camadas claras, captura de dados, motor de cálculo e interface, o que tornou a leitura automática do projeto direta.
- Bloco 1: As três camadas
  - Coletores: BCB SGS (séries realizadas), Boletim Focus (projeções), ANBIMA ETTJ (inflação implícita), B3 DI1 (curva de juros), IBGE Sidra
  - Motor: deflator, index_builder, projector e vector calculam fator acumulado e vetores mensais
  - Interface: app Streamlit com 6 abas (Calculadora, Vetor de Correção, ETTJ, Curva de Juros, Log de Atualizações, Documentação)
- Bloco 2: Por que isso facilita gerar um deck
  - Um único arquivo, ENGINE_CONTEXT.md, já documenta contratos, métodos e limites do motor
  - Código bem dividido por responsabilidade vira roteiro sem reunião de levantamento
- Dados: 7 índices suportados; 4 fontes de dados externas; cache de 1 a 7 dias
- Layout sugerido: diagrama de 3 colunas (coletores, motor, interface) com setas de fluxo de dados
- Fonte: ENGINE_CONTEXT.md, repositório do projeto (2026)

### Slide 2.2: A metodologia que sustenta cada número
- Mensagem (takeaway): Cada valor corrigido combina dados realizados em fator acumulado com projeções de mercado, sempre identificando qual parte do cálculo é fato e qual é expectativa.
- Bloco 1: Como o fator é calculado
  - Realizado: produto encadeado de (1 + taxa mensal) entre as duas datas, inclusive nas pontas
  - Projeção Focus: taxa anual mediana do Boletim Focus distribuída em taxa mensal composta uniforme
  - Projeção ETTJ: taxas forward extraídas da curva de inflação implícita da ANBIMA (NTN-B), válida apenas para IPCA
- Bloco 2: Índices disponíveis
  - IPCA, IGP-M, IPCA-15 e INPC têm projeção Focus; IPCA soma também a opção ETTJ
  - INCC, SELIC e CDI não projetam: a data final é limitada ao último dado realizado
- Dados: 7 índices, séries com início entre 1940 (IGP-M) e 1999 (IPCA-15); horizonte máximo de projeção de 120 meses (10 anos)
- Layout sugerido: tabela comparativa dos 7 índices à esquerda, fórmula do fator acumulado em destaque à direita
- Fonte: ENGINE_CONTEXT.md, API SGS e Boletim Focus do Banco Central do Brasil (2026)

### Slide 2.3: Recapitulando e como usar a ferramenta
- Mensagem (takeaway): Este deck saiu da pasta do projeto para o PDF final sem reunião de design, e o mesmo caminho está disponível para qualquer dor de dados do time de Capital Strategy.
- Bloco 1: O que vimos
  - A pipeline lê código, documentação e dados e devolve um roteiro estruturado e revisado
  - Cada etapa (conteúdo, layout, gráfico, decoração, código, QA) tem um agente dedicado à qualidade
  - O estudo de caso, a Calculadora Macroeconômica, mostrou a leitura de um projeto real do início ao fim
- Bloco 2: Próximos passos
  - Leve para o apresentacao-rapida-am o próximo memo, modelo ou repositório que precisa virar deck
  - Acesse a ferramenta em cortex.enpower.com.br/plugins/apresentacao-rapida-am
- Dados:
- Layout sugerido: 60/40, recapitulação em bullets à esquerda, QR code do link + texto "Criado com apresentacao-rapida-am" à direita
- Fonte:
