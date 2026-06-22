import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd
from playwright.sync_api import BrowserContext, FrameLocator, Locator, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from autenticador import AGHU_URL, autenticar_aghu_page, exigir_login_valido
from menu import navegar_menu_aghu


CAMINHO_MENU_CADASTRO_USUARIO = (
    "Outros Módulos",
    "Configuração",
    "Acesso",
    ("Usuários", "Usuário", "Usuarios", "Usuario"),
)

COLUNAS_OBRIGATORIAS_PLANILHA = ("Login", "Nome Completo", "E-mail")

STATUS_IMPORTADO = "importado"
STATUS_JA_IMPORTADO = "ja_importado"
STATUS_NAO_ENCONTRADO = "nao_encontrado"
STATUS_ERRO = "erro"
STATUS_IGNORADO = "ignorado"

StatusImportacao = Literal[
    "importado",
    "ja_importado",
    "nao_encontrado",
    "erro",
    "ignorado",
]

SELECTOR_PESQUISA_LOGIN = '[id="nomeOuLogin:nomeOuLogin:inputId"]'
SELECTOR_IMPORTACAO_LOGIN = (
    '[id="nomeOuLoginNaoCadastrado:nomeOuLoginNaoCadastrado:inputId"]'
)
SELECTOR_CADASTRO_NOME = 'input[name="nome:nome:inputId"]'
SELECTOR_CADASTRO_EMAIL = 'input[name="email:email:inputId"]'
SELECTOR_TABELA_USUARIOS = '[id="tabelaUsuarios:resultList_data"] > tr'
SELECTOR_TABELA_IDENTITY = (
    '[id="tabelaUsuariosIdentityManager:resultList_data"] > tr'
)
TEXTO_NENHUM_REGISTRO = "Nenhum registro encontrado!"


@dataclass(frozen=True)
class UsuarioImportacao:
    login: str
    nome_completo: str
    email: str


@dataclass(frozen=True)
class ResultadoImportacao:
    login: str
    nome_completo: str
    email: str
    status: StatusImportacao
    detalhes: str


def _normalizar_texto(valor: object) -> str:
    return re.sub(r"\s+", " ", str(valor or "").strip()).casefold()


def _normalizar_login(valor: object) -> str:
    return str(valor or "").strip().upper()


def _valor_em_branco(valor: object) -> bool:
    try:
        if pd.isna(valor):
            return True
    except (TypeError, ValueError):
        pass

    return str(valor or "").strip() == ""


def _login_confere(valor_atual: object, login_esperado: str) -> bool:
    return _normalizar_texto(valor_atual) == _normalizar_texto(login_esperado)

def _linha_tabela_por_texto_visivel(
    linhas: Locator,
    texto: str,
    timeout_ms: int = 5000,
) -> Locator | None:
    padrao = re.compile(re.escape(str(texto or "").strip()), re.IGNORECASE)
    linha = linhas.filter(has_text=padrao).first

    try:
        linha.wait_for(state="visible", timeout=timeout_ms)
        return linha
    except PlaywrightTimeoutError:
        return None

def _resultado(
    usuario: UsuarioImportacao,
    status: StatusImportacao,
    detalhes: str,
) -> ResultadoImportacao:
    return ResultadoImportacao(
        login=usuario.login,
        nome_completo=usuario.nome_completo,
        email=usuario.email,
        status=status,
        detalhes=detalhes,
    )


def _primeiro_visivel(
    janela_sistema: FrameLocator,
    seletores: tuple[str, ...],
    timeout_ms: int = 5000,
) -> Locator:
    ultimo_erro: Exception | None = None

    for seletor in seletores:
        locator = janela_sistema.locator(seletor).first

        try:
            locator.wait_for(state="visible", timeout=timeout_ms)
            return locator
        except PlaywrightTimeoutError as exc:
            ultimo_erro = exc

    raise PlaywrightTimeoutError(
        f"Nenhum seletor ficou visivel: {', '.join(seletores)}"
    ) from ultimo_erro


def _clicar_botao(janela_sistema: FrameLocator, nome: str, timeout_ms: int = 10000) -> None:
    botao = janela_sistema.get_by_role("button", name=nome).first
    botao.wait_for(state="visible", timeout=timeout_ms)
    botao.click(timeout=timeout_ms)


def _linha_tabela_por_login(
    linhas: Locator,
    login: str,
    indice_coluna_login: int,
) -> Locator | None:
    total_linhas = linhas.count()

    for indice in range(total_linhas):
        linha = linhas.nth(indice)

        try:
            if not linha.is_visible(timeout=500):
                continue
        except Exception:
            continue

        try:
            classe = linha.get_attribute("class", timeout=500) or ""
        except Exception:
            classe = ""

        if "ui-datatable-empty-message" in classe:
            continue

        celulas = linha.locator("td")

        try:
            if celulas.count() <= indice_coluna_login:
                continue

            texto_login = celulas.nth(indice_coluna_login).inner_text(
                timeout=1000
            )
        except Exception:
            continue

        if _login_confere(texto_login, login):
            return linha

    return None


def _linha_vazia_visivel(linhas: Locator) -> bool:
    total_linhas = linhas.count()

    for indice in range(total_linhas):
        linha = linhas.nth(indice)

        try:
            if not linha.is_visible(timeout=250):
                continue

            classe = linha.get_attribute("class", timeout=250) or ""
            texto = linha.inner_text(timeout=250)
        except Exception:
            continue

        if "ui-datatable-empty-message" in classe:
            return True

        if TEXTO_NENHUM_REGISTRO in texto:
            return True

    return False


def _aguardar_resultado_pesquisa_usuario(
    janela_sistema: FrameLocator,
    login: str,
    timeout_ms: int = 10000,
) -> tuple[str, Locator | None]:
    linhas = janela_sistema.locator(SELECTOR_TABELA_USUARIOS)
    fim = time.monotonic() + (timeout_ms / 1000)

    while time.monotonic() < fim:
        linha = _linha_tabela_por_login(
            linhas=linhas,
            login=login,
            indice_coluna_login=2,
        )

        if linha is not None:
            return "encontrado", linha

        if _linha_vazia_visivel(linhas):
            return "nao_encontrado", None

        try:
            if linhas.count() > 0 and linhas.first.is_visible(timeout=250):
                return "sem_login_exato", None
        except Exception:
            pass

        time.sleep(0.15)

    return "indefinido", None


def _aguardar_resultado_identity(
    janela_sistema: FrameLocator,
    login: str,
    timeout_ms: int = 10000,
) -> tuple[str, Locator | None]:
    linhas = janela_sistema.locator(SELECTOR_TABELA_IDENTITY)
    fim = time.monotonic() + (timeout_ms / 1000)

    while time.monotonic() < fim:
        linha = _linha_tabela_por_texto_visivel(
            linhas=linhas,
            texto=login,
            timeout_ms=300,
        )

        if linha is not None:
            return "encontrado", linha

        if _linha_vazia_visivel(linhas):
            return "nao_encontrado", None

        time.sleep(0.15)

    return "indefinido", None


def _pesquisar_usuario_importado(
    janela_sistema: FrameLocator,
    login: str,
) -> tuple[str, Locator | None]:
    campo_login = _primeiro_visivel(janela_sistema, (SELECTOR_PESQUISA_LOGIN,))
    campo_login.click()
    campo_login.fill("")
    campo_login.fill(login)

    _clicar_botao(janela_sistema, "Pesquisar")
    return _aguardar_resultado_pesquisa_usuario(janela_sistema, login)


def _pesquisar_usuario_identity(
    janela_sistema: FrameLocator,
    login: str,
) -> tuple[str, Locator | None]:
    campo_login = _primeiro_visivel(janela_sistema, (SELECTOR_IMPORTACAO_LOGIN,))
    campo_login.click()
    campo_login.fill("")
    campo_login.fill(login)

    _clicar_botao(janela_sistema, "Pesquisar")
    return _aguardar_resultado_identity(janela_sistema, login)


def _abrir_importacao_usuario(janela_sistema: FrameLocator) -> None:
    _clicar_botao(janela_sistema, "Importar Usuário")
    _primeiro_visivel(janela_sistema, (SELECTOR_IMPORTACAO_LOGIN,))


def _clicar_adicionar_identity(linha_identity: Locator) -> None:
    candidatos = (
        linha_identity.get_by_role("link", name=re.compile("Adicionar", re.I)).first,
        linha_identity.get_by_role("button", name=re.compile("Adicionar", re.I)).first,
        linha_identity.locator("a[title*='Adicionar' i]").first,
        linha_identity.locator("button[title*='Adicionar' i]").first,
        linha_identity.locator("a[aria-label*='Adicionar' i]").first,
        linha_identity.locator("button[aria-label*='Adicionar' i]").first,
        linha_identity.locator("a.ui-commandlink, button.ui-button").first,
    )

    ultimo_erro: Exception | None = None

    for candidato in candidatos:
        try:
            candidato.wait_for(state="visible", timeout=2000)
            candidato.click(timeout=5000)
            return
        except Exception as exc:
            ultimo_erro = exc

    raise PlaywrightTimeoutError(
        "Botao/acao 'Adicionar' nao localizado na linha do Identity Manager."
    ) from ultimo_erro


def _marcar_usuario_ativo(janela_sistema: FrameLocator) -> None:
    icone = janela_sistema.locator(".ui-chkbox-icon").first
    icone.wait_for(state="visible", timeout=5000)

    try:
        classe = icone.get_attribute("class", timeout=1000) or ""
    except Exception:
        classe = ""

    if "ui-icon-check" not in classe:
        icone.click(timeout=5000)


def _preencher_cadastro_usuario(
    janela_sistema: FrameLocator,
    usuario: UsuarioImportacao,
) -> None:
    campo_nome = _primeiro_visivel(janela_sistema, (SELECTOR_CADASTRO_NOME,))
    campo_email = _primeiro_visivel(janela_sistema, (SELECTOR_CADASTRO_EMAIL,))

    campo_nome.fill("")
    campo_nome.fill(usuario.nome_completo)
    campo_email.fill("")
    campo_email.fill(usuario.email)
    _marcar_usuario_ativo(janela_sistema)


def _aguardar_mensagem_gravacao(
    janela_sistema: FrameLocator,
    timeout_ms: int = 10000,
) -> tuple[str, str]:
    mensagem_sucesso = janela_sistema.locator("#messagesInDialog div").filter(
        has_text="Usuário incluído com sucesso"
    )
    mensagem_duplicado = janela_sistema.locator("#messagesInDialog div").filter(
        has_text="Já existe um usuário com este"
    )
    mensagem_erro = janela_sistema.locator(
        "#messagesInDialog .ui-messages-error-summary"
    )
    fim = time.monotonic() + (timeout_ms / 1000)

    while time.monotonic() < fim:
        try:
            if mensagem_sucesso.count() > 0 and mensagem_sucesso.first.is_visible(
                timeout=250
            ):
                return "sucesso", mensagem_sucesso.first.inner_text(
                    timeout=1000
                ).strip()
        except Exception:
            pass

        try:
            if mensagem_duplicado.count() > 0 and mensagem_duplicado.first.is_visible(
                timeout=250
            ):
                return "duplicado", mensagem_duplicado.first.inner_text(
                    timeout=1000
                ).strip()
        except Exception:
            pass

        try:
            if mensagem_erro.count() > 0 and mensagem_erro.first.is_visible(
                timeout=250
            ):
                return "erro", mensagem_erro.first.inner_text(timeout=1000).strip()
        except Exception:
            pass

        time.sleep(0.15)

    return "indefinido", "A gravacao nao retornou mensagem dentro do tempo limite."


def _gravar_cadastro_usuario(janela_sistema: FrameLocator) -> tuple[str, str]:
    _clicar_botao(janela_sistema, "Gravar")
    return _aguardar_mensagem_gravacao(janela_sistema)


def _validar_usuario(usuario: UsuarioImportacao) -> list[str]:
    campos_em_branco = []

    if _valor_em_branco(usuario.login):
        campos_em_branco.append("Login")

    if _valor_em_branco(usuario.nome_completo):
        campos_em_branco.append("Nome Completo")

    if _valor_em_branco(usuario.email):
        campos_em_branco.append("E-mail")

    return campos_em_branco


def fazer_login(
    page: Page,
    usuario_rede: str,
    senha: str,
    *,
    url_aghu: str = AGHU_URL,
):
    resultado = autenticar_aghu_page(
        page=page,
        usuario=usuario_rede,
        senha=senha,
        url_login=url_aghu,
        timeout_ms=15000,
    )
    exigir_login_valido(resultado)
    return resultado


def trocar_aba_aghux(
    context: BrowserContext,
    page_atual: Page,
    usuario_rede: str,
    senha: str,
    *,
    url_aghu: str = AGHU_URL,
) -> Page:
    try:
        page_atual.close()
    except Exception:
        pass

    nova_page = context.new_page()
    nova_page.goto(url_aghu)

    resultado = autenticar_aghu_page(
        page=nova_page,
        usuario=usuario_rede,
        senha=senha,
        url_login=url_aghu,
        timeout_ms=15000,
    )
    exigir_login_valido(resultado)

    return nova_page


def navegar_ate_cadastro_usuario(
    context: BrowserContext,
    page_atual: Page,
    usuario_rede: str,
    senha: str,
    *,
    url_aghu: str = AGHU_URL,
) -> tuple[Page, FrameLocator]:
    page = page_atual

    for tentativa in range(2):
        try:
            janela_sistema = navegar_menu_aghu(
                page=page,
                caminho=CAMINHO_MENU_CADASTRO_USUARIO,
            )
            _primeiro_visivel(janela_sistema, (SELECTOR_PESQUISA_LOGIN,))
            janela_sistema.get_by_role("button", name="Pesquisar").first.wait_for(
                state="visible",
                timeout=15000,
            )

            return page, janela_sistema

        except Exception:
            if tentativa == 0:
                page = trocar_aba_aghux(
                    context=context,
                    page_atual=page,
                    usuario_rede=usuario_rede,
                    senha=senha,
                    url_aghu=url_aghu,
                )
                continue

            raise

    raise RuntimeError("Falha ao navegar ate o cadastro de usuario.")


def garantir_tela_pesquisa_usuario(
    context: BrowserContext,
    page_atual: Page,
    janela_atual: FrameLocator,
    usuario_rede: str,
    senha: str,
    *,
    url_aghu: str = AGHU_URL,
) -> tuple[Page, FrameLocator]:
    try:
        _primeiro_visivel(janela_atual, (SELECTOR_PESQUISA_LOGIN,), timeout_ms=1500)
        return page_atual, janela_atual
    except Exception:
        pass

    try:
        janela_sistema = navegar_menu_aghu(
            page=page_atual,
            caminho=CAMINHO_MENU_CADASTRO_USUARIO,
        )
        _primeiro_visivel(janela_sistema, (SELECTOR_PESQUISA_LOGIN,))
        return page_atual, janela_sistema
    except Exception:
        page = trocar_aba_aghux(
            context=context,
            page_atual=page_atual,
            usuario_rede=usuario_rede,
            senha=senha,
            url_aghu=url_aghu,
        )
        return navegar_ate_cadastro_usuario(
            context=context,
            page_atual=page,
            usuario_rede=usuario_rede,
            senha=senha,
            url_aghu=url_aghu,
        )


def importar_usuario(
    janela_sistema: FrameLocator,
    usuario: UsuarioImportacao,
) -> ResultadoImportacao:
    login = _normalizar_login(usuario.login)
    usuario = UsuarioImportacao(
        login=login,
        nome_completo=usuario.nome_completo.strip(),
        email=usuario.email.strip(),
    )

    campos_em_branco = _validar_usuario(usuario)

    if campos_em_branco:
        return _resultado(
            usuario,
            STATUS_IGNORADO,
            "Linha ignorada: campos obrigatorios em branco: "
            + ", ".join(campos_em_branco),
        )

    estado_pesquisa, _ = _pesquisar_usuario_importado(janela_sistema, login)

    if estado_pesquisa == "encontrado":
        return _resultado(
            usuario,
            STATUS_JA_IMPORTADO,
            "Usuario ja estava importado no AGHUX.",
        )

    if estado_pesquisa == "indefinido":
        return _resultado(
            usuario,
            STATUS_ERRO,
            "Pesquisa inicial nao retornou estado conclusivo.",
        )

    _abrir_importacao_usuario(janela_sistema)
    estado_identity, linha_identity = _pesquisar_usuario_identity(
        janela_sistema,
        login,
    )

    if estado_identity != "encontrado" or linha_identity is None:
        return _resultado(
            usuario,
            STATUS_NAO_ENCONTRADO,
            "Usuario nao localizado para importacao no Identity Manager.",
        )

    _clicar_adicionar_identity(linha_identity)
    _preencher_cadastro_usuario(janela_sistema, usuario)
    estado_gravacao, mensagem = _gravar_cadastro_usuario(janela_sistema)

    if estado_gravacao == "sucesso":
        return _resultado(usuario, STATUS_IMPORTADO, mensagem)

    if estado_gravacao == "duplicado":
        return _resultado(usuario, STATUS_JA_IMPORTADO, mensagem)

    return _resultado(usuario, STATUS_ERRO, mensagem)


def processar_usuarios(
    context: BrowserContext,
    page_inicial: Page,
    janela_sistema_inicial: FrameLocator,
    usuarios: list[UsuarioImportacao],
    usuario_rede: str,
    senha: str,
    *,
    url_aghu: str = AGHU_URL,
) -> list[ResultadoImportacao]:
    resultados: list[ResultadoImportacao] = []
    page = page_inicial
    janela_sistema = janela_sistema_inicial

    for usuario in usuarios:
        resultado_linha: ResultadoImportacao | None = None

        for tentativa in range(2):
            try:
                page, janela_sistema = garantir_tela_pesquisa_usuario(
                    context=context,
                    page_atual=page,
                    janela_atual=janela_sistema,
                    usuario_rede=usuario_rede,
                    senha=senha,
                    url_aghu=url_aghu,
                )
                resultado_linha = importar_usuario(janela_sistema, usuario)
                break
            except Exception as exc:
                if tentativa == 0:
                    page = trocar_aba_aghux(
                        context=context,
                        page_atual=page,
                        usuario_rede=usuario_rede,
                        senha=senha,
                        url_aghu=url_aghu,
                    )
                    page, janela_sistema = navegar_ate_cadastro_usuario(
                        context=context,
                        page_atual=page,
                        usuario_rede=usuario_rede,
                        senha=senha,
                        url_aghu=url_aghu,
                    )
                    continue

                resultado_linha = _resultado(
                    usuario,
                    STATUS_ERRO,
                    f"Falha tecnica durante a importacao: {exc}",
                )

        if resultado_linha is None:
            resultado_linha = _resultado(
                usuario,
                STATUS_ERRO,
                "Falha tecnica durante a importacao.",
            )

        resultados.append(resultado_linha)

    return resultados


def ler_planilha_usuarios(caminho_planilha: str) -> list[UsuarioImportacao]:
    caminho = Path(caminho_planilha)

    if not caminho.exists():
        raise FileNotFoundError(f"Planilha nao encontrada: {caminho}")

    if caminho.suffix.lower() != ".xlsx":
        raise ValueError("A planilha de lote deve ser um arquivo .xlsx.")

    df = pd.read_excel(caminho, dtype=str, engine="openpyxl").fillna("")
    df.columns = df.columns.str.strip()

    colunas_faltantes = [
        coluna for coluna in COLUNAS_OBRIGATORIAS_PLANILHA if coluna not in df.columns
    ]

    if colunas_faltantes:
        raise ValueError(
            "Planilha invalida. Colunas obrigatorias ausentes: "
            + ", ".join(colunas_faltantes)
        )

    usuarios = []

    for _, linha in df.iterrows():
        usuarios.append(
            UsuarioImportacao(
                login=str(linha.get("Login", "")).strip(),
                nome_completo=str(linha.get("Nome Completo", "")).strip(),
                email=str(linha.get("E-mail", "")).strip(),
            )
        )

    return usuarios


def salvar_relatorio_resultados(
    resultados: list[ResultadoImportacao],
    caminho_saida: str,
) -> Path:
    caminho = Path(caminho_saida).expanduser()

    if not caminho.suffix:
        caminho = caminho.with_suffix(".xlsx")

    if caminho.suffix.lower() != ".xlsx":
        raise ValueError("O relatorio de saida deve ser um arquivo .xlsx.")

    caminho.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(
        [
            {
                "Login": resultado.login,
                "Nome Completo": resultado.nome_completo,
                "E-mail": resultado.email,
                "Status": resultado.status,
                "Detalhes": resultado.detalhes,
            }
            for resultado in resultados
        ]
    )

    with pd.ExcelWriter(caminho, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Resultado")
        worksheet = writer.sheets["Resultado"]
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions

        for coluna in worksheet.columns:
            largura = max(len(str(celula.value or "")) for celula in coluna)
            worksheet.column_dimensions[coluna[0].column_letter].width = min(
                largura + 2,
                70,
            )

    return caminho


def executar_importacao_usuarios(
    usuarios: list[UsuarioImportacao],
    usuario_rede: str,
    senha: str,
    *,
    url_aghu: str = AGHU_URL,
    mostrar_browser: bool = True,
) -> list[ResultadoImportacao]:
    if not usuario_rede or not senha:
        raise ValueError("Preencha usuario de rede e senha.")

    if not url_aghu:
        raise ValueError("Informe o ambiente do AGHU.")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=not mostrar_browser,
            slow_mo=500,
        )
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        try:
            page.goto(url_aghu)
            fazer_login(page, usuario_rede, senha, url_aghu=url_aghu)
            page, janela_sistema = navegar_ate_cadastro_usuario(
                context=context,
                page_atual=page,
                usuario_rede=usuario_rede,
                senha=senha,
                url_aghu=url_aghu,
            )
            return processar_usuarios(
                context=context,
                page_inicial=page,
                janela_sistema_inicial=janela_sistema,
                usuarios=usuarios,
                usuario_rede=usuario_rede,
                senha=senha,
                url_aghu=url_aghu,
            )
        finally:
            browser.close()


def executar_importacao_individual(
    usuario_rede: str,
    senha: str,
    login: str,
    nome_completo: str,
    email: str,
    *,
    url_aghu: str = AGHU_URL,
    mostrar_browser: bool = True,
) -> ResultadoImportacao:
    resultados = executar_importacao_usuarios(
        usuarios=[
            UsuarioImportacao(
                login=login,
                nome_completo=nome_completo,
                email=email,
            )
        ],
        usuario_rede=usuario_rede,
        senha=senha,
        url_aghu=url_aghu,
        mostrar_browser=mostrar_browser,
    )

    return resultados[0]


def executar_importacao_lote(
    usuario_rede: str,
    senha: str,
    caminho_planilha: str,
    caminho_relatorio: str,
    *,
    url_aghu: str = AGHU_URL,
    mostrar_browser: bool = True,
) -> tuple[list[ResultadoImportacao], Path]:
    usuarios = ler_planilha_usuarios(caminho_planilha)
    resultados = executar_importacao_usuarios(
        usuarios=usuarios,
        usuario_rede=usuario_rede,
        senha=senha,
        url_aghu=url_aghu,
        mostrar_browser=mostrar_browser,
    )
    relatorio = salvar_relatorio_resultados(resultados, caminho_relatorio)

    return resultados, relatorio
