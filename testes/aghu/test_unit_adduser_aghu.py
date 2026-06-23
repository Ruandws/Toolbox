# test_unit_adduser_aghu.py — Testes unitários para adduser_aghu.py
#
# Testa funções puras e dataclasses sem dependência de browser ou rede.

from pathlib import Path

import pytest

from adduser_aghu import (
    COLUNAS_OBRIGATORIAS_PLANILHA,
    STATUS_ERRO,
    STATUS_IGNORADO,
    ResultadoImportacao,
    UsuarioImportacao,
    _normalizar_login,
    _normalizar_texto,
    _resultado,
    _validar_usuario,
    _valor_em_branco,
    ler_planilha_usuarios,
    salvar_relatorio_resultados,
)


# ---------------------------------------------------------------------------
# _normalizar_texto
# ---------------------------------------------------------------------------


class TestNormalizarTexto:
    def test_texto_simples(self):
        assert _normalizar_texto("  Olá   Mundo  ") == "olá mundo"

    def test_valor_none(self):
        assert _normalizar_texto(None) == ""

    def test_valor_numerico(self):
        assert _normalizar_texto(123) == "123"

    def test_string_vazia(self):
        assert _normalizar_texto("") == ""


# ---------------------------------------------------------------------------
# _normalizar_login
# ---------------------------------------------------------------------------


class TestNormalizarLogin:
    def test_login_minusculo_para_maiusculo(self):
        assert _normalizar_login("andrade.ruan") == "ANDRADE.RUAN"

    def test_login_com_espacos(self):
        assert _normalizar_login("  joao.silva  ") == "JOAO.SILVA"

    def test_login_none(self):
        assert _normalizar_login(None) == ""


# ---------------------------------------------------------------------------
# _valor_em_branco
# ---------------------------------------------------------------------------


class TestValorEmBranco:
    def test_string_vazia(self):
        assert _valor_em_branco("") is True

    def test_string_espacos(self):
        assert _valor_em_branco("   ") is True

    def test_none(self):
        assert _valor_em_branco(None) is True

    def test_valor_preenchido(self):
        assert _valor_em_branco("abc") is False

    def test_nan_pandas(self):
        import pandas as pd

        assert _valor_em_branco(pd.NA) is True


# ---------------------------------------------------------------------------
# _validar_usuario
# ---------------------------------------------------------------------------


class TestValidarUsuario:
    def test_usuario_valido_retorna_lista_vazia(self):
        usuario = UsuarioImportacao(
            login="joao.silva",
            nome_completo="João Silva",
            email="joao@email.com",
        )
        assert _validar_usuario(usuario) == []

    def test_login_em_branco(self):
        usuario = UsuarioImportacao(
            login="",
            nome_completo="João Silva",
            email="joao@email.com",
        )
        erros = _validar_usuario(usuario)
        assert "Login" in erros

    def test_todos_campos_em_branco(self):
        usuario = UsuarioImportacao(login="", nome_completo="", email="")
        erros = _validar_usuario(usuario)
        assert len(erros) == 3


# ---------------------------------------------------------------------------
# _resultado
# ---------------------------------------------------------------------------


class TestResultado:
    def test_cria_resultado_importacao(self):
        usuario = UsuarioImportacao(
            login="ana.maria",
            nome_completo="Ana Maria",
            email="ana@mail.com",
        )
        resultado = _resultado(usuario, STATUS_IGNORADO, "Linha ignorada")

        assert isinstance(resultado, ResultadoImportacao)
        assert resultado.login == "ana.maria"
        assert resultado.status == STATUS_IGNORADO


# ---------------------------------------------------------------------------
# UsuarioImportacao / ResultadoImportacao (dataclasses)
# ---------------------------------------------------------------------------


class TestDataclasses:
    def test_usuario_importacao_frozen(self):
        usuario = UsuarioImportacao(
            login="x",
            nome_completo="X",
            email="x@x.com",
        )

        with pytest.raises(AttributeError):
            usuario.login = "y"  # type: ignore[misc]

    def test_resultado_importacao_frozen(self):
        resultado = ResultadoImportacao(
            login="x",
            nome_completo="X",
            email="x@x.com",
            status=STATUS_ERRO,
            detalhes="Erro teste",
        )

        with pytest.raises(AttributeError):
            resultado.status = "outro"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ler_planilha_usuarios
# ---------------------------------------------------------------------------


class TestLerPlanilhaUsuarios:
    def test_planilha_valida(self, tmp_xlsx):
        caminho = tmp_xlsx(
            "usuarios.xlsx",
            list(COLUNAS_OBRIGATORIAS_PLANILHA),
            [["joao.silva", "João Silva", "joao@email.com"]],
        )
        usuarios = ler_planilha_usuarios(str(caminho))

        assert len(usuarios) == 1
        assert usuarios[0].login == "joao.silva"

    def test_planilha_inexistente_levanta_erro(self):
        with pytest.raises(FileNotFoundError):
            ler_planilha_usuarios("inexistente.xlsx")

    def test_extensao_invalida_levanta_erro(self, tmp_path):
        caminho = tmp_path / "dados.csv"
        caminho.write_text("a,b,c")

        with pytest.raises(ValueError, match=".xlsx"):
            ler_planilha_usuarios(str(caminho))

    def test_colunas_faltantes_levanta_erro(self, tmp_xlsx):
        caminho = tmp_xlsx(
            "incompleta.xlsx",
            ["Login"],
            [["joao"]],
        )

        with pytest.raises(ValueError, match="Colunas obrigatorias ausentes"):
            ler_planilha_usuarios(str(caminho))


# ---------------------------------------------------------------------------
# salvar_relatorio_resultados
# ---------------------------------------------------------------------------


class TestSalvarRelatorioResultados:
    def test_salva_relatorio_xlsx(self, tmp_path):
        resultados = [
            ResultadoImportacao(
                login="ana",
                nome_completo="Ana",
                email="ana@x.com",
                status="importado",
                detalhes="OK",
            ),
        ]
        caminho = tmp_path / "relatorio.xlsx"
        retorno = salvar_relatorio_resultados(resultados, str(caminho))

        assert retorno.exists()
        assert retorno.suffix == ".xlsx"

    def test_extensao_invalida_levanta_erro(self, tmp_path):
        with pytest.raises(ValueError, match=".xlsx"):
            salvar_relatorio_resultados([], str(tmp_path / "relatorio.csv"))
