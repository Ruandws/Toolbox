import builtins
from pathlib import Path

import pandas as pd
import pytest

import PrinterAGHU as printer_aghu


class FluentLocator:
    def __init__(
        self,
        *,
        text="",
        value="",
        fail_wait=False,
        fail_click=False,
        fail_clear=False,
    ):
        self.first = self
        self.last = self
        self.text = text
        self.value = value
        self.fail_wait = fail_wait
        self.fail_click = fail_click
        self.fail_clear = fail_clear
        self.calls = []
        self.clicks = []
        self.presses = []
        self.cleared = False

    def locator(self, selector):
        self.calls.append(("locator", selector))
        return self

    def filter(self, **kwargs):
        self.calls.append(("filter", kwargs))
        return self

    def click(self, *args, **kwargs):
        self.clicks.append((args, kwargs))
        if self.fail_click:
            raise RuntimeError("click falhou")

    def clear(self):
        self.cleared = True
        if self.fail_clear:
            raise RuntimeError("clear falhou")

    def press_sequentially(self, texto, delay=None):
        self.presses.append((texto, delay))

    def wait_for(self, *args, **kwargs):
        self.calls.append(("wait_for", args, kwargs))
        if self.fail_wait:
            raise RuntimeError("elemento indisponivel")

    def inner_text(self, *args, **kwargs):
        return self.text

    def input_value(self, *args, **kwargs):
        return self.value


class JanelaFake:
    def __init__(self, *, locators=None, roles=None):
        self.locators = locators or {}
        self.roles = roles or {}
        self.locator_calls = []
        self.role_calls = []

    def locator(self, selector):
        self.locator_calls.append(selector)
        locator = self.locators.get(selector, FluentLocator())

        if isinstance(locator, list):
            return locator.pop(0)

        return locator

    def get_by_role(self, role, name=None):
        self.role_calls.append((role, name))
        return self.roles.get((role, name), FluentLocator())


@pytest.fixture(autouse=True)
def _silenciar_print(monkeypatch):
    monkeypatch.setattr(builtins, "print", lambda *args, **kwargs: None)


@pytest.fixture()
def dados_planilha():
    return printer_aghu.DadosLinhaPlanilha(
        ip_pc="10.0.0.10",
        impressora_alvo="fila-impressora",
        classe_impressao="PDF",
    )


def test_dataclasses_sao_imutaveis():
    dados = printer_aghu.DadosLinhaPlanilha(
        ip_pc="10.0.0.10",
        impressora_alvo="fila",
        classe_impressao="PDF",
    )
    resultado = printer_aghu.ResultadoLinha(status="Erro", detalhes="x")
    acao = printer_aghu.AcaoVinculo(tipo="incluir")

    with pytest.raises(AttributeError):
        dados.ip_pc = "10.0.0.99"  # type: ignore[misc]

    with pytest.raises(AttributeError):
        resultado.status = "OK"  # type: ignore[misc]

    with pytest.raises(AttributeError):
        acao.tipo = "alterar"  # type: ignore[misc]


def test_falha_tecnica_processamento_preserva_passo_e_erro():
    erro_original = RuntimeError("browser travou")
    erro = printer_aghu.FalhaTecnicaProcessamento("Pesquisando", erro_original)

    assert str(erro) == "browser travou"
    assert erro.passo == "Pesquisando"
    assert erro.erro is erro_original


def test_extrair_dados_linha_planilha_remove_espacos():
    linha = pd.Series(
        {
            "IPPC": " 10.0.0.10 ",
            "HostPrinter": " fila-impressora ",
            "PrinterClass": " PDF ",
        }
    )

    assert printer_aghu._extrair_dados_linha_planilha(linha) == (
        printer_aghu.DadosLinhaPlanilha(
            ip_pc="10.0.0.10",
            impressora_alvo="fila-impressora",
            classe_impressao="PDF",
        )
    )


def test_numero_linha_planilha_converte_indice_zero_based():
    assert printer_aghu._numero_linha_planilha("4") == 5


def test_criar_log_linha_monta_colunas_do_relatorio():
    linha = pd.Series(
        {
            "HostPC": "pc-01",
            "IPPrinter": "10.0.0.20",
        }
    )
    dados = printer_aghu.DadosLinhaPlanilha(
        ip_pc="10.0.0.10",
        impressora_alvo="fila-impressora",
        classe_impressao="PDF",
    )
    resultado = printer_aghu.ResultadoLinha(
        status="Mantido",
        detalhes="Impressora ja estava correta.",
    )

    assert printer_aghu._criar_log_linha(linha, dados, resultado) == {
        "HostPC": "pc-01",
        "IPPC": "10.0.0.10",
        "HostPrinter": "fila-impressora",
        "IPPrinter": "10.0.0.20",
        "PrinterClass": "PDF",
        "Status": "Mantido",
        "Detalhes": "Impressora ja estava correta.",
    }


def test_gerar_csv_logs_escreve_cabecalho_de_auditoria(tmp_path, monkeypatch):
    monkeypatch.setattr(builtins, "print", lambda *args, **kwargs: None)
    logs = [
        {
            "HostPC": "pc-01",
            "IPPC": "10.0.0.10",
            "HostPrinter": "fila-impressora",
            "IPPrinter": "10.0.0.20",
            "PrinterClass": "PDF",
            "Status": "Mantido",
            "Detalhes": "ok",
        }
    ]

    caminho_csv = printer_aghu._gerar_csv_logs(
        logs_do_diario=logs,
        usuario_str="operador",
        diretorio_logs=tmp_path,
    )

    conteudo = pd.read_csv(caminho_csv, sep=";", skiprows=1, encoding="utf-8-sig")
    texto = Path(caminho_csv).read_text(encoding="utf-8-sig")

    assert texto.startswith("Atualizado por: operador\n")
    assert conteudo.iloc[0].to_dict() == logs[0]


def test_processar_linha_reexecuta_apos_cadastrar_impressora(monkeypatch):
    page_inicial = object()
    janela_inicial = object()
    dados = printer_aghu.DadosLinhaPlanilha(
        ip_pc="10.0.0.10",
        impressora_alvo="fila-impressora",
        classe_impressao="PDF",
    )
    chamadas_processamento = []

    def fake_processar_linha_aghu(
        janela_sistema,
        page,
        dados,
        impressora_fabricada_agora,
    ):
        chamadas_processamento.append(impressora_fabricada_agora)

        if len(chamadas_processamento) == 1:
            raise ValueError("Impressora não existe")

        return printer_aghu.ResultadoLinha(
            status="Criado" if impressora_fabricada_agora else "Alterado",
            detalhes="ok",
        )

    def fake_tratar_impressora_inexistente(**kwargs):
        return (
            True,
            printer_aghu.ResultadoLinha(status="Erro", detalhes="Falha Desconhecida."),
            page_inicial,
            janela_inicial,
        )

    monkeypatch.setattr(
        printer_aghu,
        "_processar_linha_aghu",
        fake_processar_linha_aghu,
    )
    monkeypatch.setattr(
        printer_aghu,
        "_tratar_impressora_inexistente",
        fake_tratar_impressora_inexistente,
    )

    resultado, page_final, janela_final = printer_aghu._processar_linha_com_retentativas(
        context=object(),
        page=page_inicial,
        janela_sistema=janela_inicial,
        usuario_str="usuario",
        senha_str="senha",
        dados=dados,
        url_aghu="https://aghu.example",
    )

    assert chamadas_processamento == [False, True]
    assert resultado.status == "Criado"
    assert page_final is page_inicial
    assert janela_final is janela_inicial


def test_registrar_linha_ignorada_retorna_resultado_padrao():
    resultado = printer_aghu._registrar_linha_ignorada(
        index=1,
        total_linhas=3,
        campos_em_branco=["IPPC", "HostPrinter"],
    )

    assert resultado.status == "Erro"
    assert resultado.detalhes == (
        "Linha ignorada: campos obrigatorios em branco: IPPC, HostPrinter."
    )


def test_clicar_limpar_formulario_aciona_botao_limpar():
    botao_limpar = FluentLocator()
    janela = JanelaFake(
        locators={"button:has(.aghu-icon-cleaner-aghu)": botao_limpar}
    )

    printer_aghu._clicar_limpar_formulario(janela)

    assert botao_limpar.clicks


def test_selecionar_computador_no_formulario_preenche_e_clica_sugestao():
    campo = FluentLocator()
    sugestao = FluentLocator(text="PC 10.0.0.10")
    janela = JanelaFake(
        locators={
            "input[id*='computador' i], input.ui-autocomplete-input": campo,
            "tr, li, td, span": sugestao,
        }
    )

    campo_retorno, texto = printer_aghu._selecionar_computador_no_formulario(
        janela,
        "10.0.0.10",
        capturar_texto=True,
    )

    assert campo_retorno is campo
    assert texto == "PC 10.0.0.10"
    assert campo.cleared is True
    assert campo.presses == [("10.0.0.10", 150)]
    assert sugestao.clicks


def test_selecionar_computador_no_formulario_converte_falha_em_value_error():
    janela = JanelaFake(
        locators={
            "input[id*='computador' i], input.ui-autocomplete-input": FluentLocator(),
            "tr, li, td, span": FluentLocator(fail_wait=True),
        }
    )

    with pytest.raises(ValueError, match="Computador"):
        printer_aghu._selecionar_computador_no_formulario(janela, "10.0.0.10")


def test_buscar_computador_no_formulario_delega_selecao(monkeypatch):
    chamadas = []

    def fake_selecionar(janela_sistema, ip_pc):
        chamadas.append((janela_sistema, ip_pc))

    monkeypatch.setattr(
        printer_aghu,
        "_selecionar_computador_no_formulario",
        fake_selecionar,
    )
    janela = object()

    printer_aghu._buscar_computador_no_formulario(janela, "10.0.0.10")

    assert chamadas == [(janela, "10.0.0.10")]


def test_pesquisar_vinculos_computador_clica_e_coleta(monkeypatch):
    botao_pesquisar = FluentLocator()
    janela = JanelaFake(roles={("button", "Pesquisar"): botao_pesquisar})

    def fake_coletar(**kwargs):
        assert kwargs == {"janela_sistema": janela, "ip_pc": "10.0.0.10"}
        return "linhas", [{"ip": "10.0.0.10"}]

    monkeypatch.setattr(printer_aghu, "_coletar_linhas_computador", fake_coletar)

    assert printer_aghu._pesquisar_vinculos_computador(janela, "10.0.0.10") == (
        "linhas",
        [{"ip": "10.0.0.10"}],
    )
    assert botao_pesquisar.clicks


def test_selecionar_impressora_no_formulario_preenche_e_clica_sugestao():
    campo = FluentLocator()
    sugestao = FluentLocator()
    janela = JanelaFake(
        locators={
            "input[id*='impressora' i]": campo,
            "li, td, span": sugestao,
        }
    )

    printer_aghu._selecionar_impressora_no_formulario(janela, "fila-impressora")

    assert campo.cleared is True
    assert campo.presses == [("fila-impressora", 150)]
    assert sugestao.clicks


def test_selecionar_impressora_no_formulario_converte_falha_em_value_error():
    janela = JanelaFake(
        locators={
            "input[id*='impressora' i]": FluentLocator(),
            "li, td, span": FluentLocator(fail_wait=True),
        }
    )

    with pytest.raises(ValueError, match="Impressora"):
        printer_aghu._selecionar_impressora_no_formulario(janela, "fila")


def test_selecionar_classe_vinculo_nao_altera_quando_classe_ja_confere():
    campo_classe = FluentLocator(value="Classe A")
    janela = JanelaFake(
        locators={
            "input[id*='classe' i], input[id*='impressao' i]": campo_classe,
        }
    )

    printer_aghu._selecionar_classe_vinculo(janela, "PDF")

    assert "button:has(.ui-icon-triangle-1-s)" not in janela.locator_calls


def test_selecionar_classe_vinculo_limpa_e_escolhe_classe_aghu():
    campo_classe = FluentLocator(value="B")
    botao_limpar = FluentLocator()
    botao_lupa = FluentLocator()
    opcao_classe = FluentLocator()
    janela = JanelaFake(
        locators={
            "input[id*='classe' i], input[id*='impressao' i]": campo_classe,
            "button:has(.aghu-icon-cleaner-aghu)": botao_limpar,
            "button:has(.ui-icon-triangle-1-s)": botao_lupa,
            "li, td, span": opcao_classe,
        }
    )

    printer_aghu._selecionar_classe_vinculo(janela, "PDF")

    assert botao_limpar.clicks
    assert botao_lupa.clicks
    assert opcao_classe.clicks


def test_avaliar_pesquisa_vinculos_indefinida_limpa_e_retorna_erro(
    monkeypatch,
    dados_planilha,
):
    chamadas_limpeza = []
    monkeypatch.setattr(
        printer_aghu,
        "_limpar_estado_formulario",
        lambda janela, page: chamadas_limpeza.append((janela, page)),
    )
    janela = object()
    page = object()

    resultado, acao = printer_aghu._avaliar_pesquisa_vinculos(
        janela_sistema=janela,
        page=page,
        dados=dados_planilha,
        estado_pesquisa="indefinido",
        registros_linhas=[],
    )

    assert resultado == printer_aghu.ResultadoLinha(
        status="Erro",
        detalhes=printer_aghu.MENSAGEM_ERRO_PESQUISA_INDEFINIDA,
    )
    assert acao is None
    assert chamadas_limpeza == [(janela, page)]


def test_avaliar_pesquisa_vinculos_linhas_sem_ip_retorna_erro(
    monkeypatch,
    dados_planilha,
):
    monkeypatch.setattr(
        printer_aghu,
        "_limpar_estado_formulario",
        lambda janela, page: None,
    )

    resultado, acao = printer_aghu._avaliar_pesquisa_vinculos(
        janela_sistema=object(),
        page=object(),
        dados=dados_planilha,
        estado_pesquisa="linhas",
        registros_linhas=[],
    )

    assert resultado.status == "Erro"
    assert "nenhuma com o IP esperado [10.0.0.10]" in resultado.detalhes
    assert acao is None


def test_avaliar_pesquisa_vinculos_retorna_acao_quando_nao_exige_conferencia(
    monkeypatch,
    dados_planilha,
):
    registro = {"fila": "fila-impressora"}
    monkeypatch.setattr(
        printer_aghu,
        "_decidir_acao_linhas",
        lambda **kwargs: ("alterar", registro),
    )

    resultado, acao = printer_aghu._avaliar_pesquisa_vinculos(
        janela_sistema=object(),
        page=object(),
        dados=dados_planilha,
        estado_pesquisa="vazio",
        registros_linhas=[],
    )

    assert resultado is None
    assert acao == printer_aghu.AcaoVinculo(tipo="alterar", registro=registro)


def test_avaliar_pesquisa_vinculos_conferir_retorna_erro_e_limpa(
    monkeypatch,
    dados_planilha,
):
    chamadas_limpeza = []
    monkeypatch.setattr(
        printer_aghu,
        "_decidir_acao_linhas",
        lambda **kwargs: ("conferir", {"tipo_cups": "RAW"}),
    )
    monkeypatch.setattr(
        printer_aghu,
        "_clicar_limpar_formulario",
        lambda janela: chamadas_limpeza.append(janela),
    )
    janela = object()

    resultado, acao = printer_aghu._avaliar_pesquisa_vinculos(
        janela_sistema=janela,
        page=object(),
        dados=dados_planilha,
        estado_pesquisa="linhas",
        registros_linhas=[{"tipo_cups": "RAW"}],
    )

    assert resultado.status == "Erro"
    assert "Tipo do Cups [RAW]" in resultado.detalhes
    assert acao is None
    assert chamadas_limpeza == [janela]


@pytest.mark.parametrize(
    ("estado_gravacao", "mensagem", "operacao", "detalhe_esperado"),
    [
        ("erro", "Falha X", "alterar", "AGHU retornou erro ao alterar: Falha X"),
        (
            "erro",
            "Ja existe uma impressora cadastrada na classe A",
            "incluir",
            "AGHU bloqueou inclusao",
        ),
        (
            "indefinido",
            "",
            "incluir",
            "gravacao nao retornou sucesso nem erro conhecido",
        ),
    ],
)
def test_gravar_formulario_vinculo_retorna_erro_e_limpa(
    monkeypatch,
    estado_gravacao,
    mensagem,
    operacao,
    detalhe_esperado,
):
    botao_gravar = FluentLocator()
    janela = JanelaFake(roles={("button", "Gravar"): botao_gravar})
    page = object()
    chamadas_limpeza = []
    monkeypatch.setattr(
        printer_aghu,
        "_aguardar_resultado_gravacao",
        lambda janela_sistema, page_arg: (estado_gravacao, mensagem),
    )
    monkeypatch.setattr(
        printer_aghu,
        "_limpar_estado_formulario",
        lambda janela_sistema, page_arg: chamadas_limpeza.append(
            (janela_sistema, page_arg)
        ),
    )

    resultado = printer_aghu._gravar_formulario_vinculo(
        janela,
        page,
        operacao=operacao,
    )

    assert resultado.status == "Erro"
    assert detalhe_esperado in resultado.detalhes
    assert chamadas_limpeza == [(janela, page)]
    assert botao_gravar.clicks


def test_gravar_formulario_vinculo_sucesso_retorna_none(monkeypatch):
    janela = JanelaFake(roles={("button", "Gravar"): FluentLocator()})
    monkeypatch.setattr(
        printer_aghu,
        "_aguardar_resultado_gravacao",
        lambda janela_sistema, page_arg: ("sucesso", "ok"),
    )

    assert (
        printer_aghu._gravar_formulario_vinculo(
            janela,
            object(),
            operacao="incluir",
        )
        is None
    )


def test_registrar_vinculo_mantido_limpa_e_retorna_status(monkeypatch):
    chamadas = []
    janela = object()
    monkeypatch.setattr(
        printer_aghu,
        "_clicar_limpar_formulario",
        lambda janela_sistema: chamadas.append(janela_sistema),
    )

    resultado = printer_aghu._registrar_vinculo_mantido(janela)

    assert resultado.status == "Mantido"
    assert chamadas == [janela]


def test_linha_alvo_da_acao_retorna_linha_do_registro():
    linha = object()
    acao = printer_aghu.AcaoVinculo(tipo="alterar", registro={"linha": linha})

    assert printer_aghu._linha_alvo_da_acao(acao) is linha


def test_linha_alvo_da_acao_sem_linha_levanta_erro():
    with pytest.raises(RuntimeError, match="Linha da tabela"):
        printer_aghu._linha_alvo_da_acao(
            printer_aghu.AcaoVinculo(tipo="alterar", registro=None)
        )


@pytest.mark.parametrize(
    ("fabricada", "status_esperado"),
    [(False, "Alterado"), (True, "Criado")],
)
def test_editar_vinculo_existente_retorna_status_da_alteracao(
    monkeypatch,
    dados_planilha,
    fabricada,
    status_esperado,
):
    linha = FluentLocator()
    janela = JanelaFake(
        roles={("button", "Gravar"): FluentLocator()},
        locators={"button:has(.aghu-icon-cleaner-aghu)": FluentLocator()},
    )
    chamadas = []
    monkeypatch.setattr(
        printer_aghu,
        "_selecionar_impressora_no_formulario",
        lambda janela_sistema, impressora: chamadas.append(("selecionar", impressora)),
    )
    monkeypatch.setattr(
        printer_aghu,
        "_gravar_formulario_vinculo",
        lambda janela_sistema, page, operacao: None,
    )
    monkeypatch.setattr(
        printer_aghu,
        "_aguardar_botao_pesquisar_se_possivel",
        lambda janela_sistema: chamadas.append(("aguardar", janela_sistema)),
    )
    monkeypatch.setattr(
        printer_aghu,
        "_clicar_limpar_formulario",
        lambda janela_sistema: chamadas.append(("limpar", janela_sistema)),
    )

    resultado = printer_aghu._editar_vinculo_existente(
        janela_sistema=janela,
        page=object(),
        linha_alvo=linha,
        dados=dados_planilha,
        impressora_fabricada_agora=fabricada,
    )

    assert resultado.status == status_esperado
    assert ("selecionar", "fila-impressora") in chamadas
    assert linha.clicks


def test_editar_vinculo_existente_repassa_erro_de_gravacao(
    monkeypatch,
    dados_planilha,
):
    erro_gravacao = printer_aghu.ResultadoLinha(status="Erro", detalhes="falha")
    monkeypatch.setattr(
        printer_aghu,
        "_selecionar_impressora_no_formulario",
        lambda janela_sistema, impressora: None,
    )
    monkeypatch.setattr(
        printer_aghu,
        "_gravar_formulario_vinculo",
        lambda janela_sistema, page, operacao: erro_gravacao,
    )
    janela = JanelaFake(
        roles={("button", "Gravar"): FluentLocator()},
        locators={"button:has(.aghu-icon-cleaner-aghu)": FluentLocator()},
    )

    assert (
        printer_aghu._editar_vinculo_existente(
            janela_sistema=janela,
            page=object(),
            linha_alvo=FluentLocator(),
            dados=dados_planilha,
            impressora_fabricada_agora=False,
        )
        is erro_gravacao
    )


@pytest.mark.parametrize(
    ("fabricada", "status_esperado"),
    [(False, "Vinculado"), (True, "Criado")],
)
def test_incluir_novo_vinculo_retorna_status_do_cadastro(
    monkeypatch,
    dados_planilha,
    fabricada,
    status_esperado,
):
    janela = JanelaFake(
        roles={
            ("button", "Novo"): FluentLocator(),
            ("button", "Gravar"): FluentLocator(),
        }
    )
    chamadas = []
    monkeypatch.setattr(
        printer_aghu,
        "_selecionar_computador_no_formulario",
        lambda janela_sistema, ip, capturar_texto=False: (object(), f"PC {ip}"),
    )
    monkeypatch.setattr(
        printer_aghu,
        "_validar_computador_selecionado",
        lambda campo, ip, texto: (True, ""),
    )
    monkeypatch.setattr(
        printer_aghu,
        "_selecionar_impressora_no_formulario",
        lambda janela_sistema, impressora: chamadas.append(("impressora", impressora)),
    )
    monkeypatch.setattr(
        printer_aghu,
        "_selecionar_classe_vinculo",
        lambda janela_sistema, classe: chamadas.append(("classe", classe)),
    )
    monkeypatch.setattr(
        printer_aghu,
        "_gravar_formulario_vinculo",
        lambda janela_sistema, page, operacao: None,
    )
    monkeypatch.setattr(
        printer_aghu,
        "_aguardar_botao_pesquisar_se_possivel",
        lambda janela_sistema: None,
    )
    monkeypatch.setattr(
        printer_aghu,
        "_clicar_limpar_formulario",
        lambda janela_sistema: None,
    )

    resultado = printer_aghu._incluir_novo_vinculo(
        janela_sistema=janela,
        page=object(),
        dados=dados_planilha,
        registros_linhas=[],
        impressora_fabricada_agora=fabricada,
    )

    assert resultado.status == status_esperado
    assert chamadas == [("impressora", "fila-impressora"), ("classe", "PDF")]


def test_incluir_novo_vinculo_bloqueia_computador_divergente(
    monkeypatch,
    dados_planilha,
):
    monkeypatch.setattr(
        printer_aghu,
        "_selecionar_computador_no_formulario",
        lambda janela_sistema, ip, capturar_texto=False: (object(), "PC errado"),
    )
    monkeypatch.setattr(
        printer_aghu,
        "_validar_computador_selecionado",
        lambda campo, ip, texto: (False, "10.0.0.99"),
    )

    with pytest.raises(ValueError, match="computador selecionado diverge"):
        printer_aghu._incluir_novo_vinculo(
            janela_sistema=JanelaFake(
                roles={
                    ("button", "Novo"): FluentLocator(),
                    ("button", "Gravar"): FluentLocator(),
                }
            ),
            page=object(),
            dados=dados_planilha,
            registros_linhas=[],
            impressora_fabricada_agora=False,
        )


@pytest.mark.parametrize(
    ("tipo", "retorno_esperado"),
    [
        ("mantido", "mantido"),
        ("alterar", "alterado"),
        ("incluir", "incluido"),
    ],
)
def test_executar_acao_vinculo_despacha_para_helper_correto(
    monkeypatch,
    dados_planilha,
    tipo,
    retorno_esperado,
):
    chamadas = []
    monkeypatch.setattr(
        printer_aghu,
        "_registrar_vinculo_mantido",
        lambda janela: chamadas.append("mantido")
        or printer_aghu.ResultadoLinha("OK", "mantido"),
    )
    monkeypatch.setattr(
        printer_aghu,
        "_editar_vinculo_existente",
        lambda **kwargs: chamadas.append("alterado")
        or printer_aghu.ResultadoLinha("OK", "alterado"),
    )
    monkeypatch.setattr(
        printer_aghu,
        "_incluir_novo_vinculo",
        lambda **kwargs: chamadas.append("incluido")
        or printer_aghu.ResultadoLinha("OK", "incluido"),
    )

    acao = printer_aghu.AcaoVinculo(tipo=tipo, registro={"linha": object()})
    resultado = printer_aghu._executar_acao_vinculo(
        janela_sistema=object(),
        page=object(),
        dados=dados_planilha,
        registros_linhas=[],
        acao=acao,
        impressora_fabricada_agora=False,
    )

    assert resultado.detalhes == retorno_esperado
    assert chamadas == [retorno_esperado]


def test_processar_linha_aghu_executa_fluxo_de_pesquisa_e_acao(
    monkeypatch,
    dados_planilha,
):
    chamadas = []
    acao = printer_aghu.AcaoVinculo(tipo="incluir")
    resultado_final = printer_aghu.ResultadoLinha(status="Vinculado", detalhes="ok")
    monkeypatch.setattr(
        printer_aghu,
        "_buscar_computador_no_formulario",
        lambda janela, ip: chamadas.append(("buscar", ip)),
    )
    monkeypatch.setattr(
        printer_aghu,
        "_pesquisar_vinculos_computador",
        lambda janela_sistema, ip_pc: ("vazio", []),
    )
    monkeypatch.setattr(
        printer_aghu,
        "_avaliar_pesquisa_vinculos",
        lambda **kwargs: (None, acao),
    )
    monkeypatch.setattr(
        printer_aghu,
        "_executar_acao_vinculo",
        lambda **kwargs: resultado_final,
    )

    assert (
        printer_aghu._processar_linha_aghu(
            janela_sistema=object(),
            page=object(),
            dados=dados_planilha,
            impressora_fabricada_agora=False,
        )
        is resultado_final
    )
    assert chamadas == [("buscar", "10.0.0.10")]


def test_processar_linha_aghu_preserva_value_error(monkeypatch, dados_planilha):
    monkeypatch.setattr(
        printer_aghu,
        "_buscar_computador_no_formulario",
        lambda janela, ip: (_ for _ in ()).throw(ValueError("falha funcional")),
    )

    with pytest.raises(ValueError, match="falha funcional"):
        printer_aghu._processar_linha_aghu(
            janela_sistema=object(),
            page=object(),
            dados=dados_planilha,
            impressora_fabricada_agora=False,
        )


def test_processar_linha_aghu_encapsula_falha_tecnica(monkeypatch, dados_planilha):
    monkeypatch.setattr(
        printer_aghu,
        "_buscar_computador_no_formulario",
        lambda janela, ip: (_ for _ in ()).throw(RuntimeError("timeout")),
    )

    with pytest.raises(printer_aghu.FalhaTecnicaProcessamento) as erro:
        printer_aghu._processar_linha_aghu(
            janela_sistema=object(),
            page=object(),
            dados=dados_planilha,
            impressora_fabricada_agora=False,
        )

    assert erro.value.passo == "Buscando Computador"


def test_reiniciar_modulo_vinculo_troca_aba_e_navega(monkeypatch):
    context = object()
    page_antiga = object()
    page_nova = object()
    janela_nova = object()
    chamadas = []
    monkeypatch.setattr(
        printer_aghu,
        "trocar_aba_aghux",
        lambda context_arg, page_arg, usuario, senha, url_aghu: chamadas.append(
            ("trocar", context_arg, page_arg, usuario, senha, url_aghu)
        )
        or page_nova,
    )
    monkeypatch.setattr(
        printer_aghu,
        "navegar_ate_modulo",
        lambda context_arg, page_arg, usuario, senha, url_aghu: chamadas.append(
            ("navegar", context_arg, page_arg, usuario, senha, url_aghu)
        )
        or (page_nova, janela_nova),
    )

    assert printer_aghu._reiniciar_modulo_vinculo(
        context=context,
        page=page_antiga,
        usuario_str="usuario",
        senha_str="senha",
        url_aghu="https://aghu.example",
    ) == (page_nova, janela_nova)
    assert chamadas[0][0] == "trocar"
    assert chamadas[1][0] == "navegar"


def test_cadastrar_impressora_inexistente_retorna_sucesso(monkeypatch, dados_planilha):
    page_inicial = object()
    page_nova = object()
    janela_cadastro = object()
    dados_cups = {"fila": "fila-impressora"}
    chamadas = []
    monkeypatch.setattr(
        printer_aghu,
        "trocar_aba_aghux",
        lambda context, page, usuario, senha, url_aghu: page_nova,
    )
    monkeypatch.setattr(
        printer_aghu,
        "consultar_dados_site_secundario",
        lambda context, impressora, classe: dados_cups,
    )
    monkeypatch.setattr(
        printer_aghu,
        "navegar_ate_cadastro_impressora",
        lambda page: janela_cadastro,
    )
    monkeypatch.setattr(
        printer_aghu,
        "cadastrar_nova_impressora",
        lambda janela, dados: chamadas.append((janela, dados)),
    )

    assert printer_aghu._cadastrar_impressora_inexistente(
        context=object(),
        page=page_inicial,
        usuario_str="usuario",
        senha_str="senha",
        dados=dados_planilha,
        url_aghu="https://aghu.example",
    ) == (True, "", page_nova)
    assert chamadas == [(janela_cadastro, dados_cups)]


def test_cadastrar_impressora_inexistente_retorna_ultima_falha(
    monkeypatch,
    dados_planilha,
):
    monkeypatch.setattr(
        printer_aghu,
        "trocar_aba_aghux",
        lambda context, page, usuario, senha, url_aghu: (_ for _ in ()).throw(
            RuntimeError("falha estoque")
        ),
    )

    sucesso, erro, page = printer_aghu._cadastrar_impressora_inexistente(
        context=object(),
        page="page-original",
        usuario_str="usuario",
        senha_str="senha",
        dados=dados_planilha,
        url_aghu="https://aghu.example",
    )

    assert sucesso is False
    assert erro == "falha estoque"
    assert page == "page-original"


def test_tratar_impressora_inexistente_reinicia_modulo_quando_cadastro_sucesso(
    monkeypatch,
    dados_planilha,
):
    page_reiniciada = object()
    janela_reiniciada = object()
    monkeypatch.setattr(
        printer_aghu,
        "_cadastrar_impressora_inexistente",
        lambda **kwargs: (True, "", kwargs["page"]),
    )
    monkeypatch.setattr(
        printer_aghu,
        "_reiniciar_modulo_vinculo",
        lambda **kwargs: (page_reiniciada, janela_reiniciada),
    )

    tentar_novamente, resultado, page, janela = (
        printer_aghu._tratar_impressora_inexistente(
            context=object(),
            page=object(),
            janela_sistema=object(),
            usuario_str="usuario",
            senha_str="senha",
            dados=dados_planilha,
            url_aghu="https://aghu.example",
        )
    )

    assert tentar_novamente is True
    assert resultado.status == "Erro"
    assert page is page_reiniciada
    assert janela is janela_reiniciada


@pytest.mark.parametrize(
    ("erro_estoque", "status_esperado", "detalhe_esperado"),
    [
        (
            "N\u00e3o existe no CUPS",
            "Inexistente",
            "Fila de impress\u00e3o n\u00e3o encontrada",
        ),
        ("timeout", "Erro", "Falha no Almoxarifado"),
    ],
)
def test_tratar_impressora_inexistente_retorna_falha_final(
    monkeypatch,
    dados_planilha,
    erro_estoque,
    status_esperado,
    detalhe_esperado,
):
    page = object()
    janela = object()
    monkeypatch.setattr(
        printer_aghu,
        "_cadastrar_impressora_inexistente",
        lambda **kwargs: (False, erro_estoque, page),
    )

    tentar_novamente, resultado, page_final, janela_final = (
        printer_aghu._tratar_impressora_inexistente(
            context=object(),
            page=page,
            janela_sistema=janela,
            usuario_str="usuario",
            senha_str="senha",
            dados=dados_planilha,
            url_aghu="https://aghu.example",
        )
    )

    assert tentar_novamente is False
    assert resultado.status == status_esperado
    assert detalhe_esperado in resultado.detalhes
    assert page_final is page
    assert janela_final is janela


def test_limpar_apos_erro_funcional_tenta_cancelar_e_limpar():
    botao_cancelar = FluentLocator()
    botao_limpar = FluentLocator()
    janela = JanelaFake(
        roles={("button", "Cancelar"): botao_cancelar},
        locators={"button:has(.aghu-icon-cleaner-aghu)": botao_limpar},
    )

    printer_aghu._limpar_apos_erro_funcional(janela)

    assert botao_cancelar.clicks
    assert botao_limpar.clicks


def test_limpar_apos_erro_funcional_ignora_falhas():
    janela = JanelaFake(
        roles={("button", "Cancelar"): FluentLocator(fail_click=True)},
        locators={
            "button:has(.aghu-icon-cleaner-aghu)": FluentLocator(fail_click=True)
        },
    )

    printer_aghu._limpar_apos_erro_funcional(janela)


@pytest.mark.parametrize(
    ("mensagem", "status_esperado"),
    [
        ("Computador n\u00e3o encontrado", "Inexistente"),
        ("Falha funcional", "Erro"),
    ],
)
def test_tratar_erro_funcional_mapeia_status_e_limpa(
    monkeypatch,
    mensagem,
    status_esperado,
):
    chamadas = []
    janela = object()
    monkeypatch.setattr(
        printer_aghu,
        "_limpar_apos_erro_funcional",
        lambda janela_sistema: chamadas.append(janela_sistema),
    )

    resultado = printer_aghu._tratar_erro_funcional(janela, mensagem)

    assert resultado.status == status_esperado
    assert chamadas == [janela]


def test_tratar_falha_tecnica_reinicia_modulo_quando_ainda_ha_tentativa(monkeypatch):
    page_nova = object()
    janela_nova = object()
    monkeypatch.setattr(
        printer_aghu,
        "_reiniciar_modulo_vinculo",
        lambda **kwargs: (page_nova, janela_nova),
    )

    resultado, page, janela = printer_aghu._tratar_falha_tecnica(
        context=object(),
        page=object(),
        janela_sistema=object(),
        usuario_str="usuario",
        senha_str="senha",
        url_aghu="https://aghu.example",
        tentativa=0,
        passo_atual="Pesquisando",
    )

    assert resultado is None
    assert page is page_nova
    assert janela is janela_nova


def test_tratar_falha_tecnica_retorna_erro_na_ultima_tentativa(monkeypatch):
    monkeypatch.setattr(
        printer_aghu,
        "_reiniciar_modulo_vinculo",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("falha recuperacao")),
    )

    resultado, page, janela = printer_aghu._tratar_falha_tecnica(
        context=object(),
        page="page-atual",
        janela_sistema="janela-atual",
        usuario_str="usuario",
        senha_str="senha",
        url_aghu="https://aghu.example",
        tentativa=printer_aghu.MAX_TENTATIVAS_PROCESSAMENTO_LINHA - 1,
        passo_atual="Pesquisando",
    )

    assert resultado.status == "Erro"
    assert "Pesquisando" in resultado.detalhes
    assert page == "page-atual"
    assert janela == "janela-atual"


def test_processar_linha_com_retentativas_trata_value_error_funcional(
    monkeypatch,
    dados_planilha,
):
    resultado_funcional = printer_aghu.ResultadoLinha("Inexistente", "computador")
    monkeypatch.setattr(
        printer_aghu,
        "_processar_linha_aghu",
        lambda **kwargs: (_ for _ in ()).throw(
            ValueError("Computador n\u00e3o encontrado")
        ),
    )
    monkeypatch.setattr(
        printer_aghu,
        "_tratar_erro_funcional",
        lambda janela_sistema, mensagem: resultado_funcional,
    )

    resultado, page, janela = printer_aghu._processar_linha_com_retentativas(
        context=object(),
        page="page",
        janela_sistema="janela",
        usuario_str="usuario",
        senha_str="senha",
        dados=dados_planilha,
        url_aghu="https://aghu.example",
    )

    assert resultado is resultado_funcional
    assert page == "page"
    assert janela == "janela"


def test_processar_linha_com_retentativas_retorna_erro_tecnico_final(
    monkeypatch,
    dados_planilha,
):
    resultado_final = printer_aghu.ResultadoLinha("Erro", "tecnico final")
    chamadas = []

    def fake_processar_linha(**kwargs):
        chamadas.append(kwargs["impressora_fabricada_agora"])
        raise printer_aghu.FalhaTecnicaProcessamento(
            "Pesquisando",
            RuntimeError("timeout"),
        )

    monkeypatch.setattr(printer_aghu, "_processar_linha_aghu", fake_processar_linha)
    monkeypatch.setattr(
        printer_aghu,
        "_tratar_falha_tecnica",
        lambda **kwargs: (
            (None, kwargs["page"], kwargs["janela_sistema"])
            if kwargs["tentativa"]
            < printer_aghu.MAX_TENTATIVAS_PROCESSAMENTO_LINHA - 1
            else (resultado_final, kwargs["page"], kwargs["janela_sistema"])
        ),
    )

    resultado, _, _ = printer_aghu._processar_linha_com_retentativas(
        context=object(),
        page=object(),
        janela_sistema=object(),
        usuario_str="usuario",
        senha_str="senha",
        dados=dados_planilha,
        url_aghu="https://aghu.example",
    )

    assert resultado is resultado_final
    assert chamadas == [False, False, False]
