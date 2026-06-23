# test_e2e_idce.py — Testes end-to-end para o sistema IDCE.
#
# Exigem rede e credenciais reais. Execute com:
#   pytest testes/idce/test_e2e_idce.py -m e2e
#
# Variáveis de ambiente necessárias:
#   EXTRATOR_LOGIN, EXTRATOR_SENHA

import pytest

pytestmark = pytest.mark.e2e


class TestE2ELoginIdce:
    """Testes e2e de autenticação no IDCE.

    TODO: Implementar após refatoração do módulo adduser_idce.py.
    """

    @pytest.mark.skip(reason="Aguardando refatoração de adduser_idce.py")
    def test_login_valido_idce(self, credenciais_rede):
        """Verifica que credenciais válidas permitem login no IDCE."""
        pass

    @pytest.mark.skip(reason="Aguardando refatoração de adduser_idce.py")
    def test_importacao_usuario_idce(self, credenciais_rede):
        """Verifica o fluxo completo de importação no IDCE."""
        pass
