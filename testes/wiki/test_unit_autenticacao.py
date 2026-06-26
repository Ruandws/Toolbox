# test_unit_autenticacao.py

from unittest.mock import Mock

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from autenticador_wiki import (
    AutenticadorWiki,
    ResultadoAutenticacaoWiki,
    URL_WIKI_AUTENTICACAO,
    URL_WIKI_MAPEAMENTO_PERFIS,
    SELETOR_BOTAO_ENTRAR,
    SELETOR_INPUT_SENHA,
    SELETOR_INPUT_USUARIO,
    SELETOR_LINK_AUTENTICAR,
    SELETOR_MENSAGEM_ERRO,
    SELETOR_USUARIO_LOGADO,
    SELETOR_USUARIO_LOGADO_TEXTO,
    WikiCredenciaisInvalidasError,
    WikiLoginNaoConfirmadoError,
    WikiLoginTimeoutError,
)


def _locator(
    *,
    count: int = 1,
    visible: bool = True,
    inner_text: str = "",
) -> Mock:
    locator = Mock()
    locator.first = locator
    locator.count.return_value = count
    locator.is_visible.return_value = visible
    locator.inner_text.return_value = inner_text
    return locator


def test_autenticar_retorna_sucesso_quando_sessao_ja_esta_autenticada():
    page = Mock()
    page.url = URL_WIKI_MAPEAMENTO_PERFIS

    usuario_logado = _locator(visible=True)
    texto_usuario_logado = _locator(visible=True, inner_text="usuario.inserido")

    def locator_side_effect(selector):
        if selector == SELETOR_USUARIO_LOGADO:
            return usuario_logado

        if selector == SELETOR_USUARIO_LOGADO_TEXTO:
            return texto_usuario_logado

        return _locator(count=0, visible=False)

    page.locator.side_effect = locator_side_effect

    resultado = AutenticadorWiki(page).autenticar(
        usuario="usuario.inserido",
        senha="senha123",
    )

    assert isinstance(resultado, ResultadoAutenticacaoWiki)
    assert resultado.autenticado is True
    assert resultado.usuario_informado == "usuario.inserido"
    assert resultado.usuario_logado == "usuario.inserido"
    assert resultado.url_atual == URL_WIKI_MAPEAMENTO_PERFIS

    page.goto.assert_called_once_with(
        URL_WIKI_MAPEAMENTO_PERFIS,
        wait_until="domcontentloaded",
        timeout=30_000,
    )


def test_autenticar_executa_fluxo_completo_com_sucesso():
    page = Mock()
    page.url = URL_WIKI_MAPEAMENTO_PERFIS

    estado = {
        "autenticado": False,
    }

    link_autenticar = _locator(visible=True)
    input_usuario = _locator(visible=True)
    input_senha = _locator(visible=True)
    botao_entrar = _locator(visible=True)
    mensagem_erro = _locator(count=0, visible=False)
    texto_usuario_logado = _locator(visible=True, inner_text="usuario.inserido")

    def click_entrar(*args, **kwargs):
        estado["autenticado"] = True
        page.url = URL_WIKI_MAPEAMENTO_PERFIS

    botao_entrar.click.side_effect = click_entrar

    def locator_side_effect(selector):
        if selector == SELETOR_LINK_AUTENTICAR:
            return link_autenticar

        if selector == SELETOR_INPUT_USUARIO:
            return input_usuario

        if selector == SELETOR_INPUT_SENHA:
            return input_senha

        if selector == SELETOR_BOTAO_ENTRAR:
            return botao_entrar

        if selector == SELETOR_MENSAGEM_ERRO:
            return mensagem_erro

        if selector == SELETOR_USUARIO_LOGADO:
            return _locator(visible=estado["autenticado"])

        if selector == SELETOR_USUARIO_LOGADO_TEXTO:
            return texto_usuario_logado

        return _locator(count=0, visible=False)

    page.locator.side_effect = locator_side_effect

    resultado = AutenticadorWiki(page).autenticar(
        usuario="usuario.inserido",
        senha="senha123",
    )

    assert resultado.autenticado is True
    assert resultado.usuario_informado == "usuario.inserido"
    assert resultado.usuario_logado == "usuario.inserido"
    assert resultado.url_atual == URL_WIKI_MAPEAMENTO_PERFIS

    link_autenticar.click.assert_called_once_with(timeout=30_000)
    input_usuario.wait_for.assert_called_once_with(
        state="visible",
        timeout=30_000,
    )
    input_usuario.fill.assert_called_once_with("usuario.inserido")
    input_senha.fill.assert_called_once_with("senha123")
    botao_entrar.click.assert_called_once_with(timeout=30_000)
    page.wait_for_url.assert_called_once_with(
        URL_WIKI_MAPEAMENTO_PERFIS,
        timeout=30_000,
    )


def test_autenticar_abre_url_de_autenticacao_quando_link_nao_aparece():
    page = Mock()
    page.url = URL_WIKI_MAPEAMENTO_PERFIS

    estado = {
        "autenticado": False,
    }

    link_autenticar = _locator(count=0, visible=False)
    input_usuario = _locator(visible=True)
    input_senha = _locator(visible=True)
    botao_entrar = _locator(visible=True)
    mensagem_erro = _locator(count=0, visible=False)
    texto_usuario_logado = _locator(visible=True, inner_text="usuario.inserido")

    def click_entrar(*args, **kwargs):
        estado["autenticado"] = True
        page.url = URL_WIKI_MAPEAMENTO_PERFIS

    botao_entrar.click.side_effect = click_entrar

    def locator_side_effect(selector):
        if selector == SELETOR_LINK_AUTENTICAR:
            return link_autenticar

        if selector == SELETOR_INPUT_USUARIO:
            return input_usuario

        if selector == SELETOR_INPUT_SENHA:
            return input_senha

        if selector == SELETOR_BOTAO_ENTRAR:
            return botao_entrar

        if selector == SELETOR_MENSAGEM_ERRO:
            return mensagem_erro

        if selector == SELETOR_USUARIO_LOGADO:
            return _locator(visible=estado["autenticado"])

        if selector == SELETOR_USUARIO_LOGADO_TEXTO:
            return texto_usuario_logado

        return _locator(count=0, visible=False)

    page.locator.side_effect = locator_side_effect

    resultado = AutenticadorWiki(page).autenticar(
        usuario="usuario.inserido",
        senha="senha123",
    )

    assert resultado.autenticado is True

    page.goto.assert_any_call(
        URL_WIKI_MAPEAMENTO_PERFIS,
        wait_until="domcontentloaded",
        timeout=30_000,
    )

    page.goto.assert_any_call(
        URL_WIKI_AUTENTICACAO,
        wait_until="domcontentloaded",
        timeout=30_000,
    )


def test_autenticar_lanca_erro_quando_credenciais_sao_invalidas():
    page = Mock()
    page.url = URL_WIKI_MAPEAMENTO_PERFIS

    link_autenticar = _locator(visible=True)
    input_usuario = _locator(visible=True)
    input_senha = _locator(visible=True)
    botao_entrar = _locator(visible=True)
    usuario_logado = _locator(visible=False)

    mensagem_erro = _locator(
        visible=True,
        inner_text='Could not authenticate credentials against domain "ebserhnet.ebserh.gov.br"',
    )

    def locator_side_effect(selector):
        if selector == SELETOR_LINK_AUTENTICAR:
            return link_autenticar

        if selector == SELETOR_INPUT_USUARIO:
            return input_usuario

        if selector == SELETOR_INPUT_SENHA:
            return input_senha

        if selector == SELETOR_BOTAO_ENTRAR:
            return botao_entrar

        if selector == SELETOR_MENSAGEM_ERRO:
            return mensagem_erro

        if selector == SELETOR_USUARIO_LOGADO:
            return usuario_logado

        return _locator(count=0, visible=False)

    page.locator.side_effect = locator_side_effect

    with pytest.raises(WikiCredenciaisInvalidasError):
        AutenticadorWiki(page).autenticar(
            usuario="usuario.inserido",
            senha="senha_errada",
        )


def test_autenticar_lanca_erro_quando_login_nao_e_confirmado():
    page = Mock()
    page.url = URL_WIKI_MAPEAMENTO_PERFIS

    link_autenticar = _locator(visible=True)
    input_usuario = _locator(visible=True)
    input_senha = _locator(visible=True)
    botao_entrar = _locator(visible=True)
    usuario_logado = _locator(visible=False)
    mensagem_erro = _locator(count=0, visible=False)

    page.wait_for_url.side_effect = PlaywrightTimeoutError("Timeout")

    def locator_side_effect(selector):
        if selector == SELETOR_LINK_AUTENTICAR:
            return link_autenticar

        if selector == SELETOR_INPUT_USUARIO:
            return input_usuario

        if selector == SELETOR_INPUT_SENHA:
            return input_senha

        if selector == SELETOR_BOTAO_ENTRAR:
            return botao_entrar

        if selector == SELETOR_MENSAGEM_ERRO:
            return mensagem_erro

        if selector == SELETOR_USUARIO_LOGADO:
            return usuario_logado

        return _locator(count=0, visible=False)

    page.locator.side_effect = locator_side_effect

    with pytest.raises(WikiLoginNaoConfirmadoError):
        AutenticadorWiki(page).autenticar(
            usuario="usuario.inserido",
            senha="senha123",
        )


def test_autenticar_lanca_erro_de_timeout_quando_playwright_estoura_timeout():
    page = Mock()
    page.url = URL_WIKI_MAPEAMENTO_PERFIS
    page.goto.side_effect = PlaywrightTimeoutError("Timeout")

    with pytest.raises(WikiLoginTimeoutError):
        AutenticadorWiki(page).autenticar(
            usuario="usuario.inserido",
            senha="senha123",
        )


def test_autenticar_rejeita_usuario_vazio():
    page = Mock()

    with pytest.raises(ValueError, match="Usuário não informado."):
        AutenticadorWiki(page).autenticar(
            usuario="",
            senha="senha123",
        )


def test_autenticar_rejeita_senha_vazia():
    page = Mock()

    with pytest.raises(ValueError, match="Senha não informada."):
        AutenticadorWiki(page).autenticar(
            usuario="usuario.inserido",
            senha="",
        )
