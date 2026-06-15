import os
import time
from dataclasses import dataclass
from typing import Literal, Optional, Sequence

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


DEFAULT_AGHU_URL = "https://aghu.hub-unb.ebserh/aghu/pages/casca/casca.xhtml"

AGHU_URL = os.getenv(
    "AGHU_URL",
    os.getenv("URL_LOGIN_AGHU", DEFAULT_AGHU_URL),
)

# Alias de compatibilidade: mantém chamadas antigas funcionando.
URL_LOGIN_AGHU = AGHU_URL

SELECTOR_USUARIO = '[id="usuario:usuario:inputId"]'
SELECTOR_SENHA = '[id="password:inputId"]'
SELECTOR_ENTRAR = '[id="entrar"]'

SELETORES_USUARIO_FALLBACK = (
    SELECTOR_USUARIO,
    'input[id*="usuario" i]',
    'input[id*="login" i]',
    'input[name*="usuario" i]',
    'input[name*="login" i]',
    'input[type="text"]',
)

SELETORES_SENHA_FALLBACK = (
    SELECTOR_SENHA,
    'input[type="password"]',
    'input[id*="senha" i]',
    'input[name*="senha" i]',
    'input[id*="password" i]',
    'input[name*="password" i]',
)

SELETORES_ENTRAR_FALLBACK = (
    SELECTOR_ENTRAR,
    'button:has-text("Entrar")',
    'input[type="submit"][value*="Entrar" i]',
    'input[type="button"][value*="Entrar" i]',
    'input[type="submit"]',
    'button[type="submit"]',
)

SELECTOR_ERRO_AUTENTICACAO = ".ui-messages-info-detail"
MENSAGEM_ERRO_AUTENTICACAO = (
    "Erro de autenticação. Favor verificar o nome de usuário e a senha antes de tentar novamente."
)

SELECTOR_TELA_PRINCIPAL_AGHU = ".usuario-dados .nome-usuario"
TEXTO_TELA_PRINCIPAL_AGHU = "Olá,"
TEXTO_MENU_PRINCIPAL_AGHU = "Outros Módulos"

StatusLogin = Literal[
    "sucesso",
    "sessao_ativa",
    "credenciais_invalidas",
    "timeout",
    "erro",
]


@dataclass(frozen=True)
class ResultadoLogin:
    status: StatusLogin
    mensagem: str
    url_final: Optional[str] = None


def _url_atual(page: Page) -> Optional[str]:
    try:
        return page.url
    except PlaywrightError:
        return None


def _primeiro_visivel(
    page: Page,
    seletores: Sequence[str],
    timeout_ms: int = 1000,
):
    ultimo_erro: Optional[Exception] = None

    for seletor in seletores:
        locator = page.locator(seletor).first

        try:
            locator.wait_for(state="visible", timeout=timeout_ms)
            return locator
        except PlaywrightTimeoutError as exc:
            ultimo_erro = exc

    raise PlaywrightTimeoutError(
        f"Nenhum seletor ficou visível: {', '.join(seletores)}"
    ) from ultimo_erro


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


def _menu_principal_visivel(page: Page, timeout_ms: int = 1000) -> bool:
    try:
        page.get_by_text(TEXTO_MENU_PRINCIPAL_AGHU, exact=True).locator(
            "visible=true"
        ).first.wait_for(state="visible", timeout=timeout_ms)
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
        return _menu_principal_visivel(page, timeout_ms=timeout_ms)

    try:
        texto_usuario = usuario_logado.first.inner_text(timeout=timeout_ms)
    except PlaywrightTimeoutError:
        return _menu_principal_visivel(page, timeout_ms=timeout_ms)

    texto_normalizado = " ".join(texto_usuario.split())

    if (
        TEXTO_TELA_PRINCIPAL_AGHU in texto_normalizado
        and len(texto_normalizado.replace(TEXTO_TELA_PRINCIPAL_AGHU, "").strip()) > 0
    ):
        return True

    return _menu_principal_visivel(page, timeout_ms=timeout_ms)


def _tela_login_visivel(page: Page, timeout_ms: int = 1000) -> bool:
    try:
        _primeiro_visivel(page, SELETORES_SENHA_FALLBACK, timeout_ms=timeout_ms)
        return True
    except PlaywrightTimeoutError:
        return False


def _preencher_credenciais(
    page: Page,
    usuario: str,
    senha: str,
    timeout_ms: int,
) -> None:
    campo_usuario = _primeiro_visivel(
        page,
        SELETORES_USUARIO_FALLBACK,
        timeout_ms=timeout_ms,
    )
    campo_senha = _primeiro_visivel(
        page,
        SELETORES_SENHA_FALLBACK,
        timeout_ms=timeout_ms,
    )

    campo_usuario.fill(usuario, timeout=timeout_ms)
    campo_senha.fill(senha, timeout=timeout_ms)


def _clicar_entrar(page: Page, timeout_ms: int) -> None:
    try:
        botao_por_role = page.get_by_role("button", name="Entrar").first
        botao_por_role.wait_for(state="visible", timeout=1000)
        botao_por_role.click(timeout=timeout_ms)
        return
    except PlaywrightTimeoutError:
        pass

    botao_entrar = _primeiro_visivel(
        page,
        SELETORES_ENTRAR_FALLBACK,
        timeout_ms=timeout_ms,
    )
    botao_entrar.click(timeout=timeout_ms)


def autenticar_aghu_page(
    page: Page,
    usuario: str,
    senha: str,
    url_login: str = AGHU_URL,
    timeout_ms: int = 15000,
    tempo_tela_principal_segundos: int = 3,
    selector_tela_principal: str = SELECTOR_TELA_PRINCIPAL_AGHU,
) -> ResultadoLogin:
    """
    Autentica o AGHUX usando uma Page já existente. 

    Não cria browser.
    Não cria BrowserContext.
    Não fecha Page, Context ou Browser.
    """

    usuario = usuario.strip()

    if not usuario or not senha:
        return ResultadoLogin(
            status="erro",
            mensagem="Usuário e senha devem ser informados.",
            url_final=_url_atual(page),
        )

    try:
        if url_login:
            page.goto(
                url_login,
                wait_until="domcontentloaded",
                timeout=timeout_ms,
            )

        if _login_efetuado(
            page,
            selector_tela_principal=selector_tela_principal,
            timeout_ms=1000,
        ):
            return ResultadoLogin(
                status="sessao_ativa",
                mensagem="Sessão já autenticada.",
                url_final=_url_atual(page),
            )

        prazo_final = time.monotonic() + (timeout_ms / 1000)

        while time.monotonic() < prazo_final:
            if _erro_autenticacao_visivel(page, timeout_ms=250):
                return ResultadoLogin(
                    status="credenciais_invalidas",
                    mensagem="Usuário/Senha Inválido.",
                    url_final=_url_atual(page),
                )

            if _login_efetuado(
                page,
                selector_tela_principal=selector_tela_principal,
                timeout_ms=250,
            ):
                return ResultadoLogin(
                    status="sessao_ativa",
                    mensagem="Sessão já autenticada.",
                    url_final=_url_atual(page),
                )

            if _tela_login_visivel(page, timeout_ms=500):
                break

            page.wait_for_timeout(250)

        if not _tela_login_visivel(page, timeout_ms=1000):
            return ResultadoLogin(
                status="timeout",
                mensagem=(
                    "Não foi possível confirmar a tela de login nem uma sessão já ativa "
                    "dentro do tempo limite."
                ),
                url_final=_url_atual(page),
            )

        _preencher_credenciais(
            page=page,
            usuario=usuario,
            senha=senha,
            timeout_ms=timeout_ms,
        )
        _clicar_entrar(page=page, timeout_ms=timeout_ms)

        try:
            page.wait_for_load_state("domcontentloaded", timeout=3000)
        except PlaywrightTimeoutError:
            pass

        prazo_final = time.monotonic() + (timeout_ms / 1000)

        while time.monotonic() < prazo_final:
            if _erro_autenticacao_visivel(page, timeout_ms=500):
                return ResultadoLogin(
                    status="credenciais_invalidas",
                    mensagem="Usuário/Senha Inválido.",
                    url_final=_url_atual(page),
                )

            if _login_efetuado(
                page,
                selector_tela_principal=selector_tela_principal,
                timeout_ms=500,
            ):
                if tempo_tela_principal_segundos > 0:
                    page.wait_for_timeout(tempo_tela_principal_segundos * 1000)

                return ResultadoLogin(
                    status="sucesso",
                    mensagem="Login efetuado.",
                    url_final=_url_atual(page),
                )

            page.wait_for_timeout(250)

        if _erro_autenticacao_visivel(page, timeout_ms=1000):
            return ResultadoLogin(
                status="credenciais_invalidas",
                mensagem="Usuário/Senha Inválido.",
                url_final=_url_atual(page),
            )

        return ResultadoLogin(
            status="timeout",
            mensagem="Não foi possível confirmar o login dentro do tempo limite.",
            url_final=_url_atual(page),
        )

    except PlaywrightError as exc:
        return ResultadoLogin(
            status="erro",
            mensagem=f"Falha técnica durante a autenticação: {exc}",
            url_final=_url_atual(page),
        )
    except Exception as exc:
        return ResultadoLogin(
            status="erro",
            mensagem=f"Falha inesperada durante a autenticação: {exc}",
            url_final=_url_atual(page),
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
    """
    Wrapper de compatibilidade para teste isolado.

    Para uso dentro dos robôs, prefira autenticar_aghu_page(page, ...),
    pois ela reaproveita a Page existente.
    """

    try:
        with sync_playwright() as playwright:
            browser = None
            context = None

            try:
                browser = playwright.chromium.launch(headless=headless)
                context = browser.new_context()
                page = context.new_page()

                return autenticar_aghu_page(
                    page=page,
                    usuario=usuario,
                    senha=senha,
                    url_login=url_login,
                    timeout_ms=timeout_ms,
                    tempo_tela_principal_segundos=tempo_tela_principal_segundos,
                    selector_tela_principal=selector_tela_principal,
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
            mensagem=f"Falha técnica durante a autenticação: {exc}",
        )
    except Exception as exc:
        return ResultadoLogin(
            status="erro",
            mensagem=f"Falha inesperada durante a autenticação: {exc}",
        )


def exigir_login_valido(resultado: ResultadoLogin) -> None:
    if resultado.status in {"sucesso", "sessao_ativa"}:
        return

    raise RuntimeError(f"Falha ao autenticar no AGHUX: {resultado.mensagem}")


def fazer_login(
    page: Page,
    usuario_str: str,
    senha_str: str,
    *,
    timeout_ms: int = 15000,
) -> ResultadoLogin:
    """
    Wrapper simples para substituir os fazer_login duplicados dos robôs.
    Levanta RuntimeError quando login não for válido.
    """

    resultado = autenticar_aghu_page(
        page=page,
        usuario=usuario_str,
        senha=senha_str,
        timeout_ms=timeout_ms,
    )

    exigir_login_valido(resultado)
    return resultado


if __name__ == "__main__":
    usuario_teste = os.getenv("AGHU_USUARIO", "")
    senha_teste = os.getenv("AGHU_SENHA", "")

    resultado_teste = autenticar_aghu(
        usuario=usuario_teste,
        senha=senha_teste,
        url_login=URL_LOGIN_AGHU,
        headless=False,
        timeout_ms=15000,
        tempo_tela_principal_segundos=3,
    )

    print(f"{resultado_teste.status}: {resultado_teste.mensagem}")
    if resultado_teste.url_final:
        print(f"URL final: {resultado_teste.url_final}")