"""Extração jurídica determinística para relatórios locais.

O módulo não tenta decidir o processo nem substituir revisão humana. Ele localiza
trechos relevantes e mantém o texto original como fonte de conferência.
"""

from __future__ import annotations

import re
import unicodedata
from html import unescape
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
CPF_RE = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
TELEFONE_RE = re.compile(r"\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
CEP_RE = re.compile(r"\b\d{5}-?\d{3}\b")
ENDERECO_RE = re.compile(
    r"(?i)\b(?:endereço|endereco|residência|residencia|domicílio|domicilio|"
    r"rua|avenida|av\.|travessa|quadra|qnr|lote|conjunto|condomínio|condominio)"
    r"[^.\n;]{0,180}"
)
NOME_COMPLETO_RE = re.compile(
    r"\b(?:[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]{2,}|[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][a-záàâãéêíóôõúç]+)"
    r"(?:\s+(?:de|da|do|das|dos|e)?\s*"
    r"(?:[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]{2,}|[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][a-záàâãéêíóôõúç]+)){1,6}\b"
)
NOME_EXCECOES = {
    "Código Penal", "Codigo Penal", "Código Civil", "Codigo Civil",
    "Código de Processo Civil", "Codigo de Processo Civil",
    "Código de Processo Penal", "Codigo de Processo Penal",
    "Lei Geral", "Lei Henry Borel", "Lei Maria", "Ministério Público",
    "Ministerio Publico", "Polícia Civil", "Policia Civil", "Conselho Tutelar",
    "Supremo Tribunal Federal", "Superior Tribunal de Justiça",
}

ROTULOS_PARTES = {
    "autor": ("autor", "autora", "requerente", "exequente", "impetrante", "reclamante", "polo ativo", "vítima", "vitima", "comunicante"),
    "réu": ("réu", "ré", "requerido", "requerida", "executado", "executada", "reclamado", "polo passivo", "investigado", "acusado", "autor do fato"),
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
    "crime": ("crime", "criminal", "penal", "tco", "rai", "ameaça", "ameaca", "injúria", "injuria", "lesão corporal", "lesao corporal", "maus-tratos", "maus tratos", "furto", "roubo", "estelionato", "homicídio", "homicidio", "violência doméstica", "violencia domestica"),
    "rito": ("rito", "competência", "competencia", "juizado", "vara", "ordinário", "ordinario", "sumaríssimo", "sumarissimo", "conhecimento", "segredo de justiça", "segredo de justica"),
    "diligência": ("diligência", "diligencia", "pendente", "pendentes", "oitiva", "laudo", "perícia", "pericia", "conselho tutelar", "relatório", "relatorio", "transcrição", "transcricao", "áudio", "audio"),
    "procedibilidade": ("prescrição", "prescricao", "decadência", "decadencia", "representação", "representacao", "queixa", "ação penal", "acao penal", "anpp", "transação penal", "transacao penal", "suspensão condicional", "suspensao condicional"),
    "vulnerabilidade": ("criança", "crianca", "adolescente", "idoso", "idosa", "deficiência", "deficiencia", "vulnerável", "vulneravel", "violência doméstica", "violencia domestica", "medida protetiva"),
}

AREAS = {
    "criminal": ("crime", "criminal", "penal", "tco", "rai", "delegacia", "vítima", "vitima", "investigado", "ameaça", "ameaca", "injúria", "injuria", "lesão corporal", "lesao corporal", "maus-tratos"),
    "cível": ("cível", "civel", "indenização", "indenizacao", "contrato", "obrigação", "obrigacao", "danos morais", "danos materiais", "requerente", "requerido"),
    "família": ("família", "familia", "guarda", "alimentos", "divórcio", "divorcio", "convivência", "convivencia", "menor", "criança", "crianca"),
    "trabalhista": ("trabalhista", "reclamante", "reclamado", "verbas rescisórias", "verbas rescisorias", "ctps", "jornada", "salário", "salario"),
    "previdenciária": ("previdenciária", "previdenciaria", "inss", "benefício", "beneficio", "aposentadoria", "auxílio", "auxilio"),
}


@dataclass(frozen=True)
class Trecho:
    texto: str
    pagina: int | None

    @property
    def exibicao(self) -> str:
        sufixo = f" _(p. {self.pagina})_" if self.pagina else ""
        return _anonimizar_conteudo(self.texto.strip()) + sufixo


def _sem_acentos(valor: str) -> str:
    return "".join(
        caractere for caractere in unicodedata.normalize("NFKD", valor)
        if not unicodedata.combining(caractere)
    ).lower()


def _limpar(valor: str) -> str:
    return re.sub(r"\s+", " ", valor).strip(" \t-–—•")


def _iniciais(nome: str) -> str:
    if nome in NOME_EXCECOES:
        return nome
    partes = [
        parte[0].upper() + "."
        for parte in re.findall(r"[A-Za-zÁÀÂÃÉÊÍÓÔÕÚÇáàâãéêíóôõúç]+", nome)
        if _sem_acentos(parte) not in {"de", "da", "do", "das", "dos", "e"}
    ]
    return " ".join(partes) if len(partes) >= 2 else nome


def _anonimizar_conteudo(texto: str) -> str:
    texto = PROCESSO_RE.sub("xxx", texto)
    texto = CPF_RE.sub("[CPF ocultado]", texto)
    texto = TELEFONE_RE.sub("[telefone ocultado]", texto)
    texto = EMAIL_RE.sub("[e-mail ocultado]", texto)
    texto = CEP_RE.sub("[CEP ocultado]", texto)
    texto = ENDERECO_RE.sub("[endereço ocultado]", texto)
    return NOME_COMPLETO_RE.sub(lambda item: _iniciais(item.group(0)), texto)


def _texto_visivel(texto: str) -> str:
    texto = re.sub(r"(?is)<\s*br\s*/?\s*>", "\n", texto)
    texto = re.sub(r"(?is)</\s*(p|li|h[1-6]|div|section|article|ul|ol)\s*>", "\n", texto)
    texto = re.sub(r"(?is)<[^>]+>", " ", texto)
    return unescape(texto)


def _paginas(texto: str) -> list[tuple[int | None, str]]:
    texto = _texto_visivel(texto)
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
        for frase in re.split(r"(?<=[.!?])\s+|\n{2,}", conteudo):
            frase = _limpar(frase)
            palavras = frase.split()
            normal = _sem_acentos(frase)
            eh_aviso_ficticio = any(inicio in normal for inicio in (
                "todos os nomes, fatos",
                "este documento nao corresponde",
                "ele nao deve ser utilizado",
                "as referencias legais devem ser verificadas",
            ))
            eh_ruido_web = "http://" in normal or "https://" in normal or "](" in normal
            eh_capa_rotulada = frase.count(":") >= 3 and any(rotulo in normal for rotulo in (
                "numero do processo", "juizo", "polo ativo", "polo passivo", "data do fato"
            ))
            if (
                7 <= len(palavras) <= 150
                and not frase.isupper()
                and not eh_aviso_ficticio
                and not eh_ruido_web
                and not eh_capa_rotulada
            ):
                resultado.append(Trecho(frase, pagina))
    return resultado


def _primeiras_linhas(texto: str, limite: int = 22) -> list[str]:
    linhas: list[str] = []
    for linha in _texto_visivel(texto).splitlines():
        limpa = _limpar(linha)
        if 4 <= len(limpa) <= 220 and not limpa.isupper() and limpa not in linhas:
            linhas.append(limpa)
        if len(linhas) >= limite:
            break
    return linhas


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
    texto = _texto_visivel(texto)
    padrao = re.compile(
        rf"(?im)^\s*(?:{'|'.join(map(re.escape, rotulos))})\s*:?\s+(.{{3,180}})$"
    )
    valores = list(padrao.findall(texto))
    inline = re.compile(
        rf"(?i)(?:^|[.;\n])\s*(?:{'|'.join(map(re.escape, rotulos))})"
        rf"(?:\s*\([^)]*\))?\s*:\s*([^.\n]{{3,180}})"
    )
    valores.extend(inline.findall(texto))
    for valor in valores:
        valor = _limpar(valor)
        if valor and valor not in resposta:
            resposta.append(valor)
        if len(resposta) >= limite:
            break
    return resposta


def _lista(itens: list[str] | list[Trecho], vazio: str = "Não identificado no texto.") -> str:
    if not itens:
        return f"- {vazio}"
    return "\n".join(
        f"- {item.exibicao if isinstance(item, Trecho) else _anonimizar_conteudo(item)}"
        for item in itens
    )


def _campo(texto: str, rotulos: tuple[str, ...]) -> str:
    achados = _linhas_rotuladas(texto, rotulos, 1)
    return _anonimizar_conteudo(achados[0]) if achados else "Não identificado."


def _area_principal(texto: str) -> str:
    normal = _sem_acentos(texto)
    placar = Counter()
    for area, termos in AREAS.items():
        placar[area] = sum(normal.count(_sem_acentos(termo)) for termo in termos)
    area, pontos = placar.most_common(1)[0]
    return area.capitalize() if pontos else "Não identificada"


def _processos_principais(texto: str) -> list[str]:
    encontrados = list(dict.fromkeys(PROCESSO_RE.findall(texto)))
    if not encontrados:
        return []
    rotulo = re.compile(
        r"(?i)\b(?:número do processo|numero do processo|processo)\s*:?\s*"
        r"(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})"
    )
    preferidos = list(dict.fromkeys(rotulo.findall(texto)))
    return (preferidos or encontrados)[:2]


def _limpar_dados_sensiveis(linha: str) -> str:
    return _anonimizar_conteudo(linha)


def _lista_privada(itens: list[str] | list[Trecho], vazio: str = "Não identificado no texto.") -> str:
    if not itens:
        return f"- {vazio}"
    saida: list[str] = []
    for item in itens:
        valor = item.exibicao if isinstance(item, Trecho) else item
        saida.append(f"- {_limpar_dados_sensiveis(valor)}")
    return "\n".join(saida)


def _resumo_caso(sentencas: list[Trecho], limite: int) -> list[Trecho]:
    grupos = (
        ("extrai-se", "trata-se", "segundo", "conforme", "consta"),
        ("contratou", "ajuizou", "ocorreu", "objeto", "demanda", "ação"),
        ("alega", "alegou", "afirma", "sustenta"),
        ("contestação", "contestacao", "contesta", "nega", "impugna"),
        PALAVRAS["crime"],
        PALAVRAS["pedido"],
        PALAVRAS["decisão"],
        PALAVRAS["pendência"],
    )
    candidatos: list[Trecho] = []
    for termos in grupos:
        for trecho in _selecionar(sentencas, termos, 6):
            if trecho not in candidatos and _bom_para_resumo(trecho):
                candidatos.append(trecho)
                break
    if len(candidatos) < limite:
        candidatos.extend(s for s in sentencas if s not in candidatos and _bom_para_resumo(s))
    return candidatos[:limite]


def _bom_para_resumo(trecho: Trecho) -> bool:
    texto = trecho.texto.strip()
    normal = _sem_acentos(texto)
    if re.match(r"^(?:\d+\)|\d+|[ivxlcdm]+\)|art\.|§|\([ivxlcdm]+\))", normal):
        return False
    if texto.count(":") >= 2:
        return False
    if any(normal.startswith(prefixo) for prefixo in (
        "numero do processo:", "juizo:", "tipo de autos:", "polo ativo:", "polo passivo:",
        "data de nascimento:", "situacao do investigado:", "forma:", "status:"
    )):
        return False
    return True


def _linha_tempo(sentencas: list[Trecho], limite: int) -> list[str]:
    itens: list[str] = []
    vistos: set[str] = set()
    for trecho in sentencas:
        data = DATA_RE.search(trecho.texto)
        if not data:
            continue
        texto = _limpar(trecho.texto)
        normal = _sem_acentos(texto)
        if "http" in normal or "rel." in normal or "j." in normal or "acordao" in normal:
            continue
        if "data de nascimento" in normal or "nascid" in normal:
            continue
        chave = f"{data.group(0)}-{_sem_acentos(texto[:120])}"
        if chave not in vistos:
            vistos.add(chave)
            itens.append(f"**{data.group(0)}:** {_anonimizar_conteudo(texto)}")
        if len(itens) >= limite:
            break
    return itens


def _bloco_recomendacoes(area: str, tem_api: bool = False) -> list[str]:
    base = [
        "- Conferir o documento original antes de usar qualquer conclusão em peça ou atendimento.",
        "- Separar fatos comprovados, alegações das partes e pontos ainda pendentes de prova.",
        "- Conferir prazos, competência, legitimidade, prescrição ou decadência conforme o caso concreto.",
    ]
    if area.lower() == "criminal":
        base.extend([
            "- Mapear para cada crime: conduta narrada, vítima, investigado/acusado, materialidade, autoria e prova direta.",
            "- Conferir se há laudos, mídias, oitivas ou transcrições pendentes antes de definir a estratégia.",
            "- Avaliar cabimento de medidas urgentes, resposta defensiva, requerimento de diligências ou composição, conforme a posição do cliente.",
        ])
    else:
        base.extend([
            "- Mapear pedidos, causa de pedir, documentos essenciais, ônus da prova e providências urgentes.",
            "- Avaliar se falta contrato, comprovante, decisão, procuração, cálculo, laudo ou outro documento essencial.",
        ])
    if not tem_api:
        base.append("- Pesquisa de jurisprudência, doutrina ou legislação atualizada deve ser feita fora deste app local.")
    return base


def gerar_relatorio(texto: str, modo: str, nome_arquivo: str) -> str:
    """Gera Markdown rastreável sem realizar inferências não sustentadas."""
    modo = "completo" if modo == "completo" else "rapido"
    texto = _texto_visivel(texto)
    sentencas = _sentencas(texto)
    limite = 10 if modo == "completo" else 4
    processos = _processos_principais(texto)
    datas = list(dict.fromkeys(DATA_RE.findall(texto)))
    valores = list(dict.fromkeys(VALOR_RE.findall(texto)))[:20]
    leis = list(dict.fromkeys(m.group(0) for m in LEI_RE.finditer(texto)))[:30]
    partes = {
        nome: _linhas_rotuladas(texto, rotulos)
        for nome, rotulos in ROTULOS_PARTES.items()
    }
    resumo = _resumo_caso(sentencas, 8 if modo == "completo" else 4)
    area = _area_principal(texto)
    linhas_iniciais = _primeiras_linhas(texto)
    linha_tempo = _linha_tempo(sentencas, 8 if modo == "completo" else 4)
    crimes = _selecionar(sentencas, PALAVRAS["crime"], limite)
    provas = _selecionar(sentencas, PALAVRAS["prova"], limite)
    diligencias = _selecionar(sentencas, PALAVRAS["diligência"], limite)
    procedibilidade = _selecionar(sentencas, PALAVRAS["procedibilidade"], limite)
    vulnerabilidades = _selecionar(sentencas, PALAVRAS["vulnerabilidade"], limite)
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
        "## Quadro rápido",
        "",
        f"**Área provável:** {area}",
        f"**Número do processo:** {'xxx' if processos else 'Não identificado.'}",
        f"**Juízo ou órgão julgador:** {_campo(texto, ROTULOS_PARTES['órgão julgador'])}",
        f"**Datas localizadas:** {', '.join(datas[:8]) if datas else 'Não identificadas.'}",
        f"**Dispositivos citados:** {', '.join(leis[:8]) if leis else 'Não identificados.'}",
        "",
        "## Resuminho do caso",
        "",
        _lista(resumo, "Não foi possível formar um resumo seguro a partir do texto extraído."),
        "",
        "## Linha do tempo essencial",
        "",
        _lista(linha_tempo, "Não foram localizadas datas suficientes para montar a linha do tempo."),
        "",
        "## Envolvidos e representantes",
        "",
        f"**Polo autor, requerente ou comunicante**\n{_lista_privada(partes['autor'])}",
        "",
        f"**Polo réu, requerido, investigado ou acusado**\n{_lista_privada(partes['réu'])}",
        "",
        f"**Advogados, defensores ou procuradores**\n{_lista_privada(partes['advogado'])}",
        "",
        "## Crime ou matéria jurídica localizada",
        "",
        _lista(crimes, "Não identificado como matéria criminal no texto extraído."),
        "",
        "## Pedidos, teses ou pretensões",
        "",
        _lista(_selecionar(sentencas, PALAVRAS['pedido'], limite)),
        "",
        "## Provas e documentos centrais",
        "",
        _lista(provas),
        "",
        "## Pendências e próximos pontos de conferência",
        "",
        _lista(diligencias or _selecionar(sentencas, PALAVRAS['pendência'], limite)),
    ]

    if modo == "completo":
        secoes.extend([
            "",
            "## Identificação detalhada",
            "",
            _lista_privada(linhas_iniciais, "Não foi possível extrair uma capa ou identificação inicial."),
            "",
            "## Rito, competência e fase",
            "",
            _lista(_selecionar(sentencas, PALAVRAS['rito'], limite)),
            "",
            "## Decisões e conclusões localizadas",
            "",
            _lista(_selecionar(sentencas, PALAVRAS['decisão'], limite)),
            "",
            "## Controvérsias e versões conflitantes",
            "",
            _lista(_selecionar(sentencas, PALAVRAS['controvérsia'], limite)),
            "",
            "## Vulnerabilidades ou medidas urgentes",
            "",
            _lista(vulnerabilidades),
            "",
            "## Prazos, procedibilidade e institutos",
            "",
            _lista(procedibilidade),
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
            "## Checklist de trabalho para advogado",
            "",
            "\n".join(_bloco_recomendacoes(area)),
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
        "",
        "## Aviso jurídico e segurança",
        "",
        "- Este relatório é uma base informativa, não orientação jurídica para um caso específico.",
        "- O resultado não substitui a análise de advogado, defensoria, órgão público competente ou profissional habilitado.",
        "- Confira sempre o documento original antes de usar nomes, datas, valores, prazos, fundamentos ou conclusões.",
        "- Documentos jurídicos podem conter dados pessoais, dados sensíveis, segredo de justiça e informações confidenciais.",
        "- Por segurança, números de processo são substituídos por `xxx` e dados pessoais identificáveis devem ser abreviados ou ocultados no relatório.",
        "- A anonimização automática é uma proteção auxiliar e pode falhar; revise o arquivo antes de compartilhar.",
        "- Proteja os arquivos gerados, evite computador compartilhado e tenha cautela antes de enviar o relatório por e-mail, mensagens ou nuvem.",
        "- A pessoa usuária é responsável por avaliar sigilo profissional, LGPD, autorização de acesso, finalidade do uso, guarda e descarte dos arquivos.",
        "- O aplicativo funciona localmente e não pesquisa legislação, jurisprudência ou doutrina atualizada na internet.",
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
