#!/bin/zsh
set -u

cd "$(dirname "$0")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 não foi encontrado. Instale o Python 3.11 ou superior e tente novamente."
  read "?Pressione Enter para fechar."
  exit 1
fi

if [[ ! -d .venv ]]; then
  echo "Preparando o ambiente local pela primeira vez..."
  python3 -m venv .venv || exit 1
fi

if ! .venv/bin/python -c "import fastapi, pymupdf, markdown_it, docx, reportlab, uvicorn" >/dev/null 2>&1; then
  echo "Instalando as dependências locais..."
  .venv/bin/pip install -r requirements.txt || exit 1
fi

.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8787 &
SERVIDOR_PID=$!

for tentativa in {1..30}; do
  if curl -fsS --max-time 1 http://127.0.0.1:8787/saude >/dev/null 2>&1; then
    open http://127.0.0.1:8787/
    echo "Resumo Rápido Jurídico aberto. Mantenha esta janela aberta durante o uso."
    wait "$SERVIDOR_PID"
    exit $?
  fi
  sleep 1
done

echo "O programa demorou mais que o esperado para iniciar."
kill "$SERVIDOR_PID" >/dev/null 2>&1 || true
read "?Pressione Enter para fechar."
exit 1
