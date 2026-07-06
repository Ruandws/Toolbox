import ctypes
import os
import re
import time
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Literal

import pandas as pd
from playwright.sync_api import BrowserContext, FrameLocator, Locator, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from autenticador import AGHU_URL, autenticar_aghu_page, exigir_login_valido
from menu import navegar_menu_aghu


BASE_DIR = Path(__file__).resolve().parent
CAMINHO_MENU_CADASTRO_USUARIO = (
    "Outros Módulos",
    "Configuração",
    "Acesso",
    "Usuario",
)

COLUNAS_OBRIGATORIAS_PLANILHA = ("Login", "Nome Completo", "E-mail")
ALIASES_COLUNAS_PLANILHA = {
    "login": (
        "Login",
        "login",
        "Usuário",
        "Usuario",
        "usuário",
        "usuario",
        "User",
        "Usuário/Login",
        "Usuario/Login",
    ),
    "nome_completo": (
        "Nome Completo",
        "Nome completo",
        "nome completo",
        "Nome",
    ),
    "email": (
        "E-mail",
        "E-Mail",
        "Email",
        "email",
    ),
}
PADRAO_EMAIL_MINIMO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PADRAO_LOGIN_VALIDO = re.compile(r"^[A-Za-z0-9._-]+$")

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
TEMPO_MAXIMO_CONSULTA_USUARIO_MS = 130000
TEMPO_MAXIMO_GRAVACAO_USUARIO_MS = 10000
TEMPO_DETECCAO_WIDGET_CARREGAMENTO_MS = 2000
TEMPO_ESTABILIDADE_RESULTADO_MS = 250


def esconder_console_windows() -> None:
    if os.name != "nt":
        return

    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 0)


@contextmanager
def _controle_saida_terminal(mostrar_console: bool) -> Iterator[None]:
    if mostrar_console:
        yield
        return

    esconder_console_windows()

    with open(os.devnull, "w", encoding="utf-8") as destino_nulo:
        with redirect_stdout(destino_nulo), redirect_stderr(destino_nulo):
            yield


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


def _texto_para_validacao(valor: object) -> str:
    if _valor_em_branco(valor):
        return ""

    return str(valor)


def _normalizar_nome_completo(valor: object) -> str:
    return re.sub(r"\s+", " ", _texto_para_validacao(valor)).strip()


def _normalizar_usuario_importacao(
    usuario: UsuarioImportacao,
) -> UsuarioImportacao:
    return UsuarioImportacao(
        login=_normalizar_login(usuario.login),
        nome_completo=_normalizar_nome_completo(usuario.nome_completo),
        email=_texto_para_validacao(usuario.email).strip(),
    )


def _nome_coluna_planilha(campo: str) -> str:
    return ALIASES_COLUNAS_PLANILHA[campo][0]


def _valor_por_alias_planilha(linha: pd.Series, campo: str) -> str:
    for alias in ALIASES_COLUNAS_PLANILHA[campo]:
        if alias in linha.index:
            return str(linha.get(alias, ""))
    return ""


def _nome_tem_espacos_indevidos(nome: str) -> bool:
    nome_sem_laterais = nome.strip()

    return (
        nome != nome_sem_laterais
        or bool(re.search(r"[^\S ]", nome_sem_laterais))
        or bool(re.search(r" {2,}", nome_sem_laterais))
    )


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


def _numero_linha_usuario(indice: int) -> int:
    return indice + 1


def _criar_log_resultado(resultado: ResultadoImportacao) -> dict:
    return {
        "Login": resultado.login,
        "Nome Completo": resultado.nome_completo,
        "E-mail": resultado.email,
        "Status": resultado.status,
        "Detalhes": resultado.detalhes,
    }


def _registrar_inicio_linha(
    indice_linha: int,
    total_linhas: int,
    usuario: UsuarioImportacao,
) -> None:
    print("\n========================================")
    print(
        f"Investigando [{_numero_linha_usuario(indice_linha)}/{total_linhas}]: "
        f"Usuario [{usuario.login}] | E-mail [{usuario.email}]"
    )


def _registrar_linha_ignorada(
    indice_linha: int,
    total_linhas: int,
    resultado: ResultadoImportacao,
) -> None:
    print("\n========================================")
    print(
        f"Ignorando linha [{_numero_linha_usuario(indice_linha)}/{total_linhas}]: "
        f"{resultado.detalhes}"
    )


def _gerar_csv_logs(
    resultados: list[ResultadoImportacao],
    usuario_rede: str,
    diretorio_logs: str | os.PathLike | None,
) -> str:
    print("\nFim da leitura. Gerando arquivo CSV de logs...")
    df_logs = pd.DataFrame([_criar_log_resultado(resultado) for resultado in resultados])
    pasta_logs = Path(diretorio_logs) if diretorio_logs else BASE_DIR / "logs"
    pasta_logs.mkdir(parents=True, exist_ok=True)
    data_hora_atual = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_arquivo_log = pasta_logs / f"log_resultado_{data_hora_atual}.csv"

    with nome_arquivo_log.open("w", encoding="utf-8-sig") as arquivo:
        arquivo.write(f"Atualizado por: {usuario_rede}\n")

    df_logs.to_csv(
        nome_arquivo_log,
        index=False,
        sep=";",
        encoding="utf-8-sig",
        mode="a",
    )

    print(f"Relatorio CSV gerado com sucesso: {nome_arquivo_log}")
    return str(nome_arquivo_log)


def _resultados_preenchidos(
    resultados: list[ResultadoImportacao | None],
) -> list[ResultadoImportacao]:
    return [resultado for resultado in resultados if resultado is not None]


def _finalizar_resultados_importacao(
    resultados: list[ResultadoImportacao | None],
    usuario_rede: str,
    diretorio_logs: str | os.PathLike | None,
    gerar_csv_log: bool,
) -> list[ResultadoImportacao]:
    resultados_finais = _resultados_preenchidos(resultados)

    if gerar_csv_log:
        _gerar_csv_logs(
            resultados=resultados_finais,
            usuario_rede=usuario_rede,
            diretorio_logs=diretorio_logs,
        )

    return resultados_finais


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


def _widget_carregamento_consulta(janela_sistema: FrameLocator) -> Locator:
    return janela_sistema.get_by_label("Carregando").get_by_text("Aguarde...").first


def _titulo_widget_carregamento(janela_sistema: FrameLocator) -> Locator:
    return janela_sistema.locator("div").filter(
        has_text=re.compile(r"^Carregando$")
    ).first


def _widgets_carregamento(janela_sistema: FrameLocator) -> Iterator[Locator]:
    for criar_widget in (
        _widget_carregamento_consulta,
        _titulo_widget_carregamento,
    ):
        try:
            yield criar_widget(janela_sistema)
        except Exception:
            continue


def _existe_carregamento_visivel(janela_sistema: FrameLocator) -> bool:
    for widget in _widgets_carregamento(janela_sistema):
        try:
            if widget.is_visible(timeout=100):
                return True
        except Exception:
            continue

    return False


def _aguardar_carregamento_sumir(
    janela_sistema: FrameLocator,
    timeout_ms: int,
    deteccao_ms: int = 0,
) -> bool:
    inicio = time.monotonic()
    widgets = list(_widgets_carregamento(janela_sistema))
    carregamento_detectado = False

    for widget in widgets:
        try:
            widget.wait_for(state="visible", timeout=deteccao_ms)
            carregamento_detectado = True
        except PlaywrightTimeoutError:
            continue
        except Exception:
            continue

    if not carregamento_detectado:
        return not _existe_carregamento_visivel(janela_sistema)

    for widget in widgets:
        tempo_decorrido_ms = int((time.monotonic() - inicio) * 1000)
        timeout_restante_ms = max(timeout_ms - tempo_decorrido_ms, 1)

        try:
            widget.wait_for(state="hidden", timeout=timeout_restante_ms)
        except PlaywrightTimeoutError:
            return False
        except Exception:
            continue

    return not _existe_carregamento_visivel(janela_sistema)


def _aguardar_ciclo_carregamento_consulta(
    janela_sistema: FrameLocator,
    *,
    timeout_ms: int = TEMPO_MAXIMO_CONSULTA_USUARIO_MS,
    deteccao_ms: int = TEMPO_DETECCAO_WIDGET_CARREGAMENTO_MS,
) -> bool:
    if _aguardar_carregamento_sumir(
        janela_sistema,
        timeout_ms=timeout_ms,
        deteccao_ms=deteccao_ms,
    ):
        return True

    raise PlaywrightTimeoutError(
        "Consulta do AGHUX permaneceu em carregamento alem do tempo limite."
    )


def _pode_confirmar_resultado_sem_carregamento(
    *,
    estado_desde: float,
    consulta_concluida: bool,
    estabilidade_resultado_ms: int,
) -> bool:
    tempo_estavel_ms = (time.monotonic() - estado_desde) * 1000

    return consulta_concluida and tempo_estavel_ms >= estabilidade_resultado_ms


def _aguardar_resultado_pesquisa_usuario(
    janela_sistema: FrameLocator,
    login: str,
    timeout_ms: int = TEMPO_MAXIMO_CONSULTA_USUARIO_MS,
    estabilidade_resultado_ms: int = TEMPO_ESTABILIDADE_RESULTADO_MS,
    consulta_concluida: bool = False,
) -> tuple[str, Locator | None]:
    linhas = janela_sistema.locator(SELECTOR_TABELA_USUARIOS)
    inicio = time.monotonic()
    fim = inicio + (timeout_ms / 1000)
    estado_pendente: str | None = None
    estado_desde = inicio
    carregamento_observado = False

    while time.monotonic() < fim:
        carregando = _existe_carregamento_visivel(janela_sistema)

        if carregando:
            carregamento_observado = True
            consulta_concluida = False
        elif carregamento_observado:
            consulta_concluida = True

        linha = _linha_tabela_por_login(
            linhas=linhas,
            login=login,
            indice_coluna_login=2,
        )

        if linha is not None:
            return "encontrado", linha

        estado_atual: str | None = None

        if _linha_vazia_visivel(linhas):
            estado_atual = "nao_encontrado"
        else:
            try:
                if linhas.count() > 0 and linhas.first.is_visible(timeout=250):
                    estado_atual = "sem_login_exato"
            except Exception:
                pass

        if carregando:
            estado_pendente = None
            estado_desde = time.monotonic()
        elif estado_atual is not None:
            if estado_atual != estado_pendente:
                estado_pendente = estado_atual
                estado_desde = time.monotonic()
            elif _pode_confirmar_resultado_sem_carregamento(
                estado_desde=estado_desde,
                consulta_concluida=consulta_concluida,
                estabilidade_resultado_ms=estabilidade_resultado_ms,
            ):
                return estado_atual, None
        else:
            estado_pendente = None
            estado_desde = time.monotonic()

        time.sleep(0.15)

    return "indefinido", None


def _aguardar_resultado_identity(
    janela_sistema: FrameLocator,
    login: str,
    timeout_ms: int = TEMPO_MAXIMO_CONSULTA_USUARIO_MS,
    estabilidade_resultado_ms: int = TEMPO_ESTABILIDADE_RESULTADO_MS,
    consulta_concluida: bool = False,
) -> tuple[str, Locator | None]:
    linhas = janela_sistema.locator(SELECTOR_TABELA_IDENTITY)
    inicio = time.monotonic()
    fim = inicio + (timeout_ms / 1000)
    vazio_desde: float | None = None
    carregamento_observado = False

    while time.monotonic() < fim:
        carregando = _existe_carregamento_visivel(janela_sistema)

        if carregando:
            carregamento_observado = True
            consulta_concluida = False
        elif carregamento_observado:
            consulta_concluida = True

        linha = _linha_tabela_por_texto_visivel(
            linhas=linhas,
            texto=login,
            timeout_ms=300,
        )

        if linha is not None:
            return "encontrado", linha

        if carregando:
            vazio_desde = None
        elif _linha_vazia_visivel(linhas):
            if vazio_desde is None:
                vazio_desde = time.monotonic()
            elif _pode_confirmar_resultado_sem_carregamento(
                estado_desde=vazio_desde,
                consulta_concluida=consulta_concluida,
                estabilidade_resultado_ms=estabilidade_resultado_ms,
            ):
                return "nao_encontrado", None
        else:
            vazio_desde = None

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
    consulta_concluida = _aguardar_ciclo_carregamento_consulta(janela_sistema)
    return _aguardar_resultado_pesquisa_usuario(
        janela_sistema,
        login,
        consulta_concluida=consulta_concluida,
    )


def _pesquisar_usuario_identity(
    janela_sistema: FrameLocator,
    login: str,
) -> tuple[str, Locator | None]:
    campo_login = _primeiro_visivel(janela_sistema, (SELECTOR_IMPORTACAO_LOGIN,))
    campo_login.click()
    campo_login.fill("")
    campo_login.fill(login)

    _clicar_botao(janela_sistema, "Pesquisar")
    consulta_concluida = _aguardar_ciclo_carregamento_consulta(janela_sistema)
    return _aguardar_resultado_identity(
        janela_sistema,
        login,
        consulta_concluida=consulta_concluida,
    )


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
    timeout_ms: int = TEMPO_MAXIMO_GRAVACAO_USUARIO_MS,
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
        if _existe_carregamento_visivel(janela_sistema):
            timeout_restante_ms = int(max((fim - time.monotonic()) * 1000, 1))
            _aguardar_carregamento_sumir(
                janela_sistema,
                timeout_ms=timeout_restante_ms,
            )
            continue

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
    erros = []
    campos_em_branco = []
    login = _texto_para_validacao(usuario.login)
    nome_completo = _texto_para_validacao(usuario.nome_completo)
    email = _texto_para_validacao(usuario.email)

    if _valor_em_branco(usuario.login):
        campos_em_branco.append("Login")

    if _valor_em_branco(usuario.nome_completo):
        campos_em_branco.append("Nome Completo")

    if _valor_em_branco(usuario.email):
        campos_em_branco.append("E-mail")

    erros.extend(campos_em_branco)

    if "Login" not in campos_em_branco:
        login_sem_espacos = login.strip()

        if re.search(r"\s", login):
            erros.append("Login contem espacos indevidos")
        elif not PADRAO_LOGIN_VALIDO.fullmatch(login_sem_espacos):
            erros.append(
                "Login invalido: use apenas letras, numeros, ponto, hifen "
                "ou sublinhado"
            )

    if "Nome Completo" not in campos_em_branco and _nome_tem_espacos_indevidos(
        nome_completo
    ):
        erros.append("Nome Completo contem espacos indevidos")

    if "E-mail" not in campos_em_branco:
        email_sem_espacos = email.strip()

        if re.search(r"\s", email):
            erros.append("E-mail contem espacos indevidos")
        elif not PADRAO_EMAIL_MINIMO.fullmatch(email_sem_espacos):
            erros.append(
                "E-mail invalido: informe um endereco no formato "
                "nome@dominio.extensao"
            )

    return erros


def _detalhar_validacao_usuario(erros: list[str]) -> str:
    campos_em_branco = [
        erro for erro in erros if erro in COLUNAS_OBRIGATORIAS_PLANILHA
    ]
    demais_erros = [
        erro for erro in erros if erro not in COLUNAS_OBRIGATORIAS_PLANILHA
    ]
    detalhes = []

    if campos_em_branco:
        detalhes.append(
            "campos obrigatorios em branco: " + ", ".join(campos_em_branco)
        )

    detalhes.extend(demais_erros)

    return "Linha ignorada: " + "; ".join(detalhes) + "."


def _preparar_usuario_importacao(
    usuario: UsuarioImportacao,
) -> tuple[UsuarioImportacao, ResultadoImportacao | None]:
    usuario_normalizado = _normalizar_usuario_importacao(usuario)
    usuario_para_validacao = UsuarioImportacao(
        login=usuario.login,
        nome_completo=usuario_normalizado.nome_completo,
        email=usuario.email,
    )
    erros = _validar_usuario(usuario_para_validacao)

    if not erros:
        return usuario_normalizado, None

    return (
        usuario_normalizado,
        _resultado(
            usuario_normalizado,
            STATUS_IGNORADO,
            _detalhar_validacao_usuario(erros),
        ),
    )


def fazer_login(
    page: Page,
    usuario_rede: str,
    senha: str,
    *,
    url_aghu: str = AGHU_URL,
):
    print(f"Checando autenticacao no AGHUX com o usuario: {usuario_rede}")

    resultado = autenticar_aghu_page(
        page=page,
        usuario=usuario_rede,
        senha=senha,
        url_login=url_aghu,
        timeout_ms=15000,
    )

    if resultado.status == "sessao_ativa":
        print("Sessao ja estava ativa.")
    elif resultado.status == "sucesso":
        print("Login efetuado com sucesso.")
    else:
        print(f"Falha de autenticacao: {resultado.mensagem}")

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
    print("[Clean State] Fechando aba atual e abrindo nova aba limpa.")

    try:
        page_atual.close()
    except Exception:
        pass

    nova_page = context.new_page()
    nova_page.goto(url_aghu)
    print(f"Ambiente acessado: {nova_page.url}")

    resultado = autenticar_aghu_page(
        page=nova_page,
        usuario=usuario_rede,
        senha=senha,
        url_login=url_aghu,
        timeout_ms=15000,
    )

    if resultado.status == "sessao_ativa":
        print("Sessao reaproveitada na nova aba.")
    elif resultado.status == "sucesso":
        print("Login efetuado na nova aba.")
    else:
        print(f"Falha ao autenticar nova aba: {resultado.mensagem}")

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
    print("Navegando ate o modulo de Cadastro de Usuario...")
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
                print("Falha ao navegar no menu. Acionando Clean State...")
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
    usuario, resultado_validacao = _preparar_usuario_importacao(usuario)

    if resultado_validacao is not None:
        return resultado_validacao

    login = usuario.login

    print(f"Pesquisando usuario no AGHUX: {login}")
    estado_pesquisa, _ = _pesquisar_usuario_importado(janela_sistema, login)

    if estado_pesquisa == "encontrado":
        print("Usuario ja estava importado no AGHUX.")
        return _resultado(
            usuario,
            STATUS_JA_IMPORTADO,
            "Usuario ja estava importado no AGHUX.",
        )

    if estado_pesquisa == "indefinido":
        print("Pesquisa inicial sem retorno conclusivo.")
        return _resultado(
            usuario,
            STATUS_ERRO,
            "Pesquisa inicial nao retornou estado conclusivo.",
        )

    print("Usuario ainda nao importado. Abrindo importacao...")
    _abrir_importacao_usuario(janela_sistema)
    estado_identity, linha_identity = _pesquisar_usuario_identity(
        janela_sistema,
        login,
    )

    if estado_identity == "indefinido":
        print("Pesquisa no Identity Manager sem retorno conclusivo.")
        return _resultado(
            usuario,
            STATUS_ERRO,
            "Pesquisa no Identity Manager nao retornou estado conclusivo.",
        )

    if estado_identity != "encontrado" or linha_identity is None:
        print("Usuario nao localizado no Identity Manager.")
        return _resultado(
            usuario,
            STATUS_NAO_ENCONTRADO,
            "Usuario nao localizado para importacao no Identity Manager.",
        )

    print("Usuario localizado no Identity Manager. Adicionando...")
    _clicar_adicionar_identity(linha_identity)
    _preencher_cadastro_usuario(janela_sistema, usuario)
    estado_gravacao, mensagem = _gravar_cadastro_usuario(janela_sistema)

    if estado_gravacao == "sucesso":
        print("Cadastro finalizado com sucesso.")
        return _resultado(usuario, STATUS_IMPORTADO, mensagem)

    if estado_gravacao == "duplicado":
        print("AGHUX informou usuario duplicado/ja importado.")
        return _resultado(usuario, STATUS_JA_IMPORTADO, mensagem)

    print(f"Erro retornado pelo AGHUX: {mensagem}")
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
    indices_originais: list[int] | None = None,
    total_usuarios: int | None = None,
) -> list[ResultadoImportacao]:
    resultados: list[ResultadoImportacao] = []
    page = page_inicial
    janela_sistema = janela_sistema_inicial
    total_linhas = total_usuarios if total_usuarios is not None else len(usuarios)

    for posicao, usuario in enumerate(usuarios):
        indice_linha = (
            indices_originais[posicao]
            if indices_originais is not None and posicao < len(indices_originais)
            else posicao
        )
        usuario, resultado_validacao = _preparar_usuario_importacao(usuario)

        if resultado_validacao is not None:
            _registrar_linha_ignorada(
                indice_linha=indice_linha,
                total_linhas=total_linhas,
                resultado=resultado_validacao,
            )
            resultados.append(resultado_validacao)
            continue

        _registrar_inicio_linha(
            indice_linha=indice_linha,
            total_linhas=total_linhas,
            usuario=usuario,
        )
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
                    print(
                        "Falha tecnica durante a importacao. "
                        "Tentando novamente em nova aba..."
                    )
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
                print(f"Falha tecnica definitiva: {exc}")

        if resultado_linha is None:
            resultado_linha = _resultado(
                usuario,
                STATUS_ERRO,
                "Falha tecnica durante a importacao.",
            )

        print(
            f"Anotando no diario: [{resultado_linha.status}] "
            f"{resultado_linha.detalhes}"
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

    colunas_faltantes = []
    for campo in ALIASES_COLUNAS_PLANILHA:
        if not any(alias in df.columns for alias in ALIASES_COLUNAS_PLANILHA[campo]):
            colunas_faltantes.append(_nome_coluna_planilha(campo))

    if colunas_faltantes:
        raise ValueError(
            "Planilha invalida. Colunas obrigatorias ausentes: "
            + ", ".join(colunas_faltantes)
        )

    usuarios = []

    for _, linha in df.iterrows():
        usuarios.append(
            UsuarioImportacao(
                login=_valor_por_alias_planilha(linha, "login"),
                nome_completo=_valor_por_alias_planilha(linha, "nome_completo"),
                email=_valor_por_alias_planilha(linha, "email"),
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
    mostrar_console: bool = True,
    diretorio_logs: str | os.PathLike | None = None,
    gerar_csv_log: bool = True,
) -> list[ResultadoImportacao]:
    if not usuario_rede or not senha:
        raise ValueError("Preencha usuario de rede e senha.")

    if not url_aghu:
        raise ValueError("Informe o ambiente do AGHU.")

    with _controle_saida_terminal(mostrar_console):
        return _executar_importacao_usuarios_com_saida_configurada(
            usuarios=usuarios,
            usuario_rede=usuario_rede,
            senha=senha,
            url_aghu=url_aghu,
            mostrar_browser=mostrar_browser,
            diretorio_logs=diretorio_logs,
            gerar_csv_log=gerar_csv_log,
        )


def _executar_importacao_usuarios_com_saida_configurada(
    usuarios: list[UsuarioImportacao],
    usuario_rede: str,
    senha: str,
    *,
    url_aghu: str,
    mostrar_browser: bool,
    diretorio_logs: str | os.PathLike | None,
    gerar_csv_log: bool,
) -> list[ResultadoImportacao]:

    resultados_prevalidacao: list[ResultadoImportacao | None] = []
    usuarios_validos = []
    total_usuarios = len(usuarios)

    for usuario in usuarios:
        usuario_normalizado, resultado_validacao = _preparar_usuario_importacao(
            usuario
        )
        resultados_prevalidacao.append(resultado_validacao)

        if resultado_validacao is None:
            usuarios_validos.append(usuario_normalizado)

    if not usuarios_validos:
        for indice, resultado in enumerate(resultados_prevalidacao):
            if resultado is not None:
                _registrar_linha_ignorada(
                    indice_linha=indice,
                    total_linhas=total_usuarios,
                    resultado=resultado,
                )

        return _finalizar_resultados_importacao(
            resultados=resultados_prevalidacao,
            usuario_rede=usuario_rede,
            diretorio_logs=diretorio_logs,
            gerar_csv_log=gerar_csv_log,
        )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=not mostrar_browser,
            slow_mo=500,
        )
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        try:
            page.goto(url_aghu)
            print(f"Ambiente acessado: {page.url}")
            fazer_login(page, usuario_rede, senha, url_aghu=url_aghu)
            page, janela_sistema = navegar_ate_cadastro_usuario(
                context=context,
                page_atual=page,
                usuario_rede=usuario_rede,
                senha=senha,
                url_aghu=url_aghu,
            )
            resultados_processados = processar_usuarios(
                context=context,
                page_inicial=page,
                janela_sistema_inicial=janela_sistema,
                usuarios=usuarios,
                usuario_rede=usuario_rede,
                senha=senha,
                url_aghu=url_aghu,
                total_usuarios=total_usuarios,
            )

            return _finalizar_resultados_importacao(
                resultados=resultados_processados,
                usuario_rede=usuario_rede,
                diretorio_logs=diretorio_logs,
                gerar_csv_log=gerar_csv_log,
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
    mostrar_console: bool = True,
    diretorio_logs: str | os.PathLike | None = None,
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
        mostrar_console=mostrar_console,
        diretorio_logs=diretorio_logs,
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
    mostrar_console: bool = True,
    diretorio_logs: str | os.PathLike | None = None,
) -> tuple[list[ResultadoImportacao], Path]:
    usuarios = ler_planilha_usuarios(caminho_planilha)
    resultados = executar_importacao_usuarios(
        usuarios=usuarios,
        usuario_rede=usuario_rede,
        senha=senha,
        url_aghu=url_aghu,
        mostrar_browser=mostrar_browser,
        mostrar_console=mostrar_console,
        diretorio_logs=diretorio_logs,
    )
    relatorio = salvar_relatorio_resultados(resultados, caminho_relatorio)

    return resultados, relatorio
