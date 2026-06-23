# QA de equivalência da réplica PPTX (revisão 3)

## Correção adicional (revisão 3)
Após a revisão 2, o usuário reportou wordmark e régua superior duplicados (visível como
"fantasma" sobreposto no canto superior direito). Causa raiz: o layout do template
escolhido automaticamente (`Empty with logo`, e seu equivalente escuro) já traz, no próprio
master, um shape de imagem "Logo A&M" e uma linha "Linha Superior" fixos — e o código desta
réplica desenha seu próprio wordmark e régua por cima, gerando a duplicação. Corrigido
forçando o layout `Empty` (sem nenhum chrome pré-desenhado no master), já que o chrome é
inteiramente desenhado pelo código de cada slide, como o fluxo prevê. Reconferido nos 10
slides: nenhuma duplicação, nenhuma regressão de tamanho/posição/peso de fonte da revisão 2.

## Resumo
A primeira versão entregue tinha um problema sistêmico real, identificado pelo usuário
("texto ficou pequeno, ficou fora do layout, despadronizou as âncoras") e não capturado
pela primeira rodada de QA. Causa raiz: o template real desta apresentação
(`am-infra-template.pptx`, 18288000 x 10287000 EMU) é 1,5x maior fisicamente que o slide
16:9 padrão (13,333 x 7,5 in) para o qual o guia de tamanhos de fonte do fluxo foi
calibrado. Usar os pontos do guia ao pé da letra deixou todo texto desproporcionalmente
pequeno e desalinhou eyebrow/régua/título em relação à posição real da referência.

Correção aplicada:
- Fator de escala de fonte (`FONT_SCALE` ≈ 1,785) calibrado por medição de pixel contra
  `ref/slide-03.png` (altura do título da réplica igualada à da referência, 31px = 31px).
- Posições de eyebrow/régua/título em `chrome_claro()` recalibradas por varredura de pixel
  da referência (eyebrow ~0,016–0,034; régua ~0,052; título ~0,071–0,135 da altura), em vez
  das frações genéricas do guia.
- Peso de fonte dos títulos de separador (slides 02 e 06) corrigido de negrito para regular,
  igualando ao peso real da referência.
- Reconstrução completa do `apresentacao.pptx` a partir do template original antes de cada
  rebuild, eliminando duplicação de slides.

Após a correção, os 10 slides foram re-renderizados e comparados individualmente contra
`ref/slide-NN.png`. Score médio de divergência: 0,063 (todos abaixo de 0,094).

## Divergências remanescentes (nenhuma bloqueante)
- Slide 02 (separador 01): fundo réplica é navy sólido; a referência tem textura sutil de
  grade/pontos sobre o navy. Cosmético, não afeta legibilidade nem chrome.
- Slide 10 (contracapa): logo levemente mais acima/centrado que na referência. Menor.
- Slides 03, 04, 05, 07, 08, 09: divergência residual concentrada em antialiasing e métrica
  de fonte do LibreOffice (Arial Nova) vs. o XeLaTeX original. Tamanho, posição, hierarquia,
  cores, ícones, tabela, diagrama e QR code equivalentes à referência em todos.

## Estrutura
- Contagem pptx vs. referência: ok (10/10, mesma ordem).
- Sobras de placeholder: nenhuma.
- Travessão longo (em-dash): nenhum.
- Fontes fora de Arial Nova/Arial: nenhuma.

## Checklist aplicado slide a slide (revisado visualmente após a correção)
- Capa (01): foto full-bleed, logo, título "Workshop CS", subtítulo e data no tamanho e
  posição da referência.
- Separadores (02, 06): numeração, título (agora em peso regular, igual à referência) e
  wordmark equivalentes; quebra de linha do título do slide 06 confere com a referência.
- Conteúdo (03, 04, 05, 07, 08, 09): eyebrow, régua e título no alinhamento e tamanho da
  referência; corpo, ícones, diagrama, tabela e QR code sem distorção; takeaway e fonte de
  rodapé reproduzidos; nenhum estouro de caixa ou quebra inesperada após o aumento de fonte.
- Contracapa (10): foto full-bleed e logo centralizados.

## Veredito: APROVADO
