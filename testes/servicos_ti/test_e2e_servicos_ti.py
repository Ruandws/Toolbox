# test_e2e_servicos_ti.py — Testes end-to-end para Serviços TI.
#
# Exigem rede e credenciais reais. Execute com:
#   pytest testes/servicos_ti/test_e2e_servicos_ti.py -m e2e
#
# Variáveis de ambiente necessárias:
#   EXTRATOR_LOGIN, EXTRATOR_SENHA

import pytest

pytestmark = pytest.mark.e2e


class TestE2ELoginServicosTI:
    """Testes e2e de autenticação no Serviços TI."""

    def test_login_valido_consultor(self, credenciais_rede):
        """Verifica que credenciais válidas permitem login no Consultor."""
        from playwright.sync_api import sync_playwright

        from consultor_sti import login_to_system

        login, senha = credenciais_rede

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()

            try:
                login_to_system(page, login, senha)
                # Se não levantou exceção, login foi bem-sucedido
            finally:
                browser.close()

    def test_login_invalido_consultor(self):
        """Verifica que credenciais inválidas levantam RuntimeError."""
        from playwright.sync_api import sync_playwright

        from consultor_sti import login_to_system

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()

            try:
                with pytest.raises(RuntimeError):
                    login_to_system(page, "invalido_xyz", "senha_xyz")
            finally:
                browser.close()


class TestE2EPesquisaConsultor:
    """Testes e2e de pesquisa no Consultor STI.

    ATENÇÃO: Estes testes interagem com o sistema real.
    """

    @pytest.mark.skip(reason="Executar manualmente com credenciais válidas")
    def test_pesquisa_cpf_usuario_existente(self, credenciais_rede):
        """Verifica pesquisa por CPF de um usuário existente."""
        from playwright.sync_api import sync_playwright

        from consultor_sti import (
            login_to_system,
            open_search_users_page,
            search_user,
        )

        login, senha = credenciais_rede

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()

            try:
                login_to_system(page, login, senha)
                open_search_users_page(page)

                # Substituir por um CPF válido do ambiente de teste
                resultado = search_user(page, "cpf", "52998224725")
                assert resultado.message in {
                    "Usuário encontrado",
                    "Nenhum usuário encontrado",
                }
            finally:
                browser.close()


class TestE2EProrrogador:
    """Testes e2e do Prorrogador STI.

    ATENÇÃO: Estes testes modificam dados no sistema real.
    Use apenas em ambiente de homologação.
    """

    @pytest.mark.skip(reason="Executar manualmente apenas em homologação")
    def test_prorrogacao_usuario(self, credenciais_rede):
        """Verifica o fluxo completo de prorrogação."""
        from prorrogador_sti import run_automation

        login, senha = credenciais_rede

        # Substituir por usuário e data reais de teste
        resultado = run_automation(
            login,
            senha,
            "usuario.teste",
            "31/12/2026",
            False,
        )

        assert isinstance(resultado, str)
