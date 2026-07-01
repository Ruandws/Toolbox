import pytest

import cadastro_pessoa_aghu as aghu
from cadastro_pessoa_aghu import (
    CadastroPessoaEntrada,
    ResultadoCadastroPessoa,
    STATUS_CRIADO,
    STATUS_ERRO,
    ler_planilha_cadastros,
)
from testes.aghu.fixtures_cadastro_pessoa import ContextFake, PageFake, pessoa_valida


class JanelaFake:
    def locator(self, _seletor):
        return object()


class BotaoFake:
    @property
    def first(self):
        return self

    def wait_for(self, state, timeout):
        assert state == "visible"
        assert timeout > 0


class JanelaComBotaoFake:
    def get_by_role(self, role, name):
        assert role == "button"
        assert name == "Pesquisar"
        return BotaoFake()


class TestRegressaoPlanilhaPessoa:
    def test_aliases_ascii_continuam_sendo_aceitos_para_campos_obrigatorios(
        self,
        tmp_xlsx,
    ):
        caminho = tmp_xlsx(
            "aliases_ascii.xlsx",
            [
                "Nome",
                "Nome Mae",
                "Nascimento",
                "Naturalidade",
                "RG",
                "Orgao Emissor",
                "UF RG",
                "CPF",
            ],
            [
                [
                    "Joao",
                    "Maria",
                    "01/01/1990",
                    "Brasilia",
                    "123456",
                    "SSP",
                    "DF",
                    "123.456.789-01",
                ]
            ],
        )

        cadastros = ler_planilha_cadastros(caminho)

        assert cadastros[0].nome_pessoa == "Joao"
        assert cadastros[0].nome_mae == "Maria"
        assert cadastros[0].orgao_emissor == "SSP"
        assert cadastros[0].uf_rg == "DF"
        assert cadastros[0].cpf == "12345678901"

    def test_cpf_formatado_na_planilha_nao_quebra_validacao(self, tmp_xlsx):
        caminho = tmp_xlsx(
            "cpf_formatado.xlsx",
            [aghu.ALIASES_COLUNAS[campo][0] for campo in aghu.CAMPOS_PESSOA_OBRIGATORIOS],
            [list(getattr(pessoa_valida(), campo) for campo in aghu.CAMPOS_PESSOA_OBRIGATORIOS)],
        )

        cadastro = ler_planilha_cadastros(caminho)[0]

        assert cadastro.cpf == "12345678901"
        assert aghu.validar_entrada(cadastro) == []


class TestRegressaoPesquisaPessoa:
    def test_pesquisa_nao_confirma_vazio_antes_de_cpf_aparecer(
        self,
        monkeypatch,
    ):
        linha_encontrada = object()
        chamadas = {"total": 0}
        flow = aghu.PessoaFlow(JanelaFake())

        def localizar(_linhas, _cpf):
            chamadas["total"] += 1
            if chamadas["total"] >= 3:
                return linha_encontrada
            return None

        monkeypatch.setattr(flow, "_linha_por_cpf", localizar)
        monkeypatch.setattr(aghu, "existe_carregamento_visivel", lambda _janela: False)
        monkeypatch.setattr(aghu, "linha_vazia_visivel", lambda _linhas: True)
        monkeypatch.setattr(aghu.time, "sleep", lambda _segundos: None)

        estado, linha = flow._aguardar_resultado_pesquisa(
            "12345678901",
            timeout_ms=1000,
            consulta_concluida=True,
        )

        assert estado == "encontrado"
        assert linha is linha_encontrada

    def test_pesquisa_indefinida_vira_conferir_manual_no_processar(
        self,
        monkeypatch,
    ):
        flow = aghu.PessoaFlow(JanelaFake())
        monkeypatch.setattr(flow, "pesquisar_por_cpf", lambda _cpf: ("indefinido", None))

        resultado = flow.processar(pessoa_valida())

        assert resultado.status == aghu.STATUS_CONFERIR_MANUAL
        assert "Pesquisa de pessoa por CPF" in resultado.detalhes


class TestRegressaoCleanStatePessoa:
    def test_processar_cadastros_preserva_url_aghu_no_retry(self, monkeypatch):
        chamadas = []

        class FlowFake:
            def __init__(self, janela):
                self.janela = janela

            def fechar_painel_sucesso_se_visivel(self):
                chamadas.append(("fechar_sucesso", self.janela))
                return True

        def garantir(**kwargs):
            chamadas.append(("garantir", kwargs["page_atual"], kwargs["url_aghu"]))
            if len([chamada for chamada in chamadas if chamada[0] == "garantir"]) == 1:
                raise RuntimeError("falha temporaria")
            return kwargs["page_atual"], kwargs["janela_atual"]

        def trocar(**kwargs):
            chamadas.append(("trocar", kwargs["url_aghu"]))
            return "page-limpa"

        def navegar(**kwargs):
            chamadas.append(("navegar", kwargs["page_atual"], kwargs["url_aghu"]))
            return kwargs["page_atual"], "janela-limpa"

        monkeypatch.setattr(aghu, "garantir_tela_pesquisa_pessoa", garantir)
        monkeypatch.setattr(aghu, "trocar_aba_aghux", trocar)
        monkeypatch.setattr(aghu, "navegar_ate_cadastro_pessoa", navegar)
        monkeypatch.setattr(aghu, "PessoaFlow", FlowFake)
        monkeypatch.setattr(
            aghu,
            "processar_cadastro",
            lambda janela, entrada: ResultadoCadastroPessoa(
                cpf=entrada.cpf,
                nome_pessoa=entrada.nome_pessoa,
                status=STATUS_CRIADO,
                detalhes="OK",
            ),
        )

        resultados = aghu.processar_cadastros(
            context=object(),
            page_inicial="page-inicial",
            janela_sistema_inicial="janela-inicial",
            cadastros=[pessoa_valida()],
            usuario_rede="usuario",
            senha="senha",
            url_aghu="http://homologacao",
        )

        assert resultados[0].status == STATUS_CRIADO
        assert ("trocar", "http://homologacao") in chamadas
        assert ("navegar", "page-limpa", "http://homologacao") in chamadas
        assert ("garantir", "page-limpa", "http://homologacao") in chamadas
        assert chamadas[-1] == ("fechar_sucesso", "janela-limpa")

    def test_navegar_ate_cadastro_pessoa_tenta_clean_state_uma_vez(
        self,
        monkeypatch,
    ):
        chamadas = []

        def navegar_menu(page, caminho):
            chamadas.append(("menu", page, caminho))
            if len(chamadas) == 1:
                raise RuntimeError("menu travado")
            return JanelaComBotaoFake()

        monkeypatch.setattr(aghu, "navegar_menu_aghu", navegar_menu)
        monkeypatch.setattr(aghu, "primeiro_visivel", lambda *_args, **_kwargs: object())
        monkeypatch.setattr(
            aghu,
            "trocar_aba_aghux",
            lambda **kwargs: chamadas.append(("trocar", kwargs["url_aghu"]))
            or "page-limpa",
        )

        page, janela = aghu.navegar_ate_cadastro_pessoa(
            context=object(),
            page_atual="page-inicial",
            usuario_rede="usuario",
            senha="senha",
            url_aghu="url-homologacao",
        )

        assert page == "page-limpa"
        assert isinstance(janela, JanelaComBotaoFake)
        assert ("trocar", "url-homologacao") in chamadas
        assert chamadas[-1][0] == "menu"
        assert chamadas[-1][1] == "page-limpa"

    def test_trocar_aba_aghux_fecha_page_atual_e_reautentica_na_url(self, monkeypatch):
        page_atual = PageFake()
        context = ContextFake()
        chamadas = []
        monkeypatch.setattr(
            aghu,
            "fazer_login",
            lambda page, usuario_rede, senha, *, url_aghu: chamadas.append(
                (page, usuario_rede, senha, url_aghu)
            ),
        )

        nova_page = aghu.trocar_aba_aghux(
            context=context,
            page_atual=page_atual,
            usuario_rede="usuario",
            senha="senha",
            url_aghu="url-homologacao",
        )

        assert page_atual.fechada is True
        assert nova_page is context.page
        assert nova_page.goto_url == "url-homologacao"
        assert chamadas == [(context.page, "usuario", "senha", "url-homologacao")]


class TestRegressaoPrevalidacao:
    def test_lote_totalmente_invalido_retorna_ignorados_sem_playwright(
        self,
        monkeypatch,
        tmp_path,
    ):
        monkeypatch.setattr(
            aghu,
            "sync_playwright",
            lambda: pytest.fail("Playwright nao deveria ser iniciado"),
        )

        resultados = aghu.executar_cadastro_pessoas(
            cadastros=[CadastroPessoaEntrada(cpf="1")],
            usuario_rede="usuario",
            senha="senha",
            diretorio_logs=tmp_path,
        )

        assert len(resultados) == 1
        assert resultados[0].status == aghu.STATUS_IGNORADO
        assert "CPF deve conter 11 digitos" in resultados[0].detalhes

    def test_falha_tecnica_definitiva_mantem_cpf_e_nome_normalizados(
        self,
        monkeypatch,
    ):
        monkeypatch.setattr(
            aghu,
            "garantir_tela_pesquisa_pessoa",
            lambda **_kwargs: ("page", "janela"),
        )
        monkeypatch.setattr(
            aghu,
            "processar_cadastro",
            lambda *_args: (_ for _ in ()).throw(RuntimeError("erro tecnico")),
        )
        monkeypatch.setattr(aghu, "trocar_aba_aghux", lambda **_kwargs: "page-limpa")
        monkeypatch.setattr(
            aghu,
            "navegar_ate_cadastro_pessoa",
            lambda **_kwargs: ("page-limpa", "janela-limpa"),
        )

        resultados = aghu.processar_cadastros(
            context=object(),
            page_inicial=object(),
            janela_sistema_inicial=object(),
            cadastros=[pessoa_valida(nome_pessoa=" Joao ", cpf="123.456.789-01")],
            usuario_rede="usuario",
            senha="senha",
        )

        assert resultados[0].status == STATUS_ERRO
        assert resultados[0].cpf == "12345678901"
        assert resultados[0].nome_pessoa == "Joao"
