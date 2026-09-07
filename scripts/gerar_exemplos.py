"""Gera exemplos públicos exclusivamente fictícios."""

from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJETO))

from analise_juridica import gerar_relatorio
from exportar_relatorio import criar_formatos


DESTINO = PROJETO / "exemplos"
PDF = DESTINO / "processo-ficticio-para-teste.pdf"

TEXTO = """## Página 1

DOCUMENTO INTEIRAMENTE FICTÍCIO PARA TESTE
Processo: 1234567-89.2026.8.09.0001
Órgão julgador: 1ª Vara Fictícia da Comarca Exemplo
Autor: Marina Exemplo
Réu: Empresa Fictícia Ltda.
A autora alega falha contratual ocorrida em 01/08/2026.
Requer a devolução de R$ 1.000,00 e indenização.
O juízo decidiu intimar a parte ré para manifestar-se no prazo legal.
Este documento não corresponde a pessoas, fatos ou processos reais.
"""


def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(PDF), pagesize=A4)
    y = 790
    for linha in TEXTO.replace("## Página 1\n\n", "").splitlines():
        pdf.drawString(55, y, linha)
        y -= 28
    pdf.save()

    for modo, nome in (
        ("rapido", "resultado-resumo-rapido-ficticio.md"),
        ("completo", "resultado-relatorio-completo-ficticio.md"),
    ):
        destino = DESTINO / nome
        conteudo = gerar_relatorio(TEXTO, modo, PDF.name)
        destino.write_text(conteudo, encoding="utf-8")
        criar_formatos(conteudo, destino)
    print("Exemplos fictícios gerados em", DESTINO)


if __name__ == "__main__":
    main()
