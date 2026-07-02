import ctypes
import os
import re
import time
import unicodedata
from collections import Counter
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
PROJECT_DIR = BASE_DIR.parents[1]
REGRAS_PADRAO = PROJECT_DIR / "docs" / "regras_perfis_aghu.yaml"
LOGS_DIR = BASE_DIR / "logs"

CAMINHO_MENU_CADASTRO_USUARIO = (
    "Outros Módulos",
    "Configuração",
    "Acesso",
    "Usuario",
)

SELECTOR_PESQUISA_LOGIN = '[id="nomeOuLogin:nomeOuLogin:inputId"]'
SELECTOR_TABELA_USUARIOS = '[id="tabelaUsuarios:resultList_data"] > tr'
SELECTOR_PERFIL_INPUT = '[id="selecionaPerfil:selecionaPerfil:suggestion_input"]'
SELECTOR_PROTOCOLO_INPUT = (
    '[id="motivoDelegacao:motivoDelegacao:inputId_input"]'
)
SELECTOR_TABELA_PERFIS = '[id="tabelaItens:resultList_data"] > tr'
SELECTOR_MENSAGENS = (
    "#messagesInDialog .ui-messages-info-summary, "
    "#messagesInDialog .ui-messages-error-summary, "
    "#messagesInDialog .ui-messages-warn-summary"
)

TEXTO_NENHUM_REGISTRO = "Nenhum registro encontrado!"
TEMPO_MAXIMO_CONSULTA_MS = 90000
TEMPO_DETECCAO_WIDGET_CARREGAMENTO_MS = 2000
TEMPO_ESTABILIDADE_RESULTADO_MS = 250

PADRAO_LOGIN_VALIDO = re.compile(r"^[A-Za-z0-9._-]+$")
PADRAO_PROTOCOLO_VALIDO = re.compile(r"^\d{1,17}$")

STATUS_CONCEDIDO = "concedido"
STATUS_JA_EXISTENTE = "ja_existente"
STATUS_BLOQUEADO = "bloqueado"
STATUS_VALIDACAO_URA = "validacao_ura"
STATUS_USUARIO_NAO_ENCONTRADO = "usuario_nao_encontrado"
STATUS_CONFERIR_MANUAL = "conferir_manual"
STATUS_ERRO = "erro"
STATUS_IGNORADO = "ignorado"

ALIASES_COLUNAS_PLANILHA = {
    "login": (
        "Login",
        "Usuario",
        "Usuario alvo",
        "Usuario AGHU",
        "Login do usuario",
    ),
    "protocolo": (
        "Protocolo",
        "Nro Protocolo",
        "Numero Protocolo",
        "Numero do Protocolo",
        "Chamado",
    ),
    "escopo": ("Escopo",),
    "categoria": ("Categoria", "Perfil", "Grupo"),
}
CAMPOS_CONCESSAO_OBRIGATORIOS = ("login", "protocolo", "escopo", "categoria")

StatusPerfil = Literal[
    "concedido",
    "ja_existente",
    "bloqueado",
    "validacao_ura",
    "usuario_nao_encontrado",
    "conferir_manual",
    "erro",
    "ignorado",
]


@dataclass(frozen=True)
class RegraPerfil:
    escopo: str
    categoria: str
    perfis_conceder: tuple[str, ...]
    perfis_bloqueados: tuple[str, ...]
    perfis_validacao_ura: tuple[str, ...]
    observacoes: tuple[str, ...]


@dataclass(frozen=True)
class CatalogoPerfis:
    regras: tuple[RegraPerfil, ...]

    def escopos(self) -> tuple[str, ...]:
        return _unicos_preservando_ordem(regra.escopo for regra in self.regras)

    def categorias(self, escopo: str) -> tuple[str, ...]:
        escopo_norm = _normalizar_texto(escopo)
        return _unicos_preservando_ordem(
            regra.categoria
            for regra in self.regras
            if _normalizar_texto(regra.escopo) == escopo_norm
        )

    def obter_regra(self, escopo: str, categoria: str) -> RegraPerfil:
        escopo_norm = _normalizar_texto(escopo)
        categoria_norm = _normalizar_texto(categoria)

        for regra in self.regras:
            if (
                _normalizar_texto(regra.escopo) == escopo_norm
                and _normalizar_texto(regra.categoria) == categoria_norm
            ):
                return regra

        raise ValueError(
            "Regra de perfis nao encontrada para o escopo/categoria informados."
        )

    def perfis_bloqueados_globais(self) -> tuple[str, ...]:
        return _unicos_preservando_ordem(
            perfil
            for regra in self.regras
            for perfil in regra.perfis_bloqueados
        )

    def perfis_validacao_ura_globais(self) -> tuple[str, ...]:
        return _unicos_preservando_ordem(
            perfil
            for regra in self.regras
            for perfil in regra.perfis_validacao_ura
        )


@dataclass(frozen=True)
class ConcessaoPerfisEntrada:
    login: str
    protocolo: str
    escopo: str
    categoria: str


@dataclass(frozen=True)
class ResultadoPerfil:
    login: str
    escopo: str
    categoria: str
    perfil: str
    status: StatusPerfil
    detalhes: str


@dataclass(frozen=True)
class ResultadoConcessao:
    login: str
    protocolo: str
    escopo: str
    categoria: str
    status: StatusPerfil
    detalhes: str
    resultados_perfis: tuple[ResultadoPerfil, ...]


@dataclass(frozen=True)
class ConcessaoPreparada:
    entrada: ConcessaoPerfisEntrada
    regra: RegraPerfil
    perfis_automatizados: tuple[str, ...]
    resultados_previos: tuple[ResultadoPerfil, ...]


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


def _normalizar_texto(valor: object) -> str:
    return re.sub(r"\s+", " ", str(valor or "").strip()).casefold()


def _normalizar_login(valor: object) -> str:
    return str(valor or "").strip().upper()


def _normalizar_perfil(valor: object) -> str:
    return re.sub(r"\s+", " ", str(valor or "").strip()).upper()


def _apenas_digitos(valor: object) -> str:
    return re.sub(r"\D+", "", str(valor or ""))


def _valor_em_branco(valor: object) -> bool:
    try:
        if pd.isna(valor):
            return True
    except (TypeError, ValueError):
        pass

    return str(valor or "").strip() == ""


def _texto_planilha(valor: object) -> str:
    if _valor_em_branco(valor):
        return ""

    return str(valor).strip()


def _normalizar_cabecalho_planilha(valor: object) -> str:
    texto = unicodedata.normalize("NFKD", _texto_planilha(valor))
    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )
    return re.sub(r"\s+", " ", texto).casefold()


def _unicos_preservando_ordem(valores) -> tuple[str, ...]:
    vistos = set()
    unicos: list[str] = []

    for valor in valores:
        texto = str(valor or "").strip()
        chave = _normalizar_texto(texto)

        if not texto or chave in vistos:
            continue

        vistos.add(chave)
        unicos.append(texto)

    return tuple(unicos)


def _limpar_valor_yaml(valor: str) -> str:
    texto = valor.strip()

    if texto == "[]":
        return ""

    if (
        len(texto) >= 2
        and texto[0] == texto[-1]
        and texto[0] in {"'", '"'}
    ):
        texto = texto[1:-1]

    return texto.replace("''", "'").strip()


def _lista_yaml(valor: object) -> tuple[str, ...]:
    if isinstance(valor, list):
        return _unicos_preservando_ordem(valor)

    if valor in (None, "", []):
        return ()

    return _unicos_preservando_ordem((str(valor),))


def _parse_regras_yaml_fallback(texto: str) -> dict:
    regras: list[dict] = []
    regra_atual: dict | None = None
    em_regras = False
    chave_atual: str | None = None
    lista_atual: str | None = None
    chaves_lista = {
        "perfis_conceder",
        "perfis_bloqueados",
        "perfis_validacao_ura",
        "observacoes",
    }
    chaves_conhecidas = chaves_lista | {"escopo", "categoria"}

    for linha_original in texto.splitlines():
        if not linha_original.strip():
            continue

        if linha_original.startswith("regras:"):
            em_regras = True
            continue

        if not em_regras:
            continue

        if linha_original.startswith("- escopo:"):
            if regra_atual is not None:
                regras.append(regra_atual)

            regra_atual = {
                "escopo": _limpar_valor_yaml(linha_original.split(":", 1)[1]),
                "categoria": "",
                "perfis_conceder": [],
                "perfis_bloqueados": [],
                "perfis_validacao_ura": [],
                "observacoes": [],
            }
            chave_atual = "escopo"
            lista_atual = None
            continue

        if regra_atual is None:
            continue

        linha = linha_original.rstrip()
        texto_linha = linha.strip()

        if linha.startswith("  - ") and lista_atual:
            regra_atual[lista_atual].append(_limpar_valor_yaml(texto_linha[2:]))
            chave_atual = lista_atual
            continue

        if linha.startswith("  ") and not linha.startswith("    "):
            if ":" not in texto_linha:
                continue

            chave, valor = texto_linha.split(":", 1)
            chave = chave.strip()

            if chave not in chaves_conhecidas:
                continue

            valor_limpo = _limpar_valor_yaml(valor)

            if chave in chaves_lista:
                regra_atual[chave] = [] if valor.strip() in {"", "[]"} else [valor_limpo]
                lista_atual = chave
                chave_atual = chave
            else:
                regra_atual[chave] = valor_limpo
                lista_atual = None
                chave_atual = chave
            continue

        if linha.startswith("    ") and chave_atual:
            continuacao = _limpar_valor_yaml(texto_linha)

            if lista_atual and regra_atual.get(lista_atual):
                regra_atual[lista_atual][-1] = (
                    str(regra_atual[lista_atual][-1]).rstrip() + " " + continuacao
                ).strip()
            elif isinstance(regra_atual.get(chave_atual), str):
                regra_atual[chave_atual] = (
                    str(regra_atual[chave_atual]).rstrip() + " " + continuacao
                ).strip()

    if regra_atual is not None:
        regras.append(regra_atual)

    return {"regras": regras}


def _carregar_yaml_regras(caminho: Path) -> dict:
    texto = caminho.read_text(encoding="utf-8")

    try:
        import yaml  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        return _parse_regras_yaml_fallback(texto)

    dados = yaml.safe_load(texto)

    if not isinstance(dados, dict):
        raise ValueError("Arquivo de regras YAML invalido.")

    return dados


def carregar_catalogo_regras(
    caminho_regras: str | os.PathLike = REGRAS_PADRAO,
) -> CatalogoPerfis:
    caminho = Path(caminho_regras).expanduser()

    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo de regras nao encontrado: {caminho}")

    dados = _carregar_yaml_regras(caminho)
    regras_raw = dados.get("regras", [])

    if not isinstance(regras_raw, list):
        raise ValueError("Arquivo de regras invalido: chave 'regras' deve ser lista.")

    regras: list[RegraPerfil] = []

    for item in regras_raw:
        if not isinstance(item, dict):
            continue

        escopo = str(item.get("escopo", "")).strip()
        categoria = str(item.get("categoria", "")).strip()

        if not escopo or not categoria:
            continue

        regras.append(
            RegraPerfil(
                escopo=escopo,
                categoria=categoria,
                perfis_conceder=_lista_yaml(item.get("perfis_conceder")),
                perfis_bloqueados=_lista_yaml(item.get("perfis_bloqueados")),
                perfis_validacao_ura=_lista_yaml(item.get("perfis_validacao_ura")),
                observacoes=_lista_yaml(item.get("observacoes")),
            )
        )

    if not regras:
        raise ValueError("Nenhuma regra valida foi encontrada no YAML.")

    return CatalogoPerfis(tuple(regras))


def normalizar_entrada(entrada: ConcessaoPerfisEntrada) -> ConcessaoPerfisEntrada:
    return ConcessaoPerfisEntrada(
        login=_normalizar_login(entrada.login),
        protocolo=_apenas_digitos(entrada.protocolo),
        escopo=str(entrada.escopo or "").strip(),
        categoria=str(entrada.categoria or "").strip(),
    )


def validar_entrada(entrada: ConcessaoPerfisEntrada) -> list[str]:
    entrada_normalizada = normalizar_entrada(entrada)
    erros: list[str] = []

    if _valor_em_branco(entrada.login):
        erros.append("Usuario alvo em branco.")
    elif not PADRAO_LOGIN_VALIDO.fullmatch(entrada_normalizada.login):
        erros.append(
            "Usuario alvo invalido: use apenas letras, numeros, ponto, hifen ou sublinhado."
        )

    if _valor_em_branco(entrada.protocolo):
        erros.append("Protocolo em branco.")
    elif not PADRAO_PROTOCOLO_VALIDO.fullmatch(entrada_normalizada.protocolo):
        erros.append("Protocolo invalido: informe ate 17 digitos.")

    if _valor_em_branco(entrada.escopo):
        erros.append("Escopo em branco.")

    if _valor_em_branco(entrada.categoria):
        erros.append("Categoria em branco.")

    return erros


def _nome_coluna_planilha(campo: str) -> str:
    return ALIASES_COLUNAS_PLANILHA[campo][0]


def _mapear_colunas_planilha(colunas: pd.Index) -> dict[str, str]:
    colunas_por_nome = {
        _normalizar_cabecalho_planilha(coluna): str(coluna).strip()
        for coluna in colunas
    }
    mapa: dict[str, str] = {}
    faltantes: list[str] = []

    for campo in CAMPOS_CONCESSAO_OBRIGATORIOS:
        aliases = ALIASES_COLUNAS_PLANILHA[campo]
        coluna_encontrada = None

        for alias in aliases:
            alias_normalizado = _normalizar_cabecalho_planilha(alias)

            if alias_normalizado in colunas_por_nome:
                coluna_encontrada = colunas_por_nome[alias_normalizado]
                break

        if coluna_encontrada is None:
            faltantes.append(_nome_coluna_planilha(campo))
        else:
            mapa[campo] = coluna_encontrada

    if faltantes:
        raise ValueError(
            "Planilha invalida. Colunas obrigatorias ausentes: "
            + ", ".join(faltantes)
        )

    return mapa


def _valor_por_coluna_mapeada(
    linha: pd.Series,
    mapa_colunas: dict[str, str],
    campo: str,
) -> str:
    return _texto_planilha(linha.get(mapa_colunas[campo], ""))


def ler_planilha_concessoes(
    caminho_planilha: str | os.PathLike,
) -> list[ConcessaoPerfisEntrada]:
    caminho = Path(caminho_planilha).expanduser()

    if not caminho.exists():
        raise FileNotFoundError(f"Planilha nao encontrada: {caminho}")

    if caminho.suffix.lower() != ".xlsx":
        raise ValueError("A planilha deve ser um arquivo .xlsx.")

    df = pd.read_excel(caminho, dtype=str, engine="openpyxl").fillna("")
    df.columns = df.columns.str.strip()
    mapa_colunas = _mapear_colunas_planilha(df.columns)
    concessoes: list[ConcessaoPerfisEntrada] = []

    for _, linha in df.iterrows():
        if all(_valor_em_branco(valor) for valor in linha):
            continue

        entrada = ConcessaoPerfisEntrada(
            login=_valor_por_coluna_mapeada(linha, mapa_colunas, "login"),
            protocolo=_valor_por_coluna_mapeada(linha, mapa_colunas, "protocolo"),
            escopo=_valor_por_coluna_mapeada(linha, mapa_colunas, "escopo"),
            categoria=_valor_por_coluna_mapeada(linha, mapa_colunas, "categoria"),
        )
        concessoes.append(normalizar_entrada(entrada))

    return concessoes


def _resultado_perfil(
    entrada: ConcessaoPerfisEntrada,
    perfil: str,
    status: StatusPerfil,
    detalhes: str,
) -> ResultadoPerfil:
    return ResultadoPerfil(
        login=entrada.login,
        escopo=entrada.escopo,
        categoria=entrada.categoria,
        perfil=perfil,
        status=status,
        detalhes=detalhes,
    )


def preparar_concessao(
    entrada: ConcessaoPerfisEntrada,
    catalogo: CatalogoPerfis,
) -> ConcessaoPreparada:
    entrada = normalizar_entrada(entrada)
    erros = validar_entrada(entrada)

    if erros:
        raise ValueError("; ".join(erros))

    regra = catalogo.obter_regra(entrada.escopo, entrada.categoria)
    bloqueados = {_normalizar_perfil(perfil) for perfil in catalogo.perfis_bloqueados_globais()}
    validacao_ura = {
        _normalizar_perfil(perfil)
        for perfil in catalogo.perfis_validacao_ura_globais()
    }
    perfis_automatizados: list[str] = []
    resultados_previos: list[ResultadoPerfil] = []

    for perfil in regra.perfis_bloqueados:
        resultados_previos.append(
            _resultado_perfil(
                entrada,
                perfil,
                STATUS_BLOQUEADO,
                "Perfil critico bloqueado para concessao automatica.",
            )
        )

    for perfil in regra.perfis_validacao_ura:
        resultados_previos.append(
            _resultado_perfil(
                entrada,
                perfil,
                STATUS_VALIDACAO_URA,
                "Perfil exige validacao externa da URA/STCOR antes da concessao.",
            )
        )

    perfis_previos = {
        _normalizar_perfil(resultado.perfil) for resultado in resultados_previos
    }

    for perfil in regra.perfis_conceder:
        perfil_norm = _normalizar_perfil(perfil)

        if perfil_norm in perfis_previos:
            continue

        if perfil_norm in bloqueados:
            resultados_previos.append(
                _resultado_perfil(
                    entrada,
                    perfil,
                    STATUS_BLOQUEADO,
                    "Perfil consta na lista global de perfis criticos.",
                )
            )
            perfis_previos.add(perfil_norm)
            continue

        if perfil_norm in validacao_ura:
            resultados_previos.append(
                _resultado_perfil(
                    entrada,
                    perfil,
                    STATUS_VALIDACAO_URA,
                    "Perfil consta na lista global de validacao URA/STCOR.",
                )
            )
            perfis_previos.add(perfil_norm)
            continue

        perfis_automatizados.append(perfil)
        perfis_previos.add(perfil_norm)

    return ConcessaoPreparada(
        entrada=entrada,
        regra=regra,
        perfis_automatizados=tuple(perfis_automatizados),
        resultados_previos=tuple(resultados_previos),
    )


def _linha_relatorio_perfil(resultado: ResultadoPerfil, protocolo: str) -> dict:
    return {
        "Login": resultado.login,
        "Protocolo": protocolo,
        "Escopo": resultado.escopo,
        "Categoria": resultado.categoria,
        "Perfil": resultado.perfil,
        "Status": resultado.status,
        "Detalhes": resultado.detalhes,
    }


def _status_geral(resultados: tuple[ResultadoPerfil, ...]) -> StatusPerfil:
    status = {resultado.status for resultado in resultados}

    if STATUS_ERRO in status:
        return STATUS_ERRO
    if STATUS_CONFERIR_MANUAL in status:
        return STATUS_CONFERIR_MANUAL
    if STATUS_CONCEDIDO in status:
        return STATUS_CONCEDIDO
    if STATUS_USUARIO_NAO_ENCONTRADO in status:
        return STATUS_USUARIO_NAO_ENCONTRADO
    if STATUS_JA_EXISTENTE in status:
        return STATUS_JA_EXISTENTE
    if status & {STATUS_BLOQUEADO, STATUS_VALIDACAO_URA, STATUS_IGNORADO}:
        return STATUS_IGNORADO

    return STATUS_IGNORADO


def _resumir_status(resultados: tuple[ResultadoPerfil, ...]) -> str:
    contagem = Counter(resultado.status for resultado in resultados)
    partes = [f"Total: {len(resultados)}"]

    rotulos = (
        (STATUS_CONCEDIDO, "concedidos"),
        (STATUS_JA_EXISTENTE, "ja existentes"),
        (STATUS_BLOQUEADO, "bloqueados"),
        (STATUS_VALIDACAO_URA, "validacao URA"),
        (STATUS_USUARIO_NAO_ENCONTRADO, "usuario nao encontrado"),
        (STATUS_CONFERIR_MANUAL, "conferir manualmente"),
        (STATUS_ERRO, "erros"),
        (STATUS_IGNORADO, "ignorados"),
    )

    for status, rotulo in rotulos:
        if contagem[status]:
            partes.append(f"{rotulo}: {contagem[status]}")

    return "; ".join(partes) + "."


def _montar_resultado_concessao(
    entrada: ConcessaoPerfisEntrada,
    resultados: list[ResultadoPerfil] | tuple[ResultadoPerfil, ...],
) -> ResultadoConcessao:
    resultados_tuple = tuple(resultados)

    return ResultadoConcessao(
        login=entrada.login,
        protocolo=entrada.protocolo,
        escopo=entrada.escopo,
        categoria=entrada.categoria,
        status=_status_geral(resultados_tuple),
        detalhes=_resumir_status(resultados_tuple),
        resultados_perfis=resultados_tuple,
    )


def resultado_ignorado(
    entrada: ConcessaoPerfisEntrada,
    detalhes: str,
) -> ResultadoConcessao:
    entrada = normalizar_entrada(entrada)
    return _montar_resultado_concessao(
        entrada,
        (
            _resultado_perfil(
                entrada,
                "",
                STATUS_IGNORADO,
                detalhes,
            ),
        ),
    )


def salvar_relatorio_resultados(
    resultados: list[ResultadoConcessao] | tuple[ResultadoConcessao, ...],
    caminho_saida: str | os.PathLike,
) -> Path:
    caminho = Path(caminho_saida).expanduser()

    if not caminho.suffix:
        caminho = caminho.with_suffix(".xlsx")

    if caminho.suffix.lower() != ".xlsx":
        raise ValueError("O relatorio de saida deve ser um arquivo .xlsx.")

    caminho.parent.mkdir(parents=True, exist_ok=True)
    linhas = [
        _linha_relatorio_perfil(perfil, resultado.protocolo)
        for resultado in resultados
        for perfil in resultado.resultados_perfis
    ]
    df = pd.DataFrame(linhas)

    with pd.ExcelWriter(caminho, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Resultado")
        worksheet = writer.sheets["Resultado"]
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions

        for coluna in worksheet.columns:
            largura = max(len(str(celula.value or "")) for celula in coluna)
            worksheet.column_dimensions[coluna[0].column_letter].width = min(
                largura + 2,
                90,
            )

    return caminho


def gerar_csv_logs(
    resultados: tuple[ResultadoConcessao, ...],
    usuario_rede: str,
    diretorio_logs: str | os.PathLike | None,
) -> str:
    pasta_logs = Path(diretorio_logs) if diretorio_logs else LOGS_DIR
    pasta_logs.mkdir(parents=True, exist_ok=True)
    data_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho = pasta_logs / f"log_concessao_perfis_{data_hora}.csv"

    with caminho.open("w", encoding="utf-8-sig") as arquivo:
        arquivo.write(f"Atualizado por: {usuario_rede}\n")

    linhas = [
        _linha_relatorio_perfil(perfil, resultado.protocolo)
        for resultado in resultados
        for perfil in resultado.resultados_perfis
    ]
    pd.DataFrame(linhas).to_csv(
        caminho,
        index=False,
        sep=";",
        encoding="utf-8-sig",
        mode="a",
    )

    return str(caminho)


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


def _preencher_input(locator: Locator, valor: str, timeout_ms: int = 5000) -> None:
    locator.wait_for(state="visible", timeout=timeout_ms)
    locator.click(timeout=timeout_ms)
    locator.fill("", timeout=timeout_ms)
    locator.fill(valor, timeout=timeout_ms)


def _disparar_eventos_input_jsf(locator: Locator) -> None:
    locator.evaluate(
        """(element) => {
            for (const eventName of ['input', 'change']) {
                element.dispatchEvent(
                    new Event(eventName, { bubbles: true, cancelable: true })
                );
            }
        }"""
    )


def _preencher_protocolo(locator: Locator, protocolo: str, timeout_ms: int = 5000) -> None:
    protocolo_normalizado = _apenas_digitos(protocolo)

    locator.wait_for(state="visible", timeout=timeout_ms)
    locator.click(timeout=timeout_ms)

    try:
        locator.press("Control+A", timeout=timeout_ms)
        locator.press("Backspace", timeout=timeout_ms)
    except Exception:
        locator.fill("", timeout=timeout_ms)

    if protocolo_normalizado:
        locator.press_sequentially(
            protocolo_normalizado,
            delay=30,
            timeout=timeout_ms,
        )

    _disparar_eventos_input_jsf(locator)

    try:
        locator.blur(timeout=timeout_ms)
    except Exception:
        locator.evaluate("(element) => element.blur()")

    _disparar_eventos_input_jsf(locator)

    valor_atual = _apenas_digitos(locator.input_value(timeout=timeout_ms))

    if valor_atual != protocolo_normalizado:
        raise RuntimeError(
            "Falha ao preencher Protocolo: "
            f"valor atual '{valor_atual}', esperado '{protocolo_normalizado}'."
        )


def _widget_carregamento(janela_sistema: FrameLocator) -> Locator:
    return janela_sistema.get_by_label("Carregando").get_by_text("Aguarde...").first


def _existe_carregamento_visivel(janela_sistema: FrameLocator) -> bool:
    try:
        return _widget_carregamento(janela_sistema).is_visible(timeout=100)
    except Exception:
        return False


def _aguardar_ciclo_carregamento(
    janela_sistema: FrameLocator,
    *,
    timeout_ms: int = TEMPO_MAXIMO_CONSULTA_MS,
    deteccao_ms: int = TEMPO_DETECCAO_WIDGET_CARREGAMENTO_MS,
) -> bool:
    widget = _widget_carregamento(janela_sistema)

    try:
        widget.wait_for(state="visible", timeout=deteccao_ms)
    except PlaywrightTimeoutError:
        return not _existe_carregamento_visivel(janela_sistema)

    fim = time.monotonic() + timeout_ms / 1000

    while time.monotonic() < fim:
        if not _existe_carregamento_visivel(janela_sistema):
            return True

        time.sleep(0.15)

    raise PlaywrightTimeoutError("AGHUX permaneceu em carregamento alem do tempo limite.")


def _pode_confirmar_resultado(
    *,
    estado_desde: float,
    consulta_concluida: bool,
    estabilidade_resultado_ms: int = TEMPO_ESTABILIDADE_RESULTADO_MS,
) -> bool:
    return consulta_concluida and (
        time.monotonic() - estado_desde
    ) * 1000 >= estabilidade_resultado_ms


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

        if "ui-datatable-empty-message" in classe or TEXTO_NENHUM_REGISTRO in texto:
            return True

    return False


def _login_confere(valor_atual: object, login_esperado: str) -> bool:
    return _normalizar_texto(valor_atual) == _normalizar_texto(login_esperado)


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

            classe = linha.get_attribute("class", timeout=500) or ""
        except Exception:
            continue

        if "ui-datatable-empty-message" in classe:
            continue

        celulas = linha.locator("td")

        try:
            if celulas.count() <= indice_coluna_login:
                continue

            texto_login = celulas.nth(indice_coluna_login).inner_text(timeout=1000)
        except Exception:
            continue

        if _login_confere(texto_login, login):
            return linha

    return None


def _aguardar_resultado_pesquisa_usuario(
    janela_sistema: FrameLocator,
    login: str,
    *,
    timeout_ms: int = TEMPO_MAXIMO_CONSULTA_MS,
    estabilidade_resultado_ms: int = TEMPO_ESTABILIDADE_RESULTADO_MS,
    consulta_concluida: bool = False,
) -> tuple[str, Locator | None]:
    linhas = janela_sistema.locator(SELECTOR_TABELA_USUARIOS)
    inicio = time.monotonic()
    fim = inicio + timeout_ms / 1000
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

        linha = _linha_tabela_por_login(linhas, login, indice_coluna_login=2)

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
            elif _pode_confirmar_resultado(
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


def _pesquisar_usuario(
    janela_sistema: FrameLocator,
    login: str,
) -> tuple[str, Locator | None]:
    campo_login = _primeiro_visivel(janela_sistema, (SELECTOR_PESQUISA_LOGIN,))
    _preencher_input(campo_login, login)
    _clicar_botao(janela_sistema, "Pesquisar")
    consulta_concluida = _aguardar_ciclo_carregamento(janela_sistema)
    return _aguardar_resultado_pesquisa_usuario(
        janela_sistema,
        login,
        consulta_concluida=consulta_concluida,
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
    fazer_login(nova_page, usuario_rede, senha, url_aghu=url_aghu)

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


def _clicar_editar_usuario(linha_usuario: Locator) -> None:
    candidatos = (
        linha_usuario.get_by_role("link", name=re.compile("Editar|Alterar", re.I)).first,
        linha_usuario.get_by_role("button", name=re.compile("Editar|Alterar", re.I)).first,
        linha_usuario.locator("a[title*='Editar' i], button[title*='Editar' i]").first,
        linha_usuario.locator("a[aria-label*='Editar' i], button[aria-label*='Editar' i]").first,
        linha_usuario.locator("a[title*='Alterar' i], button[title*='Alterar' i]").first,
        linha_usuario.locator("a.silk-pencil, a.silk-user_edit, a.ui-commandlink").first,
    )
    ultimo_erro: Exception | None = None

    for candidato in candidatos:
        try:
            candidato.wait_for(state="visible", timeout=2500)
            candidato.click(timeout=5000)
            return
        except Exception as exc:
            ultimo_erro = exc

    raise PlaywrightTimeoutError("Acao de editar usuario nao localizada.") from ultimo_erro


def _frame_perfis_visivel(
    page: Page,
    janela_sistema: FrameLocator,
    timeout_ms: int = 2500,
) -> FrameLocator | None:
    candidatos = (
        page.frame_locator('iframe[name="i_frame_usuario"]'),
        janela_sistema.frame_locator('iframe[name="i_frame_usuario"]'),
        page.frame_locator("iframe").last,
        janela_sistema,
    )

    for candidato in candidatos:
        try:
            _primeiro_visivel(candidato, (SELECTOR_PERFIL_INPUT,), timeout_ms=timeout_ms)
            return candidato
        except Exception:
            continue

    return None


def _abrir_aba_perfis_usuario(
    page: Page,
    janela_sistema: FrameLocator,
) -> FrameLocator:
    frame = _frame_perfis_visivel(page, janela_sistema)

    if frame is not None:
        return frame

    candidatos = (
        janela_sistema.get_by_role("link", name=re.compile("Editar perfil|Perfis?", re.I)).first,
        janela_sistema.get_by_text("Editar perfil", exact=True).first,
        janela_sistema.get_by_text(re.compile(r"^Perfis?$", re.I)).first,
        page.get_by_text("Editar perfil", exact=True).first,
        page.get_by_text(re.compile(r"^Perfis?$", re.I)).first,
    )
    ultimo_erro: Exception | None = None

    for candidato in candidatos:
        try:
            candidato.wait_for(state="visible", timeout=2500)
            candidato.click(timeout=5000)
            time.sleep(0.5)
            frame = _frame_perfis_visivel(page, janela_sistema, timeout_ms=5000)

            if frame is not None:
                return frame
        except Exception as exc:
            ultimo_erro = exc

    raise PlaywrightTimeoutError(
        "Aba/tela de edicao de perfis do usuario nao localizada."
    ) from ultimo_erro


def _mensagens_sistema(janela_sistema: FrameLocator) -> list[str]:
    mensagens: list[str] = []
    locators = janela_sistema.locator(SELECTOR_MENSAGENS)
    total = locators.count()

    for indice in range(total):
        item = locators.nth(indice)

        try:
            if item.is_visible(timeout=250):
                texto = item.inner_text(timeout=500).strip()
                if texto:
                    mensagens.append(texto)
        except Exception:
            continue

    return mensagens


def _aguardar_mensagem_gravacao(
    janela_sistema: FrameLocator,
    timeout_ms: int = 15000,
) -> tuple[str, str]:
    fim = time.monotonic() + timeout_ms / 1000
    sucesso = "perfil do usuario atualizado com sucesso"

    while time.monotonic() < fim:
        for mensagem in _mensagens_sistema(janela_sistema):
            mensagem_norm = _normalizar_texto(mensagem)

            if sucesso in mensagem_norm:
                return "sucesso", mensagem

            if (
                "campo obrigatorio" in mensagem_norm
                or "invalido" in mensagem_norm
                or "erro" in mensagem_norm
            ):
                return "erro", mensagem

        time.sleep(0.15)

    return "indefinido", "A gravacao nao retornou mensagem dentro do tempo limite."


def _texto_item_autocomplete_confere(texto: str, perfil: str) -> bool:
    perfil_norm = _normalizar_perfil(perfil)
    partes = [
        parte.strip()
        for parte in re.split(r"[\n\r\t]+", texto)
        if parte.strip()
    ]

    for parte in partes:
        tokens = re.split(r"\s+", parte)

        if _normalizar_perfil(parte) == perfil_norm:
            return True

        if tokens and _normalizar_perfil(tokens[0]) == perfil_norm:
            return True

    return False


def _selecionar_perfil_autocomplete(
    janela_perfis: FrameLocator,
    perfil: str,
    timeout_ms: int = 7000,
) -> None:
    campo = _primeiro_visivel(janela_perfis, (SELECTOR_PERFIL_INPUT,), timeout_ms)
    campo.click(timeout=timeout_ms)
    campo.fill("", timeout=timeout_ms)
    campo.press_sequentially(perfil, delay=150, timeout=timeout_ms)

    itens = janela_perfis.locator("tr.ui-autocomplete-item, li.ui-autocomplete-item")
    itens.first.wait_for(state="visible", timeout=timeout_ms)

    total = min(itens.count(), 50)
    ultimo_texto = ""

    for indice in range(total):
        item = itens.nth(indice)

        try:
            if not item.is_visible(timeout=500):
                continue

            texto = item.inner_text(timeout=1000).strip()
            ultimo_texto = texto or ultimo_texto

            if _texto_item_autocomplete_confere(texto, perfil):
                item.click(timeout=timeout_ms)
                break
        except Exception:
            continue
    else:
        raise PlaywrightTimeoutError(
            f"Autocomplete nao retornou opcao exata para o perfil {perfil}. "
            f"Ultimo texto encontrado: {ultimo_texto}"
        )

    try:
        valor_selecionado = campo.input_value(timeout=1000).strip()
    except Exception:
        valor_selecionado = ""

    if valor_selecionado and not _texto_item_autocomplete_confere(
        valor_selecionado,
        perfil,
    ):
        raise RuntimeError(
            f"Autocomplete selecionou '{valor_selecionado}', esperado '{perfil}'."
        )


def _perfil_ja_na_tabela(janela_perfis: FrameLocator, perfil: str) -> bool:
    linhas = janela_perfis.locator(SELECTOR_TABELA_PERFIS)
    total = linhas.count()
    perfil_norm = _normalizar_perfil(perfil)

    for indice in range(total):
        linha = linhas.nth(indice)

        try:
            if not linha.is_visible(timeout=250):
                continue

            classe = linha.get_attribute("class", timeout=250) or ""
            texto_linha = linha.inner_text(timeout=500)
        except Exception:
            continue

        if "ui-datatable-empty-message" in classe or TEXTO_NENHUM_REGISTRO in texto_linha:
            continue

        celulas = linha.locator("td")

        try:
            if celulas.count() > 1:
                texto_perfil = celulas.nth(1).inner_text(timeout=500)
            else:
                texto_perfil = texto_linha
        except Exception:
            texto_perfil = texto_linha

        if _normalizar_perfil(texto_perfil) == perfil_norm:
            return True

    return False


def _aguardar_perfil_na_tabela(
    janela_perfis: FrameLocator,
    perfil: str,
    timeout_ms: int = 10000,
) -> bool:
    fim = time.monotonic() + timeout_ms / 1000

    while time.monotonic() < fim:
        if _perfil_ja_na_tabela(janela_perfis, perfil):
            return True

        time.sleep(0.15)

    return False


def _adicionar_perfil(
    janela_perfis: FrameLocator,
    perfil: str,
    protocolo: str,
) -> None:
    _selecionar_perfil_autocomplete(janela_perfis, perfil)
    campo_protocolo = _primeiro_visivel(janela_perfis, (SELECTOR_PROTOCOLO_INPUT,))
    _preencher_protocolo(campo_protocolo, protocolo)
    _clicar_botao(janela_perfis, "Adicionar")
    _aguardar_ciclo_carregamento(janela_perfis, deteccao_ms=500)

    if not _aguardar_perfil_na_tabela(janela_perfis, perfil):
        mensagens = "; ".join(_mensagens_sistema(janela_perfis))
        detalhe = f"Perfil {perfil} nao apareceu na tabela apos Adicionar."

        if mensagens:
            detalhe += f" Mensagens: {mensagens}"

        raise RuntimeError(detalhe)


def _gravar_perfis(janela_perfis: FrameLocator) -> tuple[str, str]:
    _clicar_botao(janela_perfis, "Gravar")
    _aguardar_ciclo_carregamento(janela_perfis, deteccao_ms=500)
    return _aguardar_mensagem_gravacao(janela_perfis)


def _conceder_perfis_na_tela(
    janela_perfis: FrameLocator,
    entrada: ConcessaoPerfisEntrada,
    perfis: tuple[str, ...],
) -> list[ResultadoPerfil]:
    resultados: list[ResultadoPerfil] = []
    adicionados: list[str] = []

    for perfil in perfis:
        try:
            if _perfil_ja_na_tabela(janela_perfis, perfil):
                resultados.append(
                    _resultado_perfil(
                        entrada,
                        perfil,
                        STATUS_JA_EXISTENTE,
                        "Perfil ja constava na tabela do usuario.",
                    )
                )
                continue

            print(f"Adicionando perfil {perfil} para {entrada.login}...")
            _adicionar_perfil(janela_perfis, perfil, entrada.protocolo)
            adicionados.append(perfil)
        except Exception as exc:
            resultados.append(
                _resultado_perfil(
                    entrada,
                    perfil,
                    STATUS_ERRO,
                    f"Falha ao adicionar perfil: {exc}",
                )
            )

    if not adicionados:
        return resultados

    estado_gravacao, mensagem = _gravar_perfis(janela_perfis)

    for perfil in adicionados:
        if estado_gravacao == "sucesso":
            status: StatusPerfil = STATUS_CONCEDIDO
            detalhes = mensagem
        elif estado_gravacao == "indefinido":
            status = STATUS_CONFERIR_MANUAL
            detalhes = mensagem
        else:
            status = STATUS_ERRO
            detalhes = mensagem

        resultados.append(_resultado_perfil(entrada, perfil, status, detalhes))

    return resultados


def processar_concessao(
    context: BrowserContext,
    page_inicial: Page,
    janela_sistema_inicial: FrameLocator,
    preparada: ConcessaoPreparada,
    usuario_rede: str,
    senha: str,
    *,
    url_aghu: str = AGHU_URL,
) -> ResultadoConcessao:
    entrada = preparada.entrada
    resultados = list(preparada.resultados_previos)
    page = page_inicial
    janela_sistema = janela_sistema_inicial

    if not preparada.perfis_automatizados:
        if not resultados:
            resultados.append(
                _resultado_perfil(
                    entrada,
                    "",
                    STATUS_IGNORADO,
                    "Nenhum perfil elegivel para concessao automatica nesta regra.",
                )
            )
        return _montar_resultado_concessao(entrada, resultados)

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
            estado_usuario, linha_usuario = _pesquisar_usuario(
                janela_sistema,
                entrada.login,
            )

            if estado_usuario == "indefinido":
                resultados.extend(
                    _resultado_perfil(
                        entrada,
                        perfil,
                        STATUS_CONFERIR_MANUAL,
                        "Pesquisa do usuario nao retornou estado conclusivo.",
                    )
                    for perfil in preparada.perfis_automatizados
                )
                return _montar_resultado_concessao(entrada, resultados)

            if estado_usuario != "encontrado" or linha_usuario is None:
                resultados.extend(
                    _resultado_perfil(
                        entrada,
                        perfil,
                        STATUS_USUARIO_NAO_ENCONTRADO,
                        "Usuario alvo nao localizado no AGHUX.",
                    )
                    for perfil in preparada.perfis_automatizados
                )
                return _montar_resultado_concessao(entrada, resultados)

            _clicar_editar_usuario(linha_usuario)
            _aguardar_ciclo_carregamento(janela_sistema, deteccao_ms=500)
            janela_perfis = _abrir_aba_perfis_usuario(page, janela_sistema)
            resultados.extend(
                _conceder_perfis_na_tela(
                    janela_perfis,
                    entrada,
                    preparada.perfis_automatizados,
                )
            )
            return _montar_resultado_concessao(entrada, resultados)
        except Exception as exc:
            if tentativa == 0:
                print("Falha tecnica na concessao. Tentando novamente em nova aba...")
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

            resultados.extend(
                _resultado_perfil(
                    entrada,
                    perfil,
                    STATUS_ERRO,
                    f"Falha tecnica durante a concessao: {exc}",
                )
                for perfil in preparada.perfis_automatizados
            )
            return _montar_resultado_concessao(entrada, resultados)

    return _montar_resultado_concessao(entrada, resultados)


def processar_concessoes(
    context: BrowserContext,
    page_inicial: Page,
    janela_sistema_inicial: FrameLocator,
    preparadas: list[ConcessaoPreparada],
    usuario_rede: str,
    senha: str,
    *,
    resultados_prevalidacao: list[ResultadoConcessao | None] | None = None,
    url_aghu: str = AGHU_URL,
) -> list[ResultadoConcessao]:
    resultados: list[ResultadoConcessao] = []
    page = page_inicial
    janela_sistema = janela_sistema_inicial
    total = len(preparadas)

    if resultados_prevalidacao is None:
        resultados_prevalidacao = [None] * total

    if len(resultados_prevalidacao) != total:
        raise ValueError(
            "A pre-validacao deve ter a mesma quantidade de concessoes."
        )

    for indice, (preparada, pre_resultado) in enumerate(
        zip(preparadas, resultados_prevalidacao)
    ):
        entrada = preparada.entrada
        print("\n========================================")
        print(
            f"Processando [{indice + 1}/{total}]: "
            f"Login [{entrada.login}] | Escopo [{entrada.escopo}] | "
            f"Categoria [{entrada.categoria}]"
        )

        if pre_resultado is not None:
            print(pre_resultado.detalhes)
            resultados.append(pre_resultado)
            continue

        resultado_linha = processar_concessao(
            context=context,
            page_inicial=page,
            janela_sistema_inicial=janela_sistema,
            preparada=preparada,
            usuario_rede=usuario_rede,
            senha=senha,
            url_aghu=url_aghu,
        )
        print(f"Resultado: [{resultado_linha.status}] {resultado_linha.detalhes}")
        resultados.append(resultado_linha)

    return resultados


def executar_concessao_perfis(
    entrada: ConcessaoPerfisEntrada,
    usuario_rede: str,
    senha: str,
    *,
    url_aghu: str = AGHU_URL,
    caminho_regras: str | os.PathLike = REGRAS_PADRAO,
    mostrar_browser: bool = True,
    mostrar_console: bool = True,
    diretorio_logs: str | os.PathLike | None = None,
    gerar_csv_log: bool = True,
) -> ResultadoConcessao:
    if not usuario_rede or not senha:
        raise ValueError("Preencha usuario de rede e senha.")

    if not url_aghu:
        raise ValueError("Informe o ambiente do AGHU.")

    with _controle_saida_terminal(mostrar_console):
        return _executar_concessao_perfis_com_saida_configurada(
            entrada=entrada,
            usuario_rede=usuario_rede,
            senha=senha,
            url_aghu=url_aghu,
            caminho_regras=caminho_regras,
            mostrar_browser=mostrar_browser,
            diretorio_logs=diretorio_logs,
            gerar_csv_log=gerar_csv_log,
        )


def _executar_concessao_perfis_com_saida_configurada(
    entrada: ConcessaoPerfisEntrada,
    usuario_rede: str,
    senha: str,
    *,
    url_aghu: str,
    caminho_regras: str | os.PathLike,
    mostrar_browser: bool,
    diretorio_logs: str | os.PathLike | None,
    gerar_csv_log: bool,
) -> ResultadoConcessao:
    catalogo = carregar_catalogo_regras(caminho_regras)
    preparada = preparar_concessao(entrada, catalogo)

    if not preparada.perfis_automatizados:
        resultado = processar_concessao_sem_browser(preparada)

        if gerar_csv_log:
            gerar_csv_logs((resultado,), usuario_rede, diretorio_logs)

        return resultado

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
            resultado = processar_concessao(
                context=context,
                page_inicial=page,
                janela_sistema_inicial=janela_sistema,
                preparada=preparada,
                usuario_rede=usuario_rede,
                senha=senha,
                url_aghu=url_aghu,
            )

            if gerar_csv_log:
                gerar_csv_logs((resultado,), usuario_rede, diretorio_logs)

            return resultado
        finally:
            browser.close()


def processar_concessao_sem_browser(
    preparada: ConcessaoPreparada,
) -> ResultadoConcessao:
    entrada = preparada.entrada
    resultados = list(preparada.resultados_previos)

    if not resultados:
        resultados.append(
            _resultado_perfil(
                entrada,
                "",
                STATUS_IGNORADO,
                "Nenhum perfil elegivel para concessao automatica nesta regra.",
            )
        )

    return _montar_resultado_concessao(entrada, resultados)


def _preparar_concessoes_lote(
    concessoes: list[ConcessaoPerfisEntrada],
    catalogo: CatalogoPerfis,
) -> tuple[list[ConcessaoPreparada], list[ResultadoConcessao | None], bool]:
    preparadas: list[ConcessaoPreparada] = []
    resultados_prevalidacao: list[ResultadoConcessao | None] = []
    existem_automatizaveis = False

    for entrada in concessoes:
        entrada = normalizar_entrada(entrada)
        erros = validar_entrada(entrada)

        if erros:
            preparadas.append(
                ConcessaoPreparada(
                    entrada=entrada,
                    regra=RegraPerfil("", "", (), (), (), ()),
                    perfis_automatizados=(),
                    resultados_previos=(),
                )
            )
            resultados_prevalidacao.append(
                resultado_ignorado(
                    entrada,
                    "Linha ignorada: " + "; ".join(erros) + ".",
                )
            )
            continue

        try:
            preparada = preparar_concessao(entrada, catalogo)
        except Exception as exc:
            preparadas.append(
                ConcessaoPreparada(
                    entrada=entrada,
                    regra=RegraPerfil("", "", (), (), (), ()),
                    perfis_automatizados=(),
                    resultados_previos=(),
                )
            )
            resultados_prevalidacao.append(
                resultado_ignorado(entrada, f"Linha ignorada: {exc}.")
            )
            continue

        preparadas.append(preparada)

        if preparada.perfis_automatizados:
            resultados_prevalidacao.append(None)
            existem_automatizaveis = True
        else:
            resultados_prevalidacao.append(processar_concessao_sem_browser(preparada))

    return preparadas, resultados_prevalidacao, existem_automatizaveis


def executar_concessoes_perfis(
    concessoes: list[ConcessaoPerfisEntrada],
    usuario_rede: str,
    senha: str,
    *,
    url_aghu: str = AGHU_URL,
    caminho_regras: str | os.PathLike = REGRAS_PADRAO,
    mostrar_browser: bool = True,
    mostrar_console: bool = True,
    diretorio_logs: str | os.PathLike | None = None,
    gerar_csv_log: bool = True,
) -> list[ResultadoConcessao]:
    if not usuario_rede or not senha:
        raise ValueError("Preencha usuario de rede e senha.")

    if not url_aghu:
        raise ValueError("Informe o ambiente do AGHU.")

    with _controle_saida_terminal(mostrar_console):
        return _executar_concessoes_perfis_com_saida_configurada(
            concessoes=concessoes,
            usuario_rede=usuario_rede,
            senha=senha,
            url_aghu=url_aghu,
            caminho_regras=caminho_regras,
            mostrar_browser=mostrar_browser,
            diretorio_logs=diretorio_logs,
            gerar_csv_log=gerar_csv_log,
        )


def _executar_concessoes_perfis_com_saida_configurada(
    concessoes: list[ConcessaoPerfisEntrada],
    usuario_rede: str,
    senha: str,
    *,
    url_aghu: str,
    caminho_regras: str | os.PathLike,
    mostrar_browser: bool,
    diretorio_logs: str | os.PathLike | None,
    gerar_csv_log: bool,
) -> list[ResultadoConcessao]:
    catalogo = carregar_catalogo_regras(caminho_regras)
    concessoes = [normalizar_entrada(entrada) for entrada in concessoes]
    (
        preparadas,
        resultados_prevalidacao,
        existem_automatizaveis,
    ) = _preparar_concessoes_lote(concessoes, catalogo)

    if not existem_automatizaveis:
        resultados = [
            resultado
            for resultado in resultados_prevalidacao
            if resultado is not None
        ]

        if gerar_csv_log:
            gerar_csv_logs(tuple(resultados), usuario_rede, diretorio_logs)

        return resultados

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
            resultados = processar_concessoes(
                context=context,
                page_inicial=page,
                janela_sistema_inicial=janela_sistema,
                preparadas=preparadas,
                resultados_prevalidacao=resultados_prevalidacao,
                usuario_rede=usuario_rede,
                senha=senha,
                url_aghu=url_aghu,
            )

            if gerar_csv_log:
                gerar_csv_logs(tuple(resultados), usuario_rede, diretorio_logs)

            return resultados
        finally:
            browser.close()


def executar_concessao_lote(
    usuario_rede: str,
    senha: str,
    caminho_planilha: str | os.PathLike,
    caminho_relatorio: str | os.PathLike,
    *,
    url_aghu: str = AGHU_URL,
    caminho_regras: str | os.PathLike = REGRAS_PADRAO,
    mostrar_browser: bool = True,
    mostrar_console: bool = True,
    diretorio_logs: str | os.PathLike | None = None,
) -> tuple[list[ResultadoConcessao], Path]:
    concessoes = ler_planilha_concessoes(caminho_planilha)
    resultados = executar_concessoes_perfis(
        concessoes=concessoes,
        usuario_rede=usuario_rede,
        senha=senha,
        url_aghu=url_aghu,
        caminho_regras=caminho_regras,
        mostrar_browser=mostrar_browser,
        mostrar_console=mostrar_console,
        diretorio_logs=diretorio_logs,
    )
    relatorio = salvar_relatorio_resultados(resultados, caminho_relatorio)
    return resultados, relatorio


def executar_concessao_individual(
    usuario_rede: str,
    senha: str,
    login: str,
    protocolo: str,
    escopo: str,
    categoria: str,
    *,
    url_aghu: str = AGHU_URL,
    caminho_regras: str | os.PathLike = REGRAS_PADRAO,
    mostrar_browser: bool = True,
    mostrar_console: bool = True,
    diretorio_logs: str | os.PathLike | None = None,
) -> ResultadoConcessao:
    return executar_concessao_perfis(
        entrada=ConcessaoPerfisEntrada(
            login=login,
            protocolo=protocolo,
            escopo=escopo,
            categoria=categoria,
        ),
        usuario_rede=usuario_rede,
        senha=senha,
        url_aghu=url_aghu,
        caminho_regras=caminho_regras,
        mostrar_browser=mostrar_browser,
        mostrar_console=mostrar_console,
        diretorio_logs=diretorio_logs,
    )


def main() -> None:
    from ui_concessor import executar_interface

    executar_interface()


if __name__ == "__main__":
    main()
