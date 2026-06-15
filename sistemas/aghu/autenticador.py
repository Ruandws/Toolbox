import os
import time
from dataclasses import dataclass
from typing import Literal, Optional

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


URL_LOGIN_AGHU = os.getenv("URL_LOGIN_AGHU", "http://10.6.0.152:8080/aghu/pages/casca/casca.xhtml")

SELECTOR_USUARIO = '[id="usuario:usuario:inputId"]'
SELECTOR_SENHA = '[id="password:inputId"]'
SELECTOR_ENTRAR = '[id="entrar"]'

SELECTOR_ERRO_AUTENTICACAO = ".ui-messages-info-detail"
MENSAGEM_ERRO_AUTENTICACAO = (
    "Erro de autenticação. Favor verificar o nome de usuário e a senha antes de tentar novamente."
)

SELECTOR_TELA_PRINCIPAL_AGHU = ".usuario-dados .nome-usuario"
TEXTO_TELA_PRINCIPAL_AGHU = "Olá,"

StatusLogin = Literal[
    "sucesso",
    "credenciais_invalidas",
    "timeout",
    "erro",
]


@dataclass
class ResultadoLogin:
    status: StatusLogin
    mensagem: str
    url_final: Optional[str] = None


def _erro_autenticacao_visivel(page: Page, timeout_ms: int = 1000) -> bool:
    erro_por_texto = page.get_by_text(MENSAGEM_ERRO_AUTENTICACAO, exact=True)

    try:
        erro_por_texto.first.wait_for(state="visible", timeout=timeout_ms)
        return True
    except PlaywrightTimeoutError:
        pass

    erro_por_classe = page.locator(SELECTOR_ERRO_AUTENTICACAO).filter(
        has_text=MENSAGEM_ERRO_AUTENTICACAO
    )

    try:
        erro_por_classe.first.wait_for(state="visible", timeout=timeout_ms)
        return True
    except PlaywrightTimeoutError:
        return False


def _login_efetuado(
    page: Page,
    selector_tela_principal: str = SELECTOR_TELA_PRINCIPAL_AGHU,
    timeout_ms: int = 1000,
) -> bool:
    if _erro_autenticacao_visivel(page, timeout_ms=250):
        return False

    usuario_logado = page.locator(selector_tela_principal).filter(
        has_text=TEXTO_TELA_PRINCIPAL_AGHU
    )

    try:
        usuario_logado.first.wait_for(
            state="visible",
            timeout=timeout_ms,
        )
    except PlaywrightTimeoutError:
        return False

    try:
        texto_usuario = usuario_logado.first.inner_text(timeout=timeout_ms)
    except PlaywrightTimeoutError:
        return False

    texto_normalizado = " ".join(texto_usuario.split())

    return (
        TEXTO_TELA_PRINCIPAL_AGHU in texto_normalizado
        and len(texto_normalizado.replace(TEXTO_TELA_PRINCIPAL_AGHU, "").strip()) > 0
    )


def autenticar_aghu(
    usuario: str,
    senha: str,
    url_login: str = URL_LOGIN_AGHU,
    headless: bool = False,
    timeout_ms: int = 15000,
    tempo_tela_principal_segundos: int = 3,
    selector_tela_principal: str = SELECTOR_TELA_PRINCIPAL_AGHU,
) -> ResultadoLogin:
    usuario = usuario.strip()

    if not usuario or not senha:
        return ResultadoLogin(
            status="erro",
            mensagem="Usuário e senha devem ser informados.",
        )

    try:
        with sync_playwright() as playwright:
            browser = None
            context = None

            try:
                browser = playwright.chromium.launch(headless=headless)
                context = browser.new_context()
                page = context.new_page()

                page.goto(
                    url_login,
                    wait_until="domcontentloaded",
                    timeout=timeout_ms,
                )

                page.locator(SELECTOR_USUARIO).fill(usuario, timeout=timeout_ms)
                page.locator(SELECTOR_SENHA).fill(senha, timeout=timeout_ms)
                page.locator(SELECTOR_ENTRAR).click(timeout=timeout_ms)

                try:
                    page.wait_for_load_state("domcontentloaded", timeout=3000)
                except PlaywrightTimeoutError:
                    pass

                prazo_final = time.monotonic() + (timeout_ms / 1000)

                while time.monotonic() < prazo_final:
                    if _erro_autenticacao_visivel(page, timeout_ms=500):
                        return ResultadoLogin(
                            status="credenciais_invalidas",
                            mensagem="Usuário/Senha Inválido",
                            url_final=page.url,
                        )

                    if _login_efetuado(
                        page,
                        selector_tela_principal=selector_tela_principal,
                        timeout_ms=500,
                    ):
                        page.wait_for_timeout(tempo_tela_principal_segundos * 1000)

                        return ResultadoLogin(
                            status="sucesso",
                            mensagem="Login Efetuado",
                            url_final=page.url,
                        )

                    page.wait_for_timeout(250)

                if _erro_autenticacao_visivel(page, timeout_ms=1000):
                    return ResultadoLogin(
                        status="credenciais_invalidas",
                        mensagem="Usuário/Senha Inválido",
                        url_final=page.url,
                    )

                return ResultadoLogin(
                    status="timeout",
                    mensagem="Não foi possível confirmar o login dentro do tempo limite.",
                    url_final=page.url,
                )

            finally:
                if context is not None:
                    try:
                        context.close()
                    except Exception:
                        pass

                if browser is not None:
                    try:
                        browser.close()
                    except Exception:
                        pass

    except PlaywrightError as exc:
        return ResultadoLogin(
            status="erro",
            mensagem=f"Falha durante a autenticação: {exc}",
        )

