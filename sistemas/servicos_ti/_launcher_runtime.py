"""Bootstrap de runtime compartilhado pelos launchers servicos_ti (Prorrogador/Consultor).

Chamar bootstrap_playwright_browsers_path() antes de qualquer import que
carregue o pacote `playwright` (direto ou via *_sti.py).
"""
import os
import sys


def bootstrap_playwright_browsers_path() -> None:
    """Aponta o Playwright para o Chromium embutido ao lado do executável.

    O chamador deve invocar isto apenas quando `sys.frozen` (PyInstaller).
    """
    os.environ.setdefault(
        "PLAYWRIGHT_BROWSERS_PATH",
        os.path.join(os.path.dirname(sys.executable), "ms-playwright"),
    )
