# test_e2e_aghu.py — Testes end-to-end para o sistema AGHU.
#
# Exigem rede e credenciais reais. Execute com:
#   pytest testes/aghu/test_e2e_aghu.py -m e2e
#
# Variáveis de ambiente necessárias:
#   EXTRATOR_LOGIN, EXTRATOR_SENHA

import pytest

pytestmark = pytest.mark.e2e


class TestE2EAutenticacaoAghu:
    """Testes e2e de autenticação no AGHUX."""

    def test_login_valido(self, credenciais_rede):
        """Verifica que credenciais válidas resultam em login bem-sucedido."""
        from autenticador import AGHU_URL, autenticar_aghu

        login, senha = credenciais_rede

        resultado = autenticar_aghu(
            usuario=login,
            senha=senha,
            url_login=AGHU_URL,
            headless=True,
            timeout_ms=30000,
            tempo_tela_principal_segundos=1,
        )

        assert resultado.status in {"sucesso", "sessao_ativa"}, (
            f"Login falhou: {resultado.mensagem}"
        )

    def test_login_invalido(self):
        """Verifica que credenciais inválidas retornam status correto."""
        from autenticador import AGHU_URL, autenticar_aghu

        resultado = autenticar_aghu(
            usuario="usuario_inexistente_xyz",
            senha="senha_incorreta_xyz",
            url_login=AGHU_URL,
            headless=True,
            timeout_ms=15000,
            tempo_tela_principal_segundos=0,
        )

        assert resultado.status in {"credenciais_invalidas", "timeout", "erro"}


class TestE2EImportacaoUsuarioAghu:
    """Testes e2e do fluxo de importação de usuário no AGHUX.

    ATENÇÃO: Estes testes interagem com o sistema real. Use apenas em
    ambiente de homologação.
    """

    @pytest.mark.skip(reason="Executar manualmente apenas em homologação")
    def test_importacao_usuario_individual(self, credenciais_rede):
        """Verifica o fluxo completo de importação de um usuário."""
        from autenticador import AGHU_URL_HOMOLOGACAO
        from criar_usuario_aghu import (
            UsuarioImportacao,
            executar_importacao_usuarios,
        )

        login, senha = credenciais_rede
        usuarios = [
            UsuarioImportacao(
                login="usuario.teste",
                nome_completo="Usuário de Teste Automatizado",
                email="teste@email.com",
            ),
        ]

        resultados = executar_importacao_usuarios(
            usuarios=usuarios,
            usuario_rede=login,
            senha=senha,
            url_aghu=AGHU_URL_HOMOLOGACAO,
            mostrar_browser=False,
        )

        assert len(resultados) == 1
        assert resultados[0].status in {"importado", "ja_importado", "nao_encontrado"}
