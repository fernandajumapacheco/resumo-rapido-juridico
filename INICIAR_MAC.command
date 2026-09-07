#!/bin/zsh
set -u

cd "$(dirname "$0")" || exit 1

PYTHON_CMD=""
for candidato in python3.13 python3.12 python3.11 python3; do
  if command -v "$candidato" >/dev/null 2>&1; then
    PYTHON_CMD="$candidato"
    break
  fi
done

if [[ -z "$PYTHON_CMD" ]]; then
  echo "Python 3 não foi encontrado. Instale o Python 3.11 ou superior e tente novamente."
  read "?Pressione Enter para fechar."
  exit 1
fi

if [[ ! -d .venv ]]; then
  echo "Preparando o ambiente local pela primeira vez..."
  "$PYTHON_CMD" -m venv .venv || exit 1
fi

if ! .venv/bin/python -c "import fastapi, pymupdf, markdown_it, docx, reportlab, uvicorn" >/dev/null 2>&1; then
  echo "Instalando as dependências locais..."
  .venv/bin/pip install -r requirements.txt || exit 1
fi

echo "Resumo Rápido Jurídico será aberto no navegador. Mantenha esta janela aberta durante o uso."
.venv/bin/python iniciar.py
