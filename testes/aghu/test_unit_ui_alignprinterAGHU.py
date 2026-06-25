import pytest

import ui_alignprinterAGHU as ui


class FakeEntry:
    def __init__(self, valor=""):
        self.valor = valor

    def get(self):
        return self.valor

    def delete(self, inicio, fim):
        self.valor = ""

    def insert(self, indice, valor):
        if indice == 0:
            self.valor = valor + self.valor
            return
        self.valor = self.valor[:indice] + valor + self.valor[indice:]


class FakeWidget:
    def __init__(self):
        self.configuracoes = {}

    def configure(self, **kwargs):
        self.configuracoes.update(kwargs)


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


@pytest.fixture()
def app_fake():
    app = object.__new__(ui.AghuPrinterApp)
    app.entry_user = FakeEntry()
    app.entry_password = FakeEntry()
    app.entry_spreadsheet_in = FakeEntry()
    app.entry_report_dir = FakeEntry()
    app.var_console = FakeStringVar(True)
    app.var_browser = FakeStringVar(True)
    app.var_ambiente = FakeStringVar(ui.AMBIENTE_PRODUCAO)
    app.label_status = FakeWidget()
    app.button_run = FakeWidget()
    return app


def test_select_report_directory_preenche_caminho(app_fake, monkeypatch, tmp_path):
    caminho = tmp_path / "saida"
    monkeypatch.setattr(
        ui.filedialog,
        "askdirectory",
        lambda **kwargs: str(caminho),
    )

    ui.AghuPrinterApp.select_report_directory(app_fake)

    assert app_fake.entry_report_dir.get() == str(caminho)


def test_select_report_directory_nao_altera_campos_quando_cancelado(app_fake, monkeypatch):
    app_fake.entry_report_dir.valor = "antes"
    monkeypatch.setattr(ui.filedialog, "askdirectory", lambda **kwargs: "")

    ui.AghuPrinterApp.select_report_directory(app_fake)

    assert app_fake.entry_report_dir.get() == "antes"


def test_select_input_spreadsheet_preenche_planilha_e_pasta_padrao(
    app_fake,
    monkeypatch,
    tmp_path,
):
    planilha = tmp_path / "entrada.xlsx"
    planilha.touch()
    monkeypatch.setattr(
        ui.filedialog,
        "askopenfilename",
        lambda **kwargs: str(planilha),
    )

    ui.AghuPrinterApp.select_input_spreadsheet(app_fake)

    assert app_fake.entry_spreadsheet_in.get() == str(planilha)
    assert app_fake.entry_report_dir.get() == str(tmp_path)


def test_select_input_spreadsheet_preserva_pasta_relatorio_ja_informada(
    app_fake,
    monkeypatch,
    tmp_path,
):
    planilha = tmp_path / "entrada.xlsx"
    planilha.touch()
    app_fake.entry_report_dir.valor = "C:/relatorios"
    monkeypatch.setattr(
        ui.filedialog,
        "askopenfilename",
        lambda **kwargs: str(planilha),
    )

    ui.AghuPrinterApp.select_input_spreadsheet(app_fake)

    assert app_fake.entry_spreadsheet_in.get() == str(planilha)
    assert app_fake.entry_report_dir.get() == "C:/relatorios"


def test_start_automation_inicia_thread_com_dados_da_tela(app_fake, monkeypatch, tmp_path):
    FakeThread.criadas = []
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)

    app_fake.entry_user.valor = "usuario"
    app_fake.entry_password.valor = "senha"

    planilha = tmp_path / "planilha.xlsx"
    planilha.touch()
    app_fake.entry_spreadsheet_in.valor = str(planilha)

    dir_relatorio = tmp_path / "relatorios"
    dir_relatorio.mkdir()
    app_fake.entry_report_dir.valor = str(dir_relatorio)

    ui.AghuPrinterApp.start_automation(app_fake)

    assert len(FakeThread.criadas) == 1
    thread = FakeThread.criadas[0]
    assert thread.iniciada is True
    assert thread.daemon is True
    assert thread.target == app_fake.run_playwright_task
    assert thread.args == (
        "usuario",
        "senha",
        True,
        True,
        str(planilha),
        str(dir_relatorio),
        ui.AGHU_URL,
    )
    assert app_fake.label_status.configuracoes["text"] == "Iniciando automação..."
    assert app_fake.button_run.configuracoes["state"] == "disabled"


def test_start_automation_valida_diretorio_relatorio_inexistente(app_fake, tmp_path):
    app_fake.entry_user.valor = "usuario"
    app_fake.entry_password.valor = "senha"

    planilha = tmp_path / "planilha.xlsx"
    planilha.touch()
    app_fake.entry_spreadsheet_in.valor = str(planilha)

    dir_relatorio = tmp_path / "diretorio_inexistente"
    app_fake.entry_report_dir.valor = str(dir_relatorio)

    ui.AghuPrinterApp.start_automation(app_fake)

    assert app_fake.label_status.configuracoes["text"].startswith("Erro: A pasta de relatorio nao existe:")
    assert app_fake.label_status.configuracoes["text_color"] == "red"


def test_start_automation_valida_diretorio_relatorio_vazio(app_fake, tmp_path):
    app_fake.entry_user.valor = "usuario"
    app_fake.entry_password.valor = "senha"

    planilha = tmp_path / "planilha.xlsx"
    planilha.touch()
    app_fake.entry_spreadsheet_in.valor = str(planilha)

    app_fake.entry_report_dir.valor = ""

    ui.AghuPrinterApp.start_automation(app_fake)

    assert app_fake.label_status.configuracoes["text"] == "Erro: informe a pasta de relatorio."
    assert app_fake.label_status.configuracoes["text_color"] == "red"


def test_start_automation_valida_planilha_entrada_vazia(app_fake):
    app_fake.entry_user.valor = "usuario"
    app_fake.entry_password.valor = "senha"
    app_fake.entry_spreadsheet_in.valor = ""
    app_fake.entry_report_dir.valor = "C:/algum/lugar"

    ui.AghuPrinterApp.start_automation(app_fake)

    assert app_fake.label_status.configuracoes["text"] == "Erro: informe a planilha de entrada."
    assert app_fake.label_status.configuracoes["text_color"] == "red"


def test_start_automation_valida_usuario_senha_vazios(app_fake):
    app_fake.entry_user.valor = ""
    app_fake.entry_password.valor = "senha"
    app_fake.entry_spreadsheet_in.valor = "planilha.xlsx"
    app_fake.entry_report_dir.valor = "C:/algum/lugar"

    ui.AghuPrinterApp.start_automation(app_fake)

    assert app_fake.label_status.configuracoes["text"] == "Erro: preencha usuário de rede e senha."
    assert app_fake.label_status.configuracoes["text_color"] == "red"


def test_start_automation_valida_extensao_planilha(app_fake, tmp_path):
    app_fake.entry_user.valor = "usuario"
    app_fake.entry_password.valor = "senha"

    planilha = tmp_path / "planilha.csv"
    planilha.touch()
    app_fake.entry_spreadsheet_in.valor = str(planilha)

    dir_relatorio = tmp_path / "relatorios"
    dir_relatorio.mkdir()
    app_fake.entry_report_dir.valor = str(dir_relatorio)

    ui.AghuPrinterApp.start_automation(app_fake)

    assert app_fake.label_status.configuracoes["text"].startswith("Erro:")
    assert app_fake.label_status.configuracoes["text_color"] == "red"


def test_run_playwright_task_repassa_diretorio_relatorio_para_backend(
    app_fake,
    monkeypatch,
):
    chamadas = []
    chamadas_after = []

    def fake_executar_automacao_aghu(**kwargs):
        chamadas.append(kwargs)
        return "Processo concluido."

    def fake_after(delay, callback, *args):
        chamadas_after.append((delay, callback, args))

    monkeypatch.setattr(ui, "executar_automacao_aghu", fake_executar_automacao_aghu)
    app_fake.after = fake_after

    ui.AghuPrinterApp.run_playwright_task(
        app_fake,
        "usuario",
        "senha",
        True,
        False,
        "C:/entrada.xlsx",
        "C:/relatorios",
        "https://aghu.example",
    )

    assert chamadas == [
        {
            "usuario": "usuario",
            "senha": "senha",
            "mostrar_console": True,
            "mostrar_browser": False,
            "caminho_planilha_entrada": "C:/entrada.xlsx",
            "diretorio_relatorio": "C:/relatorios",
            "url_aghu": "https://aghu.example",
        }
    ]
    assert chamadas_after[0][0] == 0
    assert chamadas_after[0][2] == ("Processo concluido.", "green")
