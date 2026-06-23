# test_regression_idce.py — Testes de regressão para o sistema IDCE.
#
# Esqueleto de testes de regressão. Será expandido conforme o módulo
# adduser_idce.py for refatorado para expor funções puras testáveis.

import pytest


class TestRegressaoIdce:
    """Testes de regressão do IDCE.

    TODO: Adicionar testes conforme bugs forem encontrados e corrigidos.
    """

    @pytest.mark.skip(reason="Aguardando refatoração de adduser_idce.py")
    def test_usuario_ja_importado_nao_causa_erro(self):
        """Regressão: popup 'Usuário já importado!' deve ser tratado."""
        pass

    @pytest.mark.skip(reason="Aguardando refatoração de adduser_idce.py")
    def test_selecao_correta_quando_multiplos_resultados(self):
        """Regressão: usuários com nomes similares devem ser diferenciados."""
        pass
