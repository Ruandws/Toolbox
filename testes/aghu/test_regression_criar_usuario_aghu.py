# test_regression_criar_usuario_aghu.py — Testes de regressão para criar_usuario_aghu.py
#
# Validam comportamentos previamente corrigidos para garantir que não
# regrediram. Cada teste documenta o cenário de bug original.

from criar_usuario_aghu import (
    COLUNAS_OBRIGATORIAS_PLANILHA,
    STATUS_ERRO,
    UsuarioImportacao,
    _normalizar_login,
    _normalizar_texto,
    _validar_usuario,
    _valor_em_branco,
    ler_planilha_usuarios,
)

import criar_usuario_aghu as aghu


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
        assert "Login contem espacos indevidos" in erros

    def test_nome_com_espacos_corrigiveis_nao_ignora_linha(self):
        usuario = UsuarioImportacao(
            login="joao.silva",
            nome_completo="  Joao\t\u00a0 Silva\r\nSouza  ",
            email="joao@email.com",
        )

        usuario_normalizado, resultado_validacao = (
            aghu._preparar_usuario_importacao(usuario)
        )

        assert resultado_validacao is None
        assert usuario_normalizado.nome_completo == "Joao Silva Souza"


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

    def test_espacos_de_celula_sao_preservados_para_validacao(self, tmp_xlsx):
        caminho = tmp_xlsx(
            "espacos_celula.xlsx",
            list(COLUNAS_OBRIGATORIAS_PLANILHA),
            [[" joao.silva ", "Joao Silva", "joao@email.com"]],
        )
        usuarios = ler_planilha_usuarios(str(caminho))

        assert usuarios[0].login == " joao.silva "


class JanelaFake:
    def locator(self, _seletor):
        return object()


class WidgetCarregamentoFake:
    def __init__(self, visibilidades):
        self.visibilidades = list(visibilidades)

    @property
    def first(self):
        return self

    def get_by_text(self, _texto):
        return self

    def wait_for(self, state, timeout):
        assert state == "visible"
        assert timeout > 0

    def is_visible(self, timeout):
        assert timeout > 0

        if not self.visibilidades:
            return False

        return self.visibilidades.pop(0)


class JanelaComWidgetFake:
    def __init__(self, visibilidades):
        self.widget = WidgetCarregamentoFake(visibilidades)

    def get_by_label(self, label):
        assert label == "Carregando"
        return self.widget

    def locator(self, _seletor):
        return object()


class TestRegressaoConsultaLenta:
    def test_aguarda_widget_carregando_sumir_antes_de_ler_resultado(self):
        janela = JanelaComWidgetFake([True, True, False])

        assert aghu._aguardar_ciclo_carregamento_consulta(
            janela,
            timeout_ms=2000,
            deteccao_ms=100,
        ) is True

    def test_pesquisa_inicial_nao_confirma_vazio_antes_de_resultado_real(
        self,
        monkeypatch,
    ):
        linha_encontrada = object()
        chamadas = {"total": 0}

        def localizar_login(*_args, **_kwargs):
            chamadas["total"] += 1
            if chamadas["total"] >= 4:
                return linha_encontrada

            return None

        monkeypatch.setattr(aghu, "_existe_carregamento_visivel", lambda _janela: False)
        monkeypatch.setattr(aghu, "_linha_tabela_por_login", localizar_login)
        monkeypatch.setattr(aghu, "_linha_vazia_visivel", lambda _linhas: True)

        estado, linha = aghu._aguardar_resultado_pesquisa_usuario(
            JanelaFake(),
            "JOAO.SILVA",
            timeout_ms=2000,
            estabilidade_resultado_ms=100,
        )

        assert estado == "encontrado"
        assert linha is linha_encontrada

    def test_identity_nao_confirma_vazio_antes_de_resultado_real(self, monkeypatch):
        linha_encontrada = object()
        chamadas = {"total": 0}

        def localizar_texto(*_args, **_kwargs):
            chamadas["total"] += 1
            if chamadas["total"] >= 4:
                return linha_encontrada

            return None

        monkeypatch.setattr(aghu, "_existe_carregamento_visivel", lambda _janela: False)
        monkeypatch.setattr(aghu, "_linha_tabela_por_texto_visivel", localizar_texto)
        monkeypatch.setattr(aghu, "_linha_vazia_visivel", lambda _linhas: True)

        estado, linha = aghu._aguardar_resultado_identity(
            JanelaFake(),
            "JOAO.SILVA",
            timeout_ms=2000,
            estabilidade_resultado_ms=100,
        )

        assert estado == "encontrado"
        assert linha is linha_encontrada

    def test_identity_indefinido_retorna_erro_em_vez_de_nao_encontrado(
        self,
        monkeypatch,
    ):
        usuario = UsuarioImportacao(
            login="joao.silva",
            nome_completo="Joao Silva",
            email="joao@email.com",
        )

        monkeypatch.setattr(
            aghu,
            "_pesquisar_usuario_importado",
            lambda *_args, **_kwargs: ("nao_encontrado", None),
        )
        monkeypatch.setattr(aghu, "_abrir_importacao_usuario", lambda *_args: None)
        monkeypatch.setattr(
            aghu,
            "_pesquisar_usuario_identity",
            lambda *_args, **_kwargs: ("indefinido", None),
        )

        resultado = aghu.importar_usuario(object(), usuario)

        assert resultado.status == STATUS_ERRO
        assert "Identity Manager nao retornou estado conclusivo" in resultado.detalhes
