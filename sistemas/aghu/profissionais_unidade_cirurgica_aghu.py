import ctypes
import os
import re
import time
import unicodedata
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
LOGS_DIR = BASE_DIR / "logs"

CAMINHO_MENU_CADASTRO_UNI_CIRURGICA = (
    "Cirurgias / PDT",
    "Cadastros",
    "Profissionais da Unidade Cirúrgica",
)

UNIDADES_FUNCIONAIS = (
    "CENTRO OBSTETRICO - PRE-PARTO",
    "CENTRO CIRURGICO AMBULATORIAL",
    "CENTRO DE ENDOSCOPIA",
    "CENTRO DE HEMODINAMICA",
    "CENTRO CIRURGICO CENTRAL",
)

FUNCAO_MEDICO_RESIDENTE = "Médico residente"
FUNCOES_PROFISSIONAL = (FUNCAO_MEDICO_RESIDENTE,)

STATUS_CRIADO = "criado"
STATUS_MANTIDO = "mantido"
STATUS_FUNCIONARIO_NAO_ENCONTRADO = "funcionario_nao_encontrado"
STATUS_CONFERIR_MANUAL = "conferir_manual"
STATUS_ERRO = "erro"
STATUS_IGNORADO = "ignorado"

StatusCadastro = Literal[
    "criado",
    "mantido",
    "funcionario_nao_encontrado",
    "conferir_manual",
    "erro",
    "ignorado",
]

ALIASES_COLUNAS = {
    "profissional": (
        "Profissional",
        "Nome",
        "Nome Profissional",
        "Nome do Profissional",
    ),
    "unidade_funcional": (
        "Unidade Funcional",
        "Unidade",
        "Unidade Cirurgica",
        "Unidade Cirúrgica",
    ),
    "funcao": ("Função", "Funcao"),
}

CAMPOS_OBRIGATORIOS_PLANILHA = ("profissional", "unidade_funcional")

SELECTOR_PESQUISA_NOME = 'input[name="nome:nome:inputId"]'
SELECTOR_BOTAO_LIMPAR_PESQUISA = '[id="bt_limpar:button"]'
SELECTOR_TABELA_PROFISSIONAIS = '[id="tabelaProfissionaisAtuantes:resultList_data"] > tr'
SELECTOR_UNIDADE_FUNCIONAL_CONTAINER = (
    '[id="sbUnidadeFuncional:sbUnidadeFuncional:suggestion"]'
)
SELECTOR_UNIDADE_FUNCIONAL_INPUT = (
    '[id="sbUnidadeFuncional:sbUnidadeFuncional:suggestion_input"]'
)
SELECTOR_PROFISSIONAL_INPUT = '[id="profissional:profissional:suggestion_input"]'
SELECTOR_PROFISSIONAL_SUGGESTION_PANEL = (
    '[id="profissional:profissional:suggestion_panel"]'
)
SELECTOR_FUNCAO_PANEL = '[id="funcaoProfissional:funcaoProfissional:inputId_panel"]'
SELECTOR_MENSAGENS = (
    "#messagesInDialog .ui-messages-info-summary, "
    "#messagesInDialog .ui-messages-error-summary, "
    "#messagesInDialog .ui-messages-warn-summary"
)
SELECTOR_FECHAR_DIALOG_MENSAGEM = (
    'a[href="#"].ui-dialog-titlebar-icon.ui-dialog-titlebar-close[role="button"]'
)

TEXTO_NENHUM_REGISTRO = "Nenhum registro encontrado!"
TEXTO_AUTOCOMPLETE_NENHUM_REGISTRO = "Nenhum Registro"
TEMPO_MAXIMO_CONSULTA_MS = 90000
TEMPO_DETECCAO_WIDGET_CARREGAMENTO_MS = 2000
TEMPO_ESTABILIDADE_RESULTADO_MS = 250


class AutocompleteSemRegistroError(RuntimeError):
    pass


@dataclass(frozen=True)
class CadastroProfissionalUnidadeEntrada:
    profissional: str = ""
    unidade_funcional: str = ""
    funcao: str = FUNCAO_MEDICO_RESIDENTE


@dataclass(frozen=True)
class ResultadoCadastroProfissional:
    profissional: str
    unidade_funcional: str
    funcao: str
    status: StatusCadastro
    detalhes: str


def esconder_console_windows() -> None:
    if os.name != "nt":
        return

    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 0)


@contextmanager
def controle_saida_terminal(mostrar_console: bool) -> Iterator[None]:
    if mostrar_console:
        yield
        return

    esconder_console_windows()
    with open(os.devnull, "w", encoding="utf-8") as destino_nulo:
        with redirect_stdout(destino_nulo), redirect_stderr(destino_nulo):
            yield


def _valor_em_branco(valor: object) -> bool:
    try:
        if pd.isna(valor):
            return True
    except (TypeError, ValueError):
        pass

    return str(valor or "").strip() == ""


def texto_planilha(valor: object) -> str:
    if _valor_em_branco(valor):
        return ""

    return str(valor).strip()


def _remover_acentos(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(
        caractere
        for caractere in normalizado
        if not unicodedata.combining(caractere)
    )


def normalizar_texto(valor: object) -> str:
    texto = _remover_acentos(str(valor or ""))
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto.casefold()


def _sem_codigo_unidade(valor: object) -> str:
    texto = texto_planilha(valor)
    return re.sub(r"^\s*\d+\s*-\s*", "", texto).strip()


def unidade_confere(valor_atual: object, unidade_esperada: str) -> bool:
    return normalizar_texto(_sem_codigo_unidade(valor_atual)) == normalizar_texto(
        unidade_esperada
    )


def funcao_confere(valor_atual: object, funcao_esperada: str) -> bool:
    return normalizar_texto(valor_atual) == normalizar_texto(funcao_esperada)


def profissional_confere(valor_atual: object, profissional_esperado: str) -> bool:
    return normalizar_texto(valor_atual) == normalizar_texto(profissional_esperado)


def normalizar_unidade_funcional(valor: object) -> str:
    texto = texto_planilha(valor)

    for unidade in UNIDADES_FUNCIONAIS:
        if unidade_confere(texto, unidade):
            return unidade

    return texto


def normalizar_funcao(valor: object) -> str:
    texto = texto_planilha(valor) or FUNCAO_MEDICO_RESIDENTE

    for funcao in FUNCOES_PROFISSIONAL:
        if funcao_confere(texto, funcao):
            return funcao

    return texto


def normalizar_entrada(
    entrada: CadastroProfissionalUnidadeEntrada,
) -> CadastroProfissionalUnidadeEntrada:
    return CadastroProfissionalUnidadeEntrada(
        profissional=texto_planilha(entrada.profissional),
        unidade_funcional=normalizar_unidade_funcional(entrada.unidade_funcional),
        funcao=normalizar_funcao(entrada.funcao),
    )


def validar_entrada(entrada: CadastroProfissionalUnidadeEntrada) -> list[str]:
    entrada = normalizar_entrada(entrada)
    erros: list[str] = []

    if _valor_em_branco(entrada.profissional):
        erros.append("Profissional em branco.")

    if _valor_em_branco(entrada.unidade_funcional):
        erros.append("Unidade Funcional em branco.")
    elif not any(
        unidade_confere(entrada.unidade_funcional, unidade)
        for unidade in UNIDADES_FUNCIONAIS
    ):
        erros.append("Unidade Funcional invalida.")

    if _valor_em_branco(entrada.funcao):
        erros.append("Funcao em branco.")
    elif not any(funcao_confere(entrada.funcao, funcao) for funcao in FUNCOES_PROFISSIONAL):
        erros.append("Funcao invalida.")

    return erros


def resultado_ignorado(
    entrada: CadastroProfissionalUnidadeEntrada,
    detalhes: str,
) -> ResultadoCadastroProfissional:
    entrada = normalizar_entrada(entrada)
    return ResultadoCadastroProfissional(
        profissional=entrada.profissional,
        unidade_funcional=entrada.unidade_funcional,
        funcao=entrada.funcao,
        status=STATUS_IGNORADO,
        detalhes=detalhes,
    )


def _normalizar_cabecalho(valor: object) -> str:
    return normalizar_texto(valor)


def _mapear_colunas_planilha(colunas: pd.Index) -> dict[str, str]:
    colunas_por_nome = {
        _normalizar_cabecalho(coluna): str(coluna).strip()
        for coluna in colunas
    }
    mapa: dict[str, str] = {}
    faltantes: list[str] = []

    for campo in CAMPOS_OBRIGATORIOS_PLANILHA:
        coluna = _coluna_por_alias(campo, colunas_por_nome)
        if coluna is None:
            faltantes.append(ALIASES_COLUNAS[campo][0])
        else:
            mapa[campo] = coluna

    coluna_funcao = _coluna_por_alias("funcao", colunas_por_nome)
    if coluna_funcao is not None:
        mapa["funcao"] = coluna_funcao

    if faltantes:
        raise ValueError(
            "Planilha invalida. Colunas obrigatorias ausentes: "
            + ", ".join(faltantes)
        )

    return mapa


def _coluna_por_alias(campo: str, colunas_por_nome: dict[str, str]) -> str | None:
    for alias in ALIASES_COLUNAS[campo]:
        coluna = colunas_por_nome.get(_normalizar_cabecalho(alias))
        if coluna is not None:
            return coluna

    return None


def _valor_coluna(linha: pd.Series, mapa: dict[str, str], campo: str) -> str:
    coluna = mapa.get(campo)
    if coluna is None:
        return ""

    return texto_planilha(linha.get(coluna, ""))


def ler_planilha_cadastros(
    caminho_planilha: str | os.PathLike,
) -> list[CadastroProfissionalUnidadeEntrada]:
    caminho = Path(caminho_planilha).expanduser()

    if not caminho.exists():
        raise FileNotFoundError(f"Planilha nao encontrada: {caminho}")

    if caminho.suffix.lower() != ".xlsx":
        raise ValueError("A planilha deve ser um arquivo .xlsx.")

    df = pd.read_excel(caminho, dtype=str, engine="openpyxl").fillna("")
    df.columns = df.columns.str.strip()
    mapa = _mapear_colunas_planilha(df.columns)
    cadastros: list[CadastroProfissionalUnidadeEntrada] = []

    for _, linha in df.iterrows():
        if all(_valor_em_branco(valor) for valor in linha):
            continue

        entrada = CadastroProfissionalUnidadeEntrada(
            profissional=_valor_coluna(linha, mapa, "profissional"),
            unidade_funcional=_valor_coluna(linha, mapa, "unidade_funcional"),
            funcao=_valor_coluna(linha, mapa, "funcao") or FUNCAO_MEDICO_RESIDENTE,
        )
        cadastros.append(normalizar_entrada(entrada))

    return cadastros


def _linha_relatorio(resultado: ResultadoCadastroProfissional) -> dict[str, str]:
    return {
        "Profissional": resultado.profissional,
        "Unidade Funcional": resultado.unidade_funcional,
        "Funcao": resultado.funcao,
        "Status": resultado.status,
        "Detalhes": resultado.detalhes,
    }


def salvar_relatorio_resultados(
    resultados: list[ResultadoCadastroProfissional],
    caminho_saida: str | os.PathLike,
) -> Path:
    caminho = Path(caminho_saida).expanduser()

    if not caminho.suffix:
        caminho = caminho.with_suffix(".xlsx")

    if caminho.suffix.lower() != ".xlsx":
        raise ValueError("O relatorio de saida deve ser um arquivo .xlsx.")

    caminho.parent.mkdir(parents=True, exist_ok=True)
    colunas = ["Profissional", "Unidade Funcional", "Funcao", "Status", "Detalhes"]
    df = pd.DataFrame([_linha_relatorio(resultado) for resultado in resultados])
    df = df.reindex(columns=colunas)

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
    resultados: list[ResultadoCadastroProfissional],
    usuario_rede: str,
    diretorio_logs: str | os.PathLike | None,
) -> str:
    pasta_logs = Path(diretorio_logs) if diretorio_logs else LOGS_DIR
    pasta_logs.mkdir(parents=True, exist_ok=True)
    data_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho = pasta_logs / f"log_profissionais_unidade_cirurgica_{data_hora}.csv"

    with caminho.open("w", encoding="utf-8-sig") as arquivo:
        arquivo.write(f"Atualizado por: {usuario_rede}\n")

    pd.DataFrame([_linha_relatorio(resultado) for resultado in resultados]).to_csv(
        caminho,
        index=False,
        sep=";",
        encoding="utf-8-sig",
        mode="a",
    )
    return str(caminho)


def primeiro_visivel(
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


def clicar_botao(janela_sistema: FrameLocator, nome: str, timeout_ms: int = 10000) -> None:
    botao = janela_sistema.get_by_role("button", name=nome).first
    botao.wait_for(state="visible", timeout=timeout_ms)
    botao.click(timeout=timeout_ms)


def widget_carregamento(janela_sistema: FrameLocator) -> Locator:
    return janela_sistema.get_by_label("Carregando").get_by_text("Aguarde...").first


def existe_carregamento_visivel(janela_sistema: FrameLocator) -> bool:
    try:
        return widget_carregamento(janela_sistema).is_visible(timeout=100)
    except Exception:
        return False


def aguardar_ciclo_carregamento(
    janela_sistema: FrameLocator,
    *,
    timeout_ms: int = TEMPO_MAXIMO_CONSULTA_MS,
    deteccao_ms: int = TEMPO_DETECCAO_WIDGET_CARREGAMENTO_MS,
) -> bool:
    widget = widget_carregamento(janela_sistema)

    try:
        widget.wait_for(state="visible", timeout=deteccao_ms)
    except PlaywrightTimeoutError:
        return not existe_carregamento_visivel(janela_sistema)

    fim = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < fim:
        if not existe_carregamento_visivel(janela_sistema):
            return True

        time.sleep(0.15)

    raise PlaywrightTimeoutError("AGHUX permaneceu em carregamento alem do tempo limite.")


def pode_confirmar_resultado(
    *,
    estado_desde: float,
    consulta_concluida: bool,
    estabilidade_resultado_ms: int = TEMPO_ESTABILIDADE_RESULTADO_MS,
) -> bool:
    return consulta_concluida and (
        time.monotonic() - estado_desde
    ) * 1000 >= estabilidade_resultado_ms


def linha_vazia_visivel(linhas: Locator) -> bool:
    total = linhas.count()

    for indice in range(total):
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


def preencher_input(locator: Locator, valor: str, timeout_ms: int = 5000) -> None:
    locator.wait_for(state="visible", timeout=timeout_ms)
    locator.click(timeout=timeout_ms)
    locator.fill("", timeout=timeout_ms)
    if valor:
        locator.fill(valor, timeout=timeout_ms)


def autocomplete_sem_registro_visivel(
    janela_sistema: FrameLocator,
    seletor_painel: str,
    timeout_ms: int = 100,
) -> bool:
    mensagem = (
        janela_sistema.locator(seletor_painel)
        .get_by_text(TEXTO_AUTOCOMPLETE_NENHUM_REGISTRO, exact=True)
        .first
    )

    try:
        return mensagem.is_visible(timeout=timeout_ms)
    except Exception:
        return False


def selecionar_autocomplete(
    janela_sistema: FrameLocator,
    seletor_input: str,
    valor: str,
    *,
    texto_esperado: str | None = None,
    seletor_painel_sem_registro: str | None = None,
    timeout_ms: int = 7000,
) -> None:
    campo = primeiro_visivel(janela_sistema, (seletor_input,), timeout_ms=timeout_ms)
    campo.click(timeout=timeout_ms)
    campo.fill("", timeout=timeout_ms)
    campo.press_sequentially(valor, delay=150, timeout=timeout_ms)

    texto_item = texto_esperado or valor
    padrao = re.compile(re.escape(texto_item), re.I)
    candidatos = (
        janela_sistema.locator("tr.ui-autocomplete-item, li.ui-autocomplete-item")
        .filter(has_text=padrao)
        .first,
        janela_sistema.get_by_role("cell", name=padrao).first,
        janela_sistema.locator(
            "tr.ui-autocomplete-item.ui-state-highlight, "
            "li.ui-autocomplete-item.ui-state-highlight"
        ).first,
        janela_sistema.locator("tr.ui-autocomplete-item, li.ui-autocomplete-item").first,
    )
    ultimo_erro: Exception | None = None

    if seletor_painel_sem_registro:
        fim = time.monotonic() + timeout_ms / 1000

        while time.monotonic() < fim:
            if autocomplete_sem_registro_visivel(
                janela_sistema,
                seletor_painel_sem_registro,
            ):
                raise AutocompleteSemRegistroError(
                    f"Autocomplete sem registro para: {valor}"
                )

            for candidato in candidatos:
                try:
                    if candidato.is_visible(timeout=100):
                        candidato.click(timeout=timeout_ms)
                        return
                except Exception as exc:
                    ultimo_erro = exc

            time.sleep(0.15)

        raise PlaywrightTimeoutError(
            f"Autocomplete sem opcao selecionavel para: {valor}"
        ) from ultimo_erro

    for candidato in candidatos:
        try:
            candidato.wait_for(state="visible", timeout=timeout_ms)
            candidato.click(timeout=timeout_ms)
            return
        except Exception as exc:
            ultimo_erro = exc

    try:
        campo.press("Enter", timeout=timeout_ms)
        return
    except Exception as exc:
        ultimo_erro = exc

    raise PlaywrightTimeoutError(
        f"Autocomplete sem opcao selecionavel para: {valor}"
    ) from ultimo_erro


def selecionar_unidade_funcional(
    janela_sistema: FrameLocator,
    unidade: str,
    timeout_ms: int = 7000,
) -> None:
    try:
        dropdown = (
            janela_sistema.locator(SELECTOR_UNIDADE_FUNCIONAL_CONTAINER)
            .get_by_role("button")
            .first
        )
        dropdown.wait_for(state="visible", timeout=timeout_ms)
        dropdown.click(timeout=timeout_ms)
    except Exception:
        selecionar_autocomplete(
            janela_sistema,
            SELECTOR_UNIDADE_FUNCIONAL_INPUT,
            unidade,
            texto_esperado=unidade,
            timeout_ms=timeout_ms,
        )
        return

    padrao = re.compile(re.escape(unidade), re.I)
    candidatos = (
        janela_sistema.get_by_role("cell", name=padrao).first,
        janela_sistema.locator("tr.ui-autocomplete-item").filter(has_text=padrao).first,
        janela_sistema.locator("tr.ui-autocomplete-item.ui-state-highlight").first,
    )
    ultimo_erro: Exception | None = None

    for candidato in candidatos:
        try:
            candidato.wait_for(state="visible", timeout=timeout_ms)
            candidato.click(timeout=timeout_ms)
            return
        except Exception as exc:
            ultimo_erro = exc

    try:
        selecionar_autocomplete(
            janela_sistema,
            SELECTOR_UNIDADE_FUNCIONAL_INPUT,
            unidade,
            texto_esperado=unidade,
            timeout_ms=timeout_ms,
        )
        return
    except Exception as exc:
        ultimo_erro = exc

    raise PlaywrightTimeoutError(
        f"Unidade Funcional nao localizada no dropdown: {unidade}"
    ) from ultimo_erro


def selecionar_selectonemenu(
    janela_sistema: FrameLocator,
    texto: str,
    *,
    panel_selector: str | None = None,
    timeout_ms: int = 7000,
) -> None:
    trigger = janela_sistema.locator(".ui-selectonemenu-trigger").first
    trigger.wait_for(state="visible", timeout=timeout_ms)
    trigger.click(timeout=timeout_ms)

    if panel_selector:
        item = janela_sistema.locator(panel_selector).get_by_text(texto, exact=True).first
    else:
        item = janela_sistema.locator("li.ui-selectonemenu-item").filter(
            has_text=re.compile(r"^" + re.escape(texto) + r"$", re.I)
        ).first

    item.wait_for(state="visible", timeout=timeout_ms)
    item.click(timeout=timeout_ms)


def clicar_voltar_se_visivel(janela_sistema: FrameLocator, timeout_ms: int = 3000) -> bool:
    botao = janela_sistema.get_by_role("button", name="Voltar").first

    try:
        botao.wait_for(state="visible", timeout=timeout_ms)
        botao.click(timeout=timeout_ms)
        aguardar_ciclo_carregamento(janela_sistema, deteccao_ms=500)
        return True
    except Exception:
        return False


def fechar_dialog_mensagem_se_visivel(
    janela_sistema: FrameLocator,
    timeout_ms: int = 1500,
) -> bool:
    botoes = janela_sistema.locator(SELECTOR_FECHAR_DIALOG_MENSAGEM)

    try:
        botoes.first.wait_for(state="attached", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        return False

    for indice in range(botoes.count()):
        botao = botoes.nth(indice)
        try:
            if botao.is_visible(timeout=250):
                botao.click(timeout=timeout_ms)
                return True
        except Exception:
            continue

    return False


def mensagens_sistema(janela_sistema: FrameLocator) -> list[str]:
    locators = janela_sistema.locator(SELECTOR_MENSAGENS)
    mensagens: list[str] = []

    for indice in range(locators.count()):
        item = locators.nth(indice)
        try:
            if item.is_visible(timeout=250):
                texto = item.inner_text(timeout=500).strip()
                if texto:
                    mensagens.append(texto)
        except Exception:
            continue

    return mensagens


def aguardar_mensagem_gravacao(
    janela_sistema: FrameLocator,
    timeout_ms: int = 15000,
) -> tuple[str, str]:
    fim = time.monotonic() + timeout_ms / 1000
    sucesso = "profissional na unidade cirurgica incluido com sucesso"

    while time.monotonic() < fim:
        for mensagem in mensagens_sistema(janela_sistema):
            mensagem_norm = normalizar_texto(mensagem)

            if sucesso in mensagem_norm:
                return "sucesso", mensagem

            if (
                "campo obrigatorio" in mensagem_norm
                or "invalido" in mensagem_norm
                or "erro" in mensagem_norm
                or "ja existe" in mensagem_norm
            ):
                return "erro", mensagem

        time.sleep(0.15)

    return "indefinido", "A gravacao nao retornou mensagem dentro do tempo limite."


class ProfissionalUnidadeCirurgicaFlow:
    def __init__(self, janela_sistema: FrameLocator):
        self.janela = janela_sistema

    def validar_tela_pesquisa(self) -> None:
        primeiro_visivel(self.janela, (SELECTOR_PESQUISA_NOME,), timeout_ms=15000)
        self.janela.get_by_role("button", name="Pesquisar").first.wait_for(
            state="visible",
            timeout=15000,
        )

    def pesquisar(
        self,
        entrada: CadastroProfissionalUnidadeEntrada,
    ) -> tuple[str, Locator | None]:
        self.validar_tela_pesquisa()
        self._limpar_pesquisa()
        campo_nome = primeiro_visivel(self.janela, (SELECTOR_PESQUISA_NOME,))
        preencher_input(campo_nome, entrada.profissional)
        clicar_botao(self.janela, "Pesquisar")
        consulta_concluida = aguardar_ciclo_carregamento(self.janela)
        return self._aguardar_resultado_pesquisa(
            entrada,
            consulta_concluida=consulta_concluida,
        )

    def _limpar_pesquisa(self) -> None:
        botao_limpar = self.janela.locator(SELECTOR_BOTAO_LIMPAR_PESQUISA).first
        botao_limpar.wait_for(state="visible", timeout=10000)
        botao_limpar.click(timeout=10000)
        aguardar_ciclo_carregamento(self.janela, deteccao_ms=500)
        primeiro_visivel(self.janela, (SELECTOR_PESQUISA_NOME,), timeout_ms=10000)

    def processar(
        self,
        entrada: CadastroProfissionalUnidadeEntrada,
    ) -> ResultadoCadastroProfissional:
        entrada = normalizar_entrada(entrada)
        estado, _linha = self.pesquisar(entrada)

        if estado == "vinculo_existente":
            return self._resultado(
                entrada,
                STATUS_MANTIDO,
                "Vinculo ativo ja existente para profissional, unidade e funcao.",
            )

        if estado == "vinculo_inativo":
            return self._resultado(
                entrada,
                STATUS_CONFERIR_MANUAL,
                "Vinculo localizado, mas a situacao nao esta ativa.",
            )

        if estado == "indefinido":
            return self._resultado(
                entrada,
                STATUS_CONFERIR_MANUAL,
                "Pesquisa nao retornou estado conclusivo.",
            )

        if estado not in {"nao_encontrado", "sem_vinculo_exato"}:
            return self._resultado(
                entrada,
                STATUS_CONFERIR_MANUAL,
                f"Estado inesperado na pesquisa: {estado}.",
            )

        clicar_botao(self.janela, "Novo")
        aguardar_ciclo_carregamento(self.janela, deteccao_ms=500)

        try:
            self._preencher_formulario(entrada)
        except AutocompleteSemRegistroError:
            self._cancelar_formulario()
            return self._resultado(
                entrada,
                STATUS_FUNCIONARIO_NAO_ENCONTRADO,
                "Funcionário não encontrado.",
            )

        status_gravacao, mensagem = self._gravar()
        self._retornar_para_pesquisa()

        if status_gravacao == "sucesso":
            return self._resultado(entrada, STATUS_CRIADO, mensagem)

        if status_gravacao == "indefinido":
            return self._resultado(entrada, STATUS_CONFERIR_MANUAL, mensagem)

        return self._resultado(entrada, STATUS_ERRO, mensagem)

    def _aguardar_resultado_pesquisa(
        self,
        entrada: CadastroProfissionalUnidadeEntrada,
        *,
        timeout_ms: int = TEMPO_MAXIMO_CONSULTA_MS,
        consulta_concluida: bool = False,
    ) -> tuple[str, Locator | None]:
        linhas = self.janela.locator(SELECTOR_TABELA_PROFISSIONAIS)
        inicio = time.monotonic()
        fim = inicio + timeout_ms / 1000
        estado_pendente: str | None = None
        estado_desde = inicio
        carregamento_observado = False

        while time.monotonic() < fim:
            carregando = existe_carregamento_visivel(self.janela)

            if carregando:
                carregamento_observado = True
                consulta_concluida = False
            elif carregamento_observado:
                consulta_concluida = True

            estado_vinculo, linha = self._estado_vinculo(linhas, entrada)
            if estado_vinculo is not None:
                return estado_vinculo, linha

            estado_atual: str | None = None
            if linha_vazia_visivel(linhas):
                estado_atual = "nao_encontrado"
            elif self._ha_resultado_visivel(linhas):
                estado_atual = "sem_vinculo_exato"

            if carregando:
                estado_pendente = None
                estado_desde = time.monotonic()
            elif estado_atual is not None:
                if estado_atual != estado_pendente:
                    estado_pendente = estado_atual
                    estado_desde = time.monotonic()
                elif pode_confirmar_resultado(
                    estado_desde=estado_desde,
                    consulta_concluida=consulta_concluida,
                ):
                    return estado_atual, None
            else:
                estado_pendente = None
                estado_desde = time.monotonic()

            time.sleep(0.15)

        return "indefinido", None

    def _estado_vinculo(
        self,
        linhas: Locator,
        entrada: CadastroProfissionalUnidadeEntrada,
    ) -> tuple[str | None, Locator | None]:
        for indice in range(linhas.count()):
            linha = linhas.nth(indice)

            try:
                if not linha.is_visible(timeout=250):
                    continue

                classe = linha.get_attribute("class", timeout=250) or ""
                if "ui-datatable-empty-message" in classe:
                    continue

                celulas = linha.locator("td")
                if celulas.count() < 6:
                    continue

                unidade = celulas.nth(1).inner_text(timeout=500)
                funcao = celulas.nth(2).inner_text(timeout=500)
                profissional = celulas.nth(5).inner_text(timeout=500)
                situacao = celulas.nth(7).inner_text(timeout=500) if celulas.count() > 7 else ""
            except Exception:
                continue

            if (
                unidade_confere(unidade, entrada.unidade_funcional)
                and funcao_confere(funcao, entrada.funcao)
                and profissional_confere(profissional, entrada.profissional)
            ):
                if normalizar_texto(situacao) == "ativo":
                    return "vinculo_existente", linha

                return "vinculo_inativo", linha

        return None, None

    @staticmethod
    def _ha_resultado_visivel(linhas: Locator) -> bool:
        for indice in range(linhas.count()):
            linha = linhas.nth(indice)
            try:
                if not linha.is_visible(timeout=250):
                    continue

                classe = linha.get_attribute("class", timeout=250) or ""
                texto = linha.inner_text(timeout=250)
            except Exception:
                continue

            if "ui-datatable-empty-message" not in classe and TEXTO_NENHUM_REGISTRO not in texto:
                return True

        return False

    def _preencher_formulario(
        self,
        entrada: CadastroProfissionalUnidadeEntrada,
    ) -> None:
        selecionar_autocomplete(
            self.janela,
            SELECTOR_PROFISSIONAL_INPUT,
            entrada.profissional,
            texto_esperado=entrada.profissional,
            seletor_painel_sem_registro=SELECTOR_PROFISSIONAL_SUGGESTION_PANEL,
        )
        selecionar_unidade_funcional(self.janela, entrada.unidade_funcional)
        selecionar_selectonemenu(
            self.janela,
            entrada.funcao,
            panel_selector=SELECTOR_FUNCAO_PANEL,
        )

    def _gravar(self) -> tuple[str, str]:
        clicar_botao(self.janela, "Gravar")
        aguardar_ciclo_carregamento(self.janela, deteccao_ms=500)
        return aguardar_mensagem_gravacao(self.janela)

    def _cancelar_formulario(self) -> None:
        try:
            clicar_botao(self.janela, "Cancelar")
            aguardar_ciclo_carregamento(self.janela, deteccao_ms=500)
            return
        except Exception:
            pass

        clicar_voltar_se_visivel(self.janela)

    def _retornar_para_pesquisa(self) -> None:
        fechar_dialog_mensagem_se_visivel(self.janela)

        for _ in range(3):
            try:
                self.validar_tela_pesquisa()
                return
            except Exception:
                if not clicar_voltar_se_visivel(self.janela):
                    break

    @staticmethod
    def _resultado(
        entrada: CadastroProfissionalUnidadeEntrada,
        status: StatusCadastro,
        detalhes: str,
    ) -> ResultadoCadastroProfissional:
        return ResultadoCadastroProfissional(
            profissional=entrada.profissional,
            unidade_funcional=entrada.unidade_funcional,
            funcao=entrada.funcao,
            status=status,
            detalhes=detalhes,
        )


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
    fazer_login(nova_page, usuario_rede, senha, url_aghu=url_aghu)
    return nova_page


def navegar_ate_cadastro_profissional_unidade(
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
                caminho=CAMINHO_MENU_CADASTRO_UNI_CIRURGICA,
            )
            ProfissionalUnidadeCirurgicaFlow(janela_sistema).validar_tela_pesquisa()
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

    raise RuntimeError("Falha ao navegar ate Profissionais da Unidade Cirurgica.")


def garantir_tela_pesquisa_profissional_unidade(
    context: BrowserContext,
    page_atual: Page,
    janela_atual: FrameLocator,
    usuario_rede: str,
    senha: str,
    *,
    url_aghu: str = AGHU_URL,
) -> tuple[Page, FrameLocator]:
    try:
        ProfissionalUnidadeCirurgicaFlow(janela_atual).validar_tela_pesquisa()
        return page_atual, janela_atual
    except Exception:
        pass

    try:
        janela_sistema = navegar_menu_aghu(
            page=page_atual,
            caminho=CAMINHO_MENU_CADASTRO_UNI_CIRURGICA,
        )
        ProfissionalUnidadeCirurgicaFlow(janela_sistema).validar_tela_pesquisa()
        return page_atual, janela_sistema
    except Exception:
        page = trocar_aba_aghux(
            context=context,
            page_atual=page_atual,
            usuario_rede=usuario_rede,
            senha=senha,
            url_aghu=url_aghu,
        )
        return navegar_ate_cadastro_profissional_unidade(
            context=context,
            page_atual=page,
            usuario_rede=usuario_rede,
            senha=senha,
            url_aghu=url_aghu,
        )


def processar_cadastro(
    janela_sistema: FrameLocator,
    entrada: CadastroProfissionalUnidadeEntrada,
) -> ResultadoCadastroProfissional:
    entrada = normalizar_entrada(entrada)
    return ProfissionalUnidadeCirurgicaFlow(janela_sistema).processar(entrada)


def processar_cadastros(
    context: BrowserContext,
    page_inicial: Page,
    janela_sistema_inicial: FrameLocator,
    cadastros: list[CadastroProfissionalUnidadeEntrada],
    usuario_rede: str,
    senha: str,
    *,
    resultados_prevalidacao: list[ResultadoCadastroProfissional | None] | None = None,
    url_aghu: str = AGHU_URL,
) -> list[ResultadoCadastroProfissional]:
    resultados: list[ResultadoCadastroProfissional] = []
    page = page_inicial
    janela_sistema = janela_sistema_inicial
    total = len(cadastros)

    if resultados_prevalidacao is None:
        resultados_prevalidacao = [
            resultado_ignorado(cadastro, "Linha ignorada: " + "; ".join(erros) + ".")
            if (erros := validar_entrada(cadastro))
            else None
            for cadastro in cadastros
        ]

    if len(resultados_prevalidacao) != total:
        raise ValueError("A pre-validacao deve ter a mesma quantidade de cadastros.")

    for indice, (entrada, pre_resultado) in enumerate(zip(cadastros, resultados_prevalidacao)):
        entrada = normalizar_entrada(entrada)
        print("\n========================================")
        print(
            f"Processando [{indice + 1}/{total}]: "
            f"{entrada.profissional} | {entrada.unidade_funcional} | {entrada.funcao}"
        )

        if pre_resultado is not None:
            print(pre_resultado.detalhes)
            resultados.append(pre_resultado)
            continue

        resultado_linha: ResultadoCadastroProfissional | None = None

        for tentativa in range(2):
            try:
                page, janela_sistema = garantir_tela_pesquisa_profissional_unidade(
                    context=context,
                    page_atual=page,
                    janela_atual=janela_sistema,
                    usuario_rede=usuario_rede,
                    senha=senha,
                    url_aghu=url_aghu,
                )
                resultado_linha = processar_cadastro(janela_sistema, entrada)
                break
            except Exception as exc:
                if tentativa == 0:
                    print("Falha tecnica no cadastro. Tentando Clean State...")
                    page = trocar_aba_aghux(
                        context=context,
                        page_atual=page,
                        usuario_rede=usuario_rede,
                        senha=senha,
                        url_aghu=url_aghu,
                    )
                    page, janela_sistema = navegar_ate_cadastro_profissional_unidade(
                        context=context,
                        page_atual=page,
                        usuario_rede=usuario_rede,
                        senha=senha,
                        url_aghu=url_aghu,
                    )
                    continue

                resultado_linha = ResultadoCadastroProfissional(
                    profissional=entrada.profissional,
                    unidade_funcional=entrada.unidade_funcional,
                    funcao=entrada.funcao,
                    status=STATUS_ERRO,
                    detalhes=f"Falha tecnica definitiva durante o cadastro: {exc}",
                )

        if resultado_linha is None:
            resultado_linha = ResultadoCadastroProfissional(
                profissional=entrada.profissional,
                unidade_funcional=entrada.unidade_funcional,
                funcao=entrada.funcao,
                status=STATUS_ERRO,
                detalhes="Falha tecnica durante o cadastro.",
            )

        print(f"Resultado: [{resultado_linha.status}] {resultado_linha.detalhes}")
        resultados.append(resultado_linha)

    return resultados


def executar_cadastros_profissionais(
    cadastros: list[CadastroProfissionalUnidadeEntrada],
    usuario_rede: str,
    senha: str,
    *,
    url_aghu: str = AGHU_URL,
    mostrar_browser: bool = True,
    mostrar_console: bool = True,
    diretorio_logs: str | os.PathLike | None = None,
    gerar_csv_log: bool = True,
) -> list[ResultadoCadastroProfissional]:
    if not usuario_rede or not senha:
        raise ValueError("Preencha usuario de rede e senha.")

    if not url_aghu:
        raise ValueError("Informe o ambiente do AGHU.")

    cadastros = [normalizar_entrada(cadastro) for cadastro in cadastros]

    with controle_saida_terminal(mostrar_console):
        return _executar_cadastros_profissionais_com_saida_configurada(
            cadastros=cadastros,
            usuario_rede=usuario_rede,
            senha=senha,
            url_aghu=url_aghu,
            mostrar_browser=mostrar_browser,
            diretorio_logs=diretorio_logs,
            gerar_csv_log=gerar_csv_log,
        )


def _executar_cadastros_profissionais_com_saida_configurada(
    cadastros: list[CadastroProfissionalUnidadeEntrada],
    usuario_rede: str,
    senha: str,
    *,
    url_aghu: str,
    mostrar_browser: bool,
    diretorio_logs: str | os.PathLike | None,
    gerar_csv_log: bool,
) -> list[ResultadoCadastroProfissional]:
    resultados_prevalidacao: list[ResultadoCadastroProfissional | None] = []
    existem_validos = False

    for cadastro in cadastros:
        erros = validar_entrada(cadastro)
        if erros:
            resultados_prevalidacao.append(
                resultado_ignorado(cadastro, "Linha ignorada: " + "; ".join(erros) + ".")
            )
        else:
            resultados_prevalidacao.append(None)
            existem_validos = True

    if not existem_validos:
        resultados = [
            resultado
            for resultado in resultados_prevalidacao
            if resultado is not None
        ]
        if gerar_csv_log:
            gerar_csv_logs(resultados, usuario_rede, diretorio_logs)
        return resultados

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not mostrar_browser, slow_mo=500)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        try:
            page.goto(url_aghu)
            fazer_login(page, usuario_rede, senha, url_aghu=url_aghu)
            page, janela_sistema = navegar_ate_cadastro_profissional_unidade(
                context=context,
                page_atual=page,
                usuario_rede=usuario_rede,
                senha=senha,
                url_aghu=url_aghu,
            )
            resultados = processar_cadastros(
                context=context,
                page_inicial=page,
                janela_sistema_inicial=janela_sistema,
                cadastros=cadastros,
                resultados_prevalidacao=resultados_prevalidacao,
                usuario_rede=usuario_rede,
                senha=senha,
                url_aghu=url_aghu,
            )
            if gerar_csv_log:
                gerar_csv_logs(resultados, usuario_rede, diretorio_logs)
            return resultados
        finally:
            browser.close()


def executar_cadastro_lote(
    usuario_rede: str,
    senha: str,
    caminho_planilha: str | os.PathLike,
    caminho_relatorio: str | os.PathLike,
    *,
    url_aghu: str = AGHU_URL,
    mostrar_browser: bool = True,
    mostrar_console: bool = True,
    diretorio_logs: str | os.PathLike | None = None,
) -> tuple[list[ResultadoCadastroProfissional], Path]:
    cadastros = ler_planilha_cadastros(caminho_planilha)
    resultados = executar_cadastros_profissionais(
        cadastros=cadastros,
        usuario_rede=usuario_rede,
        senha=senha,
        url_aghu=url_aghu,
        mostrar_browser=mostrar_browser,
        mostrar_console=mostrar_console,
        diretorio_logs=diretorio_logs,
    )
    relatorio = salvar_relatorio_resultados(resultados, caminho_relatorio)
    return resultados, relatorio


def executar_cadastro_individual(
    usuario_rede: str,
    senha: str,
    cadastro: CadastroProfissionalUnidadeEntrada,
    *,
    url_aghu: str = AGHU_URL,
    mostrar_browser: bool = True,
    mostrar_console: bool = True,
    diretorio_logs: str | os.PathLike | None = None,
) -> ResultadoCadastroProfissional:
    resultados = executar_cadastros_profissionais(
        cadastros=[cadastro],
        usuario_rede=usuario_rede,
        senha=senha,
        url_aghu=url_aghu,
        mostrar_browser=mostrar_browser,
        mostrar_console=mostrar_console,
        diretorio_logs=diretorio_logs,
    )
    return resultados[0]


def main() -> None:
    from ui_profissionais_unidade_cirurgica import executar_interface

    executar_interface()


if __name__ == "__main__":
    main()
