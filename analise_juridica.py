"""Extração jurídica determinística para relatórios locais.

O módulo não tenta decidir o processo nem substituir revisão humana. Ele localiza
trechos relevantes e mantém o texto original como fonte de conferência.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


PROCESSO_RE = re.compile(r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b")
DATA_RE = re.compile(r"\b(?:0?[1-9]|[12]\d|3[01])[/.-](?:0?[1-9]|1[0-2])[/.-](?:19|20)\d{2}\b")
VALOR_RE = re.compile(r"R\$\s*[\d.]+(?:,\d{2})?", re.I)
LEI_RE = re.compile(
    r"\b(?:art(?:igo)?\.?\s*\d+[º°o]?(?:\s*,?\s*§\s*\d+[º°o]?)?|"
    r"lei\s+(?:n[º°o]?\s*)?[\d.]+(?:/\d{2,4})?|súmula\s+\d+)\b",
    re.I,
)

ROTULOS_PARTES = {
    "autor": ("autor", "autora", "requerente", "exequente", "impetrante", "reclamante"),
    "réu": ("réu", "ré", "requerido", "requerida", "executado", "executada", "reclamado"),
    "advogado": ("advogado", "advogada", "procurador", "procuradora", "defensor", "defensora"),
    "órgão julgador": ("órgão julgador", "orgao julgador", "juízo", "juizo", "vara", "turma", "câmara", "camara", "tribunal"),
}

PALAVRAS = {
    "pedido": ("requer", "requerer", "requereu", "requerimento", "pedido", "pedidos", "pretende", "postula", "pleiteia", "condenação", "condenacao"),
    "decisão": ("decido", "decidiu", "decisão", "decisao", "sentença", "sentenca", "julgo", "julgou", "defiro", "deferiu", "deferir", "indefiro", "indeferiu", "acórdão", "acordao"),
    "prova": ("prova", "provas", "documento", "documentos", "laudo", "perícia", "pericia", "testemunha", "depoimento", "certidão", "certidao"),
    "pendência": ("intime-se", "prazo", "prazos", "pendente", "aguarda", "manifestar", "providencie", "determino", "determinou"),
    "controvérsia": ("contesta", "contestou", "nega", "negou", "alega", "alegou", "diverge", "contradição", "contradicao", "controvertido", "impugna", "impugnou"),
    "recurso": ("recurso", "recursos", "apelação", "apelacao", "agravo", "embargos", "recorrente", "recorrido"),
}


@dataclass(frozen=True)
class Trecho:
    texto: str
    pagina: int | None

    @property
    def exibicao(self) -> str:
        sufixo = f" _(p. {self.pagina})_" if self.pagina else ""
        return self.texto.strip() + sufixo


def _sem_acentos(valor: str) -> str:
    return "".join(
        caractere for caractere in unicodedata.normalize("NFKD", valor)
        if not unicodedata.combining(caractere)
    ).lower()


def _limpar(valor: str) -> str:
    return re.sub(r"\s+", " ", valor).strip(" \t-–—•")


def _paginas(texto: str) -> list[tuple[int | None, str]]:
    marcador = re.compile(r"(?im)^\s*##\s+Página\s+(\d+)\s*$")
    encontrados = list(marcador.finditer(texto))
    if encontrados:
        paginas: list[tuple[int | None, str]] = []
        for indice, item in enumerate(encontrados):
            fim = encontrados[indice + 1].start() if indice + 1 < len(encontrados) else len(texto)
            paginas.append((int(item.group(1)), texto[item.end():fim]))
        return paginas
    blocos = texto.split("\f")
    if len(blocos) > 1:
        return [(numero, bloco) for numero, bloco in enumerate(blocos, 1) if bloco.strip()]
    return [(None, texto)]


def _sentencas(texto: str) -> list[Trecho]:
    resultado: list[Trecho] = []
    for pagina, conteudo in _paginas(texto):
        conteudo = re.sub(r"(?m)^#{1,6}\s+", "", conteudo)
        for frase in re.split(r"(?<=[.!?;:])\s+|\n{2,}", conteudo):
            frase = _limpar(frase)
            palavras = frase.split()
            normal = _sem_acentos(frase)
            eh_aviso_ficticio = any(inicio in normal for inicio in (
                "todos os nomes, fatos",
                "este documento nao corresponde",
                "ele nao deve ser utilizado",
                "as referencias legais devem ser verificadas",
            ))
            if 7 <= len(palavras) <= 150 and not frase.isupper() and not eh_aviso_ficticio:
                resultado.append(Trecho(frase, pagina))
    return resultado


def _selecionar(sentencas: list[Trecho], termos: tuple[str, ...], limite: int) -> list[Trecho]:
    achados: list[Trecho] = []
    vistos: set[str] = set()
    termos_norm = tuple(_sem_acentos(t) for t in termos)
    for trecho in sentencas:
        normal = _sem_acentos(trecho.texto)
        if any(re.search(rf"(?<!\w){re.escape(termo)}(?!\w)", normal) for termo in termos_norm):
            chave = normal[:240]
            if chave not in vistos:
                vistos.add(chave)
                achados.append(trecho)
        if len(achados) >= limite:
            break
    return achados


def _linhas_rotuladas(texto: str, rotulos: tuple[str, ...], limite: int = 8) -> list[str]:
    resposta: list[str] = []
    padrao = re.compile(
        rf"(?im)^\s*(?:{'|'.join(map(re.escape, rotulos))})\s*:?\s+(.{{3,180}})$"
    )
    for valor in padrao.findall(texto):
        valor = _limpar(valor)
        if valor and valor not in resposta:
            resposta.append(valor)
        if len(resposta) >= limite:
            break
    return resposta


def _lista(itens: list[str] | list[Trecho], vazio: str = "Não identificado no texto.") -> str:
    if not itens:
        return f"- {vazio}"
    return "\n".join(f"- {item.exibicao if isinstance(item, Trecho) else item}" for item in itens)


def _resumo_caso(sentencas: list[Trecho], limite: int) -> list[Trecho]:
    grupos = (
        ("contratou", "ajuizou", "ocorreu", "objeto", "demanda", "ação"),
        ("alega", "alegou", "afirma", "sustenta"),
        ("contestação", "contestacao", "contesta", "nega", "impugna"),
        PALAVRAS["pedido"],
        PALAVRAS["decisão"],
        PALAVRAS["pendência"],
    )
    candidatos: list[Trecho] = []
    for termos in grupos:
        for trecho in _selecionar(sentencas, termos, 1):
            if trecho not in candidatos:
                candidatos.append(trecho)
    if len(candidatos) < limite:
        candidatos.extend(s for s in sentencas if s not in candidatos)
    return candidatos[:limite]


def gerar_relatorio(texto: str, modo: str, nome_arquivo: str) -> str:
    """Gera Markdown rastreável sem realizar inferências não sustentadas."""
    modo = "completo" if modo == "completo" else "rapido"
    sentencas = _sentencas(texto)
    limite = 10 if modo == "completo" else 4
    processos = list(dict.fromkeys(PROCESSO_RE.findall(texto)))[:5]
    datas = list(dict.fromkeys(DATA_RE.findall(texto)))
    valores = list(dict.fromkeys(VALOR_RE.findall(texto)))[:20]
    leis = list(dict.fromkeys(m.group(0) for m in LEI_RE.finditer(texto)))[:30]
    partes = {
        nome: _linhas_rotuladas(texto, rotulos)
        for nome, rotulos in ROTULOS_PARTES.items()
    }
    resumo = _resumo_caso(sentencas, 8 if modo == "completo" else 4)
    titulo = "Relatório Jurídico Completo" if modo == "completo" else "Resumo Jurídico Rápido"
    agora = datetime.now().strftime("%d/%m/%Y às %H:%M")

    secoes = [
        f"# {titulo}",
        "",
        f"**Documento analisado:** {Path(nome_arquivo).name}",
        f"**Gerado em:** {agora}",
        "**Método:** extração objetiva em Python, sem interpretação decisória.",
        "",
        "> Este relatório é auxiliar. Confira nomes, datas, valores e conclusões diretamente nos autos.",
        "",
        "## Resumo do caso",
        "",
        _lista(resumo, "Não foi possível formar um resumo seguro a partir do texto extraído."),
        "",
        "## Identificação",
        "",
        f"**Número do processo:** {', '.join(processos) if processos else 'Não identificado.'}",
        f"**Órgão julgador:** {', '.join(partes['órgão julgador']) if partes['órgão julgador'] else 'Não identificado.'}",
        "",
        "## Partes e representantes",
        "",
        f"**Polo autor ou requerente**\n{_lista(partes['autor'])}",
        "",
        f"**Polo réu ou requerido**\n{_lista(partes['réu'])}",
        "",
        f"**Advogados, defensores ou procuradores**\n{_lista(partes['advogado'])}",
        "",
        "## Pedidos e pretensões localizados",
        "",
        _lista(_selecionar(sentencas, PALAVRAS['pedido'], limite)),
        "",
        "## Decisões e conclusões localizadas",
        "",
        _lista(_selecionar(sentencas, PALAVRAS['decisão'], limite)),
        "",
        "## Providências, prazos e atos pendentes",
        "",
        _lista(_selecionar(sentencas, PALAVRAS['pendência'], limite)),
    ]

    if modo == "completo":
        linha_tempo = [
            trecho for trecho in sentencas
            if DATA_RE.search(trecho.texto)
        ][:20]
        secoes.extend([
            "",
            "## Linha do tempo",
            "",
            _lista(linha_tempo),
            "",
            "## Provas e documentos mencionados",
            "",
            _lista(_selecionar(sentencas, PALAVRAS['prova'], limite)),
            "",
            "## Alegações, controvérsias e possíveis contradições",
            "",
            _lista(_selecionar(sentencas, PALAVRAS['controvérsia'], limite)),
            "",
            "## Recursos mencionados",
            "",
            _lista(_selecionar(sentencas, PALAVRAS['recurso'], limite)),
            "",
            "## Valores localizados",
            "",
            _lista(valores),
            "",
            "## Dispositivos legais mencionados",
            "",
            _lista(leis),
            "",
            "## Pontos para conferência humana",
            "",
            "- Confirmar se todas as páginas foram extraídas corretamente, especialmente em PDFs escaneados.",
            "- Distinguir alegações das partes de fatos efetivamente provados.",
            "- Conferir a vigência e a aplicação dos dispositivos legais mencionados.",
            "- Verificar prazos, intimações, valores e o teor integral das decisões nos autos.",
            "- Avaliar competência, prescrição, decadência, nulidades e ônus da prova conforme o caso concreto.",
        ])

    secoes.extend([
        "",
        "## Limitações",
        "",
        f"- Foram localizadas {len(sentencas)} passagens textuais aproveitáveis.",
        "- A ferramenta apenas seleciona trechos por critérios objetivos e pode deixar de localizar informações.",
        "- A ausência de um item neste relatório não prova que ele não exista no processo.",
        "- Nenhuma jurisprudência, fato ou conclusão foi acrescentada fora do documento.",
    ])
    return "\n".join(secoes).strip() + "\n"


def estatisticas(texto: str) -> dict[str, int]:
    paginas = _paginas(texto)
    palavras = re.findall(r"\b\w+\b", texto, re.UNICODE)
    return {
        "paginas": len(paginas) if paginas[0][0] is not None else 0,
        "palavras": len(palavras),
        "caracteres": len(texto),
        "datas": len(DATA_RE.findall(texto)),
        "processos": len(set(PROCESSO_RE.findall(texto))),
    }
