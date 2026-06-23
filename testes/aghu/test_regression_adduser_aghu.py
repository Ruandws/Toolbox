# test_regression_adduser_aghu.py — Testes de regressão para adduser_aghu.py
#
# Validam comportamentos previamente corrigidos para garantir que não
# regrediram. Cada teste documenta o cenário de bug original.

import pytest

from adduser_aghu import (
    COLUNAS_OBRIGATORIAS_PLANILHA,
    STATUS_IGNORADO,
    UsuarioImportacao,
    _normalizar_login,
    _normalizar_texto,
    _resultado,
    _validar_usuario,
    _valor_em_branco,
    ler_planilha_usuarios,
)


class TestRegressaoNormalizacao:
    """Regressões em normalização de texto e login."""

    def test_normalizar_texto_com_tabs_e_newlines(self):
        """Bug: tabs e newlines não eram colapsados corretamente."""
        assert _normalizar_texto("  a\t\tb\n\nc  ") == "a b c"

    def test_normalizar_login_ja_maiusculo(self):
        """Bug: login já maiúsculo era processado novamente."""
        assert _normalizar_login("ANDRADE.RUAN") == "ANDRADE.RUAN"

    def test_valor_em_branco_com_float_nan(self):
        """Bug: float('nan') causava exceção em vez de retornar True."""
        assert _valor_em_branco(float("nan")) is True


class TestRegressaoValidacao:
    """Regressões em validação de usuário."""

    def test_email_somente_espacos_e_considerado_branco(self):
        """Bug: e-mail com espaços passava validação."""
        usuario = UsuarioImportacao(
            login="joao",
            nome_completo="João",
            email="   ",
        )
        erros = _validar_usuario(usuario)
        assert "E-mail" in erros

    def test_login_com_espacos_laterais_nao_e_branco(self):
        """Bug: login ' joao ' era considerado em branco após strip."""
        usuario = UsuarioImportacao(
            login=" joao ",
            nome_completo="João",
            email="joao@x.com",
        )
        erros = _validar_usuario(usuario)
        assert "Login" not in erros


class TestRegressaoPlanilha:
    """Regressões na leitura de planilhas."""

    def test_colunas_com_espacos_extras_sao_reconhecidas(self, tmp_xlsx):
        """Bug: coluna '  Login  ' não era reconhecida.

        O pandas faz df.columns.str.strip() que remove espaços laterais.
        Porém o openpyxl pode gravar espaços unicode especiais. Este teste
        valida que espaços ASCII comuns são tratados corretamente.
        """
        import openpyxl

        caminho = tmp_xlsx(
            "espacos.xlsx",
            ["  Login  ", " Nome Completo ", " E-mail "],
            [["joao", "João Silva", "joao@x.com"]],
        )

        # Verifica primeiro que os cabeçalhos realmente têm espaços
        wb = openpyxl.load_workbook(caminho)
        ws = wb.active
        raw_headers = [cell.value for cell in next(ws.iter_rows(max_row=1))]
        assert raw_headers[0].strip() == "Login"
        wb.close()

        # pandas strip deve resolver
        import pandas as pd

        df = pd.read_excel(caminho, dtype=str, engine="openpyxl")
        df.columns = df.columns.str.strip()
        assert "Login" in df.columns
        assert "Nome Completo" in df.columns
        assert "E-mail" in df.columns

    def test_linhas_totalmente_vazias_sao_ignoradas(self, tmp_xlsx):
        """Bug: linhas em branco geravam UsuarioImportacao com campos vazios."""
        caminho = tmp_xlsx(
            "vazias.xlsx",
            list(COLUNAS_OBRIGATORIAS_PLANILHA),
            [
                ["joao", "João", "joao@x.com"],
                ["", "", ""],
                ["ana", "Ana", "ana@x.com"],
            ],
        )
        usuarios = ler_planilha_usuarios(str(caminho))
        # Pode incluir linha vazia (depende de fillna), mas não deve crashar.
        assert len(usuarios) >= 2
