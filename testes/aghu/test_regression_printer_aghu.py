import builtins

import pandas as pd
import pytest

import PrinterAGHU as printer_aghu


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


def test_regressao_processar_computadores_ignora_linha_com_campo_obrigatorio_vazio(
    monkeypatch,
):
    planilha = pd.DataFrame(
        [
            {
                "HostPC": "pc-01",
                "IPPC": "",
                "HostPrinter": "fila-impressora",
                "IPPrinter": "10.0.0.20",
                "PrinterClass": "PDF",
            }
        ]
    )
    logs_recebidos = []
    monkeypatch.setattr(
        printer_aghu,
        "_processar_linha_com_retentativas",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("linha invalida nao deve acionar browser")
        ),
    )
    monkeypatch.setattr(
        printer_aghu,
        "_gerar_csv_logs",
        lambda logs_do_diario, usuario_str, diretorio_logs: logs_recebidos.extend(
            logs_do_diario
        )
        or "relatorio.csv",
    )

    caminho = printer_aghu.processar_computadores(
        context=object(),
        page_inicial=object(),
        janela_sistema_inicial=object(),
        planilha=planilha,
        usuario_str="operador",
        senha_str="senha",
        diretorio_logs=None,
        url_aghu="https://aghu.example",
    )

    assert caminho == "relatorio.csv"
    assert logs_recebidos == [
        {
            "HostPC": "pc-01",
            "IPPC": "",
            "HostPrinter": "fila-impressora",
            "IPPrinter": "10.0.0.20",
            "PrinterClass": "PDF",
            "Status": "Erro",
            "Detalhes": (
                "Linha ignorada: campos obrigatorios em branco: IPPC."
            ),
        }
    ]


def test_regressao_pesquisa_com_linhas_sem_ip_nao_decide_inclusao(
    monkeypatch,
    dados_planilha,
):
    chamadas_limpeza = []
    monkeypatch.setattr(
        printer_aghu,
        "_limpar_estado_formulario",
        lambda janela, page: chamadas_limpeza.append((janela, page)),
    )
    monkeypatch.setattr(
        printer_aghu,
        "_decidir_acao_linhas",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("nao deve decidir quando nenhuma linha tem o IP")
        ),
    )
    janela = object()
    page = object()

    resultado, acao = printer_aghu._avaliar_pesquisa_vinculos(
        janela_sistema=janela,
        page=page,
        dados=dados_planilha,
        estado_pesquisa="linhas",
        registros_linhas=[],
    )

    assert resultado.status == "Erro"
    assert "nenhuma com o IP esperado" in resultado.detalhes
    assert acao is None
    assert chamadas_limpeza == [(janela, page)]


@pytest.mark.parametrize(
    ("tipo_acao", "passo_esperado"),
    [
        ("alterar", "Editando Impressora Existente"),
        ("incluir", "Cadastrando Nova Impressora (Vinculando)"),
    ],
)
def test_regressao_processar_linha_reporta_passo_tecnico_da_acao(
    monkeypatch,
    dados_planilha,
    tipo_acao,
    passo_esperado,
):
    monkeypatch.setattr(
        printer_aghu,
        "_buscar_computador_no_formulario",
        lambda janela, ip: None,
    )
    monkeypatch.setattr(
        printer_aghu,
        "_pesquisar_vinculos_computador",
        lambda janela_sistema, ip_pc: ("linhas", [{"linha": object()}]),
    )
    monkeypatch.setattr(
        printer_aghu,
        "_avaliar_pesquisa_vinculos",
        lambda **kwargs: (
            None,
            printer_aghu.AcaoVinculo(tipo=tipo_acao, registro={"linha": object()}),
        ),
    )
    monkeypatch.setattr(
        printer_aghu,
        "_executar_acao_vinculo",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("timeout")),
    )

    with pytest.raises(printer_aghu.FalhaTecnicaProcessamento) as erro:
        printer_aghu._processar_linha_aghu(
            janela_sistema=object(),
            page=object(),
            dados=dados_planilha,
            impressora_fabricada_agora=False,
        )

    assert erro.value.passo == passo_esperado


def test_regressao_retentativa_marca_impressora_fabricada_apos_estoquista(
    monkeypatch,
    dados_planilha,
):
    page_inicial = object()
    janela_inicial = object()
    chamadas = []

    def fake_processar_linha_aghu(**kwargs):
        chamadas.append(kwargs["impressora_fabricada_agora"])

        if len(chamadas) == 1:
            raise ValueError("Impressora n\u00e3o existe")

        return printer_aghu.ResultadoLinha(
            status="Criado",
            detalhes="Impressora nova identificada no CUPS, criada e vinculada no AGHU.",
        )

    monkeypatch.setattr(
        printer_aghu,
        "_processar_linha_aghu",
        fake_processar_linha_aghu,
    )
    monkeypatch.setattr(
        printer_aghu,
        "_tratar_impressora_inexistente",
        lambda **kwargs: (
            True,
            printer_aghu.ResultadoLinha(status="Erro", detalhes="Falha Desconhecida."),
            page_inicial,
            janela_inicial,
        ),
    )

    resultado, page_final, janela_final = printer_aghu._processar_linha_com_retentativas(
        context=object(),
        page=page_inicial,
        janela_sistema=janela_inicial,
        usuario_str="usuario",
        senha_str="senha",
        dados=dados_planilha,
        url_aghu="https://aghu.example",
    )

    assert chamadas == [False, True]
    assert resultado.status == "Criado"
    assert page_final is page_inicial
    assert janela_final is janela_inicial


def test_regressao_falha_estoquista_cups_mantem_status_inexistente(
    monkeypatch,
    dados_planilha,
):
    page = object()
    janela = object()
    monkeypatch.setattr(
        printer_aghu,
        "_cadastrar_impressora_inexistente",
        lambda **kwargs: (False, "N\u00e3o existe no CUPS", page),
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
    assert resultado.status == "Inexistente"
    assert page_final is page
    assert janela_final is janela
