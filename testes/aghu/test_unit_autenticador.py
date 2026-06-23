# test_unit_autenticador.py — Testes unitários para autenticador.py
#
# Testa funções puras e dataclasses do módulo de autenticação.

import pytest

from autenticador import (
    AGHU_URL,
    ResultadoLogin,
    exigir_login_valido,
)


# ---------------------------------------------------------------------------
# ResultadoLogin
# ---------------------------------------------------------------------------


class TestResultadoLogin:
    def test_criacao_basica(self):
        resultado = ResultadoLogin(
            status="sucesso",
            mensagem="Login efetuado.",
        )
        assert resultado.status == "sucesso"
        assert resultado.url_final is None

    def test_criacao_com_url(self):
        resultado = ResultadoLogin(
            status="erro",
            mensagem="Falha",
            url_final="https://example.com",
        )
        assert resultado.url_final == "https://example.com"

    def test_frozen(self):
        resultado = ResultadoLogin(status="sucesso", mensagem="OK")

        with pytest.raises(AttributeError):
            resultado.status = "erro"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# exigir_login_valido
# ---------------------------------------------------------------------------


class TestExigirLoginValido:
    def test_sucesso_nao_levanta(self):
        resultado = ResultadoLogin(status="sucesso", mensagem="OK")
        exigir_login_valido(resultado)  # Não deve levantar exceção

    def test_sessao_ativa_nao_levanta(self):
        resultado = ResultadoLogin(status="sessao_ativa", mensagem="Ativa")
        exigir_login_valido(resultado)

    def test_credenciais_invalidas_levanta(self):
        resultado = ResultadoLogin(
            status="credenciais_invalidas",
            mensagem="Usuário/Senha Inválido.",
        )

        with pytest.raises(RuntimeError, match="Falha ao autenticar"):
            exigir_login_valido(resultado)

    def test_erro_levanta(self):
        resultado = ResultadoLogin(status="erro", mensagem="Falha técnica")

        with pytest.raises(RuntimeError):
            exigir_login_valido(resultado)

    def test_timeout_levanta(self):
        resultado = ResultadoLogin(status="timeout", mensagem="Timeout")

        with pytest.raises(RuntimeError):
            exigir_login_valido(resultado)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------


class TestConstantes:
    def test_aghu_url_nao_vazia(self):
        assert AGHU_URL
        assert isinstance(AGHU_URL, str)
