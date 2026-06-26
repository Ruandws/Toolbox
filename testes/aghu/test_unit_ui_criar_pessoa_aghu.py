from datetime import datetime
from pathlib import Path

import pytest

import ui_criar_pessoa_aghu as ui
from cadastro_pessoa_aghu import (
    CadastroPessoaEntrada,
    ResultadoCadastroPessoa,
    STATUS_ATUALIZADO,
    STATUS_CONFERIR_MANUAL,
    STATUS_CRIADO,
    STATUS_ERRO,
    STATUS_IGNORADO,
    STATUS_MANTIDO,
)


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


class FakeFrame:
    def __init__(self):
        self.visivel = False
        self.grid_args = None

    def grid(self, **kwargs):
        self.visivel = True
        self.grid_args = kwargs

    def grid_remove(self):
        self.visivel = False


class FakeVar:
    def __init__(self, valor):
        self.valor = valor

    def get(self):
        return self.valor

    def set(self, valor):
        self.valor = valor


class FakeButton(FakeWidget):
    pass


class FakeSegment(FakeWidget):
    def __init__(self, valores):
        super().__init__()
        self._buttons_dict = {valor: FakeButton() for valor in valores}


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
        return datetime(2026, 6, 26, 9, 8, 7)


CAMINHO_TMP_TESTE = Path("C:/Extrator2/testes/aghu")


@pytest.fixture()
def app_fake():
    app = object.__new__(ui.AghuCadastroPessoaApp)
    app.em_execucao = False
    app.var_ambiente = FakeVar(ui.AMBIENTE_PRODUCAO)
    app.var_tipo_execucao = FakeVar(ui.TIPO_INDIVIDUAL)
    app.var_browser = FakeVar(True)
    app.var_console = FakeVar(True)
    app.var_sexo = FakeVar(ui.SEXO_MASCULINO)
    app.entry_usuario_rede = FakeEntry()
    app.entry_senha = FakeEntry()
    app.entry_planilha_lote = FakeEntry()
    app.entry_relatorio_lote = FakeEntry()
    app.entries_individual = {
        nome_campo: FakeEntry()
        for nome_campo, _label, _placeholder in ui.CAMPOS_PESSOA
        if nome_campo != "sexo"
    }
    app.button_executar = FakeWidget()
    app.segment_tipo_execucao = FakeSegment([ui.TIPO_INDIVIDUAL, ui.TIPO_LOTE])
    app.segment_sexo = FakeSegment(list(ui.OPCOES_SEXO))
    app.checkbox_browser = FakeWidget()
    app.checkbox_console = FakeWidget()
    app.option_ambiente = FakeWidget()
    app.button_planilha_lote = FakeWidget()
    app.button_relatorio_lote = FakeWidget()
    app.label_status = FakeWidget()
    app.frame_individual = FakeFrame()
    app.frame_lote = FakeFrame()
    app.frame_alerta_producao = FakeFrame()
    return app


@pytest.fixture()
def caminho_tmp_teste():
    return CAMINHO_TMP_TESTE


def preencher_cadastro_individual(app, **sobrescritas):
    dados = {
        "nome_pessoa": " Joao Silva ",
        "nome_mae": " Maria Silva ",
        "data_nascimento": " 01/01/1990 ",
        "nacionalidade": " Brasileira ",
        "naturalidade": " Brasilia/DF ",
        "rg": " 123456 ",
        "orgao_emissor": " SSP ",
        "uf_rg": " DF ",
        "cpf": " 123.456.789-01 ",
        "ddd": " 61 ",
        "telefone_celular": " 999999999 ",
        "cep_cadastrado": " 70000-000 ",
        "logradouro_nao_cadastrado": " Rua A ",
        "bairro_nao_cadastrado": " Centro ",
        "cep_nao_cadastrado": " 71000-000 ",
        "municipio_nao_cadastrado": " Brasilia ",
    }
    dados.update(sobrescritas)
    for campo, valor in dados.items():
        app.entries_individual[campo].valor = valor
    return dados


def test_obter_url_ambiente_aghu_retorna_urls_conhecidas():
    assert ui.obter_url_ambiente_aghu(ui.AMBIENTE_PRODUCAO) == ui.AGHU_URL
    assert (
        ui.obter_url_ambiente_aghu(ui.AMBIENTE_HOMOLOGACAO)
        == ui.AGHU_URL_HOMOLOGACAO
    )


def test_obter_url_ambiente_aghu_usa_producao_com_ambiente_desconhecido():
    assert ui.obter_url_ambiente_aghu("desconhecido") == ui.AGHU_URL


def test_caminho_relatorio_padrao_usa_cwd_sem_base(monkeypatch, caminho_tmp_teste):
    monkeypatch.setattr(ui, "datetime", FixedDatetime)
    monkeypatch.chdir(caminho_tmp_teste)

    caminho = Path(ui.caminho_relatorio_padrao())

    assert caminho == (
        caminho_tmp_teste / "relatorio_cadastro_pessoas_20260626_090807.xlsx"
    )


def test_caminho_relatorio_padrao_usa_diretorio_pai_quando_base_e_arquivo(
    monkeypatch,
    caminho_tmp_teste,
):
    monkeypatch.setattr(ui, "datetime", FixedDatetime)

    caminho = Path(ui.caminho_relatorio_padrao(str(caminho_tmp_teste / "entrada.xlsx")))

    assert caminho == (
        caminho_tmp_teste / "relatorio_cadastro_pessoas_20260626_090807.xlsx"
    )


def test_caminho_relatorio_padrao_usa_base_quando_base_e_diretorio(
    monkeypatch,
    caminho_tmp_teste,
):
    monkeypatch.setattr(ui, "datetime", FixedDatetime)

    caminho = Path(ui.caminho_relatorio_padrao(str(caminho_tmp_teste)))

    assert caminho == (
        caminho_tmp_teste / "relatorio_cadastro_pessoas_20260626_090807.xlsx"
    )


def test_atualizar_tipo_execucao_mostra_frame_individual(app_fake):
    ui.AghuCadastroPessoaApp._atualizar_tipo_execucao(
        app_fake,
        ui.TIPO_INDIVIDUAL,
    )

    assert app_fake.frame_individual.visivel is True
    assert app_fake.frame_lote.visivel is False
    assert (
        app_fake.segment_tipo_execucao._buttons_dict[ui.TIPO_INDIVIDUAL]
        .configuracoes["text_color"]
        == "white"
    )


def test_atualizar_tipo_execucao_mostra_frame_lote(app_fake):
    ui.AghuCadastroPessoaApp._atualizar_tipo_execucao(app_fake, ui.TIPO_LOTE)

    assert app_fake.frame_individual.visivel is False
    assert app_fake.frame_lote.visivel is True
    assert (
        app_fake.segment_tipo_execucao._buttons_dict[ui.TIPO_LOTE]
        .configuracoes["text_color"]
        == "white"
    )


def test_atualizar_visual_sexo_ignora_segmento_ausente(app_fake):
    app_fake.segment_sexo = None

    ui.AghuCadastroPessoaApp._atualizar_visual_sexo(app_fake, ui.SEXO_FEMININO)


def test_atualizar_visual_segmented_button_destaca_valor_selecionado(app_fake):
    ui.AghuCadastroPessoaApp._atualizar_visual_segmented_button(
        app_fake,
        app_fake.segment_sexo,
        ui.SEXO_FEMININO,
    )

    assert (
        app_fake.segment_sexo._buttons_dict[ui.SEXO_FEMININO]
        .configuracoes["text_color"]
        == "white"
    )


def test_alerta_de_producao_aparece_somente_em_producao(app_fake):
    ui.AghuCadastroPessoaApp._atualizar_alerta_ambiente(
        app_fake,
        ui.AMBIENTE_PRODUCAO,
    )
    assert app_fake.frame_alerta_producao.visivel is True

    ui.AghuCadastroPessoaApp._atualizar_alerta_ambiente(
        app_fake,
        ui.AMBIENTE_HOMOLOGACAO,
    )
    assert app_fake.frame_alerta_producao.visivel is False


def test_on_ambiente_changed_exibe_alerta_modal_em_producao(app_fake, monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        ui.messagebox,
        "showwarning",
        lambda *args, **kwargs: chamadas.append((args, kwargs)),
    )

    ui.AghuCadastroPessoaApp._on_ambiente_changed(app_fake, ui.AMBIENTE_PRODUCAO)

    assert app_fake.frame_alerta_producao.visivel is True
    assert len(chamadas) == 1
    assert ui.AMBIENTE_PRODUCAO in chamadas[0][0][0]
    assert chamadas[0][1]["parent"] is app_fake


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

    ui.AghuCadastroPessoaApp._on_ambiente_changed(app_fake, ui.AMBIENTE_HOMOLOGACAO)

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

    ui.AghuCadastroPessoaApp._validar_opcoes_visibilidade(
        app_fake,
        app_fake.var_browser,
    )

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

    ui.AghuCadastroPessoaApp._validar_opcoes_visibilidade(
        app_fake,
        app_fake.var_console,
    )

    assert app_fake.var_browser.get() is False
    assert app_fake.var_console.get() is True
    assert len(chamadas) == 1


def test_credenciais_e_url_retorna_dados_normalizados(app_fake):
    app_fake.entry_usuario_rede.valor = " usuario.rede "
    app_fake.entry_senha.valor = " senha com espaco "
    app_fake.var_ambiente.set(ui.AMBIENTE_HOMOLOGACAO)

    usuario, senha, url = ui.AghuCadastroPessoaApp._credenciais_e_url(app_fake)

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
        ui.AghuCadastroPessoaApp._credenciais_e_url(app_fake)


def test_cadastro_individual_coleta_campos_e_sexo(app_fake):
    preencher_cadastro_individual(app_fake)
    app_fake.var_sexo.set(ui.SEXO_FEMININO)

    cadastro = ui.AghuCadastroPessoaApp._cadastro_individual(app_fake)

    assert isinstance(cadastro, CadastroPessoaEntrada)
    assert cadastro.nome_pessoa == "Joao Silva"
    assert cadastro.nome_mae == "Maria Silva"
    assert cadastro.sexo == ui.SEXO_FEMININO
    assert cadastro.cpf == "123.456.789-01"


def test_cadastro_individual_rejeita_sexo_invalido(app_fake):
    preencher_cadastro_individual(app_fake)
    app_fake.var_sexo.set("Outro")

    with pytest.raises(ValueError, match="sexo"):
        ui.AghuCadastroPessoaApp._cadastro_individual(app_fake)


def test_selecionar_planilha_lote_nao_altera_campos_quando_cancelado(
    app_fake,
    monkeypatch,
):
    app_fake.entry_planilha_lote.valor = "antes.xlsx"
    app_fake.entry_relatorio_lote.valor = ""
    monkeypatch.setattr(ui.filedialog, "askopenfilename", lambda **kwargs: "")

    ui.AghuCadastroPessoaApp.selecionar_planilha_lote(app_fake)

    assert app_fake.entry_planilha_lote.get() == "antes.xlsx"
    assert app_fake.entry_relatorio_lote.get() == ""


def test_selecionar_planilha_lote_preenche_planilha_e_relatorio_padrao(
    app_fake,
    monkeypatch,
    caminho_tmp_teste,
):
    planilha = caminho_tmp_teste / "pessoas.xlsx"
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

    ui.AghuCadastroPessoaApp.selecionar_planilha_lote(app_fake)

    assert app_fake.entry_planilha_lote.get() == str(planilha)
    assert app_fake.entry_relatorio_lote.get() == str(
        caminho_tmp_teste / "relatorio.xlsx"
    )


def test_selecionar_planilha_lote_nao_sobrescreve_relatorio_existente(
    app_fake,
    monkeypatch,
    caminho_tmp_teste,
):
    app_fake.entry_relatorio_lote.valor = "relatorio_existente.xlsx"
    monkeypatch.setattr(
        ui.filedialog,
        "askopenfilename",
        lambda **kwargs: str(caminho_tmp_teste / "pessoas.xlsx"),
    )

    ui.AghuCadastroPessoaApp.selecionar_planilha_lote(app_fake)

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

    ui.AghuCadastroPessoaApp.selecionar_relatorio_lote(app_fake)

    assert app_fake.entry_relatorio_lote.get() == str(caminho)


def test_bloquear_e_liberar_execucao_alteram_estados(app_fake):
    ui.AghuCadastroPessoaApp._bloquear_execucao(app_fake, "Executando...")

    assert app_fake.em_execucao is True
    assert app_fake.button_executar.configuracoes["state"] == "disabled"
    assert app_fake.button_executar.configuracoes["text"] == "Executando..."
    assert app_fake.segment_tipo_execucao.configuracoes["state"] == "disabled"
    assert app_fake.checkbox_browser.configuracoes["state"] == "disabled"
    assert app_fake.checkbox_console.configuracoes["state"] == "disabled"
    assert app_fake.option_ambiente.configuracoes["state"] == "disabled"
    assert app_fake.button_planilha_lote.configuracoes["state"] == "disabled"
    assert app_fake.button_relatorio_lote.configuracoes["state"] == "disabled"

    ui.AghuCadastroPessoaApp._liberar_execucao(app_fake)

    assert app_fake.em_execucao is False
    assert app_fake.button_executar.configuracoes["state"] == "normal"
    assert app_fake.button_executar.configuracoes["text"] == "Executar cadastro"
    assert app_fake.segment_tipo_execucao.configuracoes["state"] == "normal"
    assert app_fake.checkbox_browser.configuracoes["state"] == "normal"
    assert app_fake.checkbox_console.configuracoes["state"] == "normal"
    assert app_fake.option_ambiente.configuracoes["state"] == "normal"
    assert app_fake.button_planilha_lote.configuracoes["state"] == "normal"
    assert app_fake.button_relatorio_lote.configuracoes["state"] == "normal"


def test_iniciar_execucao_despacha_conforme_tipo(app_fake, monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        ui.AghuCadastroPessoaApp,
        "iniciar_execucao_individual",
        lambda self: chamadas.append("individual"),
    )
    monkeypatch.setattr(
        ui.AghuCadastroPessoaApp,
        "iniciar_execucao_lote",
        lambda self: chamadas.append("lote"),
    )

    app_fake.var_tipo_execucao.set(ui.TIPO_INDIVIDUAL)
    ui.AghuCadastroPessoaApp.iniciar_execucao(app_fake)
    app_fake.var_tipo_execucao.set(ui.TIPO_LOTE)
    ui.AghuCadastroPessoaApp.iniciar_execucao(app_fake)

    assert chamadas == ["individual", "lote"]


def test_iniciar_execucao_individual_nao_faz_nada_se_ja_em_execucao(
    app_fake,
    monkeypatch,
):
    app_fake.em_execucao = True
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    FakeThread.criadas = []

    ui.AghuCadastroPessoaApp.iniciar_execucao_individual(app_fake)

    assert FakeThread.criadas == []


def test_iniciar_execucao_individual_mostra_erro_sem_credenciais(app_fake):
    ui.AghuCadastroPessoaApp.iniciar_execucao_individual(app_fake)

    assert app_fake.label_status.configuracoes["text"].startswith("Erro:")
    assert app_fake.label_status.configuracoes["text_color"] == "red"


def test_iniciar_execucao_individual_inicia_thread_com_dados_da_tela(
    app_fake,
    monkeypatch,
):
    FakeThread.criadas = []
    monkeypatch.setattr(ui.threading, "Thread", FakeThread)
    app_fake.entry_usuario_rede.valor = " usuario "
    app_fake.entry_senha.valor = "senha"
    preencher_cadastro_individual(app_fake)

    ui.AghuCadastroPessoaApp.iniciar_execucao_individual(app_fake)

    thread = FakeThread.criadas[0]
    cadastro = CadastroPessoaEntrada(
        nome_pessoa="Joao Silva",
        nome_mae="Maria Silva",
        sexo=ui.SEXO_MASCULINO,
        data_nascimento="01/01/1990",
        nacionalidade="Brasileira",
        naturalidade="Brasilia/DF",
        rg="123456",
        orgao_emissor="SSP",
        uf_rg="DF",
        cpf="123.456.789-01",
        ddd="61",
        telefone_celular="999999999",
        cep_cadastrado="70000-000",
        logradouro_nao_cadastrado="Rua A",
        bairro_nao_cadastrado="Centro",
        cep_nao_cadastrado="71000-000",
        municipio_nao_cadastrado="Brasilia",
    )

    assert thread.iniciada is True
    assert thread.daemon is True
    assert thread.target == app_fake._executar_individual_thread
    assert thread.args == (
        "usuario",
        "senha",
        cadastro,
        ui.AGHU_URL,
        True,
        True,
    )
    assert app_fake.label_status.configuracoes["text"] == (
        "Executando cadastro individual..."
    )
    assert app_fake.button_executar.configuracoes["state"] == "disabled"


def test_iniciar_execucao_lote_valida_planilha_obrigatoria(app_fake):
    app_fake.entry_usuario_rede.valor = "usuario"
    app_fake.entry_senha.valor = "senha"

    ui.AghuCadastroPessoaApp.iniciar_execucao_lote(app_fake)

    assert app_fake.label_status.configuracoes["text"] == (
        "Erro: Informe a planilha .xlsx de lote."
    )
    assert app_fake.label_status.configuracoes["text_color"] == "red"


def test_iniciar_execucao_lote_valida_extensao_planilha_xlsx(app_fake):
    app_fake.entry_usuario_rede.valor = "usuario"
    app_fake.entry_senha.valor = "senha"
    app_fake.entry_planilha_lote.valor = "pessoas.csv"

    ui.AghuCadastroPessoaApp.iniciar_execucao_lote(app_fake)

    assert app_fake.label_status.configuracoes["text"] == (
        "Erro: A planilha de lote deve ser um arquivo .xlsx."
    )


def test_iniciar_execucao_lote_valida_extensao_relatorio_xlsx(app_fake):
    app_fake.entry_usuario_rede.valor = "usuario"
    app_fake.entry_senha.valor = "senha"
    app_fake.entry_planilha_lote.valor = "pessoas.xlsx"
    app_fake.entry_relatorio_lote.valor = "saida.csv"

    ui.AghuCadastroPessoaApp.iniciar_execucao_lote(app_fake)

    assert app_fake.label_status.configuracoes["text"].startswith("Erro:")
    assert app_fake.label_status.configuracoes["text"].endswith(
        "deve ser um arquivo .xlsx."
    )


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
    app_fake.entry_planilha_lote.valor = "pessoas.xlsx"

    ui.AghuCadastroPessoaApp.iniciar_execucao_lote(app_fake)

    thread = FakeThread.criadas[0]
    assert thread.iniciada is True
    assert app_fake.entry_relatorio_lote.get() == "relatorio_gerado.xlsx"
    assert thread.args == (
        "usuario",
        "senha",
        "pessoas.xlsx",
        "relatorio_gerado.xlsx",
        ui.AGHU_URL,
        True,
        True,
    )


def test_resumir_resultados_conta_status_conhecidos(app_fake):
    resultados = [
        ResultadoCadastroPessoa("1", "A", STATUS_CRIADO, "ok"),
        ResultadoCadastroPessoa("2", "B", STATUS_ATUALIZADO, "ok"),
        ResultadoCadastroPessoa("3", "C", STATUS_MANTIDO, "ok"),
        ResultadoCadastroPessoa("4", "D", STATUS_CONFERIR_MANUAL, "ok"),
        ResultadoCadastroPessoa("5", "E", STATUS_IGNORADO, "ok"),
        ResultadoCadastroPessoa("6", "F", STATUS_ERRO, "ok"),
    ]

    resumo = ui.AghuCadastroPessoaApp._resumir_resultados(app_fake, resultados)

    assert "Lote conclu" in resumo
    assert "Total: 6." in resumo
    assert "Criados: 1." in resumo
    assert "Atualizados: 1." in resumo
    assert "Mantidos: 1." in resumo
    assert "Conferir manualmente: 1." in resumo
    assert "Ignorados: 1." in resumo
    assert "Erros: 1." in resumo


def test_executar_individual_thread_agenda_finalizacao_em_sucesso(
    app_fake,
    monkeypatch,
):
    resultado = ResultadoCadastroPessoa(
        cpf="12345678901",
        nome_pessoa="Joao",
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

    cadastro = CadastroPessoaEntrada(nome_pessoa="Joao", cpf="12345678901")
    ui.AghuCadastroPessoaApp._executar_individual_thread(
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
        ("12345678901: criado - OK", "green"),
    )
    assert capturados["cadastro"] == cadastro
    assert capturados["url_aghu"] == "url"
    assert capturados["mostrar_browser"] is False
    assert capturados["mostrar_console"] is True
    assert capturados["diretorio_logs"] == ui.LOGS_DIR


def test_executar_individual_thread_agenda_finalizacao_em_resultado_ignorado(
    app_fake,
    monkeypatch,
):
    resultado = ResultadoCadastroPessoa(
        cpf="",
        nome_pessoa="Joao",
        status=STATUS_IGNORADO,
        detalhes="dados invalidos",
    )
    chamadas = []
    app_fake.after = lambda delay, func, *args: chamadas.append((delay, func, args))
    monkeypatch.setattr(ui, "executar_cadastro_individual", lambda **kwargs: resultado)

    ui.AghuCadastroPessoaApp._executar_individual_thread(
        app_fake,
        "usuario",
        "senha",
        CadastroPessoaEntrada(nome_pessoa="Joao"),
        "url",
        True,
        True,
    )

    assert chamadas[0][2] == ("Joao: ignorado - dados invalidos", "red")


def test_executar_individual_thread_agenda_finalizacao_em_excecao(
    app_fake,
    monkeypatch,
):
    chamadas = []
    app_fake.after = lambda delay, func, *args: chamadas.append((delay, func, args))

    def falhar(**kwargs):
        raise RuntimeError("falha")

    monkeypatch.setattr(ui, "executar_cadastro_individual", falhar)

    ui.AghuCadastroPessoaApp._executar_individual_thread(
        app_fake,
        "usuario",
        "senha",
        CadastroPessoaEntrada(),
        "url",
        True,
        True,
    )

    assert chamadas[0][2] == ("Erro: falha", "red")


def test_executar_lote_thread_agenda_finalizacao_com_resumo(
    app_fake,
    monkeypatch,
):
    resultados = [ResultadoCadastroPessoa("1", "Joao", STATUS_CRIADO, "OK")]
    chamadas = []
    capturados = {}
    app_fake.after = lambda delay, func, *args: chamadas.append((delay, func, args))

    def executar_fake(**kwargs):
        capturados.update(kwargs)
        return resultados, Path("relatorio.xlsx")

    monkeypatch.setattr(ui, "executar_cadastro_lote", executar_fake)

    ui.AghuCadastroPessoaApp._executar_lote_thread(
        app_fake,
        "usuario",
        "senha",
        "pessoas.xlsx",
        "relatorio.xlsx",
        "url",
        False,
        True,
    )

    assert chamadas[0][0] == 0
    assert chamadas[0][1] == app_fake._finalizar_execucao
    mensagem, cor = chamadas[0][2]
    assert "Lote conclu" in mensagem
    assert "Total: 1." in mensagem
    assert "Criados: 1." in mensagem
    assert "Atualizados: 0." in mensagem
    assert "Mantidos: 0." in mensagem
    assert "Conferir manualmente: 0." in mensagem
    assert "Ignorados: 0." in mensagem
    assert "Erros: 0." in mensagem
    assert "relatorio.xlsx" in mensagem
    assert cor == "green"
    assert capturados["url_aghu"] == "url"
    assert capturados["mostrar_browser"] is False
    assert capturados["mostrar_console"] is True
    assert capturados["diretorio_logs"] == ui.LOGS_DIR


def test_executar_lote_thread_agenda_finalizacao_em_excecao(app_fake, monkeypatch):
    chamadas = []
    app_fake.after = lambda delay, func, *args: chamadas.append((delay, func, args))

    def falhar(**kwargs):
        raise RuntimeError("falha lote")

    monkeypatch.setattr(ui, "executar_cadastro_lote", falhar)

    ui.AghuCadastroPessoaApp._executar_lote_thread(
        app_fake,
        "usuario",
        "senha",
        "pessoas.xlsx",
        "relatorio.xlsx",
        "url",
        True,
        True,
    )

    assert chamadas[0][2] == ("Erro: falha lote", "red")


def test_finalizar_execucao_mostra_status_e_libera(app_fake):
    ui.AghuCadastroPessoaApp._bloquear_execucao(app_fake, "Executando...")

    ui.AghuCadastroPessoaApp._finalizar_execucao(app_fake, "feito", "green")

    assert app_fake.label_status.configuracoes == {
        "text": "feito",
        "text_color": "green",
    }
    assert app_fake.em_execucao is False
