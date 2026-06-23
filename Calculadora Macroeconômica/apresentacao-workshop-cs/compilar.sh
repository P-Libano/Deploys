#!/bin/bash
# Compila uma apresentação A&M com XeLaTeX (2 passadas) e limpa auxiliares.
# Uso: ./compilar.sh [nome-do-arquivo-sem-extensao]   (padrão: apresentacao)
set -e
cd "$(dirname "$0")"
ARQUIVO="${1:-apresentacao}"

xelatex -interaction=nonstopmode "${ARQUIVO}.tex" > /dev/null || true
xelatex -interaction=nonstopmode "${ARQUIVO}.tex" > /dev/null || true

if [ -f "${ARQUIVO}.pdf" ]; then
    rm -f "${ARQUIVO}".{aux,log,nav,out,snm,toc,vrb}
    echo "OK: ${ARQUIVO}.pdf gerado"
else
    echo "ERRO: PDF nao gerado. Rode 'xelatex ${ARQUIVO}.tex' para ver o log." >&2
    exit 1
fi
