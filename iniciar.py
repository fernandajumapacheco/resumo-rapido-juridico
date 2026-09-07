"""Inicializador comum para macOS, Windows e Linux."""

from __future__ import annotations

import socket
import threading
import webbrowser

import uvicorn


def escolher_porta(inicio: int = 8787, fim: int = 8799) -> int:
    """Devolve a primeira porta local livre dentro do intervalo."""
    for porta in range(inicio, fim + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as teste:
            try:
                teste.bind(("127.0.0.1", porta))
            except OSError:
                continue
            return porta
    raise RuntimeError(
        f"As portas locais de {inicio} a {fim} estão ocupadas. "
        "Feche outra cópia do aplicativo e tente novamente."
    )


def main() -> None:
    porta = escolher_porta()
    endereco = f"http://127.0.0.1:{porta}/"
    print(f"Abrindo Resumo Rápido Jurídico em {endereco}")
    threading.Timer(1.2, lambda: webbrowser.open(endereco)).start()
    uvicorn.run("app:app", host="127.0.0.1", port=porta)


if __name__ == "__main__":
    main()
