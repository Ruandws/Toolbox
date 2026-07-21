import pytest

import ui_consultor as ui


class FakeEntry:
    def __init__(self, valor=""):
        self.valor = valor
        self.configuracoes = {}

    def get(self):
        return self.valor

    def delete(self, _inicio, _fim):
        self.valor = ""

    def insert(self, indice, valor):
        if indice == 0:
            self.valor = valor + self.valor
            return

        self.valor = self.valor[:indice] + valor + self.valor[indice:]

    def configure(self, **kwargs):
        self.configuracoes.update(kwargs)


class FakeWidget:
    def __init__(self):
        self.configuracoes = {}
        self.visivel = False

    def configure(self, **kwargs):
        self.configuracoes.update(kwargs)

    def grid(self, **_kwargs):
        self.visivel = True

    def grid_remove(self):
        self.visivel = False


class FakeTextbox(FakeWidget):
    def __init__(self):
        super().__init__()
        self.valor = ""

    def insert(self, indice, valor):
        self.valor += valor

    def delete(self, inicio, fim):
        self.valor = ""


class FakeSegment(FakeWidget):
    def __init__(self):
        super().__init__()
        self._buttons_dict = {
            ui.TIPO_INDIVIDUAL: FakeWidget(),
            ui.TIPO_LOTE: FakeWidget(),
        }


class FakeVar:
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


def criar_app_fake():
    app = object.__new__(ui.ConsultorSTI)
    app.em_execucao = False
    app.collect_email_var = FakeVar(False)
    app.var_browser = FakeVar(True)
    app.var_show_terminal_logs = FakeVar(False)
    app.var_tipo_execucao = FakeVar(ui.TIPO_INDIVIDUAL)
    app.entry_login = FakeEntry()
    app.entry_password = FakeEntry()
    app.linhas_usuarios_individual = [{"valor": FakeEntry(), "frame": FakeWidget(), "remover": FakeWidget()}]
    app.button_adicionar = FakeWidget()
    app.label_limite = FakeWidget()
    app.textbox_resultado = FakeTextbox()
    app.entry_spreadsheet = FakeEntry()
    app.label_cabecalho_pesquisa = FakeWidget()
    app.entry_report_dir = FakeEntry()
    app.combo_search_type = FakeEntry("CPF")
    app.checkbox_collect_email = FakeWidget()
    app.checkbox_browser = FakeWidget()
    app.switch_terminal_logs = FakeWidget()
    app.button_run = FakeWidget()
    app.segment_tipo_execucao = FakeSegment()
    app.button_select_spreadsheet = FakeWidget()
    app.button_select_report_dir = FakeWidget()
    app.label_status = FakeWidget()
    app.widgets_individuais = [FakeWidget(), FakeWidget()]
    app.widgets_lote = [FakeWidget(), FakeWidget(), FakeWidget()]
    return app


@pytest.fixture(autouse=True)
def limpar_threads_fake():
    FakeThread.criadas = []


def test_atualizar_tipo_execucao_alterna_visibilidade_e_contraste():
    app = criar_app_fake()

    ui.ConsultorSTI._atualizar_tipo_execucao(app, ui.TIPO_LOTE)

    assert all(not widget.visivel for widget in app.widgets_individuais)
    assert all(widget.visivel for widget in app.widgets_lote)
    assert (
        app.segment_tipo_execucao._buttons_dict[ui.TIPO_LOTE]
        .configuracoes["text_color"]
        == "white"
    )

    ui.ConsultorSTI._atualizar_tipo_execucao(app, ui.TIPO_INDIVIDUAL)

    assert all(widget.visivel for widget in app.widgets_individuais)
    assert all(not widget.visivel for widget in app.widgets_lote)
    assert (
        app.segment_tipo_execucao._buttons_dict[ui.TIPO_INDIVIDUAL]
        .configuracoes["text_color"]
        == "white"
    )


def test_atualizar_visual_segmented_button_ignora_segmento_ausente():
    app = criar_app_fake()
    del app.segment_tipo_execucao

    ui.ConsultorSTI._atualizar_visual_segmented_button(app, ui.TIPO_INDIVIDUAL)


def test_on_search_type_change_atualiza_placeholder():
    app = criar_app_fake()

    ui.ConsultorSTI.on_search_type_change(app, "Nome Completo")

    assert app.linhas_usuarios_individual[0]["valor"].configuracoes["placeholder_text"] == (
        "Digite o nome completo sem números"
    )

    ui.ConsultorSTI.on_search_type_change(app, "CPF")

    assert app.linhas_usuarios_individual[0]["valor"].configuracoes["placeholder_text"] == (
        "Digite CPF com ou sem pontuação"
    )


def test_bloquear_e_liberar_execucao_alteram_controles():
    app = criar_app_fake()

    ui.ConsultorSTI._bloquear_execucao(app)

    assert app.em_execucao is True
    assert app.button_run.configuracoes["state"] == "disabled"
    assert app.button_run.configuracoes["text"] == "Executando..."
    assert app.segment_tipo_execucao.configuracoes["state"] == "disabled"
    assert app.entry_password.configuracoes["state"] == "disabled"
    assert app.checkbox_collect_email.configuracoes["state"] == "disabled"
    assert app.checkbox_browser.configuracoes["state"] == "disabled"
    assert app.switch_terminal_logs.configuracoes["state"] == "disabled"
    assert app.button_select_report_dir.configuracoes["state"] == "disabled"
    assert app.linhas_usuarios_individual[0]["valor"].configuracoes["state"] == "disabled"
    assert app.button_adicionar.configuracoes["state"] == "disabled"

    ui.ConsultorSTI._liberar_execucao(app)

    assert app.em_execucao is False
    assert app.button_run.configuracoes["state"] == "normal"
    assert app.button_run.configuracoes["text"] == "Executar Automação"
    assert app.segment_tipo_execucao.configuracoes["state"] == "normal"
    assert app.entry_password.configuracoes["state"] == "normal"
    assert app.checkbox_collect_email.configuracoes["state"] == "normal"
    assert app.checkbox_browser.configuracoes["state"] == "normal"
    assert app.switch_terminal_logs.configuracoes["state"] == "normal"
    assert app.button_select_report_dir.configuracoes["state"] == "normal"
    assert app.linhas_usuarios_individual[0]["valor"].configuracoes["state"] == "normal"
    assert app.button_adicionar.configuracoes["state"] == "normal"


def test_start_automation_nao_faz_nada_se_ja_em_execucao(monkeypatch):
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    app = criar_app_fake()
    app.em_execucao = True

    ui.ConsultorSTI.start_automation(app)

    assert FakeThread.criadas == []


def test_start_automation_valida_credenciais_obrigatorias(monkeypatch):
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    app = criar_app_fake()

    ui.ConsultorSTI.start_automation(app)

    assert FakeThread.criadas == []
    assert app.label_status.configuracoes == {
        "text": "Erro: Preencha login e senha.",
        "text_color": "red",
    }


def test_start_automation_unitaria_valida_valor_de_pesquisa(monkeypatch):
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    app = criar_app_fake()
    app.entry_login.valor = "tecnico"
    app.entry_password.valor = "senha"
    app.linhas_usuarios_individual[0]["valor"].valor = ""

    ui.ConsultorSTI.start_automation(app)

    assert FakeThread.criadas == []
    assert app.label_status.configuracoes == {
        "text": "Erro: Preencha ao menos um valor de pesquisa.",
        "text_color": "red",
    }


def test_start_automation_unitaria_exibe_erro_de_preparacao(monkeypatch):
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    monkeypatch.setattr(
        ui,
        "prepare_search_value",
        lambda _tipo, _valor: (_ for _ in ()).throw(ValueError("valor invalido")),
    )
    app = criar_app_fake()
    app.entry_login.valor = "tecnico"
    app.entry_password.valor = "senha"
    app.linhas_usuarios_individual[0]["valor"].valor = "abc"

    ui.ConsultorSTI.start_automation(app)

    assert FakeThread.criadas == []
    assert app.label_status.configuracoes == {
        "text": "Erro em 'abc': valor invalido",
        "text_color": "red",
    }


def test_start_automation_unitaria_inicia_thread_com_valor_preparado(monkeypatch):
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    monkeypatch.setattr(ui, "prepare_search_value", lambda _tipo, _valor: "52998224725")
    monkeypatch.setattr(ui, "set_terminal_visibility", lambda _show: None)
    app = criar_app_fake()
    app.entry_login.valor = " tecnico "
    app.entry_password.valor = " senha "
    app.linhas_usuarios_individual[0]["valor"].valor = "529.982.247-25"
    app.collect_email_var.set(True)

    ui.ConsultorSTI.start_automation(app)

    thread = FakeThread.criadas[0]
    assert thread.iniciada is True
    assert thread.daemon is True
    assert thread.target == app.run_playwright_task
    assert thread.args == (
        "multi",
        "tecnico",
        " senha ",
        "CPF",
        [ui.UsuarioConsulta(login="52998224725")],
        True,
        False,
        True,
    )
    assert app.em_execucao is True
    assert app.label_status.configuracoes == {
        "text": "Iniciando automação unitária...",
        "text_color": "blue",
    }


def test_start_automation_unitaria_propaga_modo_headless(monkeypatch):
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    monkeypatch.setattr(ui, "prepare_search_value", lambda _tipo, _valor: "52998224725")
    monkeypatch.setattr(ui, "set_terminal_visibility", lambda _show: None)
    app = criar_app_fake()
    app.entry_login.valor = "tecnico"
    app.entry_password.valor = "senha"
    app.linhas_usuarios_individual[0]["valor"].valor = "529.982.247-25"
    app.var_browser.set(False)
    app.var_show_terminal_logs.set(True)

    ui.ConsultorSTI.start_automation(app)

    assert FakeThread.criadas[0].args == (
        "multi",
        "tecnico",
        "senha",
        "CPF",
        [ui.UsuarioConsulta(login="52998224725")],
        False,
        True,
        False,
    )


def test_start_automation_unitaria_headless_exige_terminal_logs(monkeypatch):
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    app = criar_app_fake()
    app.entry_login.valor = "tecnico"
    app.entry_password.valor = "senha"
    app.linhas_usuarios_individual[0]["valor"].valor = "529.982.247-25"
    app.var_browser.set(False)
    app.var_show_terminal_logs.set(False)

    ui.ConsultorSTI.start_automation(app)

    assert FakeThread.criadas == []
    assert app.label_status.configuracoes == {
        "text": (
            "Erro: Para executar em modo headless, habilite também "
            "terminal/logs de execução."
        ),
        "text_color": "red",
    }


def test_start_automation_lote_usa_tipo_explicito(monkeypatch):
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    monkeypatch.setattr(ui, "set_terminal_visibility", lambda _show: None)
    app = criar_app_fake()
    app.var_tipo_execucao.set(ui.TIPO_LOTE)
    app.entry_login.valor = "tecnico"
    app.entry_password.valor = "senha"
    app.entry_spreadsheet.valor = "C:/entrada.xlsx"
    app.entry_report_dir.valor = "C:/relatorios"

    ui.ConsultorSTI.start_automation(app)

    thread = FakeThread.criadas[0]
    assert thread.iniciada is True
    assert thread.args == (
        "batch",
        "tecnico",
        "senha",
        "CPF",
        "C:/entrada.xlsx",
        "C:/relatorios",
        False,
        False,
        True,
    )
    assert app.label_status.configuracoes == {
        "text": "Iniciando automação em lote...",
        "text_color": "blue",
    }


def test_start_automation_lote_propaga_modo_headless(monkeypatch):
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    monkeypatch.setattr(ui, "set_terminal_visibility", lambda _show: None)
    app = criar_app_fake()
    app.var_tipo_execucao.set(ui.TIPO_LOTE)
    app.var_browser.set(False)
    app.var_show_terminal_logs.set(True)
    app.entry_login.valor = "tecnico"
    app.entry_password.valor = "senha"
    app.entry_spreadsheet.valor = "C:/entrada.xlsx"
    app.entry_report_dir.valor = "C:/relatorios"

    ui.ConsultorSTI.start_automation(app)

    assert FakeThread.criadas[0].args == (
        "batch",
        "tecnico",
        "senha",
        "CPF",
        "C:/entrada.xlsx",
        "C:/relatorios",
        False,
        True,
        False,
    )


def test_start_automation_lote_headless_exige_terminal_logs(monkeypatch):
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    app = criar_app_fake()
    app.var_tipo_execucao.set(ui.TIPO_LOTE)
    app.var_browser.set(False)
    app.var_show_terminal_logs.set(False)
    app.entry_login.valor = "tecnico"
    app.entry_password.valor = "senha"
    app.entry_spreadsheet.valor = "C:/entrada.xlsx"
    app.entry_report_dir.valor = "C:/relatorios"

    ui.ConsultorSTI.start_automation(app)

    assert FakeThread.criadas == []
    assert app.label_status.configuracoes == {
        "text": (
            "Erro: Para executar em modo headless, habilite também "
            "terminal/logs de execução."
        ),
        "text_color": "red",
    }


def test_start_automation_lote_valida_planilha_e_relatorio(monkeypatch):
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    app = criar_app_fake()
    app.var_tipo_execucao.set(ui.TIPO_LOTE)
    app.entry_login.valor = "tecnico"
    app.entry_password.valor = "senha"

    ui.ConsultorSTI.start_automation(app)

    assert FakeThread.criadas == []
    assert app.label_status.configuracoes == {
        "text": "Erro: Para lote, informe planilha e pasta de relatório.",
        "text_color": "red",
    }


def test_run_playwright_task_agenda_finalizacao_unitaria_com_sucesso(monkeypatch):
    app = criar_app_fake()
    chamadas = []
    app.after = lambda delay, func, *args: chamadas.append((delay, func, args))
    monkeypatch.setattr(
        ui,
        "run_automation",
        lambda *args: ("Usuário encontrado", "green"),
    )

    ui.ConsultorSTI.run_playwright_task(app, "single", "arg")

    assert chamadas == [
        (0, app.finish_automation, ("Usuário encontrado", "green", "")),
    ]


def test_run_playwright_task_agenda_finalizacao_multi_com_sucesso(
    monkeypatch,
):
    app = criar_app_fake()
    chamadas = []
    app.after = lambda delay, func, *args: chamadas.append((delay, func, args))
    monkeypatch.setattr(
        ui,
        "run_multi_automation",
        lambda *args: ("Mais de um usuário encontrado", "orange", "detalhe_aqui"),
    )

    ui.ConsultorSTI.run_playwright_task(app, "multi", "arg")

    assert chamadas == [
        (0, app.finish_automation, ("Mais de um usuário encontrado", "orange", "detalhe_aqui")),
    ]


def test_run_playwright_task_agenda_finalizacao_lote_sem_resultado(monkeypatch):
    app = criar_app_fake()
    chamadas = []
    app.after = lambda delay, func, *args: chamadas.append((delay, func, args))
    monkeypatch.setattr(
        ui,
        "run_batch_automation",
        lambda *args: ("Nenhum usuário", "orange"),
    )

    ui.ConsultorSTI.run_playwright_task(app, "batch", "arg")

    assert chamadas == [
        (0, app.finish_automation, ("Nenhum usuário", "orange", "")),
    ]


def test_run_playwright_task_prefixa_mensagem_de_login_falho_com_erro(monkeypatch):
    app = criar_app_fake()
    chamadas = []
    app.after = lambda delay, func, *args: chamadas.append((delay, func, args))

    def falhar(*_args):
        raise RuntimeError("Login falhou: credenciais invalidas")

    monkeypatch.setattr(ui, "run_automation", falhar)

    ui.ConsultorSTI.run_playwright_task(app, "single", "arg")

    assert chamadas == [
        (0, app.finish_automation, ("Erro: Login falhou: credenciais invalidas", "red", "")),
    ]


def test_finish_automation_atualiza_status_e_libera_execucao():
    app = criar_app_fake()
    ui.ConsultorSTI._bloquear_execucao(app)

    ui.ConsultorSTI.finish_automation(app, "concluido", "green", "detalhe_aqui")

    assert app.label_status.configuracoes == {
        "text": "concluido",
        "text_color": "green",
    }
    assert app.em_execucao is False
