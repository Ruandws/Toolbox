from datetime import datetime
from pathlib import Path

import pytest

import ui_criar_usuario_aghu as ui
from criar_usuario_aghu import (
    STATUS_CONFERIR_MANUALMENTE,
    STATUS_ERRO,
    STATUS_IGNORADO,
    STATUS_IMPORTADO,
    STATUS_JA_IMPORTADO,
    STATUS_NAO_ENCONTRADO,
    ResultadoImportacao,
    UsuarioImportacao,
)


class FakeEntry:
    def __init__(self, *args, valor="", **kwargs):
        if args and isinstance(args[0], str):
            valor = args[0]
        self.valor = valor
        self.configuracoes = dict(kwargs)
        self.focus_recebido = False

    def get(self):
        return self.valor

    def delete(self, inicio, fim):
        self.valor = ""

    def insert(self, indice, valor):
        if indice == 0:
            self.valor = valor + self.valor
            return

        self.valor = self.valor[:indice] + valor + self.valor[indice:]

    def configure(self, **kwargs):
        self.configuracoes.update(kwargs)

    def grid(self, **kwargs):
        self.grid_args = kwargs

    def focus(self):
        self.focus_recebido = True


class FakeWidget:
    def __init__(self, *args, **kwargs):
        self.configuracoes = dict(kwargs)
        self.grid_args = None
        self.grid_column_args = []
        self.destruido = False
        self.focus_recebido = False

    def configure(self, **kwargs):
        self.configuracoes.update(kwargs)

    def grid(self, **kwargs):
        self.grid_args = kwargs

    def grid_configure(self, **kwargs):
        self.grid_args = {**(self.grid_args or {}), **kwargs}

    def grid_columnconfigure(self, *args, **kwargs):
        self.grid_column_args.append((args, kwargs))

    def grid_remove(self):
        self.visivel = False

    def destroy(self):
        self.destruido = True

    def focus(self):
        self.focus_recebido = True


class FakeFrame:
    def __init__(self, *args, **kwargs):
        self.visivel = False
        self.configuracoes = dict(kwargs)
        self.grid_args = None
        self.grid_column_args = []
        self.destruido = False

    def grid(self, **kwargs):
        self.visivel = True
        self.grid_args = kwargs

    def grid_configure(self, **kwargs):
        self.grid_args = {**(self.grid_args or {}), **kwargs}

    def grid_columnconfigure(self, *args, **kwargs):
        self.grid_column_args.append((args, kwargs))

    def grid_remove(self):
        self.visivel = False

    def destroy(self):
        self.destruido = True


class FakeStringVar:
    def __init__(self, valor):
        self.valor = valor

    def get(self):
        return self.valor

    def set(self, valor):
        self.valor = valor


class FakeButton(FakeWidget):
    def __init__(self, *args, command=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.command = command


class FakeSegment(FakeWidget):
    def __init__(self):
        super().__init__()
        self._buttons_dict = {
            ui.TIPO_INDIVIDUAL: FakeButton(),
            ui.TIPO_LOTE: FakeButton(),
        }


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


class FixedDatetime:
    @classmethod
    def now(cls):
        return datetime(2026, 6, 24, 15, 30, 45)


def linha_usuario_fake(login="", nome_completo="", email=""):
    return {
        "frame": FakeFrame(),
        "login": FakeEntry(login),
        "nome_completo": FakeEntry(nome_completo),
        "email": FakeEntry(email),
        "remover": FakeButton(),
    }


@pytest.fixture()
def app_fake():
    app = object.__new__(ui.AghuImportUserApp)
    app.em_execucao = False
    app.var_ambiente = FakeStringVar(ui.AMBIENTE_PRODUCAO)
    app.var_tipo_execucao = FakeStringVar(ui.TIPO_INDIVIDUAL)
    app.var_browser = FakeStringVar(True)
    app.var_console = FakeStringVar(True)
    app.entry_usuario_rede = FakeEntry()
    app.entry_senha = FakeEntry()
    app.entry_planilha_lote = FakeEntry()
    app.entry_relatorio_lote = FakeEntry()
    app.button_executar = FakeWidget()
    app.segment_tipo_execucao = FakeSegment()
    app.checkbox_browser = FakeWidget()
    app.checkbox_console = FakeWidget()
    app.button_planilha_lote = FakeWidget()
    app.button_relatorio_lote = FakeWidget()
    app.label_status = FakeWidget()
    app.frame_individual = FakeFrame()
    app.frame_lote = FakeFrame()
    app.frame_alerta_producao = FakeFrame()
    app.frame_linhas_usuarios = FakeFrame()
    app.button_adicionar_usuario = FakeButton()
    app.label_limite_usuarios = FakeWidget()
    app.linhas_usuarios_individual = [linha_usuario_fake()]
    app.option_ambiente = FakeWidget()
    return app


def test_obter_url_ambiente_aghu_retorna_urls_conhecidas():
    assert ui.obter_url_ambiente_aghu(ui.AMBIENTE_PRODUCAO) == ui.AGHU_URL
    assert (
        ui.obter_url_ambiente_aghu(ui.AMBIENTE_HOMOLOGACAO)
        == ui.AGHU_URL_HOMOLOGACAO
    )


def test_obter_url_ambiente_aghu_usa_producao_com_ambiente_desconhecido():
    assert ui.obter_url_ambiente_aghu("desconhecido") == ui.AGHU_URL


@pytest.fixture()
def caminho_tmp_teste(tmp_path):
    return tmp_path


def test_caminho_relatorio_padrao_usa_cwd_sem_base(monkeypatch, caminho_tmp_teste):
    monkeypatch.setattr(ui, "datetime", FixedDatetime)
    monkeypatch.chdir(caminho_tmp_teste)

    caminho = Path(ui.caminho_relatorio_padrao())

    assert caminho == (
        caminho_tmp_teste / "relatorio_importacao_usuario_20260624_153045.xlsx"
    )


def test_caminho_relatorio_padrao_usa_diretorio_pai_quando_base_e_arquivo(
    monkeypatch,
    caminho_tmp_teste,
):
    monkeypatch.setattr(ui, "datetime", FixedDatetime)

    caminho = Path(ui.caminho_relatorio_padrao(str(caminho_tmp_teste / "entrada.xlsx")))

    assert caminho == (
        caminho_tmp_teste / "relatorio_importacao_usuario_20260624_153045.xlsx"
    )


def test_caminho_relatorio_padrao_usa_base_quando_base_e_diretorio(
    monkeypatch,
    caminho_tmp_teste,
):
    monkeypatch.setattr(ui, "datetime", FixedDatetime)

    caminho = Path(ui.caminho_relatorio_padrao(str(caminho_tmp_teste)))

    assert caminho == (
        caminho_tmp_teste / "relatorio_importacao_usuario_20260624_153045.xlsx"
    )


def test_atualizar_tipo_execucao_mostra_frame_individual(app_fake):
    ui.AghuImportUserApp._atualizar_tipo_execucao(app_fake, ui.TIPO_INDIVIDUAL)

    assert app_fake.frame_individual.visivel is True
    assert app_fake.frame_lote.visivel is False
    assert (
        app_fake.segment_tipo_execucao._buttons_dict[ui.TIPO_INDIVIDUAL]
        .configuracoes["text_color"]
        == "white"
    )


def test_atualizar_tipo_execucao_mostra_frame_lote(app_fake):
    ui.AghuImportUserApp._atualizar_tipo_execucao(app_fake, ui.TIPO_LOTE)

    assert app_fake.frame_individual.visivel is False
    assert app_fake.frame_lote.visivel is True
    assert (
        app_fake.segment_tipo_execucao._buttons_dict[ui.TIPO_LOTE]
        .configuracoes["text_color"]
        == "white"
    )


def test_alerta_de_producao_aparece_somente_em_producao(app_fake):
    ui.AghuImportUserApp._atualizar_alerta_ambiente(app_fake, ui.AMBIENTE_PRODUCAO)
    assert app_fake.frame_alerta_producao.visivel is True

    ui.AghuImportUserApp._atualizar_alerta_ambiente(app_fake, ui.AMBIENTE_HOMOLOGACAO)
    assert app_fake.frame_alerta_producao.visivel is False


def test_on_ambiente_changed_exibe_alerta_modal_em_producao(app_fake, monkeypatch):
    chamadas = []

    def showwarning_fake(titulo, mensagem, parent=None):
        chamadas.append((titulo, mensagem, parent))

    monkeypatch.setattr(ui.messagebox, "showwarning", showwarning_fake)

    ui.AghuImportUserApp._on_ambiente_changed(app_fake, ui.AMBIENTE_PRODUCAO)

    assert app_fake.frame_alerta_producao.visivel is True
    assert len(chamadas) == 1
    titulo, mensagem, parent = chamadas[0]
    assert ui.AMBIENTE_PRODUCAO in titulo
    assert ui.AMBIENTE_PRODUCAO in mensagem
    assert "cautela" in mensagem.lower()
    assert parent is app_fake


def test_on_ambiente_changed_nao_exibe_alerta_modal_em_homologacao(
    app_fake,
    monkeypatch,
):
    chamadas = []
    monkeypatch.setattr(
        ui.messagebox,
        "showwarning",
        lambda *args, **kwargs: chamadas.append((args, kwargs)),
    )

    ui.AghuImportUserApp._on_ambiente_changed(app_fake, ui.AMBIENTE_HOMOLOGACAO)

    assert app_fake.frame_alerta_producao.visivel is False
    assert chamadas == []


def test_validar_opcoes_visibilidade_religa_browser_quando_tudo_oculto(
    app_fake,
    monkeypatch,
):
    chamadas = []
    app_fake.var_browser.set(False)
    app_fake.var_console.set(False)
    monkeypatch.setattr(
        ui.messagebox,
        "showwarning",
        lambda *args, **kwargs: chamadas.append((args, kwargs)),
    )

    ui.AghuImportUserApp._validar_opcoes_visibilidade(app_fake, app_fake.var_browser)

    assert app_fake.var_browser.get() is True
    assert app_fake.var_console.get() is False
    assert len(chamadas) == 1


def test_validar_opcoes_visibilidade_religa_console_quando_tudo_oculto(
    app_fake,
    monkeypatch,
):
    chamadas = []
    app_fake.var_browser.set(False)
    app_fake.var_console.set(False)
    monkeypatch.setattr(
        ui.messagebox,
        "showwarning",
        lambda *args, **kwargs: chamadas.append((args, kwargs)),
    )

    ui.AghuImportUserApp._validar_opcoes_visibilidade(app_fake, app_fake.var_console)

    assert app_fake.var_browser.get() is False
    assert app_fake.var_console.get() is True
    assert len(chamadas) == 1


def test_credenciais_e_url_retorna_dados_normalizados(app_fake):
    app_fake.entry_usuario_rede.valor = " usuario.rede "
    app_fake.entry_senha.valor = " senha com espaco "
    app_fake.var_ambiente.set(ui.AMBIENTE_HOMOLOGACAO)

    usuario, senha, url = ui.AghuImportUserApp._credenciais_e_url(app_fake)

    assert usuario == "usuario.rede"
    assert senha == " senha com espaco "
    assert url == ui.AGHU_URL_HOMOLOGACAO


@pytest.mark.parametrize(
    ("usuario", "senha"),
    [
        ("", "senha"),
        ("usuario", ""),
        ("   ", "senha"),
    ],
)
def test_credenciais_e_url_rejeita_usuario_ou_senha_em_branco(
    app_fake,
    usuario,
    senha,
):
    app_fake.entry_usuario_rede.valor = usuario
    app_fake.entry_senha.valor = senha

    with pytest.raises(ValueError, match="senha"):
        ui.AghuImportUserApp._credenciais_e_url(app_fake)


def test_selecionar_planilha_lote_nao_altera_campos_quando_cancelado(
    app_fake,
    monkeypatch,
):
    app_fake.entry_planilha_lote.valor = "antes.xlsx"
    app_fake.entry_relatorio_lote.valor = ""
    monkeypatch.setattr(ui.filedialog, "askopenfilename", lambda **kwargs: "")

    ui.AghuImportUserApp.selecionar_planilha_lote(app_fake)

    assert app_fake.entry_planilha_lote.get() == "antes.xlsx"
    assert app_fake.entry_relatorio_lote.get() == ""


def test_selecionar_planilha_lote_preenche_planilha_e_relatorio_padrao(
    app_fake,
    monkeypatch,
    caminho_tmp_teste,
):
    planilha = caminho_tmp_teste / "usuarios.xlsx"
    monkeypatch.setattr(
        ui.filedialog,
        "askopenfilename",
        lambda **kwargs: str(planilha),
    )
    monkeypatch.setattr(
        ui,
        "caminho_relatorio_padrao",
        lambda base="": str(caminho_tmp_teste / "relatorio.xlsx"),
    )

    ui.AghuImportUserApp.selecionar_planilha_lote(app_fake)

    assert app_fake.entry_planilha_lote.get() == str(planilha)
    assert app_fake.entry_relatorio_lote.get() == str(caminho_tmp_teste / "relatorio.xlsx")


def test_selecionar_planilha_lote_nao_sobrescreve_relatorio_existente(
    app_fake,
    monkeypatch,
    caminho_tmp_teste,
):
    app_fake.entry_relatorio_lote.valor = "relatorio_existente.xlsx"
    monkeypatch.setattr(
        ui.filedialog,
        "askopenfilename",
        lambda **kwargs: str(caminho_tmp_teste / "usuarios.xlsx"),
    )

    ui.AghuImportUserApp.selecionar_planilha_lote(app_fake)

    assert app_fake.entry_relatorio_lote.get() == "relatorio_existente.xlsx"


def test_selecionar_relatorio_lote_preenche_caminho(
    app_fake,
    monkeypatch,
    caminho_tmp_teste,
):
    caminho = caminho_tmp_teste / "saida.xlsx"
    monkeypatch.setattr(
        ui.filedialog,
        "asksaveasfilename",
        lambda **kwargs: str(caminho),
    )

    ui.AghuImportUserApp.selecionar_relatorio_lote(app_fake)

    assert app_fake.entry_relatorio_lote.get() == str(caminho)


def test_adicionar_linha_usuario_cria_linha_e_respeita_limite(
    app_fake,
    monkeypatch,
):
    monkeypatch.setattr(ui.ctk, "CTkFrame", FakeFrame)
    monkeypatch.setattr(ui.ctk, "CTkEntry", FakeEntry)
    monkeypatch.setattr(ui.ctk, "CTkButton", FakeButton)
    app_fake.linhas_usuarios_individual = []

    for _ in range(ui.MAX_USUARIOS_MANUAIS):
        ui.AghuImportUserApp.adicionar_linha_usuario(app_fake)

    ui.AghuImportUserApp.adicionar_linha_usuario(app_fake)

    assert len(app_fake.linhas_usuarios_individual) == ui.MAX_USUARIOS_MANUAIS
    assert app_fake.button_adicionar_usuario.configuracoes["state"] == "disabled"
    assert app_fake.label_limite_usuarios.configuracoes["text"] == (
        "Limite de 5 usuários atingido."
    )
    assert app_fake.linhas_usuarios_individual[-1]["login"].focus_recebido is True


def test_remover_linha_usuario_nao_remove_linha_unica(app_fake):
    linha_unica = app_fake.linhas_usuarios_individual[0]

    ui.AghuImportUserApp.remover_linha_usuario(app_fake, linha_unica)

    assert app_fake.linhas_usuarios_individual == [linha_unica]
    assert linha_unica["frame"].destruido is False
    assert linha_unica["remover"].configuracoes["state"] == "disabled"


def test_remover_linha_usuario_remove_e_reindexa_linhas(app_fake):
    linha_1 = linha_usuario_fake("a", "A", "a@x.com")
    linha_2 = linha_usuario_fake("b", "B", "b@x.com")
    linha_3 = linha_usuario_fake("c", "C", "c@x.com")
    app_fake.linhas_usuarios_individual = [linha_1, linha_2, linha_3]

    ui.AghuImportUserApp.remover_linha_usuario(app_fake, linha_2)

    assert app_fake.linhas_usuarios_individual == [linha_1, linha_3]
    assert linha_2["frame"].destruido is True
    assert linha_1["frame"].grid_args["row"] == 0
    assert linha_3["frame"].grid_args["row"] == 1


def test_remover_linha_usuario_ignora_linha_desconhecida(app_fake):
    linha_existente = app_fake.linhas_usuarios_individual[0]
    linha_desconhecida = linha_usuario_fake("fora", "Fora", "fora@x.com")

    ui.AghuImportUserApp.remover_linha_usuario(app_fake, linha_desconhecida)

    assert app_fake.linhas_usuarios_individual == [linha_existente]
    assert linha_desconhecida["frame"].destruido is False


def test_coletar_usuarios_individuais_preserva_ordem_e_valores(app_fake):
    app_fake.linhas_usuarios_individual = [
        linha_usuario_fake("login1", "Nome 1", "email1@x.com"),
        linha_usuario_fake("login2", "Nome 2", "email2@x.com"),
    ]

    usuarios = ui.AghuImportUserApp.coletar_usuarios_individuais(app_fake)

    assert usuarios == [
        UsuarioImportacao("login1", "Nome 1", "email1@x.com"),
        UsuarioImportacao("login2", "Nome 2", "email2@x.com"),
    ]


def test_atualizar_estado_lista_usuarios_bloqueia_campos_durante_execucao(
    app_fake,
):
    app_fake.linhas_usuarios_individual = [
        linha_usuario_fake("login1", "Nome 1", "email1@x.com"),
        linha_usuario_fake("login2", "Nome 2", "email2@x.com"),
    ]
    app_fake.em_execucao = True

    ui.AghuImportUserApp._atualizar_estado_lista_usuarios(app_fake)

    assert app_fake.button_adicionar_usuario.configuracoes["state"] == "disabled"
    for linha in app_fake.linhas_usuarios_individual:
        assert linha["login"].configuracoes["state"] == "disabled"
        assert linha["nome_completo"].configuracoes["state"] == "disabled"
        assert linha["email"].configuracoes["state"] == "disabled"
        assert linha["remover"].configuracoes["state"] == "disabled"


def test_atualizar_estado_lista_usuarios_habilita_remocao_quando_ha_mais_de_um(
    app_fake,
):
    app_fake.linhas_usuarios_individual = [
        linha_usuario_fake("login1", "Nome 1", "email1@x.com"),
        linha_usuario_fake("login2", "Nome 2", "email2@x.com"),
    ]

    ui.AghuImportUserApp._atualizar_estado_lista_usuarios(app_fake)

    assert app_fake.button_adicionar_usuario.configuracoes["state"] == "normal"
    for linha in app_fake.linhas_usuarios_individual:
        assert linha["login"].configuracoes["state"] == "normal"
        assert linha["remover"].configuracoes["state"] == "normal"


def test_bloquear_e_liberar_execucao_alteram_estados(app_fake):
    ui.AghuImportUserApp._bloquear_execucao(app_fake, "Executando...")

    assert app_fake.em_execucao is True
    assert app_fake.button_executar.configuracoes["state"] == "disabled"
    assert app_fake.button_executar.configuracoes["text"] == "Executando..."
    assert app_fake.segment_tipo_execucao.configuracoes["state"] == "disabled"
    assert app_fake.checkbox_browser.configuracoes["state"] == "disabled"
    assert app_fake.checkbox_console.configuracoes["state"] == "disabled"
    assert app_fake.button_planilha_lote.configuracoes["state"] == "disabled"
    assert app_fake.button_relatorio_lote.configuracoes["state"] == "disabled"

    ui.AghuImportUserApp._liberar_execucao(app_fake)

    assert app_fake.em_execucao is False
    assert app_fake.button_executar.configuracoes["state"] == "normal"
    assert app_fake.button_executar.configuracoes["text"] == "Executar importação"
    assert app_fake.segment_tipo_execucao.configuracoes["state"] == "normal"
    assert app_fake.checkbox_browser.configuracoes["state"] == "normal"
    assert app_fake.checkbox_console.configuracoes["state"] == "normal"
    assert app_fake.button_planilha_lote.configuracoes["state"] == "normal"
    assert app_fake.button_relatorio_lote.configuracoes["state"] == "normal"


def test_iniciar_execucao_despacha_conforme_tipo(app_fake, monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        ui.AghuImportUserApp,
        "iniciar_execucao_individual",
        lambda self: chamadas.append("individual"),
    )
    monkeypatch.setattr(
        ui.AghuImportUserApp,
        "iniciar_execucao_lote",
        lambda self: chamadas.append("lote"),
    )

    app_fake.var_tipo_execucao.set(ui.TIPO_INDIVIDUAL)
    ui.AghuImportUserApp.iniciar_execucao(app_fake)
    app_fake.var_tipo_execucao.set(ui.TIPO_LOTE)
    ui.AghuImportUserApp.iniciar_execucao(app_fake)

    assert chamadas == ["individual", "lote"]


def test_iniciar_execucao_individual_nao_faz_nada_se_ja_em_execucao(
    app_fake,
    monkeypatch,
):
    app_fake.em_execucao = True
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    FakeThread.criadas = []

    ui.AghuImportUserApp.iniciar_execucao_individual(app_fake)

    assert FakeThread.criadas == []


def test_iniciar_execucao_individual_mostra_erro_sem_credenciais(app_fake):
    ui.AghuImportUserApp.iniciar_execucao_individual(app_fake)

    assert app_fake.label_status.configuracoes["text"].startswith("Erro:")
    assert app_fake.label_status.configuracoes["text_color"] == "red"


def test_iniciar_execucao_individual_mostra_erro_com_campo_em_branco(
    app_fake,
    monkeypatch,
):
    FakeThread.criadas = []
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    app_fake.entry_usuario_rede.valor = "usuario"
    app_fake.entry_senha.valor = "senha"
    app_fake.linhas_usuarios_individual = [
        linha_usuario_fake("login1", "", "email1@x.com"),
    ]

    ui.AghuImportUserApp.iniciar_execucao_individual(app_fake)

    assert FakeThread.criadas == []
    assert app_fake.label_status.configuracoes["text"].startswith("Erro:")
    assert app_fake.label_status.configuracoes["text_color"] == "red"


def test_iniciar_execucao_individual_inicia_thread_com_dados_da_tela(
    app_fake,
    monkeypatch,
):
    FakeThread.criadas = []
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    app_fake.entry_usuario_rede.valor = "usuario"
    app_fake.entry_senha.valor = "senha"
    app_fake.linhas_usuarios_individual = [
        linha_usuario_fake("login1", "Nome 1", "email1@x.com"),
        linha_usuario_fake("login2", "Nome 2", "email2@x.com"),
    ]

    ui.AghuImportUserApp.iniciar_execucao_individual(app_fake)

    thread = FakeThread.criadas[0]
    usuarios = thread.args[2]
    assert thread.iniciada is True
    assert thread.daemon is True
    assert thread.target == app_fake._executar_individual_thread
    assert thread.args == (
        "usuario",
        "senha",
        usuarios,
        ui.AGHU_URL,
        True,
        True,
    )
    assert usuarios == [
        UsuarioImportacao("login1", "Nome 1", "email1@x.com"),
        UsuarioImportacao("login2", "Nome 2", "email2@x.com"),
    ]
    assert app_fake.label_status.configuracoes["text"] == (
        "Executando importação unitária..."
    )
    assert app_fake.button_executar.configuracoes["state"] == "disabled"


def test_iniciar_execucao_lote_valida_planilha_obrigatoria(app_fake):
    app_fake.entry_usuario_rede.valor = "usuario"
    app_fake.entry_senha.valor = "senha"

    ui.AghuImportUserApp.iniciar_execucao_lote(app_fake)

    assert app_fake.label_status.configuracoes["text"] == "Erro: Informe a planilha .xlsx de lote."
    assert app_fake.label_status.configuracoes["text_color"] == "red"


def test_iniciar_execucao_lote_valida_extensao_xlsx(app_fake):
    app_fake.entry_usuario_rede.valor = "usuario"
    app_fake.entry_senha.valor = "senha"
    app_fake.entry_planilha_lote.valor = "usuarios.csv"

    ui.AghuImportUserApp.iniciar_execucao_lote(app_fake)

    assert app_fake.label_status.configuracoes["text"] == (
        "Erro: A planilha de lote deve ser um arquivo .xlsx."
    )


def test_iniciar_execucao_lote_valida_extensao_xlsx_do_relatorio(app_fake):
    app_fake.entry_usuario_rede.valor = "usuario"
    app_fake.entry_senha.valor = "senha"
    app_fake.entry_planilha_lote.valor = "usuarios.xlsx"
    app_fake.entry_relatorio_lote.valor = "relatorio.txt"

    ui.AghuImportUserApp.iniciar_execucao_lote(app_fake)

    assert app_fake.label_status.configuracoes["text"] == (
        "Erro: O relatório de saída deve ser um arquivo .xlsx."
    )
    assert app_fake.label_status.configuracoes["text_color"] == "red"


def test_iniciar_execucao_lote_gera_relatorio_padrao_e_inicia_thread(
    app_fake,
    monkeypatch,
):
    FakeThread.criadas = []
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    monkeypatch.setattr(
        ui,
        "caminho_relatorio_padrao",
        lambda base="": "relatorio_gerado.xlsx",
    )
    app_fake.entry_usuario_rede.valor = "usuario"
    app_fake.entry_senha.valor = "senha"
    app_fake.entry_planilha_lote.valor = "usuarios.xlsx"

    ui.AghuImportUserApp.iniciar_execucao_lote(app_fake)

    thread = FakeThread.criadas[0]
    assert thread.iniciada is True
    assert app_fake.entry_relatorio_lote.get() == "relatorio_gerado.xlsx"
    assert thread.args == (
        "usuario",
        "senha",
        "usuarios.xlsx",
        "relatorio_gerado.xlsx",
        ui.AGHU_URL,
        True,
        True,
    )


def test_resumir_resultados_conta_status_conhecidos(app_fake):
    resultados = [
        ResultadoImportacao("a", "A", "a@x.com", STATUS_IMPORTADO, "ok"),
        ResultadoImportacao("b", "B", "b@x.com", STATUS_JA_IMPORTADO, "ok"),
        ResultadoImportacao("c", "C", "c@x.com", STATUS_NAO_ENCONTRADO, "ok"),
        ResultadoImportacao("d", "D", "d@x.com", STATUS_IGNORADO, "ok"),
        ResultadoImportacao("e", "E", "e@x.com", STATUS_CONFERIR_MANUALMENTE, "ok"),
        ResultadoImportacao("f", "F", "f@x.com", STATUS_ERRO, "ok"),
    ]

    resumo = ui.AghuImportUserApp._resumir_resultados(app_fake, resultados)

    assert resumo == (
        "Lote concluído. Total: 6. "
        "Importados: 1. "
        "Já importados: 1. "
        "Não encontrados: 1. "
        "Ignorados: 1. "
        "Conferir manualmente: 1. "
        "Erros: 1."
    )


class TestCorResultado:
    def test_verde_quando_tudo_importado(self, app_fake):
        resultados = [
            ResultadoImportacao("a", "A", "a@x.com", STATUS_IMPORTADO, "ok"),
            ResultadoImportacao("b", "B", "b@x.com", STATUS_JA_IMPORTADO, "ok"),
        ]

        assert ui.AghuImportUserApp._cor_resultado(app_fake, resultados) == "green"

    def test_laranja_quando_ha_ignorado_sem_erro(self, app_fake):
        resultados = [
            ResultadoImportacao("a", "A", "a@x.com", STATUS_IMPORTADO, "ok"),
            ResultadoImportacao("b", "B", "b@x.com", STATUS_IGNORADO, "faltou campo"),
        ]

        assert ui.AghuImportUserApp._cor_resultado(app_fake, resultados) == "orange"

    def test_laranja_quando_ha_conferir_manualmente_sem_erro(self, app_fake):
        resultados = [
            ResultadoImportacao(
                "a", "A", "a@x.com", STATUS_CONFERIR_MANUALMENTE, "indefinido"
            ),
        ]

        assert ui.AghuImportUserApp._cor_resultado(app_fake, resultados) == "orange"

    def test_vermelho_quando_ha_erro(self, app_fake):
        resultados = [
            ResultadoImportacao("a", "A", "a@x.com", STATUS_IMPORTADO, "ok"),
            ResultadoImportacao("b", "B", "b@x.com", STATUS_IGNORADO, "faltou campo"),
            ResultadoImportacao("c", "C", "c@x.com", STATUS_ERRO, "falha tecnica"),
        ]

        assert ui.AghuImportUserApp._cor_resultado(app_fake, resultados) == "red"


def test_executar_individual_thread_agenda_finalizacao_em_sucesso(
    app_fake,
    monkeypatch,
):
    resultado = ResultadoImportacao(
        "login",
        "Nome",
        "email@x.com",
        STATUS_IMPORTADO,
        "OK",
    )
    usuarios = [UsuarioImportacao("login", "Nome", "email@x.com")]
    chamadas = []
    capturados = {}
    app_fake.after = lambda delay, func, *args: chamadas.append((delay, func, args))

    def executar_fake(**kwargs):
        capturados.update(kwargs)
        return [resultado]

    monkeypatch.setattr(
        ui,
        "executar_importacao_usuarios",
        executar_fake,
    )

    ui.AghuImportUserApp._executar_individual_thread(
        app_fake,
        "usuario",
        "senha",
        usuarios,
        "url",
        False,
        True,
    )

    delay, func, args = chamadas[0]
    assert delay == 0
    assert func == app_fake._finalizar_execucao
    assert args == ("login: importado - OK", "green")
    assert capturados["usuarios"] == usuarios
    assert capturados["mostrar_browser"] is False
    assert capturados["mostrar_console"] is True


def test_executar_individual_thread_resume_multiplos_resultados(
    app_fake,
    monkeypatch,
):
    resultados = [
        ResultadoImportacao("a", "A", "a@x.com", STATUS_IMPORTADO, "OK"),
        ResultadoImportacao("b", "B", "b@x.com", STATUS_ERRO, "Falha"),
    ]
    usuarios = [
        UsuarioImportacao("a", "A", "a@x.com"),
        UsuarioImportacao("b", "B", "b@x.com"),
    ]
    chamadas = []
    app_fake.after = lambda delay, func, *args: chamadas.append((delay, func, args))
    monkeypatch.setattr(
        ui,
        "executar_importacao_usuarios",
        lambda **kwargs: resultados,
    )

    ui.AghuImportUserApp._executar_individual_thread(
        app_fake,
        "usuario",
        "senha",
        usuarios,
        "url",
        True,
        True,
    )

    assert chamadas[0][2] == (
        "Execução unitária concluída. Total: 2. "
        "Importados: 1. "
        "Já importados: 0. "
        "Não encontrados: 0. "
        "Ignorados: 0. "
        "Conferir manualmente: 0. "
        "Erros: 1.",
        "red",
    )


def test_executar_individual_thread_agenda_finalizacao_em_erro(
    app_fake,
    monkeypatch,
):
    chamadas = []
    app_fake.after = lambda delay, func, *args: chamadas.append((delay, func, args))

    def falhar(**kwargs):
        raise RuntimeError("falha")

    monkeypatch.setattr(ui, "executar_importacao_usuarios", falhar)

    ui.AghuImportUserApp._executar_individual_thread(
        app_fake,
        "usuario",
        "senha",
        [UsuarioImportacao("login", "Nome", "email@x.com")],
        "url",
        True,
        True,
    )

    assert chamadas[0][2] == ("Erro: falha", "red")


def test_executar_lote_thread_agenda_finalizacao_com_resumo(app_fake, monkeypatch):
    resultados = [
        ResultadoImportacao("login", "Nome", "email@x.com", STATUS_IMPORTADO, "OK")
    ]
    chamadas = []
    capturados = {}
    app_fake.after = lambda delay, func, *args: chamadas.append((delay, func, args))

    def executar_fake(**kwargs):
        capturados.update(kwargs)
        return resultados, Path("relatorio.xlsx")

    monkeypatch.setattr(
        ui,
        "executar_importacao_lote",
        executar_fake,
    )

    ui.AghuImportUserApp._executar_lote_thread(
        app_fake,
        "usuario",
        "senha",
        "usuarios.xlsx",
        "relatorio.xlsx",
        "url",
        False,
        True,
    )

    assert chamadas[0][0] == 0
    assert chamadas[0][1] == app_fake._finalizar_execucao
    assert capturados["mostrar_browser"] is False
    assert capturados["mostrar_console"] is True
    assert chamadas[0][2] == (
        "Lote concluído. Total: 1. "
        "Importados: 1. "
        "Já importados: 0. "
        "Não encontrados: 0. "
        "Ignorados: 0. "
        "Conferir manualmente: 0. "
        "Erros: 0. Relatório: relatorio.xlsx",
        "green",
    )
