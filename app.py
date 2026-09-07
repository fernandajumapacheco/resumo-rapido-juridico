"""Resumo Rápido Jurídico com extração e análise determinística em Python."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from threading import Lock, Thread
from time import monotonic
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from markdown_it import MarkdownIt

from analise_juridica import gerar_relatorio, estatisticas
from exportar_relatorio import criar_formatos


PROJETO = Path(__file__).resolve().parent
BASE = Path(os.getenv("RESUMO_LOCAL_DADOS", PROJETO / "dados")).expanduser().resolve()
ENTRADA = Path(os.getenv("RESUMO_ENTRADA", BASE / "01_entrada")).expanduser().resolve()
MARKDOWN = Path(os.getenv("RESUMO_MARKDOWN", BASE / "02_markdown")).expanduser().resolve()
RESUMOS = Path(os.getenv("RESUMO_SAIDA", BASE / "03_resumos")).expanduser().resolve()
LIMITE_MB = int(os.getenv("LIMITE_ARQUIVO_MB", "100"))
VERSAO = "1.1.1"
EXTENSOES_ACEITAS = {".pdf", ".md", ".markdown"}
RENDERIZADOR = MarkdownIt("commonmark", {"html": False, "linkify": False})
TRABALHOS: dict[str, dict] = {}
TRAVA = Lock()

for pasta in (ENTRADA, MARKDOWN, RESUMOS):
    pasta.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Resumo Rápido Jurídico")
app.mount("/web", StaticFiles(directory=PROJETO / "web"), name="web")


@app.get("/")
def inicio():
    return FileResponse(PROJETO / "web" / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/saude")
def saude():
    return {"ok": True, "motor": "Python", "versao": VERSAO}


def atualizar(trabalho_id: str, **dados):
    with TRAVA:
        TRABALHOS[trabalho_id].update(dados)


def destino_seguro(pasta: Path, nome: str) -> Path:
    """Evita sobrescrever um documento anterior com o mesmo nome."""
    destino = pasta / nome
    if destino.exists():
        destino = pasta / f"{Path(nome).stem}-{uuid4().hex[:8]}{Path(nome).suffix.lower()}"
    return destino


def extrair_pdf(origem: Path, trabalho_id: str) -> tuple[str, str]:
    pdftotext = shutil.which("pdftotext")
    texto = ""
    if pdftotext:
        atualizar(
            trabalho_id,
            etapa="Lendo o PDF rapidamente",
            progresso=18,
            detalhe="Tentando extrair o texto que já existe no PDF.",
        )
        with tempfile.NamedTemporaryFile(suffix=".txt") as temporario:
            subprocess.run(
                [pdftotext, "-layout", str(origem), temporario.name],
                check=True,
                timeout=180,
                capture_output=True,
            )
            bruto = Path(temporario.name).read_text(encoding="utf-8", errors="replace")
            paginas = [pagina.strip() for pagina in bruto.split("\f") if pagina.strip()]
            texto = "\n\n".join(
                f"## Página {numero}\n\n{pagina}" for numero, pagina in enumerate(paginas, 1)
            )

    if len("".join(texto.split())) >= 80:
        return texto, "Leitor rápido (pdftotext)"

    atualizar(
        trabalho_id,
        etapa="Tentando o leitor Python",
        progresso=24,
        detalhe="Procurando texto incorporado ao PDF antes de usar OCR.",
    )
    try:
        import pymupdf as fitz
    except ImportError as erro:
        raise RuntimeError("Instale as dependências principais descritas no guia.") from erro

    paginas_python: list[str] = []
    with fitz.open(origem) as documento:
        for numero, pagina in enumerate(documento, start=1):
            conteudo = pagina.get_text("text").strip()
            if conteudo:
                paginas_python.append(f"## Página {numero}\n\n{conteudo}")
    texto_python = "\n\n".join(paginas_python)
    if len("".join(texto_python.split())) >= 80:
        return texto_python, "Leitor Python (PyMuPDF)"

    atualizar(
        trabalho_id,
        etapa="PDF escaneado: usando OCR",
        progresso=28,
        detalhe="O arquivo parece ser uma imagem. O OCR será mais demorado.",
    )
    try:
        from rapidocr import RapidOCR
    except ImportError as erro:
        raise RuntimeError(
            "Este PDF precisa de OCR. Instale as dependências opcionais descritas no guia."
        ) from erro

    leitor = RapidOCR()
    partes: list[str] = []
    with fitz.open(origem) as documento:
        total = len(documento)
        for numero, pagina in enumerate(documento, start=1):
            atualizar(
                trabalho_id,
                progresso=min(52, 28 + int(24 * numero / max(total, 1))),
                detalhe=f"OCR lendo página {numero} de {total}.",
            )
            imagem = pagina.get_pixmap(dpi=144, alpha=False).tobytes("png")
            resultado = leitor(imagem)
            partes.append(f"\n\n## Página {numero}\n\n" + "\n".join(resultado.txts or ()))
    return "".join(partes), "OCR (PyMuPDF + RapidOCR)"


def executar(trabalho_id: str, origem: Path, extensao: str, modo: str):
    inicio_tempo = monotonic()
    try:
        if extensao == ".pdf":
            texto, metodo = extrair_pdf(origem, trabalho_id)
            destino_md = MARKDOWN / f"{origem.stem}.md"
            destino_md.write_text(texto, encoding="utf-8")
            atualizar(
                trabalho_id,
                etapa="Texto extraído; preparando o relatório",
                progresso=55,
                markdown_nome=destino_md.name,
                markdown_concluido=True,
                metodo=metodo,
                detalhe=f"Markdown salvo. Método usado: {metodo}.",
            )
        else:
            texto = origem.read_text(encoding="utf-8-sig")
            destino_md = origem
            atualizar(
                trabalho_id,
                etapa="Markdown pronto; iniciando a análise",
                progresso=55,
            markdown_nome=destino_md.name,
                markdown_concluido=True,
                metodo="Markdown já pronto",
                detalhe="Indo diretamente para a análise em Python.",
            )

        if not texto.strip():
            raise ValueError("O arquivo não contém texto para analisar.")

        atualizar(
            trabalho_id,
            etapa="Python organizando as informações",
            progresso=70,
            detalhe="Localizando identificação, partes, pedidos, decisões e prazos.",
        )
        analise = gerar_relatorio(texto, modo, origem.name).strip()
        if not analise:
            raise ValueError("A análise terminou sem produzir um relatório.")
        sufixo = "relatorio-completo" if modo == "completo" else "resumo-rapido"
        destino_resumo = RESUMOS / f"{destino_md.stem}-{sufixo}.md"
        destino_resumo.write_text(analise, encoding="utf-8")
        atualizar(
            trabalho_id,
            etapa="Preparando arquivos para baixar",
            progresso=92,
            detalhe="Criando as versões editável em Word e pronta para leitura em PDF.",
        )
        formatos = criar_formatos(analise, destino_resumo)
        atualizar(
            trabalho_id,
            estado="concluido",
            etapa="Concluído",
            progresso=100,
            detalhe="Conversão e análise em Python concluídas com sucesso.",
            analise_html=RENDERIZADOR.render(analise),
            arquivo_analise_nome=destino_resumo.name,
            download_md=f"/downloads/{destino_resumo.name}",
            download_docx=f"/downloads/{formatos['docx'].name}",
            download_pdf=f"/downloads/{formatos['pdf'].name}",
            resumo_concluido=True,
            modo=modo,
            estatisticas=estatisticas(texto),
            segundos=round(monotonic() - inicio_tempo),
        )
    except Exception as erro:
        atualizar(
            trabalho_id,
            estado="erro",
            etapa="Não foi possível concluir",
            detalhe=str(erro),
            erro=str(erro),
            segundos=round(monotonic() - inicio_tempo),
        )


def novo_trabalho(origem: Path, extensao: str, modo: str = "rapido", markdown_pronto: bool = False) -> dict:
    if modo not in {"rapido", "completo"}:
        modo = "rapido"
    trabalho_id = uuid4().hex
    TRABALHOS[trabalho_id] = {
        "id": trabalho_id,
        "estado": "processando",
        "etapa": "Arquivo recebido",
        "progresso": 8,
        "detalhe": "Arquivo salvo. Iniciando o processamento.",
        "nome_arquivo": origem.name,
        "markdown_nome": origem.name if markdown_pronto else None,
        "arquivo_analise_nome": None,
        "markdown_concluido": markdown_pronto,
        "resumo_concluido": False,
        "modo": modo,
    }
    Thread(target=executar, args=(trabalho_id, origem, extensao, modo), daemon=True).start()
    return TRABALHOS[trabalho_id]


@app.post("/trabalhos")
def criar_trabalho(arquivo: UploadFile = File(...), modo: str = Form("rapido")):
    if not arquivo.filename:
        raise HTTPException(400, "Escolha um arquivo PDF ou Markdown.")
    nome = Path(arquivo.filename).name
    extensao = Path(nome).suffix.lower()
    if extensao not in EXTENSOES_ACEITAS:
        raise HTTPException(400, "Escolha um arquivo PDF, MD ou MARKDOWN.")
    pasta_destino = ENTRADA if extensao == ".pdf" else MARKDOWN
    destino = destino_seguro(pasta_destino, nome)
    total = 0
    with destino.open("wb") as saida:
        while bloco := arquivo.file.read(1024 * 1024):
            total += len(bloco)
            if total > LIMITE_MB * 1024 * 1024:
                saida.close()
                destino.unlink(missing_ok=True)
                raise HTTPException(413, f"O limite é {LIMITE_MB} MB por arquivo.")
            saida.write(bloco)
    return novo_trabalho(destino, extensao, modo=modo, markdown_pronto=extensao != ".pdf")


@app.get("/trabalhos/{trabalho_id}")
def consultar_trabalho(trabalho_id: str):
    with TRAVA:
        trabalho = TRABALHOS.get(trabalho_id)
        if not trabalho:
            raise HTTPException(404, "Trabalho não encontrado. Reenvie o arquivo.")
        return dict(trabalho)


@app.get("/arquivos")
def listar_arquivos():
    arquivos = list(MARKDOWN.glob("*.md")) + list(MARKDOWN.glob("*.markdown"))
    return {
        "markdowns": [
            {
                "nome": arquivo.name,
                "id": arquivo.name,
                "resumo_pronto": any(RESUMOS.glob(f"{arquivo.stem}-*.md")),
            }
            for arquivo in sorted(arquivos, key=lambda p: p.stat().st_mtime, reverse=True)
        ]
    }


@app.post("/resumir-existente")
def resumir_existente(nome: str, modo: str = "rapido"):
    if Path(nome).name != nome:
        raise HTTPException(400, "Escolha um Markdown válido.")
    origem = MARKDOWN / nome
    if not origem.is_file() or origem.suffix.lower() not in {".md", ".markdown"}:
        raise HTTPException(404, "Markdown não encontrado.")
    return novo_trabalho(origem, origem.suffix.lower(), modo=modo, markdown_pronto=True)


@app.get("/downloads/{nome}")
def baixar_relatorio(nome: str):
    arquivo = RESUMOS / Path(nome).name
    tipos = {
        ".md": "text/markdown; charset=utf-8",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pdf": "application/pdf",
    }
    if not arquivo.is_file() or arquivo.suffix.lower() not in tipos:
        raise HTTPException(404, "Relatório não encontrado.")
    return FileResponse(arquivo, filename=arquivo.name, media_type=tipos[arquivo.suffix.lower()])
