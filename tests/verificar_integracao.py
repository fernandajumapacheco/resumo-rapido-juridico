"""Verificação local sem pytest e sem documentos reais."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from time import sleep

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJETO))


def criar_pdf_ficticio(destino: Path) -> None:
    pdf = canvas.Canvas(str(destino), pagesize=A4)
    linhas = [
        "DOCUMENTO INTEIRAMENTE FICTICIO PARA TESTE",
        "Processo: 1234567-89.2026.8.09.0001",
        "Autor: Marina Exemplo",
        "Reu: Empresa Ficticia Ltda.",
        "A autora alega falha contratual ocorrida em 01/08/2026.",
        "Requer a devolucao de R$ 1.000,00 e indenizacao.",
        "O juizo decidiu intimar a parte re para manifestar-se no prazo legal.",
        "Este documento nao corresponde a pessoas ou processos reais.",
    ]
    y = 790
    for linha in linhas:
        pdf.drawString(60, y, linha)
        y -= 30
    pdf.save()


def aguardar(app, trabalho_id: str) -> dict:
    for _ in range(200):
        resultado = app.consultar_trabalho(trabalho_id)
        if resultado["estado"] != "processando":
            return resultado
        sleep(0.05)
    raise TimeoutError("O teste demorou mais de 10 segundos.")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="resumo-juridico-") as temporaria:
        raiz = Path(temporaria)
        os.environ["RESUMO_LOCAL_DADOS"] = str(raiz / "dados")
        pdf = raiz / "processo-ficticio-para-teste.pdf"
        criar_pdf_ficticio(pdf)

        import app

        assert app.saude() == {"ok": True, "motor": "Python", "versao": "1.1.0"}
        existente = app.ENTRADA / "repetido.pdf"
        existente.write_bytes(b"teste")
        novo = app.destino_seguro(app.ENTRADA, existente.name)
        assert novo != existente and novo.suffix == ".pdf"

        for modo in ("rapido", "completo"):
            trabalho = app.novo_trabalho(pdf, ".pdf", modo=modo)
            resultado = aguardar(app, trabalho["id"])
            assert resultado["estado"] == "concluido", resultado
            assert not any("/" in str(resultado.get(chave, "")) for chave in (
                "nome_arquivo", "markdown_nome", "arquivo_analise_nome"
            ))
            base = app.RESUMOS / resultado["arquivo_analise_nome"]
            for extensao in (".md", ".docx", ".pdf"):
                arquivo = base.with_suffix(extensao)
                assert arquivo.is_file() and arquivo.stat().st_size > 0

        original_which = app.shutil.which
        app.shutil.which = lambda comando: None if comando == "pdftotext" else original_which(comando)
        try:
            trabalho = app.novo_trabalho(pdf, ".pdf", modo="rapido")
            resultado = aguardar(app, trabalho["id"])
            assert resultado["estado"] == "concluido", resultado
            assert resultado["metodo"] == "Leitor Python (PyMuPDF)"
        finally:
            app.shutil.which = original_which

        print("OK: rápido, completo, leitor Python, nomes seguros, saúde privada e três formatos")


if __name__ == "__main__":
    main()
