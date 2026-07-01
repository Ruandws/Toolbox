import concessor_aghu as aghu
from concessor_aghu import (
    CatalogoPerfis,
    ConcessaoPerfisEntrada,
    RegraPerfil,
    STATUS_BLOQUEADO,
    STATUS_IGNORADO,
    STATUS_VALIDACAO_URA,
)


def catalogo_regressao() -> CatalogoPerfis:
    return CatalogoPerfis(
        (
            RegraPerfil(
                escopo="Escopo A",
                categoria="Categoria A",
                perfis_conceder=("PERF01", "PERF02", "PERF03", "PERF03"),
                perfis_bloqueados=("PERF02",),
                perfis_validacao_ura=("PERF03",),
                observacoes=(),
            ),
            RegraPerfil(
                escopo="Escopo B",
                categoria="Categoria B",
                perfis_conceder=(),
                perfis_bloqueados=("PERF99",),
                perfis_validacao_ura=(),
                observacoes=(),
            ),
        )
    )


def test_normalizar_entrada_uppercase_login_e_mantem_apenas_digitos_protocolo():
    entrada = aghu.normalizar_entrada(
        ConcessaoPerfisEntrada(
            login=" usuario.teste ",
            protocolo="ABC-52501301/2026",
            escopo=" Escopo A ",
            categoria=" Categoria A ",
        )
    )

    assert entrada.login == "USUARIO.TESTE"
    assert entrada.protocolo == "525013012026"
    assert entrada.escopo == "Escopo A"
    assert entrada.categoria == "Categoria A"


def test_preparar_concessao_nao_automatiza_perfis_bloqueados_ou_validacao_ura():
    preparada = aghu.preparar_concessao(
        ConcessaoPerfisEntrada(
            login="usuario.teste",
            protocolo="52501301",
            escopo="escopo a",
            categoria="categoria a",
        ),
        catalogo_regressao(),
    )

    assert preparada.perfis_automatizados == ("PERF01",)
    assert [(item.perfil, item.status) for item in preparada.resultados_previos] == [
        ("PERF02", STATUS_BLOQUEADO),
        ("PERF03", STATUS_VALIDACAO_URA),
    ]


def test_processar_concessao_sem_browser_retorna_ignorado_para_regra_sem_elegiveis():
    preparada = aghu.preparar_concessao(
        ConcessaoPerfisEntrada(
            login="usuario.teste",
            protocolo="52501301",
            escopo="Escopo B",
            categoria="Categoria B",
        ),
        catalogo_regressao(),
    )

    resultado = aghu.processar_concessao_sem_browser(preparada)

    assert resultado.status == STATUS_IGNORADO
    assert resultado.resultados_perfis[0].status == STATUS_BLOQUEADO
    assert "bloqueados: 1" in resultado.detalhes


def test_autocomplete_confere_codigo_exato_e_primeiro_token():
    assert aghu._texto_item_autocomplete_confere("PERF01 - Perfil teste", "PERF01")
    assert aghu._texto_item_autocomplete_confere("PERF01\nDescricao", "PERF01")
    assert not aghu._texto_item_autocomplete_confere("PERF010 - Outro", "PERF01")


class LinhasFake:
    @property
    def first(self):
        return self

    def count(self):
        return 0

    def is_visible(self, timeout):
        return False


class JanelaFake:
    def locator(self, seletor):
        assert seletor == aghu.SELECTOR_TABELA_USUARIOS
        return LinhasFake()


def test_pesquisa_usuario_indefinida_nao_retorna_nao_encontrado_sem_estado_estavel(
    monkeypatch,
):
    tempos = iter((0, 0.1, 0.2, 0.3))
    monkeypatch.setattr(aghu.time, "monotonic", lambda: next(tempos))
    monkeypatch.setattr(aghu.time, "sleep", lambda _tempo: None)
    monkeypatch.setattr(aghu, "_existe_carregamento_visivel", lambda _janela: False)
    monkeypatch.setattr(aghu, "_linha_tabela_por_login", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(aghu, "_linha_vazia_visivel", lambda _linhas: False)

    estado, linha = aghu._aguardar_resultado_pesquisa_usuario(
        JanelaFake(),
        "USUARIO.TESTE",
        timeout_ms=250,
        estabilidade_resultado_ms=100,
    )

    assert estado == "indefinido"
    assert linha is None
