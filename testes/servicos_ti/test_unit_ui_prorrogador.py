import ui_prorrogador as ui


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
    app = object.__new__(ui.ProrrogadorSTI)
    app.em_execucao = False
    app.var_tipo_execucao = FakeVar(ui.TIPO_INDIVIDUAL)
    app.var_show_terminal_logs = FakeVar(False)
    app.var_browser = FakeVar(True)
    app.entry_login = FakeEntry()
    app.entry_password = FakeEntry()
    app.entry_date = FakeEntry()
    app.linhas_usuarios_individual = [
        {"valor": FakeEntry(), "frame": FakeWidget(), "remover": FakeWidget()}
    ]
    app.button_adicionar = FakeWidget()
    app.label_limite = FakeWidget()
    app.textbox_resultado = FakeTextbox()
    app.entry_spreadsheet = FakeEntry()
    app.entry_report_dir = FakeEntry()
    app.button_run = FakeWidget()
    app.segment_tipo_execucao = FakeSegment()
    app.button_select_spreadsheet = FakeWidget()
    app.button_select_report_dir = FakeWidget()
    app.checkbox_browser = FakeWidget()
    app.switch_terminal_logs = FakeWidget()
    app.label_status = FakeWidget()
    app.widgets_individuais = [FakeWidget(), FakeWidget()]
    app.widgets_lote = [FakeWidget(), FakeWidget(), FakeWidget()]
    return app


def test_atualizar_tipo_execucao_alterna_visibilidade_e_contraste():
    app = criar_app_fake()

    ui.ProrrogadorSTI._atualizar_tipo_execucao(app, ui.TIPO_LOTE)

    assert all(not widget.visivel for widget in app.widgets_individuais)
    assert all(widget.visivel for widget in app.widgets_lote)
    assert (
        app.segment_tipo_execucao._buttons_dict[ui.TIPO_LOTE]
        .configuracoes["text_color"]
        == "white"
    )

    ui.ProrrogadorSTI._atualizar_tipo_execucao(app, ui.TIPO_INDIVIDUAL)

    assert all(widget.visivel for widget in app.widgets_individuais)
    assert all(not widget.visivel for widget in app.widgets_lote)
    assert (
        app.segment_tipo_execucao._buttons_dict[ui.TIPO_INDIVIDUAL]
        .configuracoes["text_color"]
        == "white"
    )


def test_coletar_usuarios_retorna_valores_das_linhas():
    app = criar_app_fake()
    app.linhas_usuarios_individual.append(
        {"valor": FakeEntry(" outro.usuario "), "frame": FakeWidget(), "remover": FakeWidget()}
    )
    app.linhas_usuarios_individual[0]["valor"].valor = " usuario.alvo "

    resultado = ui.ProrrogadorSTI.coletar_usuarios(app)

    assert resultado == ["usuario.alvo", "outro.usuario"]


def test_bloquear_e_liberar_execucao_alteram_controles():
    app = criar_app_fake()

    ui.ProrrogadorSTI._bloquear_execucao(app)

    assert app.em_execucao is True
    assert app.button_run.configuracoes["state"] == "disabled"
    assert app.segment_tipo_execucao.configuracoes["state"] == "disabled"
    assert app.entry_password.configuracoes["state"] == "disabled"
    assert app.checkbox_browser.configuracoes["state"] == "disabled"
    assert app.switch_terminal_logs.configuracoes["state"] == "disabled"
    assert app.linhas_usuarios_individual[0]["valor"].configuracoes["state"] == "disabled"
    assert app.button_adicionar.configuracoes["state"] == "disabled"

    ui.ProrrogadorSTI._liberar_execucao(app)

    assert app.em_execucao is False
    assert app.button_run.configuracoes["state"] == "normal"
    assert app.button_run.configuracoes["text"].startswith("Executar")
    assert app.segment_tipo_execucao.configuracoes["state"] == "normal"
    assert app.checkbox_browser.configuracoes["state"] == "normal"
    assert app.switch_terminal_logs.configuracoes["state"] == "normal"
    assert app.linhas_usuarios_individual[0]["valor"].configuracoes["state"] == "normal"
    assert app.button_adicionar.configuracoes["state"] == "normal"


def test_start_automation_rejeita_senha_apenas_com_espacos(monkeypatch):
    FakeThread.criadas.clear()
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    app = criar_app_fake()
    app.entry_login.valor = "tecnico"
    app.entry_password.valor = "   "
    app.entry_date.valor = "22/06/2026"
    app.linhas_usuarios_individual[0]["valor"].valor = "usuario"

    ui.ProrrogadorSTI.start_automation(app)

    assert FakeThread.criadas == []
    assert app.label_status.configuracoes["text"] == (
        "Erro: Preencha login e senha."
    )
    assert app.label_status.configuracoes["text_color"] == "red"


def test_start_automation_rejeita_data_vazia(monkeypatch):
    FakeThread.criadas.clear()
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    app = criar_app_fake()
    app.entry_login.valor = "tecnico"
    app.entry_password.valor = "senha"
    app.entry_date.valor = ""
    app.linhas_usuarios_individual[0]["valor"].valor = "usuario"

    ui.ProrrogadorSTI.start_automation(app)

    assert FakeThread.criadas == []
    assert app.label_status.configuracoes["text"] == (
        "Erro: Preencha a nova data."
    )
    assert app.label_status.configuracoes["text_color"] == "red"


def test_start_automation_unitaria_rejeita_lista_vazia(monkeypatch):
    FakeThread.criadas.clear()
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    app = criar_app_fake()
    app.entry_login.valor = "tecnico"
    app.entry_password.valor = "senha"
    app.entry_date.valor = "22/06/2026"
    app.linhas_usuarios_individual[0]["valor"].valor = ""

    ui.ProrrogadorSTI.start_automation(app)

    assert FakeThread.criadas == []
    assert app.label_status.configuracoes["text"] == (
        "Erro: Informe ao menos um usuário alvo."
    )
    assert app.label_status.configuracoes["text_color"] == "red"


def test_start_automation_unitaria_exibe_erro_de_preparacao(monkeypatch):
    FakeThread.criadas.clear()
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    monkeypatch.setattr(
        ui,
        "prepare_user_value",
        lambda _valor: (_ for _ in ()).throw(ValueError("valor invalido")),
    )
    app = criar_app_fake()
    app.entry_login.valor = "tecnico"
    app.entry_password.valor = "senha"
    app.entry_date.valor = "22/06/2026"
    app.linhas_usuarios_individual[0]["valor"].valor = "usuario invalido"

    ui.ProrrogadorSTI.start_automation(app)

    assert FakeThread.criadas == []
    assert app.label_status.configuracoes["text"] == (
        "Erro em 'usuario invalido': valor invalido"
    )
    assert app.label_status.configuracoes["text_color"] == "red"


def test_start_automation_unitaria_inicia_thread_com_dados(monkeypatch):
    FakeThread.criadas.clear()
    chamadas_terminal = []
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    monkeypatch.setattr(ui, "set_terminal_visibility", chamadas_terminal.append)
    app = criar_app_fake()
    app.entry_login.valor = " tecnico "
    app.entry_password.valor = " senha "
    app.entry_date.valor = "22062026"
    app.linhas_usuarios_individual[0]["valor"].valor = " usuario.alvo "

    ui.ProrrogadorSTI.start_automation(app)

    thread = FakeThread.criadas[0]
    assert thread.iniciada is True
    assert thread.daemon is True
    assert thread.target == app.run_playwright_task
    assert thread.args == (
        "multi",
        "tecnico",
        " senha ",
        "22/06/2026",
        ["usuario.alvo"],
        False,
        True,
    )
    assert chamadas_terminal == [False]
    assert app.em_execucao is True
    assert app.button_run.configuracoes["state"] == "disabled"


def test_start_automation_unitaria_ignora_linhas_vazias_e_mantem_ordem(monkeypatch):
    FakeThread.criadas.clear()
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    monkeypatch.setattr(ui, "set_terminal_visibility", lambda _show: None)
    app = criar_app_fake()
    app.entry_login.valor = "tecnico"
    app.entry_password.valor = "senha"
    app.entry_date.valor = "22/06/2026"
    app.linhas_usuarios_individual[0]["valor"].valor = "usuario.um"
    app.linhas_usuarios_individual.append(
        {"valor": FakeEntry(""), "frame": FakeWidget(), "remover": FakeWidget()}
    )
    app.linhas_usuarios_individual.append(
        {"valor": FakeEntry("usuario.dois"), "frame": FakeWidget(), "remover": FakeWidget()}
    )

    ui.ProrrogadorSTI.start_automation(app)

    assert FakeThread.criadas[0].args == (
        "multi",
        "tecnico",
        "senha",
        "22/06/2026",
        ["usuario.um", "usuario.dois"],
        False,
        True,
    )


def test_start_automation_lote_usa_tipo_explicito(monkeypatch):
    FakeThread.criadas.clear()
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    monkeypatch.setattr(ui, "set_terminal_visibility", lambda _show: None)
    app = criar_app_fake()
    app.var_tipo_execucao.set(ui.TIPO_LOTE)
    app.entry_login.valor = "tecnico"
    app.entry_password.valor = "senha"
    app.entry_date.valor = "22/06/2026"
    app.entry_spreadsheet.valor = "C:/entrada.xlsx"
    app.entry_report_dir.valor = "C:/relatorios"

    ui.ProrrogadorSTI.start_automation(app)

    thread = FakeThread.criadas[0]
    assert thread.iniciada is True
    assert thread.args == (
        "batch",
        "tecnico",
        "senha",
        "C:/entrada.xlsx",
        "C:/relatorios",
        "22/06/2026",
        False,
        True,
    )
    assert app.label_status.configuracoes["text"].startswith("Iniciando")


def test_start_automation_headless_exige_terminal_logs(monkeypatch):
    FakeThread.criadas.clear()
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    app = criar_app_fake()
    app.var_browser.set(False)
    app.var_show_terminal_logs.set(False)
    app.entry_login.valor = "tecnico"
    app.entry_password.valor = "senha"
    app.entry_date.valor = "22/06/2026"
    app.linhas_usuarios_individual[0]["valor"].valor = "usuario"

    ui.ProrrogadorSTI.start_automation(app)

    assert FakeThread.criadas == []
    assert app.label_status.configuracoes["text"] == (
        "Erro: Para executar em modo headless, habilite também "
        "terminal/logs de execução."
    )
    assert app.label_status.configuracoes["text_color"] == "red"


def test_run_playwright_task_agenda_finalizacao_multi_com_sucesso(monkeypatch):
    app = criar_app_fake()
    chamadas = []
    app.after = lambda delay, func, *args: chamadas.append((delay, func, args))
    monkeypatch.setattr(
        ui,
        "run_multi_automation",
        lambda *args: ("Unitária concluída. Total: 2.", "orange", "detalhe_aqui"),
    )

    ui.ProrrogadorSTI.run_playwright_task(app, "multi", "arg")

    assert chamadas == [
        (0, app.finish_automation, ("Unitária concluída. Total: 2.", "orange", "detalhe_aqui")),
    ]


def test_run_playwright_task_agenda_finalizacao_lote_sem_resultado(monkeypatch):
    app = criar_app_fake()
    chamadas = []
    app.after = lambda delay, func, *args: chamadas.append((delay, func, args))
    monkeypatch.setattr(
        ui,
        "run_batch_automation",
        lambda *args: "Lote finalizado. Total: 0.",
    )

    ui.ProrrogadorSTI.run_playwright_task(app, "batch", "arg")

    assert chamadas == [
        (0, app.finish_automation, ("Lote finalizado. Total: 0.", "green", "")),
    ]


def test_run_playwright_task_prefixa_mensagem_de_login_falho_com_erro(monkeypatch):
    app = criar_app_fake()
    chamadas = []
    app.after = lambda delay, func, *args: chamadas.append((delay, func, args))

    def falhar(*_args):
        raise RuntimeError("Login falhou: credenciais invalidas")

    monkeypatch.setattr(ui, "run_multi_automation", falhar)

    ui.ProrrogadorSTI.run_playwright_task(app, "multi", "arg")

    assert chamadas == [
        (0, app.finish_automation, ("Erro: Login falhou: credenciais invalidas", "red", "")),
    ]


def test_finish_automation_atualiza_status_e_libera_execucao():
    app = criar_app_fake()
    ui.ProrrogadorSTI._bloquear_execucao(app)

    ui.ProrrogadorSTI.finish_automation(app, "concluido", "green", "detalhe_aqui")

    assert app.label_status.configuracoes["text"] == "concluido"
    assert app.label_status.configuracoes["text_color"] == "green"
    assert app.em_execucao is False
    assert app.textbox_resultado.valor == "detalhe_aqui"
    assert app.textbox_resultado.visivel is True


def test_mostrar_resultado_detalhado_oculta_quando_vazio():
    app = criar_app_fake()
    app.textbox_resultado.visivel = True

    ui.ProrrogadorSTI.mostrar_resultado_detalhado(app, "")

    assert app.textbox_resultado.visivel is False
