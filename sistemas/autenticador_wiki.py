# autenticador_wiki.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError


URL_WIKI_MAPEAMENTO_PERFIS = (
    "https://wiki.hub-unb.ebserh/index.php/Mapeamento_de_Perfis"
)

URL_WIKI_AUTENTICACAO = (
    "https://wiki.hub-unb.ebserh/index.php"
    "?title=Especial:Autenticar-se"
    "&returnto=Mapeamento+de+Perfis"
    "&returntoquery="
)

SELETOR_LINK_AUTENTICAR = 'a[href*="Especial:Autenticar-se"]'
SELETOR_INPUT_USUARIO = "#wpName1"
SELETOR_INPUT_SENHA = "#wpPassword1"
SELETOR_BOTAO_ENTRAR = "#mw-input-pluggableauthlogin0"

SELETOR_USUARIO_LOGADO = "#pt-userpage"
SELETOR_USUARIO_LOGADO_TEXTO = "#pt-userpage span"
SELETOR_MENSAGEM_ERRO = ".cdx-message__content"

MENSAGEM_CREDENCIAIS_INVALIDAS = (
    'Could not authenticate credentials against domain "ebserhnet.ebserh.gov.br"'
)


class WikiAuthError(Exception):
    """Erro base da autenticação da Wiki."""


class WikiCredenciaisInvalidasError(WikiAuthError):
    """Credenciais recusadas pelo domínio de autenticação."""


class WikiLoginNaoConfirmadoError(WikiAuthError):
    """Login submetido, mas não confirmado pela tela esperada."""


class WikiLoginTimeoutError(WikiAuthError):
    """Timeout durante o fluxo de autenticação."""


@dataclass(frozen=True)
class ResultadoAutenticacaoWiki:
    autenticado: bool
    usuario_informado: str
    usuario_logado: Optional[str]
    url_atual: str


def _normalizar_texto(valor: Optional[str]) -> str:
    return (valor or "").strip()


class AutenticadorWiki:
    def __init__(
        self,
        page: Page,
        *,
        url_inicial: str = URL_WIKI_MAPEAMENTO_PERFIS,
        url_autenticacao: str = URL_WIKI_AUTENTICACAO,
        timeout: int = 30_000,
    ) -> None:
        self.page = page
        self.url_inicial = url_inicial
        self.url_autenticacao = url_autenticacao
        self.timeout = timeout

    def autenticar(
        self,
        usuario: str,
        senha: str,
    ) -> ResultadoAutenticacaoWiki:
        usuario = _normalizar_texto(usuario)
        senha = _normalizar_texto(senha)

        if not usuario:
            raise ValueError("Usuário não informado.")

        if not senha:
            raise ValueError("Senha não informada.")

        try:
            self.abrir_url_inicial()

            if self.esta_autenticado():
                return self._montar_resultado(usuario)

            self.abrir_tela_autenticacao()
            self.preencher_credenciais(usuario, senha)
            self.submeter_login()
            self.validar_resultado_login()

            return self._montar_resultado(usuario)

        except PlaywrightTimeoutError as exc:
            raise WikiLoginTimeoutError(
                "Timeout durante o fluxo de autenticação da Wiki."
            ) from exc

    def abrir_url_inicial(self) -> None:
        self.page.goto(
            self.url_inicial,
            wait_until="domcontentloaded",
            timeout=self.timeout,
        )

    def abrir_tela_autenticacao(self) -> None:
        link_autenticar = self.page.locator(SELETOR_LINK_AUTENTICAR).first

        if link_autenticar.count() > 0 and link_autenticar.is_visible():
            link_autenticar.click(timeout=self.timeout)
            self.page.wait_for_load_state(
                "domcontentloaded",
                timeout=self.timeout,
            )
            return

        self.page.goto(
            self.url_autenticacao,
            wait_until="domcontentloaded",
            timeout=self.timeout,
        )

    def preencher_credenciais(
        self,
        usuario: str,
        senha: str,
    ) -> None:
        self.page.locator(SELETOR_INPUT_USUARIO).wait_for(
            state="visible",
            timeout=self.timeout,
        )

        self.page.locator(SELETOR_INPUT_USUARIO).fill(usuario)
        self.page.locator(SELETOR_INPUT_SENHA).fill(senha)

    def submeter_login(self) -> None:
        self.page.locator(SELETOR_BOTAO_ENTRAR).click(timeout=self.timeout)

        try:
            self.page.wait_for_load_state(
                "domcontentloaded",
                timeout=self.timeout,
            )
        except PlaywrightTimeoutError:
            self._validar_erro_credenciais()
            raise

    def validar_resultado_login(self) -> None:
        self._validar_erro_credenciais()

        try:
            self.page.wait_for_url(
                self.url_inicial,
                timeout=self.timeout,
            )
        except PlaywrightTimeoutError:
            self._validar_erro_credenciais()

        if not self.esta_autenticado():
            self._validar_erro_credenciais()

            raise WikiLoginNaoConfirmadoError(
                "Login submetido, mas a URL final ou o seletor de usuário logado "
                "não confirmou a autenticação."
            )

    def esta_autenticado(self) -> bool:
        url_ok = self.page.url.rstrip("/") == self.url_inicial.rstrip("/")

        try:
            seletor_ok = self.page.locator(SELETOR_USUARIO_LOGADO).is_visible()
        except Exception:
            seletor_ok = False

        return url_ok and seletor_ok

    def obter_usuario_logado(self) -> Optional[str]:
        seletor = self.page.locator(SELETOR_USUARIO_LOGADO_TEXTO).first

        if seletor.count() == 0:
            return None

        try:
            if seletor.is_visible():
                return _normalizar_texto(seletor.inner_text())
        except Exception:
            return None

        return None

    def _validar_erro_credenciais(self) -> None:
        mensagem = self.page.locator(SELETOR_MENSAGEM_ERRO).first

        if mensagem.count() == 0:
            return

        try:
            if not mensagem.is_visible():
                return

            texto = _normalizar_texto(mensagem.inner_text())

            if MENSAGEM_CREDENCIAIS_INVALIDAS in texto:
                raise WikiCredenciaisInvalidasError(texto)

        except WikiCredenciaisInvalidasError:
            raise

    def _montar_resultado(
        self,
        usuario_informado: str,
    ) -> ResultadoAutenticacaoWiki:
        return ResultadoAutenticacaoWiki(
            autenticado=True,
            usuario_informado=usuario_informado,
            usuario_logado=self.obter_usuario_logado(),
            url_atual=self.page.url,
        )


def autenticar_wiki(
    page: Page,
    usuario: str,
    senha: str,
    *,
    url_inicial: str = URL_WIKI_MAPEAMENTO_PERFIS,
    url_autenticacao: str = URL_WIKI_AUTENTICACAO,
    timeout: int = 30_000,
) -> ResultadoAutenticacaoWiki:
    autenticador = AutenticadorWiki(
        page,
        url_inicial=url_inicial,
        url_autenticacao=url_autenticacao,
        timeout=timeout,
    )

    return autenticador.autenticar(usuario, senha)


def wiki_esta_autenticada(
    page: Page,
    *,
    url_inicial: str = URL_WIKI_MAPEAMENTO_PERFIS,
    timeout: int = 10_000,
) -> bool:
    autenticador = AutenticadorWiki(
        page,
        url_inicial=url_inicial,
        timeout=timeout,
    )

    return autenticador.esta_autenticado()


__all__ = [
    "URL_WIKI_MAPEAMENTO_PERFIS",
    "URL_WIKI_AUTENTICACAO",
    "ResultadoAutenticacaoWiki",
    "AutenticadorWiki",
    "WikiAuthError",
    "WikiCredenciaisInvalidasError",
    "WikiLoginNaoConfirmadoError",
    "WikiLoginTimeoutError",
    "autenticar_wiki",
    "wiki_esta_autenticada",
]