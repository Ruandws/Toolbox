from pathlib import Path

import pytest

import concessor_aghu as aghu
from concessor_aghu import (
    ConcessaoPerfisEntrada,
    STATUS_BLOQUEADO,
    STATUS_IGNORADO,
    STATUS_VALIDACAO_URA,
)


def test_carregar_catalogo_regras_le_yaml_real():
    catalogo = aghu.carregar_catalogo_regras()

    assert len(catalogo.regras) >= 60
    assert "Perfis Básicos" in catalogo.escopos()
    assert "Medicina Geral" in catalogo.categorias("Perfis Básicos")

    regra = catalogo.obter_regra("Perfis Básicos", "Medicina Geral")

    assert "MED01" in regra.perfis_conceder
    assert "RM01" in regra.perfis_conceder


def test_fallback_yaml_preserva_lista_e_continuacao_de_texto():
    dados = aghu._parse_regras_yaml_fallback(
        """
metadata:
  nome: teste
regras:
- escopo: Escopo A
  categoria: Categoria com texto
    continuado
  perfis_conceder:
  - PERF01
  - PERF02
  perfis_bloqueados: []
  perfis_validacao_ura:
  - PERF03
  observacoes:
  - Observacao
    continuada
"""
    )

    regra = dados["regras"][0]

    assert regra["categoria"] == "Categoria com texto continuado"
    assert regra["perfis_conceder"] == ["PERF01", "PERF02"]
    assert regra["perfis_bloqueados"] == []
    assert regra["perfis_validacao_ura"] == ["PERF03"]
    assert regra["observacoes"] == ["Observacao continuada"]


def test_preparar_concessao_libera_perfis_nao_criticos():
    catalogo = aghu.carregar_catalogo_regras()
    entrada = ConcessaoPerfisEntrada(
        login="usuario.teste",
        protocolo="52501301",
        escopo="Perfis Básicos",
        categoria="Medicina Geral",
    )

    preparada = aghu.preparar_concessao(entrada, catalogo)

    assert "MED01" in preparada.perfis_automatizados
    assert "RM01" in preparada.perfis_automatizados
    assert preparada.resultados_previos == ()


def test_preparar_concessao_bloqueia_perfil_critico_global():
    catalogo = aghu.carregar_catalogo_regras()
    entrada = ConcessaoPerfisEntrada(
        login="usuario.teste",
        protocolo="52501301",
        escopo="Perfis Módulo Cirurgia/PDT",
        categoria="Assistente Administrativo / Recepcionista",
    )

    preparada = aghu.preparar_concessao(entrada, catalogo)

    assert preparada.perfis_automatizados == ()
    assert len(preparada.resultados_previos) == 1
    assert preparada.resultados_previos[0].perfil == "ADM04"
    assert preparada.resultados_previos[0].status == STATUS_BLOQUEADO


def test_preparar_concessao_exige_validacao_ura_global():
    catalogo = aghu.carregar_catalogo_regras()
    entrada = ConcessaoPerfisEntrada(
        login="usuario.teste",
        protocolo="52501301",
        escopo="Perfis Básicos Unidade do Sistema Urinário (USUR)",
        categoria=(
            "Psicólogo, Psicólogos Residentes, Assistente Social, "
            "Assistente Social Residente"
        ),
    )

    preparada = aghu.preparar_concessao(entrada, catalogo)

    assert "ADM02.02" not in preparada.perfis_automatizados
    assert any(
        resultado.perfil == "ADM02.02"
        and resultado.status == STATUS_VALIDACAO_URA
        for resultado in preparada.resultados_previos
    )


def test_executar_concessao_sem_perfis_elegiveis_nao_abre_playwright(monkeypatch):
    def falhar_sync_playwright():
        raise AssertionError("Playwright nao deveria ser iniciado")

    monkeypatch.setattr(aghu, "sync_playwright", falhar_sync_playwright)

    resultado = aghu.executar_concessao_perfis(
        entrada=ConcessaoPerfisEntrada(
            login="usuario.teste",
            protocolo="52501301",
            escopo="PERFIS CRÍTICOS. ATENÇÃO!",
            categoria="Ninguém",
        ),
        usuario_rede="tecnico",
        senha="senha",
        mostrar_console=True,
        gerar_csv_log=False,
    )

    assert resultado.status == STATUS_IGNORADO
    assert any(
        perfil.status == STATUS_BLOQUEADO
        for perfil in resultado.resultados_perfis
    )


def test_validar_entrada_rejeita_login_e_protocolo_invalidos():
    erros = aghu.validar_entrada(
        ConcessaoPerfisEntrada(
            login="usuario invalido",
            protocolo="abc",
            escopo="Perfis Básicos",
            categoria="Medicina Geral",
        )
    )

    assert any("Usuario alvo invalido" in erro for erro in erros)
    assert any("Protocolo invalido" in erro for erro in erros)


class LocatorProtocoloFake:
    def __init__(self) -> None:
        self.valor = "111"
        self.chamadas: list[tuple[str, object]] = []

    def wait_for(self, **kwargs):
        self.chamadas.append(("wait_for", kwargs))

    def click(self, **kwargs):
        self.chamadas.append(("click", kwargs))

    def press(self, tecla, **kwargs):
        self.chamadas.append(("press", tecla))
        if tecla == "Control+A":
            return
        if tecla == "Backspace":
            self.valor = ""

    def fill(self, valor, **kwargs):
        self.chamadas.append(("fill", valor))
        self.valor = valor

    def press_sequentially(self, valor, **kwargs):
        self.chamadas.append(("press_sequentially", valor))
        self.valor += valor

    def evaluate(self, script):
        self.chamadas.append(("evaluate", script))

    def blur(self, **kwargs):
        self.chamadas.append(("blur", kwargs))

    def input_value(self, **kwargs):
        self.chamadas.append(("input_value", kwargs))
        return self.valor


def test_preencher_protocolo_digita_e_dispara_eventos_jsf():
    locator = LocatorProtocoloFake()

    aghu._preencher_protocolo(locator, "ABC-52501301")

    assert locator.valor == "52501301"
    assert ("press_sequentially", "52501301") in locator.chamadas
    assert ("blur", {"timeout": 5000}) in locator.chamadas
    assert not any(chamada[0] == "fill" for chamada in locator.chamadas)
    assert sum(1 for chamada in locator.chamadas if chamada[0] == "evaluate") == 2


def test_salvar_relatorio_resultados_cria_xlsx(tmp_path: Path):
    catalogo = aghu.carregar_catalogo_regras()
    preparada = aghu.preparar_concessao(
        ConcessaoPerfisEntrada(
            login="usuario.teste",
            protocolo="52501301",
            escopo="Perfis Módulo Cirurgia/PDT",
            categoria="Assistente Administrativo / Recepcionista",
        ),
        catalogo,
    )
    resultado = aghu.processar_concessao_sem_browser(preparada)
    caminho = tmp_path / "relatorio.xlsx"

    retorno = aghu.salvar_relatorio_resultados([resultado], caminho)

    assert retorno.exists()
    assert retorno.suffix == ".xlsx"


def test_obter_regra_inexistente_levanta_erro():
    catalogo = aghu.carregar_catalogo_regras()

    with pytest.raises(ValueError, match="Regra de perfis"):
        catalogo.obter_regra("Escopo inexistente", "Categoria inexistente")
