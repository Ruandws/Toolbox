# test_regression_prorrogador_sti.py — Testes de regressão para prorrogador_sti.py
#
# Validam cenários de bugs previamente corrigidos.

import pytest
from datetime import datetime

from prorrogador_sti import (
    build_user_url,
    normalize_expiration_date,
    normalize_user_value,
    prepare_user_value,
)


class TestRegressaoData:
    """Regressões em normalização de data."""

    def test_data_somente_digitos_oito_caracteres(self):
        """Bug: 8 dígitos puros não eram convertidos para dd/mm/aaaa."""
        assert normalize_expiration_date("01012027") == "01/01/2027"

    def test_data_com_barra_e_espacos(self):
        """Bug: espaços ao redor da data causavam falha."""
        assert normalize_expiration_date("  22/06/2026  ") == "22/06/2026"

    def test_dia_29_fevereiro_bissexto(self):
        """Bug: 29/02 em ano bissexto era rejeitado."""
        assert normalize_expiration_date("29/02/2028") == "29/02/2028"

    def test_dia_29_fevereiro_nao_bissexto_rejeita(self):
        """Bug: 29/02 em ano não bissexto não era rejeitado."""
        with pytest.raises(ValueError):
            normalize_expiration_date("29/02/2027")


class TestRegressaoUsuario:
    """Regressões em validação de usuário."""

    def test_float_inteiro_normaliza_sem_decimal(self):
        """Bug: 12345.0 gerava '12345.0' em vez de '12345'."""
        assert normalize_user_value(12345.0) == "12345"

    def test_usuario_com_apostrofo_aceito(self):
        """Bug: apóstrofo em nomes como O'Brien era rejeitado."""
        resultado = prepare_user_value("o'brien")
        assert resultado == "o'brien"

    def test_usuario_com_arroba_aceito(self):
        """Bug: @ em logins de e-mail era rejeitado."""
        resultado = prepare_user_value("joao@dominio")
        assert resultado == "joao@dominio"


class TestRegressaoUrl:
    """Regressões na construção de URL."""

    def test_url_com_caracteres_especiais(self):
        """Bug: caracteres especiais permitidos não eram URL-safe."""
        url = build_user_url("joao.silva")
        assert "joao.silva" in url
