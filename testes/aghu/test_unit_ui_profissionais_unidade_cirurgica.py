import pytest

import ui_profissionais_unidade_cirurgica as ui
from profissionais_unidade_cirurgica_aghu import (
    CadastroProfissionalUnidadeEntrada,
    ResultadoCadastroProfissional,
    STATUS_CONFERIR_MANUAL,
    STATUS_CRIADO,
    STATUS_ERRO,
    STATUS_IGNORADO,
    STATUS_MANTIDO,
    UNIDADES_FUNCIONAIS,
    FUNCAO_MEDICO_RESIDENTE,
)


class FakeEntry:
    def __init__(self, valor=""):
        self.valor = valor

    def get(self):
        return self.valor

    def delete(self, inicio, fim):
        self.valor = ""

    def insert(self, indice, valor):
        self.valor = valor


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

    def grid(self, **kwargs):
        self.visivel = True
        self.grid_args = kwargs

    def grid_remove(self):
        self.visivel = False


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
    app.var_unidade_funcional = FakeStringVar(UNIDADES_FUNCIONAIS[0])
    app.var_funcao = FakeStringVar(FUNCAO_MEDICO_RESIDENTE)
    app.entry_usuario_rede = FakeEntry()
    app.entry_senha = FakeEntry()
    app.entry_profissional = FakeEntry()
    app.entry_planilha_lote = FakeEntry()
    app.entry_relatorio_lote = FakeEntry()
    app.button_executar = FakeWidget()
    app.segment_tipo_execucao = FakeWidget()
    app.checkbox_browser = FakeWidget()
    app.checkbox_console = FakeWidget()
    app.option_ambiente = FakeWidget()
    app.option_unidade_funcional = FakeWidget()
    app.option_funcao = FakeWidget()
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


def test_cadastro_individual_coleta_profissional_unidade_e_funcao(app_fake):
    app_fake.entry_profissional.valor = "Ana Silva"
    app_fake.var_unidade_funcional.set(UNIDADES_FUNCIONAIS[1])

    cadastro = ui.AghuProfissionaisUnidadeCirurgicaApp._cadastro_individual(app_fake)

    assert cadastro == CadastroProfissionalUnidadeEntrada(
        profissional="Ana Silva",
        unidade_funcional=UNIDADES_FUNCIONAIS[1],
        funcao=FUNCAO_MEDICO_RESIDENTE,
    )


def test_bloquear_e_liberar_execucao_alteram_estados(app_fake):
    ui.AghuProfissionaisUnidadeCirurgicaApp._bloquear_execucao(
        app_fake,
        "Executando...",
    )

    assert app_fake.em_execucao is True
    assert app_fake.button_executar.configuracoes["state"] == "disabled"
    assert app_fake.option_unidade_funcional.configuracoes["state"] == "disabled"

    ui.AghuProfissionaisUnidadeCirurgicaApp._liberar_execucao(app_fake)

    assert app_fake.em_execucao is False
    assert app_fake.button_executar.configuracoes["state"] == "normal"
    assert app_fake.button_executar.configuracoes["text"] == "Executar cadastro"
    assert app_fake.option_unidade_funcional.configuracoes["state"] == "normal"


def test_iniciar_execucao_despacha_conforme_tipo(app_fake, monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        ui.AghuProfissionaisUnidadeCirurgicaApp,
        "iniciar_execucao_individual",
        lambda self: chamadas.append("individual"),
    )
    monkeypatch.setattr(
        ui.AghuProfissionaisUnidadeCirurgicaApp,
        "iniciar_execucao_lote",
        lambda self: chamadas.append("lote"),
    )

    app_fake.var_tipo_execucao.set(ui.TIPO_INDIVIDUAL)
    ui.AghuProfissionaisUnidadeCirurgicaApp.iniciar_execucao(app_fake)
    app_fake.var_tipo_execucao.set(ui.TIPO_LOTE)
    ui.AghuProfissionaisUnidadeCirurgicaApp.iniciar_execucao(app_fake)

    assert chamadas == ["individual", "lote"]


def test_iniciar_execucao_individual_inicia_thread_com_dados(app_fake, monkeypatch):
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    app_fake.entry_usuario_rede.valor = "usuario"
    app_fake.entry_senha.valor = "senha"
    app_fake.entry_profissional.valor = "Ana Silva"

    ui.AghuProfissionaisUnidadeCirurgicaApp.iniciar_execucao_individual(app_fake)

    thread = FakeThread.criadas[0]
    assert thread.iniciada is True
    assert thread.daemon is True
    assert thread.target == app_fake._executar_individual_thread
    assert thread.args == (
        "usuario",
        "senha",
        CadastroProfissionalUnidadeEntrada(
            profissional="Ana Silva",
            unidade_funcional=UNIDADES_FUNCIONAIS[0],
            funcao=FUNCAO_MEDICO_RESIDENTE,
        ),
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
    assert "Profissional em branco" in app_fake.label_status.configuracoes["text"]


def test_iniciar_execucao_lote_valida_planilha_obrigatoria(app_fake):
    app_fake.entry_usuario_rede.valor = "usuario"
    app_fake.entry_senha.valor = "senha"

    ui.AghuProfissionaisUnidadeCirurgicaApp.iniciar_execucao_lote(app_fake)

    assert app_fake.label_status.configuracoes["text"] == (
        "Erro: Informe a planilha .xlsx de lote."
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
        return resultado

    monkeypatch.setattr(ui, "executar_cadastro_individual", executar_fake)
    cadastro = CadastroProfissionalUnidadeEntrada(
        profissional="Ana",
        unidade_funcional=UNIDADES_FUNCIONAIS[0],
    )

    ui.AghuProfissionaisUnidadeCirurgicaApp._executar_individual_thread(
        app_fake,
        "usuario",
        "senha",
        cadastro,
        "url",
        False,
        True,
    )

    assert chamadas[0] == (
        0,
        app_fake._finalizar_execucao,
        ("Ana: criado - OK", "green"),
    )
    assert capturados["cadastro"] == cadastro
    assert capturados["url_aghu"] == "url"
    assert capturados["mostrar_browser"] is False
    assert capturados["mostrar_console"] is True
    assert capturados["diretorio_logs"] == ui.LOGS_DIR
