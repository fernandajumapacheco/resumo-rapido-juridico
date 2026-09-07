import importlib
import os
import sys
from pathlib import Path


def carregar_app(tmp_path: Path):
    os.environ["RESUMO_LOCAL_DADOS"] = str(tmp_path / "dados")
    os.environ["RESUMO_ENTRADA"] = str(tmp_path / "entrada")
    os.environ["RESUMO_MARKDOWN"] = str(tmp_path / "markdown")
    os.environ["RESUMO_SAIDA"] = str(tmp_path / "saida")
    sys.modules.pop("app", None)
    return importlib.import_module("app")


def test_saude_nao_expoe_caminhos(tmp_path):
    modulo = carregar_app(tmp_path)
    resposta = modulo.saude()
    assert resposta == {"ok": True, "motor": "Python", "versao": "1.1.2"}


def test_inicializador_escolhe_outra_porta_quando_a_primeira_esta_ocupada():
    import socket
    from iniciar import escolher_porta

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ocupada:
        ocupada.bind(("127.0.0.1", 0))
        porta = ocupada.getsockname()[1]
        assert escolher_porta(porta, porta + 1) == porta + 1


def test_upload_repetido_recebe_nome_unico(tmp_path):
    modulo = carregar_app(tmp_path)
    primeiro = modulo.ENTRADA / "teste.pdf"
    primeiro.write_bytes(b"existente")
    segundo = modulo.destino_seguro(modulo.ENTRADA, "teste.pdf")
    assert primeiro != segundo
    assert segundo.name.startswith("teste-")
    assert segundo.suffix == ".pdf"


def test_nome_de_markdown_nao_aceita_caminho(tmp_path):
    modulo = carregar_app(tmp_path)
    try:
        modulo.resumir_existente("../segredo.md")
    except Exception as erro:
        assert getattr(erro, "status_code", None) == 400
    else:
        raise AssertionError("O caminho inseguro deveria ser recusado")


def test_relatorio_mascara_dados_pessoais_e_processo():
    from analise_juridica import gerar_relatorio

    texto = """
    Processo: 1234567-89.2026.8.09.0001
    Autor: Maria Fernanda Silva
    Réu: João Pedro de Souza
    CPF: 000.000.000-00
    Telefone: (00) 90000-0000
    E-mail: pessoa@example.test
    Endereço: Rua Fictícia, lote 10, CEP 00000-000
    Maria Fernanda Silva alega falha contratual em 01/08/2026 e requer indenização.
    """
    relatorio = gerar_relatorio(texto, "rapido", "teste.md")

    assert "**Número do processo:** xxx" in relatorio
    assert "M. F. S." in relatorio
    assert "J. P. S." in relatorio
    assert "1234567-89.2026.8.09.0001" not in relatorio
    assert "Maria Fernanda Silva" not in relatorio
    assert "João Pedro de Souza" not in relatorio
    assert "000.000.000-00" not in relatorio
    assert "(00) 90000-0000" not in relatorio
    assert "pessoa@example.test" not in relatorio
    assert "Rua Fictícia" not in relatorio
