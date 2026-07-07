import pytest

import ui_concessor as ui
from concessor_aghu import (
    ConcessaoPerfisEntrada,
    ResultadoConcessao,
    ResultadoPerfil,
    STATUS_CONCEDIDO,
    STATUS_CONFERIR_MANUAL,
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


class FakeText:
    def __init__(self):
        self.configuracoes = {}
        self.texto = ""

    def configure(self, **kwargs):
        self.configuracoes.update(kwargs)

    def delete(self, inicio, fim):
        assert (inicio, fim) == ("1.0", "end")
        self.texto = ""

    def insert(self, indice, texto):
        assert indice == "1.0"
        self.texto = texto


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


class FakeRegra:
    perfis_conceder = ("PERF01", "PERF02")
    perfis_bloqueados = ("PERF03",)
    perfis_validacao_ura = ("PERF04",)
    observacoes = ("Validar chamado",)


class FakeCatalogo:
    def __init__(self):
        self.escopos = {"Escopo A": ("Categoria A", "Categoria B")}
        self.regra = FakeRegra()

    def categorias(self, escopo):
        return self.escopos.get(escopo, ())

    def obter_regra(self, escopo, categoria):
        if escopo == "erro":
            raise ValueError("regra ausente")

        assert categoria
        return self.regra


@pytest.fixture()
def app_fake():
    app = object.__new__(ui.AghuConcessorPerfisApp)
    app.catalogo = FakeCatalogo()
    app.em_execucao = False
    app.var_ambiente = FakeStringVar(ui.AMBIENTE_HOMOLOGACAO)
    app.var_tipo_execucao = FakeStringVar(ui.TIPO_INDIVIDUAL)
    app.var_browser = FakeStringVar(True)
    app.var_console = FakeStringVar(True)
    app.var_escopo = FakeStringVar("Escopo A")
    app.var_categoria = FakeStringVar("Categoria A")
    app.entry_usuario_rede = FakeEntry()
    app.entry_senha = FakeEntry()
    app.entry_login_alvo = FakeEntry()
    app.entry_protocolo = FakeEntry()
    app.entry_planilha_lote = FakeEntry()
    app.entry_relatorio_lote = FakeEntry()
    app.button_executar = FakeWidget()
    app.segment_tipo_execucao = FakeWidget()
    app.checkbox_browser = FakeWidget()
    app.checkbox_console = FakeWidget()
    app.option_ambiente = FakeWidget()
    app.option_escopo = FakeWidget()
    app.option_categoria = FakeWidget()
    app.button_planilha_lote = FakeWidget()
    app.button_relatorio_lote = FakeWidget()
    app.frame_alerta_producao = FakeFrame()
    app.text_perfis = FakeText()
    app.label_status = FakeWidget()
    return app


def test_obter_url_ambiente_aghu_retorna_urls_conhecidas():
    assert ui.obter_url_ambiente_aghu(ui.AMBIENTE_PRODUCAO) == ui.AGHU_URL
    assert (
        ui.obter_url_ambiente_aghu(ui.AMBIENTE_HOMOLOGACAO)
        == ui.AGHU_URL_HOMOLOGACAO
    )


def test_obter_url_ambiente_aghu_usa_producao_para_ambiente_desconhecido():
    assert ui.obter_url_ambiente_aghu("desconhecido") == ui.AGHU_URL


def test_validar_opcoes_visibilidade_religa_opcao_alvo(app_fake, monkeypatch):
    chamadas = []
    app_fake.var_browser.set(False)
    app_fake.var_console.set(False)
    monkeypatch.setattr(
        ui.messagebox,
        "showwarning",
        lambda *args, **kwargs: chamadas.append((args, kwargs)),
    )

    ui.AghuConcessorPerfisApp._validar_opcoes_visibilidade(
        app_fake,
        app_fake.var_console,
    )

    assert app_fake.var_browser.get() is False
    assert app_fake.var_console.get() is True
    assert len(chamadas) == 1


def test_alerta_producao_aparece_somente_em_producao(app_fake):
    ui.AghuConcessorPerfisApp._atualizar_alerta_ambiente(
        app_fake,
        ui.AMBIENTE_PRODUCAO,
    )
    assert app_fake.frame_alerta_producao.visivel is True

    ui.AghuConcessorPerfisApp._atualizar_alerta_ambiente(
        app_fake,
        ui.AMBIENTE_HOMOLOGACAO,
    )
    assert app_fake.frame_alerta_producao.visivel is False


def test_on_ambiente_changed_exibe_modal_em_producao(app_fake, monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        ui.messagebox,
        "showwarning",
        lambda *args, **kwargs: chamadas.append((args, kwargs)),
    )

    ui.AghuConcessorPerfisApp._on_ambiente_changed(app_fake, ui.AMBIENTE_PRODUCAO)

    assert app_fake.frame_alerta_producao.visivel is True
    assert len(chamadas) == 1
    assert chamadas[0][1]["parent"] is app_fake


def test_on_escopo_changed_atualiza_categorias_e_previa(app_fake):
    ui.AghuConcessorPerfisApp._on_escopo_changed(app_fake, "Escopo A")

    assert app_fake.option_categoria.configuracoes["values"] == [
        "Categoria A",
        "Categoria B",
    ]
    assert app_fake.var_categoria.get() == "Categoria A"
    assert app_fake.option_categoria.configuracoes["set"] == "Categoria A"
    assert "Conceder: PERF01, PERF02" in app_fake.text_perfis.texto


def test_atualizar_previa_perfis_mostra_erro_da_regra(app_fake):
    app_fake.var_escopo.set("erro")

    ui.AghuConcessorPerfisApp._atualizar_previa_perfis(app_fake)

    assert app_fake.text_perfis.texto == "Erro ao carregar regra: regra ausente"
    assert app_fake.text_perfis.configuracoes["state"] == "disabled"


def test_credenciais_e_url_retorna_dados_da_tela(app_fake):
    app_fake.entry_usuario_rede.valor = " tecnico "
    app_fake.entry_senha.valor = " senha "
    app_fake.var_ambiente.set(ui.AMBIENTE_HOMOLOGACAO)

    usuario, senha, url = ui.AghuConcessorPerfisApp._credenciais_e_url(app_fake)

    assert usuario == "tecnico"
    assert senha == " senha "
    assert url == ui.AGHU_URL_HOMOLOGACAO


@pytest.mark.parametrize(
    ("usuario", "senha"),
    [
        ("", "senha"),
        ("   ", "senha"),
        ("tecnico", ""),
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
        ui.AghuConcessorPerfisApp._credenciais_e_url(app_fake)


def test_entrada_concessao_monta_dataclass_com_campos_da_tela(app_fake):
    app_fake.entry_login_alvo.valor = "usuario.teste"
    app_fake.entry_protocolo.valor = "52501301"
    app_fake.var_escopo.set("Escopo A")
    app_fake.var_categoria.set("Categoria A")

    entrada = ui.AghuConcessorPerfisApp._entrada_concessao(app_fake)

    assert entrada == ConcessaoPerfisEntrada(
        login="usuario.teste",
        protocolo="52501301",
        escopo="Escopo A",
        categoria="Categoria A",
    )


def test_bloquear_e_liberar_execucao_alteram_estados(app_fake):
    ui.AghuConcessorPerfisApp._bloquear_execucao(app_fake, "Executando...")

    assert app_fake.em_execucao is True
    assert app_fake.button_executar.configuracoes == {
        "state": "disabled",
        "text": "Executando...",
    }
    assert app_fake.option_categoria.configuracoes["state"] == "disabled"

    ui.AghuConcessorPerfisApp._liberar_execucao(app_fake)

    assert app_fake.em_execucao is False
    assert app_fake.button_executar.configuracoes["state"] == "normal"
    assert app_fake.button_executar.configuracoes["text"].startswith("Executar concess")
    assert app_fake.option_categoria.configuracoes["state"] == "normal"


def test_iniciar_execucao_exibe_erro_quando_entrada_invalida(app_fake, monkeypatch):
    FakeThread.criadas = []
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    app_fake.entry_usuario_rede.valor = "tecnico"
    app_fake.entry_senha.valor = "senha"
    app_fake.entry_login_alvo.valor = "usuario invalido"
    app_fake.entry_protocolo.valor = "abc"

    ui.AghuConcessorPerfisApp.iniciar_execucao(app_fake)

    assert FakeThread.criadas == []
    assert app_fake.label_status.configuracoes["text"].startswith("Erro:")
    assert app_fake.label_status.configuracoes["text_color"] == "red"


def test_iniciar_execucao_inicia_thread_com_dados_validados(app_fake, monkeypatch):
    FakeThread.criadas = []
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    app_fake.entry_usuario_rede.valor = "tecnico"
    app_fake.entry_senha.valor = "senha"
    app_fake.entry_login_alvo.valor = "usuario.teste"
    app_fake.entry_protocolo.valor = "52501301"

    ui.AghuConcessorPerfisApp.iniciar_execucao(app_fake)

    thread = FakeThread.criadas[0]
    assert thread.iniciada is True
    assert thread.daemon is True
    assert thread.target == app_fake._executar_thread
    assert thread.args == (
        "tecnico",
        "senha",
        ConcessaoPerfisEntrada(
            login="usuario.teste",
            protocolo="52501301",
            escopo="Escopo A",
            categoria="Categoria A",
        ),
        ui.AGHU_URL_HOMOLOGACAO,
        True,
        True,
    )
    assert app_fake.label_status.configuracoes["text"].startswith("Executando concess")
    assert app_fake.label_status.configuracoes["text"].endswith(" de perfis...")


def test_iniciar_execucao_lote_inicia_thread_com_dados_validados(
    app_fake,
    monkeypatch,
):
    FakeThread.criadas = []
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    app_fake.var_tipo_execucao.set(ui.TIPO_LOTE)
    app_fake.entry_usuario_rede.valor = "tecnico"
    app_fake.entry_senha.valor = "senha"
    app_fake.entry_planilha_lote.valor = "entrada.xlsx"
    app_fake.entry_relatorio_lote.valor = "saida.xlsx"

    ui.AghuConcessorPerfisApp.iniciar_execucao(app_fake)

    thread = FakeThread.criadas[0]
    assert thread.iniciada is True
    assert thread.daemon is True
    assert thread.target == app_fake._executar_lote_thread
    assert thread.args == (
        "tecnico",
        "senha",
        "entrada.xlsx",
        "saida.xlsx",
        ui.AGHU_URL_HOMOLOGACAO,
        True,
        True,
    )
    assert app_fake.label_status.configuracoes["text"].startswith("Executando lote")


def test_iniciar_execucao_lote_preenche_relatorio_padrao(app_fake, monkeypatch):
    FakeThread.criadas = []
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    monkeypatch.setattr(
        ui,
        "caminho_relatorio_padrao",
        lambda _base="": "relatorio_padrao.xlsx",
    )
    app_fake.var_tipo_execucao.set(ui.TIPO_LOTE)
    app_fake.entry_usuario_rede.valor = "tecnico"
    app_fake.entry_senha.valor = "senha"
    app_fake.entry_planilha_lote.valor = "entrada.xlsx"
    app_fake.entry_relatorio_lote.valor = ""

    ui.AghuConcessorPerfisApp.iniciar_execucao(app_fake)

    assert app_fake.entry_relatorio_lote.valor == "relatorio_padrao.xlsx"
    assert FakeThread.criadas[0].args[3] == "relatorio_padrao.xlsx"


def test_executar_thread_agenda_finalizacao_com_sucesso(app_fake, monkeypatch):
    chamadas = []
    capturados = {}
    resultado_perfil = ResultadoPerfil(
        "usuario.teste",
        "Escopo A",
        "Categoria A",
        "PERF01",
        STATUS_CONCEDIDO,
        "OK",
    )
    resultado = ResultadoConcessao(
        "usuario.teste",
        "52501301",
        "Escopo A",
        "Categoria A",
        STATUS_CONCEDIDO,
        "Total: 1; concedidos: 1.",
        (resultado_perfil,),
    )
    app_fake.after = lambda delay, func, *args: chamadas.append((delay, func, args))

    def executar_fake(**kwargs):
        capturados.update(kwargs)
        return resultado

    monkeypatch.setattr(ui, "executar_concessao_perfis", executar_fake)

    ui.AghuConcessorPerfisApp._executar_thread(
        app_fake,
        "tecnico",
        "senha",
        ConcessaoPerfisEntrada("usuario.teste", "52501301", "Escopo A", "Categoria A"),
        "url",
        False,
        True,
    )

    assert chamadas[0] == (
        0,
        app_fake._finalizar_execucao,
        ("usuario.teste: concedido - Total: 1; concedidos: 1.", "green"),
    )
    assert capturados["mostrar_browser"] is False
    assert capturados["mostrar_console"] is True
    assert capturados["diretorio_logs"] == ui.LOGS_DIR


def test_executar_thread_agenda_finalizacao_vermelha_para_conferir_manual(
    app_fake,
    monkeypatch,
):
    chamadas = []
    resultado = ResultadoConcessao(
        "usuario.teste",
        "52501301",
        "Escopo A",
        "Categoria A",
        STATUS_CONFERIR_MANUAL,
        "Conferir manualmente.",
        (),
    )
    app_fake.after = lambda delay, func, *args: chamadas.append((delay, func, args))
    monkeypatch.setattr(ui, "executar_concessao_perfis", lambda **_kwargs: resultado)

    ui.AghuConcessorPerfisApp._executar_thread(
        app_fake,
        "tecnico",
        "senha",
        ConcessaoPerfisEntrada("usuario.teste", "52501301", "Escopo A", "Categoria A"),
        "url",
        True,
        True,
    )

    assert chamadas[0][2] == (
        "usuario.teste: conferir_manual - Conferir manualmente.",
        "red",
    )


def test_executar_thread_agenda_finalizacao_em_excecao(app_fake, monkeypatch):
    chamadas = []
    app_fake.after = lambda delay, func, *args: chamadas.append((delay, func, args))

    def falhar(**_kwargs):
        raise RuntimeError("falha")

    monkeypatch.setattr(ui, "executar_concessao_perfis", falhar)

    ui.AghuConcessorPerfisApp._executar_thread(
        app_fake,
        "tecnico",
        "senha",
        ConcessaoPerfisEntrada("usuario.teste", "52501301", "Escopo A", "Categoria A"),
        "url",
        True,
        True,
    )

    assert chamadas[0][2] == ("Erro: falha", "red")


def test_executar_lote_thread_agenda_finalizacao_com_resumo(app_fake, monkeypatch):
    chamadas = []
    capturados = {}
    resultado = ResultadoConcessao(
        "usuario.teste",
        "52501301",
        "Escopo A",
        "Categoria A",
        STATUS_CONCEDIDO,
        "Total: 1; concedidos: 1.",
        (),
    )
    app_fake.after = lambda delay, func, *args: chamadas.append((delay, func, args))

    def executar_fake(**kwargs):
        capturados.update(kwargs)
        return [resultado], "saida.xlsx"

    monkeypatch.setattr(ui, "executar_concessao_lote", executar_fake)

    ui.AghuConcessorPerfisApp._executar_lote_thread(
        app_fake,
        "tecnico",
        "senha",
        "entrada.xlsx",
        "saida.xlsx",
        "url",
        False,
        True,
    )

    assert chamadas[0][0] == 0
    assert chamadas[0][1] == app_fake._finalizar_execucao
    assert "Lote concluido. Total: 1." in chamadas[0][2][0]
    assert "Relatorio: saida.xlsx" in chamadas[0][2][0]
    assert chamadas[0][2][1] == "green"
    assert capturados["caminho_planilha"] == "entrada.xlsx"
    assert capturados["caminho_relatorio"] == "saida.xlsx"
    assert capturados["mostrar_browser"] is False
    assert capturados["mostrar_console"] is True
