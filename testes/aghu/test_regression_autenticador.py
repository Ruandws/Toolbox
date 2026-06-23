# test_regression_autenticador.py — Testes de regressão para autenticador.py
#
# Garantem que comportamentos previamente corrigidos continuam funcionando.

import pytest

from autenticador import ResultadoLogin, exigir_login_valido


class TestRegressaoExigirLoginValido:
    """Regressões em exigir_login_valido."""

    def test_todos_status_de_falha_levantam_runtime_error(self):
        """Bug: alguns status de falha não levantavam exceção."""
        status_falha = ["credenciais_invalidas", "timeout", "erro"]

        for status in status_falha:
            resultado = ResultadoLogin(status=status, mensagem="teste")

            with pytest.raises(RuntimeError):
                exigir_login_valido(resultado)

    def test_resultado_com_url_final_preserva_mensagem(self):
        """Bug: mensagem era descartada quando url_final estava presente."""
        resultado = ResultadoLogin(
            status="erro",
            mensagem="Falha específica",
            url_final="https://aghu.example.com",
        )

        with pytest.raises(RuntimeError, match="Falha específica"):
            exigir_login_valido(resultado)
