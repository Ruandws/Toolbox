import pytest

import ui_profissionais_unidade_cirurgica as ui
from profissionais_unidade_cirurgica_aghu import (
    CadastroProfissionalUnidadeEntrada,
    ResultadoCadastroProfissional,
    STATUS_CONFERIR_MANUAL,
    STATUS_CRIADO,
    STATUS_ERRO,
    STATUS_FUNCIONARIO_NAO_ENCONTRADO,
    STATUS_IGNORADO,
    STATUS_MANTIDO,
    UNIDADES_FUNCIONAIS,
    FUNCAO_MEDICO_RESIDENTE,
)


class FakeEntry:
    def __init__(self, valor=""):
        self.valor = valor
        self.configuracoes = {}

    def get(self):
        return self.valor

    def delete(self, inicio, fim):
        self.valor = ""

    def insert(self, indice, valor):
        self.valor = valor

    def configure(self, **kwargs):
        self.configuracoes.update(kwargs)

    def focus(self):
        self.configuracoes["focus"] = True


class FakeWidget:
    def __init__(self):
        self.configuracoes = {}

    def configure(self, **kwargs):
        self.configuracoes.update(kwargs)

    def set(self, valor):
        self.configuracoes["set"] = valor


class FakeFrame:
    def __init__(self):
        self.visivel = False
        self.grid_args = None
        self.destruido = False

    def grid(self, **kwargs):
        self.visivel = True
        self.grid_args = kwargs

    def grid_remove(self):
        self.visivel = False

    def grid_configure(self, **kwargs):
        if self.grid_args is None:
            self.grid_args = {}
        self.grid_args.update(kwargs)

    def destroy(self):
        self.destruido = True


class FakeStringVar:
    def __init__(self, valor):
        self.valor = valor

    def get(self):
        return self.valor

    def set(self, valor):
        self.valor = valor


class FakeThread:
    criadas = []

    def __init__(self, target, args, daemon):
        self.target = target
        self.args = args
        self.daemon = daemon
        self.iniciada = False
        FakeThread.criadas.append(self)

    def start(self):
        self.iniciada = True


class FakeBrowser:
    def __init__(self):
        self.contextos = []
        self.fechado = False

    def new_context(self, **kwargs):
        contexto = FakeBrowserContext(kwargs)
        self.contextos.append(contexto)
        return contexto

    def close(self):
        self.fechado = True


class FakeBrowserContext:
    def __init__(self, kwargs):
        self.kwargs = kwargs
        self.pages = []

    def new_page(self):
        page = object()
        self.pages.append(page)
        return page


class FakeChromium:
    def __init__(self):
        self.launch_kwargs = None
        self.browser = FakeBrowser()

    def launch(self, **kwargs):
        self.launch_kwargs = kwargs
        return self.browser


class FakeSyncPlaywright:
    def __init__(self):
        self.chromium = FakeChromium()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def linha_profissional_fake(valor=""):
    return {
        "frame": FakeFrame(),
        "indice": FakeWidget(),
        "profissional": FakeEntry(valor),
        "remover": FakeWidget(),
    }


@pytest.fixture(autouse=True)
def limpar_threads_fake():
    FakeThread.criadas.clear()


@pytest.fixture()
def app_fake():
    app = object.__new__(ui.AghuProfissionaisUnidadeCirurgicaApp)
    app.em_execucao = False
    app.var_ambiente = FakeStringVar(ui.AMBIENTE_HOMOLOGACAO)
    app.var_tipo_execucao = FakeStringVar(ui.TIPO_INDIVIDUAL)
    app.var_browser = FakeStringVar(True)
    app.var_console = FakeStringVar(True)
    app.vars_unidades_funcionais = {
        unidade: FakeStringVar(indice == 0)
        for indice, unidade in enumerate(UNIDADES_FUNCIONAIS)
    }
    app.checkboxes_unidades_funcionais = [
        FakeWidget() for _ in UNIDADES_FUNCIONAIS
    ]
    app.linhas_profissionais_individual = [linha_profissional_fake()]
    app.entry_usuario_rede = FakeEntry()
    app.entry_senha = FakeEntry()
    app.entry_planilha_lote = FakeEntry()
    app.entry_relatorio_lote = FakeEntry()
    app.button_executar = FakeWidget()
    app.segment_tipo_execucao = FakeWidget()
    app.checkbox_browser = FakeWidget()
    app.checkbox_console = FakeWidget()
    app.option_ambiente = FakeWidget()
    app.button_adicionar_usuario = FakeWidget()
    app.label_contador_usuarios = FakeWidget()
    app.button_planilha_lote = FakeWidget()
    app.button_relatorio_lote = FakeWidget()
    app.frame_alerta_producao = FakeFrame()
    app.frame_individual = FakeFrame()
    app.frame_lote = FakeFrame()
    app.label_status = FakeWidget()
    return app


def test_obter_url_ambiente_aghu_retorna_urls_conhecidas():
    assert ui.obter_url_ambiente_aghu(ui.AMBIENTE_PRODUCAO) == ui.AGHU_URL
    assert (
        ui.obter_url_ambiente_aghu(ui.AMBIENTE_HOMOLOGACAO)
        == ui.AGHU_URL_HOMOLOGACAO
    )


def test_obter_url_ambiente_aghu_usa_producao_para_desconhecido():
    assert ui.obter_url_ambiente_aghu("outro") == ui.AGHU_URL


def test_alerta_producao_aparece_somente_em_producao(app_fake):
    ui.AghuProfissionaisUnidadeCirurgicaApp._atualizar_alerta_ambiente(
        app_fake,
        ui.AMBIENTE_PRODUCAO,
    )
    assert app_fake.frame_alerta_producao.visivel is True

    ui.AghuProfissionaisUnidadeCirurgicaApp._atualizar_alerta_ambiente(
        app_fake,
        ui.AMBIENTE_HOMOLOGACAO,
    )
    assert app_fake.frame_alerta_producao.visivel is False


def test_on_ambiente_changed_exibe_modal_producao_com_parent_self(
    app_fake,
    monkeypatch,
):
    chamadas = []
    monkeypatch.setattr(
        ui.messagebox,
        "showwarning",
        lambda *args, **kwargs: chamadas.append((args, kwargs)),
    )

    ui.AghuProfissionaisUnidadeCirurgicaApp._on_ambiente_changed(
        app_fake,
        ui.AMBIENTE_PRODUCAO,
    )

    assert app_fake.frame_alerta_producao.visivel is True
    assert len(chamadas) == 1
    assert ui.AMBIENTE_PRODUCAO in chamadas[0][0][0]
    assert chamadas[0][1]["parent"] is app_fake


def test_validar_opcoes_visibilidade_religa_opcao_alvo(app_fake, monkeypatch):
    chamadas = []
    app_fake.var_browser.set(False)
    app_fake.var_console.set(False)
    monkeypatch.setattr(
        ui.messagebox,
        "showwarning",
        lambda *args, **kwargs: chamadas.append((args, kwargs)),
    )

    ui.AghuProfissionaisUnidadeCirurgicaApp._validar_opcoes_visibilidade(
        app_fake,
        app_fake.var_console,
    )

    assert app_fake.var_console.get() is True
    assert len(chamadas) == 1


def test_credenciais_e_url_retorna_dados(app_fake):
    app_fake.entry_usuario_rede.valor = " usuario "
    app_fake.entry_senha.valor = " senha "

    usuario, senha, url = ui.AghuProfissionaisUnidadeCirurgicaApp._credenciais_e_url(
        app_fake
    )

    assert usuario == "usuario"
    assert senha == " senha "
    assert url == ui.AGHU_URL_HOMOLOGACAO


def test_cadastros_individuais_combinam_profissionais_e_unidades(app_fake):
    app_fake.linhas_profissionais_individual[0]["profissional"].valor = "Ana Silva"
    app_fake.linhas_profissionais_individual.append(
        linha_profissional_fake("Bia Costa")
    )
    app_fake.vars_unidades_funcionais[UNIDADES_FUNCIONAIS[1]].set(True)

    cadastros = ui.AghuProfissionaisUnidadeCirurgicaApp._cadastros_individuais(
        app_fake
    )

    assert cadastros == [
        CadastroProfissionalUnidadeEntrada(
            profissional="Ana Silva",
            unidade_funcional=UNIDADES_FUNCIONAIS[0],
            funcao=FUNCAO_MEDICO_RESIDENTE,
        ),
        CadastroProfissionalUnidadeEntrada(
            profissional="Ana Silva",
            unidade_funcional=UNIDADES_FUNCIONAIS[1],
            funcao=FUNCAO_MEDICO_RESIDENTE,
        ),
        CadastroProfissionalUnidadeEntrada(
            profissional="Bia Costa",
            unidade_funcional=UNIDADES_FUNCIONAIS[0],
            funcao=FUNCAO_MEDICO_RESIDENTE,
        ),
        CadastroProfissionalUnidadeEntrada(
            profissional="Bia Costa",
            unidade_funcional=UNIDADES_FUNCIONAIS[1],
            funcao=FUNCAO_MEDICO_RESIDENTE,
        ),
    ]


def test_cadastros_individuais_valida_unidade_selecionada(app_fake):
    app_fake.linhas_profissionais_individual[0]["profissional"].valor = "Ana Silva"
    for variavel in app_fake.vars_unidades_funcionais.values():
        variavel.set(False)

    with pytest.raises(ValueError, match="Selecione ao menos uma Unidade Funcional"):
        ui.AghuProfissionaisUnidadeCirurgicaApp._cadastros_individuais(app_fake)


def test_remover_linha_profissional_renumera_e_preserva_ultima(app_fake):
    primeira = app_fake.linhas_profissionais_individual[0]
    segunda = linha_profissional_fake("Bia Costa")
    app_fake.linhas_profissionais_individual.append(segunda)

    ui.AghuProfissionaisUnidadeCirurgicaApp._remover_linha_profissional(
        app_fake,
        primeira,
    )

    assert primeira["frame"].destruido is True
    assert app_fake.linhas_profissionais_individual == [segunda]
    assert segunda["indice"].configuracoes["text"] == "1"
    assert segunda["remover"].configuracoes["state"] == "disabled"

    ui.AghuProfissionaisUnidadeCirurgicaApp._remover_linha_profissional(
        app_fake,
        segunda,
    )

    assert app_fake.linhas_profissionais_individual == [segunda]


def test_atualizar_estado_linhas_profissionais_desabilita_adicionar_no_limite(
    app_fake,
):
    app_fake.linhas_profissionais_individual = [
        linha_profissional_fake(f"Profissional {indice}")
        for indice in range(ui.MAX_USUARIOS_UNITARIOS)
    ]

    ui.AghuProfissionaisUnidadeCirurgicaApp._atualizar_estado_linhas_profissionais(
        app_fake
    )

    assert app_fake.button_adicionar_usuario.configuracoes["state"] == "disabled"
    assert app_fake.label_contador_usuarios.configuracoes["text"] == "5 / 5 usuários"


def test_bloquear_e_liberar_execucao_alteram_estados(app_fake):
    ui.AghuProfissionaisUnidadeCirurgicaApp._bloquear_execucao(
        app_fake,
        "Executando...",
    )

    assert app_fake.em_execucao is True
    assert app_fake.button_executar.configuracoes["state"] == "disabled"
    assert app_fake.segment_tipo_execucao.configuracoes["state"] == "disabled"
    assert app_fake.entry_usuario_rede.configuracoes["state"] == "disabled"
    assert app_fake.entry_senha.configuracoes["state"] == "disabled"
    assert app_fake.option_ambiente.configuracoes["state"] == "disabled"
    assert app_fake.checkbox_browser.configuracoes["state"] == "disabled"
    assert app_fake.checkbox_console.configuracoes["state"] == "disabled"
    assert (
        app_fake.checkboxes_unidades_funcionais[0].configuracoes["state"]
        == "disabled"
    )
    assert (
        app_fake.linhas_profissionais_individual[0]["profissional"]
        .configuracoes["state"]
        == "disabled"
    )
    assert app_fake.button_adicionar_usuario.configuracoes["state"] == "disabled"
    assert app_fake.entry_planilha_lote.configuracoes["state"] == "disabled"
    assert app_fake.button_planilha_lote.configuracoes["state"] == "disabled"
    assert app_fake.entry_relatorio_lote.configuracoes["state"] == "disabled"
    assert app_fake.button_relatorio_lote.configuracoes["state"] == "disabled"

    ui.AghuProfissionaisUnidadeCirurgicaApp._liberar_execucao(app_fake)

    assert app_fake.em_execucao is False
    assert app_fake.button_executar.configuracoes["state"] == "normal"
    assert app_fake.button_executar.configuracoes["text"] == "Executar cadastro"
    assert app_fake.segment_tipo_execucao.configuracoes["state"] == "normal"
    assert app_fake.entry_usuario_rede.configuracoes["state"] == "normal"
    assert app_fake.entry_senha.configuracoes["state"] == "normal"
    assert app_fake.option_ambiente.configuracoes["state"] == "normal"
    assert app_fake.checkbox_browser.configuracoes["state"] == "normal"
    assert app_fake.checkbox_console.configuracoes["state"] == "normal"
    assert (
        app_fake.checkboxes_unidades_funcionais[0].configuracoes["state"]
        == "normal"
    )
    assert (
        app_fake.linhas_profissionais_individual[0]["profissional"]
        .configuracoes["state"]
        == "normal"
    )
    assert app_fake.button_adicionar_usuario.configuracoes["state"] == "normal"


def test_iniciar_execucao_individual_inicia_thread_com_dados(app_fake, monkeypatch):
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    app_fake.entry_usuario_rede.valor = "usuario"
    app_fake.entry_senha.valor = "senha"
    app_fake.linhas_profissionais_individual[0]["profissional"].valor = "Ana Silva"

    ui.AghuProfissionaisUnidadeCirurgicaApp.iniciar_execucao_individual(app_fake)

    thread = FakeThread.criadas[0]
    assert thread.iniciada is True
    assert thread.daemon is True
    assert thread.target == app_fake._executar_individual_thread
    assert thread.args == (
        "usuario",
        "senha",
        [
            CadastroProfissionalUnidadeEntrada(
                profissional="Ana Silva",
                unidade_funcional=UNIDADES_FUNCIONAIS[0],
                funcao=FUNCAO_MEDICO_RESIDENTE,
            )
        ],
        ui.AGHU_URL_HOMOLOGACAO,
        True,
        True,
    )
    assert app_fake.button_executar.configuracoes["state"] == "disabled"


def test_iniciar_execucao_individual_mostra_erro_sem_profissional(app_fake):
    app_fake.entry_usuario_rede.valor = "usuario"
    app_fake.entry_senha.valor = "senha"

    ui.AghuProfissionaisUnidadeCirurgicaApp.iniciar_execucao_individual(app_fake)

    assert app_fake.label_status.configuracoes["text"].startswith("Erro:")
    assert (
        "Informe ao menos um profissional"
        in app_fake.label_status.configuracoes["text"]
    )


def test_iniciar_execucao_lote_valida_planilha_obrigatoria(app_fake):
    app_fake.entry_usuario_rede.valor = "usuario"
    app_fake.entry_senha.valor = "senha"

    ui.AghuProfissionaisUnidadeCirurgicaApp.iniciar_execucao_lote(app_fake)

    assert app_fake.label_status.configuracoes["text"] == (
        "Erro: Informe a planilha .xlsx de lote."
    )


def test_selecionar_planilha_lote_nao_altera_campos_quando_cancelado(
    app_fake,
    monkeypatch,
):
    app_fake.entry_planilha_lote.valor = "antes.xlsx"
    app_fake.entry_relatorio_lote.valor = ""
    monkeypatch.setattr(ui.filedialog, "askopenfilename", lambda **kwargs: "")

    ui.AghuProfissionaisUnidadeCirurgicaApp.selecionar_planilha_lote(app_fake)

    assert app_fake.entry_planilha_lote.get() == "antes.xlsx"
    assert app_fake.entry_relatorio_lote.get() == ""


def test_selecionar_planilha_lote_nao_sobrescreve_relatorio_existente(
    app_fake,
    monkeypatch,
):
    app_fake.entry_relatorio_lote.valor = "relatorio_existente.xlsx"
    monkeypatch.setattr(
        ui.filedialog,
        "askopenfilename",
        lambda **kwargs: "profissionais.xlsx",
    )

    ui.AghuProfissionaisUnidadeCirurgicaApp.selecionar_planilha_lote(app_fake)

    assert app_fake.entry_planilha_lote.get() == "profissionais.xlsx"
    assert app_fake.entry_relatorio_lote.get() == "relatorio_existente.xlsx"


def test_iniciar_execucao_lote_valida_extensao_relatorio_xlsx(app_fake):
    app_fake.entry_usuario_rede.valor = "usuario"
    app_fake.entry_senha.valor = "senha"
    app_fake.entry_planilha_lote.valor = "profissionais.xlsx"
    app_fake.entry_relatorio_lote.valor = "saida.csv"

    ui.AghuProfissionaisUnidadeCirurgicaApp.iniciar_execucao_lote(app_fake)

    assert app_fake.label_status.configuracoes["text"] == (
        "Erro: O relatório de saída deve ser um arquivo .xlsx."
    )


def test_iniciar_execucao_lote_gera_relatorio_padrao_e_inicia_thread(
    app_fake,
    monkeypatch,
):
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    monkeypatch.setattr(
        ui,
        "caminho_relatorio_padrao",
        lambda base="": "relatorio.xlsx",
    )
    app_fake.entry_usuario_rede.valor = "usuario"
    app_fake.entry_senha.valor = "senha"
    app_fake.entry_planilha_lote.valor = "profissionais.xlsx"

    ui.AghuProfissionaisUnidadeCirurgicaApp.iniciar_execucao_lote(app_fake)

    thread = FakeThread.criadas[0]
    assert thread.iniciada is True
    assert app_fake.entry_relatorio_lote.get() == "relatorio.xlsx"
    assert thread.args == (
        "usuario",
        "senha",
        "profissionais.xlsx",
        "relatorio.xlsx",
        ui.AGHU_URL_HOMOLOGACAO,
        True,
        True,
    )


def test_executar_com_playwright_cria_contexto_e_fecha_browser(app_fake, monkeypatch):
    fake_playwright = FakeSyncPlaywright()
    monkeypatch.setattr(ui, "sync_playwright", lambda: fake_playwright)

    retorno = ui.AghuProfissionaisUnidadeCirurgicaApp._executar_com_playwright(
        app_fake,
        False,
        lambda context, page: (context, page),
    )

    browser = fake_playwright.chromium.browser
    contexto = browser.contextos[0]

    assert fake_playwright.chromium.launch_kwargs == {
        "headless": True,
        "slow_mo": 0,
    }
    assert contexto.kwargs == {"ignore_https_errors": True}
    assert retorno == (contexto, contexto.pages[0])
    assert browser.fechado is True


def test_executar_com_playwright_usa_slow_mo_com_navegador_visivel(
    app_fake,
    monkeypatch,
):
    fake_playwright = FakeSyncPlaywright()
    monkeypatch.setattr(ui, "sync_playwright", lambda: fake_playwright)

    ui.AghuProfissionaisUnidadeCirurgicaApp._executar_com_playwright(
        app_fake,
        True,
        lambda context, page: (context, page),
    )

    assert fake_playwright.chromium.launch_kwargs == {
        "headless": False,
        "slow_mo": 500,
    }


def test_resumir_resultados_conta_status_conhecidos(app_fake):
    resultados = [
        ResultadoCadastroProfissional("A", "U", "F", STATUS_CRIADO, "ok"),
        ResultadoCadastroProfissional("B", "U", "F", STATUS_MANTIDO, "ok"),
        ResultadoCadastroProfissional("C", "U", "F", STATUS_CONFERIR_MANUAL, "ok"),
        ResultadoCadastroProfissional("D", "U", "F", STATUS_IGNORADO, "ok"),
        ResultadoCadastroProfissional("E", "U", "F", STATUS_ERRO, "ok"),
    ]

    resumo = ui.AghuProfissionaisUnidadeCirurgicaApp._resumir_resultados(
        app_fake,
        resultados,
    )

    assert "Total: 5." in resumo
    assert "Criados: 1." in resumo
    assert "Mantidos: 1." in resumo
    assert "Conferir manualmente: 1." in resumo
    assert "Ignorados: 1." in resumo
    assert "Erros: 1." in resumo


def test_executar_individual_thread_agenda_finalizacao(app_fake, monkeypatch):
    resultado = ResultadoCadastroProfissional(
        profissional="Ana",
        unidade_funcional=UNIDADES_FUNCIONAIS[0],
        funcao=FUNCAO_MEDICO_RESIDENTE,
        status=STATUS_CRIADO,
        detalhes="OK",
    )
    chamadas = []
    capturados = {}
    app_fake.after = lambda delay, func, *args: chamadas.append((delay, func, args))

    def executar_fake(**kwargs):
        capturados.update(kwargs)
        return [resultado]

    monkeypatch.setattr(ui, "executar_cadastros_profissionais", executar_fake)
    monkeypatch.setattr(
        ui.AghuProfissionaisUnidadeCirurgicaApp,
        "_executar_com_playwright",
        lambda self, mostrar_browser, acao: acao("context", "page"),
    )
    cadastro = CadastroProfissionalUnidadeEntrada(
        profissional="Ana",
        unidade_funcional=UNIDADES_FUNCIONAIS[0],
    )

    ui.AghuProfissionaisUnidadeCirurgicaApp._executar_individual_thread(
        app_fake,
        "usuario",
        "senha",
        [cadastro],
        "url",
        False,
        True,
    )

    assert chamadas[0] == (
        0,
        app_fake._finalizar_execucao,
        (
            "Execução unitária concluída. Total processado: 1. "
            "Criados: 1. Mantidos: 0. Funcionários não encontrados: 0. "
            "Conferir manualmente: 0. Ignorados: 0. Erros: 0.",
            "green",
        ),
    )
    assert capturados["cadastros"] == [cadastro]
    assert capturados["context"] == "context"
    assert capturados["page"] == "page"
    assert capturados["url_aghu"] == "url"
    assert capturados["mostrar_console"] is True
    assert capturados["diretorio_logs"] == ui.LOGS_DIR


def test_executar_individual_thread_encerra_com_mensagem_clara_para_pessoa_unica(
    app_fake,
    monkeypatch,
):
    resultados = [
        ResultadoCadastroProfissional(
            profissional="Ana",
            unidade_funcional=UNIDADES_FUNCIONAIS[0],
            funcao=FUNCAO_MEDICO_RESIDENTE,
            status=STATUS_FUNCIONARIO_NAO_ENCONTRADO,
            detalhes="Funcionário não encontrado.",
        ),
        ResultadoCadastroProfissional(
            profissional="Ana",
            unidade_funcional=UNIDADES_FUNCIONAIS[1],
            funcao=FUNCAO_MEDICO_RESIDENTE,
            status=STATUS_FUNCIONARIO_NAO_ENCONTRADO,
            detalhes="Funcionário não encontrado (ja confirmado anteriormente).",
        ),
    ]
    chamadas = []
    app_fake.after = lambda delay, func, *args: chamadas.append((delay, func, args))
    monkeypatch.setattr(ui, "executar_cadastros_profissionais", lambda **kwargs: resultados)
    monkeypatch.setattr(
        ui.AghuProfissionaisUnidadeCirurgicaApp,
        "_executar_com_playwright",
        lambda self, mostrar_browser, acao: acao("context", "page"),
    )
    cadastros = [
        CadastroProfissionalUnidadeEntrada(
            profissional="Ana",
            unidade_funcional=UNIDADES_FUNCIONAIS[0],
        ),
        CadastroProfissionalUnidadeEntrada(
            profissional="Ana",
            unidade_funcional=UNIDADES_FUNCIONAIS[1],
        ),
    ]

    ui.AghuProfissionaisUnidadeCirurgicaApp._executar_individual_thread(
        app_fake,
        "usuario",
        "senha",
        cadastros,
        "url",
        False,
        True,
    )

    mensagem, cor = chamadas[0][2]
    assert mensagem == (
        'Execução encerrada: profissional "Ana" não encontrado no AGHUX. '
        "Verifique o nome informado."
    )
    assert cor == "red"


def test_executar_lote_thread_finaliza_amarelo_com_funcionario_nao_encontrado_ou_ignorado(
    app_fake,
    monkeypatch,
):
    resultados = [
        ResultadoCadastroProfissional(
            "Ana",
            "U",
            "F",
            STATUS_FUNCIONARIO_NAO_ENCONTRADO,
            "nao encontrado",
        ),
        ResultadoCadastroProfissional("Bia", "U", "F", STATUS_IGNORADO, "ignorado"),
    ]
    chamadas = []
    capturados = {}
    app_fake.after = lambda delay, func, *args: chamadas.append((delay, func, args))
    monkeypatch.setattr(
        ui.AghuProfissionaisUnidadeCirurgicaApp,
        "_executar_com_playwright",
        lambda self, mostrar_browser, acao: acao("context", "page"),
    )
    monkeypatch.setattr(
        ui,
        "executar_cadastro_lote",
        lambda **kwargs: (capturados.update(kwargs) or (resultados, "relatorio.xlsx")),
    )

    ui.AghuProfissionaisUnidadeCirurgicaApp._executar_lote_thread(
        app_fake,
        "usuario",
        "senha",
        "profissionais.xlsx",
        "relatorio.xlsx",
        "url",
        True,
        True,
    )

    assert chamadas[0][0] == 0
    assert chamadas[0][1] == app_fake._finalizar_execucao
    mensagem, cor = chamadas[0][2]
    assert "Funcionários não encontrados: 1." in mensagem
    assert "Ignorados: 1." in mensagem
    assert "Relatório: relatorio.xlsx" in mensagem
    assert cor == "yellow"
    assert capturados["context"] == "context"
    assert capturados["page"] == "page"
