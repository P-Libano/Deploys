# Mapa de réplica PPTX

Referência de cada slide: a imagem em `ref/`. Texto vira texto
editável; todo visual vira PNG de `assets-png/`. Caixas em frações
da página (x, y, largura, altura), de 0 a 1.

## Slide 01 (ref/slide-01.png) — capa, escura
Bloco: blocos/slide-01.tex
Chrome: fundo full-bleed com foto de skyline noturno (tons de azul/navy), logo A&M/INFRA no topo esquerdo, régua fina horizontal acima do bloco de título.
Texto:
- logo (0.02, 0.03, 0.20, 0.09): wordmark "A&M" + "INFRA — A Capital Projects by Alvarez & Marsal" (ver assets-png/covers_tecnologia.png como referência visual; logo em si é vetor do tema)
- titulo (0.02, 0.60, 0.55, 0.09): "Workshop CS"
- subtitulo (0.02, 0.70, 0.62, 0.06): "Calculadora Macroeconômica — de repositório a apresentação" (sem travessão na réplica: usar "de repositório a apresentação")
- data (0.84, 0.91, 0.14, 0.04): "22.06.2026"
Visuais:
- assets-png/covers_tecnologia.png -> (0.0, 0.0, 1.0, 1.0)  imagem de fundo full-bleed
Acento: amSignal (régua e detalhes), fundo amNavy escurecido pela foto

## Slide 02 (ref/slide-02.png) — separador, escuro
Bloco: blocos/slide-02.tex
Chrome: fundo amNavy sólido; régua superior fina; logo "Alvarez & Marsal / Leadership. Action. Results." no canto superior direito.
Texto:
- numero (0.02, 0.32, 0.14, 0.16): "01" (cinza-claro/amMist, fonte condensada leve)
- titulo (0.02, 0.47, 0.55, 0.10): "Da dor ao deck em minutos" (branco, bold)
Visuais:
- (nenhum visual além do chrome do tema; logo é vetor do template)
Acento: amMist (número), branco (título), amNavy (fundo)

## Slide 03 (ref/slide-03.png) — conteúdo, claro
Bloco: blocos/slide-03.tex
Chrome: eyebrow "DA DOR AO DECK EM MINUTOS" no topo esquerdo; logo A&M no topo direito; régua fina sob o cabeçalho; número de página "1" no rodapé direito.
Texto:
- eyebrow (0.02, 0.02, 0.45, 0.03): "DA DOR AO DECK EM MINUTOS"
- titulo (0.02, 0.08, 0.60, 0.08): "Objetivos deste workshop"
- item-01 (0.02, 0.27, 0.47, 0.07): "01  [ícone busca]  Como a pipeline lê um projeto real (código, dados, documentação) e gera um roteiro estruturado"
- item-02 (0.02, 0.38, 0.47, 0.07): "02  [ícone escudo]  Como cada etapa (roteiro, layout, gráficos, decoração, código, QA) é revisada por um agente especialista antes de avançar"
- item-03 (0.02, 0.49, 0.47, 0.07): "03  [ícone documento]  Este próprio deck como prova: foi gerado a partir da pasta do projeto Calculadora Macroeconômica"
- kpi-numero (0.50, 0.26, 0.48, 0.06): "7 etapas"
- kpi-rotulo (0.50, 0.32, 0.48, 0.03): "do roteiro ao PDF final"
- bullet-1 (0.52, 0.40, 0.45, 0.05): "Propostas e relatórios de Capital Strategy nascem de planilhas, modelos e memos densos"
- bullet-2 (0.52, 0.47, 0.45, 0.04): "Hoje, tempo de formatação compete com tempo de análise"
- takeaway (0.02, 0.86, 0.92, 0.09): "Ao final deste workshop, o time de Capital Strategy entende como transformar um repositório de código e dados em uma apresentação pronta, sem depender de designer ou de horas de formatação manual."
- pagina (0.96, 0.96, 0.03, 0.03): "1"
Visuais:
- assets-png/decoracao_icones_search-slate.png -> (0.02, 0.275, 0.035, 0.045)
- assets-png/decoracao_icones_shield-check-slate.png -> (0.02, 0.385, 0.035, 0.045)
- assets-png/decoracao_icones_file-text-slate.png -> (0.02, 0.495, 0.035, 0.045)
- divisor 1: recortar de ref/slide-03.png (0.02, 0.345, 0.47, 0.003) linha fina amMist
- divisor 2: recortar de ref/slide-03.png (0.02, 0.455, 0.47, 0.003) linha fina amMist
- divisor card (0.50, 0.355, 0.45, 0.003) linha fina amMist
- card kpi fundo: recortar de ref/slide-03.png (0.50, 0.255, 0.48, 0.095) caixa cinza-claro (amTableStripe/amMist)
Acento: amSignal (números 01/02/03 e ícones)

## Slide 04 (ref/slide-04.png) — conteúdo, claro
Bloco: blocos/slide-04.tex
Chrome: eyebrow "DA DOR AO DECK EM MINUTOS", logo topo direito, régua sob cabeçalho, número de página "2".
Texto:
- eyebrow (0.02, 0.02, 0.45, 0.03): "DA DOR AO DECK EM MINUTOS"
- titulo (0.02, 0.08, 0.70, 0.08): "A dor: dados prontos, apresentação represada"
- rotulo-sintomas (0.02, 0.24, 0.30, 0.04): "Sintomas comuns" (bold)
- bullets-sintomas (0.02, 0.29, 0.50, 0.20): lista de 4 itens (ver bloco .tex)
- highlight-numero (0.61, 0.24, 0.34, 0.06): "8–12"
- highlight-rotulo (0.61, 0.30, 0.34, 0.04): "slides por proposta A&M, hoje gastos em formatação"
- card-titulo (0.62, 0.41, 0.32, 0.04): "Custo real" (bold)
- card-texto (0.62, 0.46, 0.32, 0.14): "Cada deck consome ciclos de analista sênior em tarefa de formatação, não de julgamento. É o intervalo que, hoje, amarra contexto, escopo e investimento em cada proposta."
- takeaway (0.02, 0.84, 0.82, 0.08): "O gargalo de uma apresentação raramente é a análise, é transformar a análise em slides consistentes e bem desenhados na velocidade que o negócio pede."
- fonte (0.02, 0.94, 0.30, 0.03): "Fonte: referência interna A&M, estrutura-deck.md"
- pagina (0.96, 0.96, 0.03, 0.03): "2"
Visuais:
- amcard borda: recortar de ref/slide-04.png (0.61, 0.39, 0.34, 0.23) caixa com borda cinza-clara
Acento: amSignal (número de destaque "8–12")

## Slide 05 (ref/slide-05.png) — conteúdo, claro
Bloco: blocos/slide-05.tex
Chrome: eyebrow "DA DOR AO DECK EM MINUTOS", logo topo direito, régua sob cabeçalho, número de página "3".
Texto:
- eyebrow (0.02, 0.02, 0.45, 0.03): "DA DOR AO DECK EM MINUTOS"
- titulo (0.02, 0.08, 0.70, 0.08): "Como funciona o apresentacao-rapida-am"
- rotulo-garante (0.02, 0.455, 0.46, 0.03): "O que isso garante" (bold)
- texto-garante (0.02, 0.49, 0.46, 0.14): "Cada uma das 7 etapas, do roteiro ao código LaTeX, passa por validação própria antes de avançar para a próxima, o que elimina retrabalho de formatação e inconsistência visual entre seções do mesmo deck."
- rotulo-elimina (0.50, 0.455, 0.46, 0.03): "O que isso elimina" (bold)
- bullets-elimina (0.52, 0.49, 0.44, 0.08): 2 itens (ver bloco .tex)
- takeaway (0.02, 0.84, 0.82, 0.09): "Dividir a criação do deck em sete etapas com validação cruzada entre agentes é o que permite trocar reunião de design por revisão automática, sem perder rigor."
- pagina (0.96, 0.96, 0.03, 0.03): "3"
Visuais:
- assets-png/decoracao__valida_d1.png -> (0.02, 0.24, 0.96, 0.16)  diagrama de fluxo horizontal com as 7 etapas numeradas (caixas navy conectadas por setas)
Acento: amNavy (caixas do diagrama)

## Slide 06 (ref/slide-06.png) — separador, claro
Bloco: blocos/slide-06.tex
Chrome: fundo branco; régua superior fina azul; logo "Alvarez & Marsal" no canto superior direito.
Texto:
- numero (0.02, 0.32, 0.14, 0.16): "02" (azul claro/amSignal acinzentado)
- titulo (0.02, 0.47, 0.66, 0.13): "Estudo de caso ao vivo: Calculadora Macroeconômica" (navy, bold, duas linhas)
Visuais:
- (nenhum visual além do chrome do tema)
Acento: amSignal (número), amNavy (título)

## Slide 07 (ref/slide-07.png) — conteúdo, claro
Bloco: blocos/slide-07.tex
Chrome: eyebrow "ESTUDO DE CASO AO VIVO: CALCULADORA MACROECONÔMICA", logo topo direito, régua sob cabeçalho, número de página "4".
Texto:
- eyebrow (0.02, 0.02, 0.55, 0.03): "ESTUDO DE CASO AO VIVO: CALCULADORA MACROECONÔMICA"
- titulo (0.02, 0.08, 0.70, 0.08): "Por dentro do projeto: de coletores a interface"
- card1-titulo (0.03, 0.275, 0.28, 0.04): "Coletores" (bold, com ícone à esquerda)
- card1-texto (0.03, 0.32, 0.28, 0.13): "BCB SGS (séries realizadas), Boletim Focus (projeções), ANBIMA ETTJ (inflação implícita), B3 DI1 (curva de juros) e IBGE Sidra."
- card2-titulo (0.35, 0.275, 0.28, 0.04): "Motor" (bold, com ícone à esquerda)
- card2-texto (0.35, 0.32, 0.28, 0.13): "Módulos deflator, index_builder, projector e vector calculam fator acumulado e vetores mensais."
- card3-titulo (0.67, 0.275, 0.28, 0.04): "Interface" (bold, com ícone à esquerda)
- card3-texto (0.67, 0.32, 0.28, 0.13): "App Streamlit com 6 abas: Calculadora, Vetor de Correção, ETTJ, Curva de Juros, Log de Atualizações, Documentação."
- stat1-numero (0.02, 0.58, 0.30, 0.06): "7"
- stat1-rotulo (0.02, 0.66, 0.30, 0.03): "índices suportados"
- stat2-numero (0.35, 0.58, 0.30, 0.06): "4"
- stat2-rotulo (0.35, 0.66, 0.30, 0.03): "fontes de dados"
- stat3-numero (0.67, 0.58, 0.30, 0.06): "1–7 dias"
- stat3-rotulo (0.67, 0.66, 0.30, 0.03): "ciclo de cache"
- nota-central (0.13, 0.74, 0.74, 0.06): "Um único arquivo, ENGINE_CONTEXT.md, já documenta contratos e limites do motor: código dividido por responsabilidade vira roteiro sem reunião de levantamento." (cinza, centralizado)
- takeaway (0.02, 0.84, 0.78, 0.08): "A Calculadora Macroeconômica organiza a correção monetária em três camadas claras, captura de dados, motor de cálculo e interface, o que tornou a leitura automática do projeto direta."
- fonte (0.02, 0.94, 0.35, 0.03): "Fonte: ENGINE_CONTEXT.md, repositório do projeto (2026)"
- pagina (0.96, 0.96, 0.03, 0.03): "4"
Visuais:
- assets-png/decoracao_icones_database-navy.png -> (0.03, 0.28, 0.03, 0.04)
- assets-png/decoracao_icones_cog-navy.png -> (0.35, 0.28, 0.03, 0.04)
- assets-png/decoracao_icones_monitor-navy.png -> (0.67, 0.28, 0.03, 0.04)
- bordas dos 3 cards: recortar de ref/slide-07.png (cada card com borda cinza-clara fina)
- linhas verticais divisórias da statstrip: recortar de ref/slide-07.png entre os 3 blocos
Acento: amNavy (números/ícones), amSignal (não dominante neste slide)

## Slide 08 (ref/slide-08.png) — conteúdo, claro
Bloco: blocos/slide-08.tex
Chrome: eyebrow "ESTUDO DE CASO AO VIVO: CALCULADORA MACROECONÔMICA", logo topo direito, régua sob cabeçalho, número de página "5".
Texto:
- eyebrow (0.02, 0.02, 0.55, 0.03): "ESTUDO DE CASO AO VIVO: CALCULADORA MACROECONÔMICA"
- titulo (0.02, 0.08, 0.70, 0.08): "A metodologia que sustenta cada número"
- tabela (0.02, 0.255, 0.38, 0.22): tabela 4 colunas x 8 linhas (cabeçalho navy + linhas com zebra amTableStripe) — Índice/Fonte SGS/Início/Projeção, 7 índices (IPCA, IGP-M, IPCA-15, INPC, INCC, SELIC, CDI)
- rotulo-formula (0.62, 0.255, 0.34, 0.04): "Como o fator é calculado" (bold)
- formula (0.62, 0.30, 0.34, 0.05): "factor = ∏(1+rₜ/100)" (azul, bold)
- bullets-formula (0.62, 0.36, 0.34, 0.16): 3 itens (Realizado/Focus/ETTJ, ver bloco .tex)
- nota-indices (0.62, 0.575, 0.34, 0.09): "IPCA, IGP-M, IPCA-15 e INPC têm projeção Focus, e o IPCA soma também a opção ETTJ. INCC, SELIC e CDI não projetam: a data final fica limitada ao último dado realizado." (cinza)
- takeaway (0.02, 0.84, 0.78, 0.08): "Cada valor corrigido combina dados realizados em fator acumulado com projeções de mercado, sempre identificando qual parte do cálculo é fato e qual é expectativa."
- fonte (0.02, 0.94, 0.45, 0.03): "Fonte: ENGINE_CONTEXT.md, API SGS e Boletim Focus do Banco Central do Brasil (2026)"
- pagina (0.96, 0.96, 0.03, 0.03): "5"
Visuais:
- tabela: recriar como tabela nativa do PowerPoint (não é imagem; replicar cores cabeçalho amNavy/texto branco e zebra amTableStripe)
- divisor (0.62, 0.555, 0.30, 0.003) linha fina amMist
Acento: amSignal (fórmula), amNavy (cabeçalho da tabela)

## Slide 09 (ref/slide-09.png) — conteúdo, claro
Bloco: blocos/slide-09.tex
Chrome: eyebrow "ESTUDO DE CASO AO VIVO: CALCULADORA MACROECONÔMICA", logo topo direito, régua sob cabeçalho, número de página "6".
Texto:
- eyebrow (0.02, 0.02, 0.55, 0.03): "ESTUDO DE CASO AO VIVO: CALCULADORA MACROECONÔMICA"
- titulo (0.02, 0.08, 0.70, 0.08): "Recapitulando e como usar a ferramenta"
- recap-01 (0.02, 0.24, 0.62, 0.04): "01  A pipeline lê código, documentação e dados e devolve um roteiro estruturado e revisado"
- recap-02 (0.02, 0.30, 0.62, 0.04): "02  Cada etapa tem um agente dedicado à qualidade"
- recap-03 (0.02, 0.355, 0.62, 0.04): "03  Estudo de caso real do início ao fim"
- rotulo-proximos (0.02, 0.455, 0.45, 0.04): "[ícone foguete]  Próximos passos" (bold)
- bullet-1 (0.04, 0.50, 0.45, 0.06): "Leve para o apresentacao-rapida-am o próximo memo, modelo ou repositório que precisa virar deck"
- bullet-2 (0.04, 0.565, 0.45, 0.06): "Acesse a ferramenta em cortex.enpower.com.br/plugins/apresentacao-rapida-am"
- legenda-qr (0.66, 0.715, 0.22, 0.03): "Criado com apresentacao-rapida-am" (cinza, pequeno)
- takeaway (0.02, 0.84, 0.78, 0.08): "Este deck saiu da pasta do projeto para o PDF final sem reunião de design, e o mesmo caminho está disponível para qualquer dor de dados do time de Capital Strategy."
- pagina (0.96, 0.96, 0.03, 0.03): "6"
Visuais:
- assets-png/decoracao_icones_rocket-navy.png -> (0.02, 0.46, 0.03, 0.04)
- QR code apontando para https://cortex.enpower.com.br/plugins/apresentacao-rapida-am: recortar de ref/slide-09.png (0.70, 0.48, 0.13, 0.22) — gerar PNG vetorial equivalente ao qrcode do .tex
Acento: amSignal (números 01/02/03)

## Slide 10 (ref/slide-10.png) — contracapa, escura
Bloco: blocos/slide-10.tex
Chrome: fundo amNavy com gradiente sutil mais claro no canto superior; logo "A&M / INFRA" centralizado no terço inferior.
Texto:
- (sem texto além do logo/wordmark do template)
Visuais:
- assets-png/covers_backcover.png -> (0.0, 0.0, 1.0, 1.0)  fundo gradiente full-bleed
Acento: amNavy (fundo)
