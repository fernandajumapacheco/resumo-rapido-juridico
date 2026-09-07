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
    assert resposta == {"ok": True, "motor": "Python", "versao": "1.1.1"}


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
