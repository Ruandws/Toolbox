from pathlib import Path

import pytest

import profissionais_unidade_cirurgica_aghu as aghu
from profissionais_unidade_cirurgica_aghu import (
    CadastroProfissionalUnidadeEntrada,
    ResultadoCadastroProfissional,
    STATUS_CONFERIR_MANUAL,
    STATUS_CRIADO,
    STATUS_FUNCIONARIO_NAO_ENCONTRADO,
    STATUS_IGNORADO,
    STATUS_MANTIDO,
    UNIDADES_FUNCIONAIS,
    FUNCAO_MEDICO_RESIDENTE,
)


class FakeCell:
    def __init__(self, texto: str):
        self.texto = texto

    def inner_text(self, timeout=None):
        return self.texto


class FakeCells:
    def __init__(self, textos: list[str]):
        self.cells = [FakeCell(texto) for texto in textos]

    def count(self):
        return len(self.cells)

    def nth(self, indice):
        return self.cells[indice]


class FakeLinha:
    def __init__(
        self,
        celulas: list[str],
        *,
        visivel: bool = True,
        classe: str = "",
        texto: str = "",
    ):
        self.celulas = FakeCells(celulas)
        self.visivel = visivel
        self.classe = classe
        self.texto = texto

    def is_visible(self, timeout=None):
        return self.visivel

    def get_attribute(self, nome, timeout=None):
        return self.classe if nome == "class" else None

    def locator(self, seletor):
        if seletor != "td":
            raise AssertionError(f"Seletor inesperado: {seletor}")

        return self.celulas

    def inner_text(self, timeout=None):
        return self.texto


class FakeLinhas:
    def __init__(self, *linhas: FakeLinha):
        self.linhas = list(linhas)

    def count(self):
        return len(self.linhas)

    def nth(self, indice):
        return self.linhas[indice]


class FakeFlow(aghu.ProfissionalUnidadeCirurgicaFlow):
    def __init__(
        self,
        estado_pesquisa: str,
        *,
        status_gravacao: tuple[str, str] = ("sucesso", "Cadastro OK"),
        erro_preenchimento: Exception | None = None,
    ):
        super().__init__(janela_sistema=object())
        self.estado_pesquisa = estado_pesquisa
        self.status_gravacao = status_gravacao
        self.erro_preenchimento = erro_preenchimento
        self.formulario_cancelado = False
        self.retorno_pesquisa = False

    def pesquisar(self, entrada):
        return self.estado_pesquisa, None

    def _preencher_formulario(self, entrada):
        if self.erro_preenchimento:
            raise self.erro_preenchimento

    def _gravar(self):
        return self.status_gravacao

    def _cancelar_formulario(self):
        self.formulario_cancelado = True

    def _retornar_para_pesquisa(self):
        self.retorno_pesquisa = True


def cadastro_valido(**kwargs) -> CadastroProfissionalUnidadeEntrada:
    dados = {
        "profissional": "Ruan Victor de Jesus Andrade",
        "unidade_funcional": UNIDADES_FUNCIONAIS[0],
        "funcao": FUNCAO_MEDICO_RESIDENTE,
    }
    dados.update(kwargs)
    return CadastroProfissionalUnidadeEntrada(**dados)


def test_normalizar_entrada_converte_unidade_com_codigo_e_funcao_padrao():
    entrada = CadastroProfissionalUnidadeEntrada(
        profissional="  Ruan Victor  ",
        unidade_funcional="3 - centro obstetrico - pre-parto",
        funcao="",
    )

    normalizada = aghu.normalizar_entrada(entrada)

    assert normalizada.profissional == "Ruan Victor"
    assert normalizada.unidade_funcional == "CENTRO OBSTETRICO - PRE-PARTO"
    assert normalizada.funcao == FUNCAO_MEDICO_RESIDENTE


def test_validar_entrada_rejeita_campos_invalidos():
    erros = aghu.validar_entrada(
        CadastroProfissionalUnidadeEntrada(
            profissional="",
            unidade_funcional="Unidade desconhecida",
            funcao="Outra funcao",
        )
    )

    assert "Profissional em branco." in erros
    assert "Unidade Funcional invalida." in erros
    assert "Funcao invalida." in erros


def test_resultado_ignorado_normaliza_dados():
    resultado = aghu.resultado_ignorado(
        cadastro_valido(profissional="  Ana  ", unidade_funcional="94 - centro cirurgico central"),
        "motivo",
    )

    assert resultado.profissional == "Ana"
    assert resultado.unidade_funcional == "CENTRO CIRURGICO CENTRAL"
    assert resultado.status == STATUS_IGNORADO


def test_ler_planilha_cadastros_aceita_aliases_sem_acentos(tmp_xlsx):
    caminho = tmp_xlsx(
        "profissionais.xlsx",
        ["Nome do Profissional", "Unidade Cirurgica"],
        [["Ana Silva", "CENTRO DE ENDOSCOPIA"]],
    )

    cadastros = aghu.ler_planilha_cadastros(caminho)

    assert cadastros == [
        CadastroProfissionalUnidadeEntrada(
            profissional="Ana Silva",
            unidade_funcional="CENTRO DE ENDOSCOPIA",
            funcao=FUNCAO_MEDICO_RESIDENTE,
        )
    ]


def test_ler_planilha_rejeita_extensao_invalida(tmp_path: Path):
    caminho = tmp_path / "profissionais.csv"
    caminho.write_text("x", encoding="utf-8")

    with pytest.raises(ValueError, match=".xlsx"):
        aghu.ler_planilha_cadastros(caminho)


def test_ler_planilha_rejeita_colunas_obrigatorias_ausentes(tmp_xlsx):
    caminho = tmp_xlsx("incompleta.xlsx", ["Profissional"], [["Ana"]])

    with pytest.raises(ValueError, match="Colunas obrigatorias ausentes"):
        aghu.ler_planilha_cadastros(caminho)


def test_salvar_relatorio_resultados_cria_xlsx(tmp_path: Path):
    caminho = tmp_path / "relatorio.xlsx"
    resultado = ResultadoCadastroProfissional(
        profissional="Ana",
        unidade_funcional=UNIDADES_FUNCIONAIS[0],
        funcao=FUNCAO_MEDICO_RESIDENTE,
        status=STATUS_CRIADO,
        detalhes="OK",
    )

    retorno = aghu.salvar_relatorio_resultados([resultado], caminho)

    assert retorno.exists()
    assert retorno.suffix == ".xlsx"


def test_executar_cadastros_invalidos_nao_abre_playwright(monkeypatch):
    def falhar_sync_playwright():
        raise AssertionError("Playwright nao deveria ser iniciado")

    monkeypatch.setattr(aghu, "sync_playwright", falhar_sync_playwright)

    resultados = aghu.executar_cadastros_profissionais(
        cadastros=[
            CadastroProfissionalUnidadeEntrada(
                profissional="",
                unidade_funcional="Unidade desconhecida",
                funcao="Outra funcao",
            )
        ],
        usuario_rede="usuario",
        senha="senha",
        gerar_csv_log=False,
    )

    assert len(resultados) == 1
    assert resultados[0].status == STATUS_IGNORADO
    assert "Linha ignorada:" in resultados[0].detalhes


def test_estado_vinculo_identifica_vinculo_ativo_com_normalizacao():
    entrada = cadastro_valido(
        profissional="Ana Silva",
        unidade_funcional="CENTRO OBSTETRICO - PRE-PARTO",
    )
    linha = FakeLinha(
        [
            "",
            "3 - centro obstetrico - pre-parto",
            "medico residente",
            "",
            "",
            " ANA SILVA ",
            "",
            "Ativo",
        ]
    )

    estado, linha_encontrada = aghu.ProfissionalUnidadeCirurgicaFlow(
        object()
    )._estado_vinculo(FakeLinhas(linha), entrada)

    assert estado == "vinculo_existente"
    assert linha_encontrada is linha


def test_estado_vinculo_identifica_vinculo_inativo():
    entrada = cadastro_valido(profissional="Ana Silva")
    linha = FakeLinha(
        [
            "",
            UNIDADES_FUNCIONAIS[0],
            FUNCAO_MEDICO_RESIDENTE,
            "",
            "",
            "Ana Silva",
            "",
            "Inativo",
        ]
    )

    estado, linha_encontrada = aghu.ProfissionalUnidadeCirurgicaFlow(
        object()
    )._estado_vinculo(FakeLinhas(linha), entrada)

    assert estado == "vinculo_inativo"
    assert linha_encontrada is linha


def test_estado_vinculo_ignora_linhas_sem_correspondencia():
    entrada = cadastro_valido(profissional="Ana Silva")
    linhas = FakeLinhas(
        FakeLinha(
            [
                "",
                UNIDADES_FUNCIONAIS[1],
                FUNCAO_MEDICO_RESIDENTE,
                "",
                "",
                "Outro Profissional",
            ]
        ),
        FakeLinha([], classe="ui-datatable-empty-message"),
    )

    estado, linha_encontrada = aghu.ProfissionalUnidadeCirurgicaFlow(
        object()
    )._estado_vinculo(linhas, entrada)

    assert estado is None
    assert linha_encontrada is None


def test_aguardar_mensagem_gravacao_identifica_sucesso(monkeypatch):
    monkeypatch.setattr(
        aghu,
        "mensagens_sistema",
        lambda janela: ["Profissional na unidade cirurgica incluido com sucesso."],
    )

    status, mensagem = aghu.aguardar_mensagem_gravacao(object(), timeout_ms=1)

    assert status == "sucesso"
    assert "incluido com sucesso" in mensagem


def test_aguardar_mensagem_gravacao_identifica_erro(monkeypatch):
    monkeypatch.setattr(
        aghu,
        "mensagens_sistema",
        lambda janela: ["Erro: campo obrigatorio nao informado."],
    )

    status, mensagem = aghu.aguardar_mensagem_gravacao(object(), timeout_ms=1)

    assert status == "erro"
    assert "campo obrigatorio" in mensagem


def test_processar_transiciona_vinculo_existente_para_mantido():
    resultado = FakeFlow("vinculo_existente").processar(cadastro_valido())

    assert resultado.status == STATUS_MANTIDO
    assert "ja existente" in resultado.detalhes


def test_processar_transiciona_vinculo_inativo_para_conferir_manual():
    resultado = FakeFlow("vinculo_inativo").processar(cadastro_valido())

    assert resultado.status == STATUS_CONFERIR_MANUAL
    assert "situacao nao esta ativa" in resultado.detalhes


def test_processar_grava_novo_vinculo_com_sucesso(monkeypatch):
    cliques = []
    monkeypatch.setattr(aghu, "clicar_botao", lambda janela, nome: cliques.append(nome))
    monkeypatch.setattr(aghu, "aguardar_ciclo_carregamento", lambda *args, **kwargs: True)
    flow = FakeFlow("nao_encontrado")

    resultado = flow.processar(cadastro_valido())

    assert resultado.status == STATUS_CRIADO
    assert resultado.detalhes == "Cadastro OK"
    assert cliques == ["Novo"]
    assert flow.retorno_pesquisa is True


def test_processar_cancela_formulario_quando_profissional_nao_existe(monkeypatch):
    monkeypatch.setattr(aghu, "clicar_botao", lambda *args, **kwargs: None)
    monkeypatch.setattr(aghu, "aguardar_ciclo_carregamento", lambda *args, **kwargs: True)
    flow = FakeFlow(
        "nao_encontrado",
        erro_preenchimento=aghu.AutocompleteSemRegistroError(),
    )

    resultado = flow.processar(cadastro_valido())

    assert resultado.status == STATUS_FUNCIONARIO_NAO_ENCONTRADO
    assert flow.formulario_cancelado is True


def test_processar_cadastros_reexecuta_linha_apos_clean_state(monkeypatch):
    cadastros = [
        cadastro_valido(profissional="Ana"),
        cadastro_valido(profissional="Bia"),
    ]
    chamadas_processar = []

    def garantir_fake(**kwargs):
        return kwargs["page_atual"], kwargs["janela_atual"]

    def processar_fake(janela_sistema, entrada):
        chamadas_processar.append((janela_sistema, entrada.profissional))
        if entrada.profissional == "Ana" and len(chamadas_processar) == 1:
            raise RuntimeError("falha transitoria")

        return ResultadoCadastroProfissional(
            profissional=entrada.profissional,
            unidade_funcional=entrada.unidade_funcional,
            funcao=entrada.funcao,
            status=STATUS_CRIADO,
            detalhes="OK",
        )

    monkeypatch.setattr(
        aghu,
        "garantir_tela_pesquisa_profissional_unidade",
        garantir_fake,
    )
    monkeypatch.setattr(aghu, "processar_cadastro", processar_fake)
    monkeypatch.setattr(aghu, "trocar_aba_aghux", lambda **kwargs: "page-clean")
    monkeypatch.setattr(
        aghu,
        "navegar_ate_cadastro_profissional_unidade",
        lambda **kwargs: ("page-clean", "janela-clean"),
    )

    resultados = aghu.processar_cadastros(
        context="context",
        page_inicial="page-original",
        janela_sistema_inicial="janela-original",
        cadastros=cadastros,
        usuario_rede="usuario",
        senha="senha",
    )

    assert [resultado.status for resultado in resultados] == [
        STATUS_CRIADO,
        STATUS_CRIADO,
    ]
    assert chamadas_processar == [
        ("janela-original", "Ana"),
        ("janela-clean", "Ana"),
        ("janela-clean", "Bia"),
    ]
