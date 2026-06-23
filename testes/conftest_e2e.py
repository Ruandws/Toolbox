# conftest_e2e.py — Fixtures compartilhadas para testes end-to-end (Playwright).
#
# Testes e2e exigem credenciais reais e acesso à rede. Marque-os com
# @pytest.mark.e2e para que possam ser excluídos nas execuções rápidas.
#
# Variáveis de ambiente esperadas:
#   EXTRATOR_LOGIN    – login de rede
#   EXTRATOR_SENHA    – senha de rede

import os

import pytest


@pytest.fixture(scope="session")
def credenciais_rede():
    """Retorna (login, senha) de variáveis de ambiente.

    Pula o teste se as credenciais não estiverem configuradas.
    """
    login = os.getenv("EXTRATOR_LOGIN", "")
    senha = os.getenv("EXTRATOR_SENHA", "")

    if not login or not senha:
        pytest.skip(
            "Credenciais de rede não configuradas "
            "(EXTRATOR_LOGIN / EXTRATOR_SENHA)."
        )

    return login, senha
