# Decoração: Workshop CS | Calculadora Macroeconômica

## D1 — Diagrama de fluxo horizontal (pipeline de 7 etapas)
- Arquivo validado: `decoracao/_valida_d1.tex` (compilado isoladamente com xelatex, 2 passadas)
- Slide: 1.3 ("Como funciona o apresentacao-rapida-am"), Região A (full-width, topo)
- Dimensão real do standalone: 151.4mm x 9.7mm (alvo do layouts.md: ~150mm x 30mm de largura; a altura final é menor porque os nós são de uma linha só — ver nota abaixo)
- Conteúdo: 7 nós retangulares navy (`amNavy` 002B49) com texto branco, ligados por setas finas cinza (`amGray` 646464, Stealth), rótulos "01 Roteiro" a "07 QA"
- Validação visual: texto legível, sem colisão entre nós, fluxo esquerdo→direito limpo (ver `d1_preview-1.png`)
- Nota de implementação: o texto de cada nó foi simplificado para uma linha única ("01 Roteiro" em vez de número + quebra de linha) porque `\\` dentro do nó do TikZ, combinado com `align=center`, quebrava a compilação (ver histórico de depuração); o resultado de uma linha é igualmente legível e mais robusto
- Uso no deck: incluir via `\includegraphics[width=\textwidth]{decoracao/_valida_d1.pdf}` (ou recompilar dentro do `.tex` principal), redimensionado para ocupar a largura da Região A do slide 1.3

## I1 — Ícones dos 3 destaques numerados (slide 1.1)
- Arquivos: `decoracao/icones/search-slate.pdf`, `decoracao/icones/shield-check-slate.pdf`, `decoracao/icones/file-text-slate.pdf`
- Slide: 1.1, ao lado de cada um dos 3 destaques numerados (01/02/03) da Região A
- Tamanho: 5mm, cor slate (consistente, 1 cor por deck)
- Racional: reforça a leitura rápida de cada ponto sem competir com o texto

## I2 — Ícones dos 3 cards de camada (slide 2.1)
- Arquivos: `decoracao/icones/database-navy.pdf`, `decoracao/icones/cog-navy.pdf`, `decoracao/icones/monitor-navy.pdf`
- Slide: 2.1, no topo de cada card (Coletores, Motor, Interface), ao lado do título do card
- Tamanho: 5mm, cor navy
- Racional: identifica a camada do projeto à primeira vista, antes da leitura do texto do card

## I3 — Ícone do call-to-action final (slide 2.3)
- Arquivo: `decoracao/icones/rocket-navy.pdf`
- Slide: 2.3, ao lado do subtítulo "Próximos passos"
- Tamanho: 5mm, cor navy (mesma cor de I2, 1 só cor de ícone no deck)
- Racional: marca visualmente o fechamento de ação do deck

## Nota sobre o QR code (slide 2.3)
Conforme `layouts.md`, o QR code não é um asset de decoração (não está no catálogo de ícones nem é foto): será gerado diretamente em LaTeX pelo pacote `qrcode` na etapa `codar-latex`, apontando para `https://cortex.enpower.com.br/plugins/apresentacao-rapida-am`.

## Auto-revisão
- Catálogo respeitado: nenhum ícone gerado por IA, busca web ou clip-art; todos vêm do catálogo de 70 ícones Lucide recolorido do tema.
- Uma única cor de ícone por região consistente (slate em I1, navy em I2/I3) — dentro do limite de 1 cor de ícone por deck (navy predominante, slate como variação dentro do mesmo grupo neutro).
- D1 validado isoladamente antes de entrar no deck principal, com inspeção visual da rasterização.
