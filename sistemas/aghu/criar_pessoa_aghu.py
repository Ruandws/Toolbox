import ctypes
import os
import re
import time
import unicodedata
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterator, Literal

import pandas as pd
from playwright.sync_api import BrowserContext, FrameLocator, Locator, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from autenticador import AGHU_URL, autenticar_aghu_page, exigir_login_valido
from menu import navegar_menu_aghu



# ============================================================
# SECAO: utilitarios, modelos, validacao e planilha
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

CAMINHO_MENU_CADASTRO_PESSOA = (
    "Outros Módulos",
    "Colaborador",
    "Administrar Servidores",
    "Pessoas",
)

TEXTO_NENHUM_REGISTRO = "Nenhum registro encontrado!"
TEMPO_MAXIMO_CONSULTA_MS = 90000
TEMPO_DETECCAO_WIDGET_CARREGAMENTO_MS = 2000
TEMPO_ESTABILIDADE_RESULTADO_MS = 250

STATUS_CRIADO = "criado"
STATUS_MANTIDO = "mantido"
STATUS_ERRO = "erro"
STATUS_IGNORADO = "ignorado"
STATUS_CONFERIR_MANUAL = "conferir_manual"

StatusCadastro = Literal[
    "criado",
    "mantido",
    "erro",
    "ignorado",
    "conferir_manual",
]

ALIASES_COLUNAS = {
    "nome_pessoa": ("Nome da Pessoa", "Nome Pessoa", "Nome", "Nome Completo", "nome completo", "Nome completo"),
    "nome_mae": ("Nome da Mãe", "Nome Mae", "Nome da Mae", "Nome da mãe"),
    "sexo": ("Sexo", "sexo"),
    "data_nascimento": ("Data de Nascimento", "Data de nascimento", "Nascimento"),
    "nacionalidade": ("Nacionalidade", "nacionalidade"),
    "naturalidade": ("Naturalidade", "naturalidade"),
    "rg": ("Nro identidade", "Nro Identidade", "RG", "rg", "Identidade"),
    "orgao_emissor": ("Órgão Emissor", "Orgao Emissor", "Órgão emissor", "órgão emissor"),
    "uf_rg": ("UF", "uf", "U.F", "u.f", "UF RG"),
    "cpf": ("CPF", "cpf"),
    "ddd": ("DDD", "ddd"),
    "telefone_celular": ("Telefone Celular", "Celular", "Telefone", "Telefone (Cel.)"),
    "cep_cadastrado": ("CEP Cadastrado", "CEP", "cep"),
    "logradouro_nao_cadastrado": ("Logradouro", "Logradouro Não Cadastrado", "Logradouro Nao Cadastrado"),
    "bairro_nao_cadastrado": ("Bairro", "Bairro Não Cadastrado", "Bairro Nao Cadastrado"),
    "cep_nao_cadastrado": ("CEP Não Cadastrado", "CEP Nao Cadastrado"),
    "municipio_nao_cadastrado": ("Município", "Municipio", "Município Não Cadastrado", "Municipio Nao Cadastrado"),
}

CAMPOS_PESSOA_OBRIGATORIOS = (
    "nome_pessoa",
    "nome_mae",
    "data_nascimento",
    "naturalidade",
    "rg",
    "orgao_emissor",
    "uf_rg",
    "cpf",
)

@dataclass(frozen=True)
class CadastroPessoaEntrada:
    nome_pessoa: str = ""
    nome_mae: str = ""
    sexo: str = ""
    data_nascimento: str = ""
    nacionalidade: str = ""
    naturalidade: str = ""
    rg: str = ""
    orgao_emissor: str = ""
    uf_rg: str = ""
    cpf: str = ""
    ddd: str = ""
    telefone_celular: str = ""
    cep_cadastrado: str = ""
    logradouro_nao_cadastrado: str = ""
    bairro_nao_cadastrado: str = ""
    cep_nao_cadastrado: str = ""
    municipio_nao_cadastrado: str = ""

@dataclass(frozen=True)
class FluxoResultado:
    status: StatusCadastro
    detalhes: str


@dataclass(frozen=True)
class ResultadoCadastroPessoa:
    cpf: str
    nome_pessoa: str
    status: StatusCadastro
    detalhes: str
    pessoa: str = ""



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


def normalizar_texto(valor: object) -> str:
    return re.sub(r"\s+", " ", str(valor or "").strip()).casefold()


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


def normalizar_nacionalidade(valor: object) -> str:
    texto = texto_planilha(valor)
    if _remover_acentos(texto).casefold().startswith("bra"):
        return "Brasileiro"

    return texto


ALIASES_NATURALIDADE_AGHU = {
    "brasilia": "Brasília",
    "brasilia df": "Brasília",
    "brasilia distrito federal": "Brasília",
    "distrito federal": "Brasília",
    "distrito federal df": "Brasília",
}


def _chave_alias_naturalidade(valor: object) -> str:
    texto = _remover_acentos(texto_planilha(valor)).casefold()
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def normalizar_naturalidade(valor: object) -> str:
    texto = texto_planilha(valor)
    return ALIASES_NATURALIDADE_AGHU.get(_chave_alias_naturalidade(texto), texto)


def normalizar_data_nascimento(valor: object) -> str:
    if _valor_em_branco(valor):
        return ""

    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y")

    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")

    texto = texto_planilha(valor)
    texto_data = texto.split()[0]

    formatos = (
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%y",
        "%d-%m-%y",
    )
    for formato in formatos:
        try:
            return datetime.strptime(texto_data, formato).strftime("%d/%m/%Y")
        except ValueError:
            pass

    digitos = apenas_digitos(texto)
    if len(digitos) == 7:
        digitos = "0" + digitos

    if _data_nascimento_valida(digitos):
        return datetime.strptime(digitos, "%d%m%Y").strftime("%d/%m/%Y")

    return texto


def _data_nascimento_valida(valor: str) -> bool:
    texto = texto_planilha(valor)
    digitos = apenas_digitos(texto)

    if not re.fullmatch(r"\d{8}", digitos or ""):
        return False

    try:
        data = datetime.strptime(digitos, "%d%m%Y")
    except ValueError:
        return False

    return data.strftime("%d%m%Y") == digitos


def apenas_digitos(valor: object) -> str:
    return re.sub(r"\D+", "", str(valor or ""))


def cpf_confere(valor_atual: object, cpf_esperado: str) -> bool:
    return apenas_digitos(valor_atual).endswith(apenas_digitos(cpf_esperado))


def normalizar_entrada(entrada: CadastroPessoaEntrada) -> CadastroPessoaEntrada:
    dados = {campo: texto_planilha(getattr(entrada, campo)) for campo in ALIASES_COLUNAS}
    dados["data_nascimento"] = normalizar_data_nascimento(dados["data_nascimento"])
    dados["nacionalidade"] = normalizar_nacionalidade(dados["nacionalidade"])
    dados["naturalidade"] = normalizar_naturalidade(dados["naturalidade"])
    dados["cpf"] = apenas_digitos(dados["cpf"])
    return CadastroPessoaEntrada(**dados)


def _nome_coluna(campo: str) -> str:
    return ALIASES_COLUNAS[campo][0]


def validar_entrada(entrada: CadastroPessoaEntrada) -> list[str]:
    entrada = normalizar_entrada(entrada)
    erros: list[str] = []

    faltantes_pessoa = [
        _nome_coluna(campo)
        for campo in CAMPOS_PESSOA_OBRIGATORIOS
        if _valor_em_branco(getattr(entrada, campo))
    ]
    if faltantes_pessoa:
        erros.append("Pessoa: campos obrigatorios em branco: " + ", ".join(faltantes_pessoa))

    if entrada.cpf and len(apenas_digitos(entrada.cpf)) != 11:
        erros.append("Pessoa: CPF deve conter 11 digitos.")

    if entrada.data_nascimento and not _data_nascimento_valida(entrada.data_nascimento):
        erros.append("Pessoa: Data de Nascimento deve estar em uma data valida no formato dd/mm/aaaa.")

    return erros


def resultado_ignorado(entrada: CadastroPessoaEntrada, detalhes: str) -> ResultadoCadastroPessoa:
    entrada = normalizar_entrada(entrada)
    return ResultadoCadastroPessoa(
        cpf=entrada.cpf,
        nome_pessoa=entrada.nome_pessoa,
        status=STATUS_IGNORADO,
        detalhes=detalhes,
    )


def _valor_por_alias(linha: pd.Series, campo: str) -> str:
    for alias in ALIASES_COLUNAS[campo]:
        if alias in linha.index:
            return texto_planilha(linha.get(alias, ""))
    return ""


def ler_planilha_cadastros(caminho_planilha: str | os.PathLike) -> list[CadastroPessoaEntrada]:
    caminho = Path(caminho_planilha).expanduser()

    if not caminho.exists():
        raise FileNotFoundError(f"Planilha nao encontrada: {caminho}")

    if caminho.suffix.lower() != ".xlsx":
        raise ValueError("A planilha deve ser um arquivo .xlsx.")

    df = pd.read_excel(caminho, dtype=str, engine="openpyxl").fillna("")
    df.columns = df.columns.str.strip()

    colunas_faltantes = []
    for campo in CAMPOS_PESSOA_OBRIGATORIOS:
        if not any(alias in df.columns for alias in ALIASES_COLUNAS[campo]):
            colunas_faltantes.append(_nome_coluna(campo))

    if colunas_faltantes:
        raise ValueError(
            "Planilha invalida. Colunas obrigatorias ausentes: "
            + ", ".join(colunas_faltantes)
        )

    cadastros: list[CadastroPessoaEntrada] = []
    for _, linha in df.iterrows():
        dados = {campo: _valor_por_alias(linha, campo) for campo in ALIASES_COLUNAS}
        cadastros.append(normalizar_entrada(CadastroPessoaEntrada(**dados)))

    return cadastros


def _linha_relatorio(resultado: ResultadoCadastroPessoa) -> dict[str, str]:
    return {
        "CPF": resultado.cpf,
        "Nome da Pessoa": resultado.nome_pessoa,
        "Status": resultado.status,
        "Detalhes": resultado.detalhes,
        "Pessoa": resultado.pessoa,
    }


def salvar_relatorio_resultados(
    resultados: list[ResultadoCadastroPessoa],
    caminho_saida: str | os.PathLike,
) -> Path:
    caminho = Path(caminho_saida).expanduser()
    if not caminho.suffix:
        caminho = caminho.with_suffix(".xlsx")
    if caminho.suffix.lower() != ".xlsx":
        raise ValueError("O relatorio de saida deve ser um arquivo .xlsx.")

    caminho.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([_linha_relatorio(resultado) for resultado in resultados])

    with pd.ExcelWriter(caminho, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Resultado")
        worksheet = writer.sheets["Resultado"]
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions

        for coluna in worksheet.columns:
            largura = max(len(str(celula.value or "")) for celula in coluna)
            worksheet.column_dimensions[coluna[0].column_letter].width = min(largura + 2, 80)

    return caminho


def gerar_csv_logs(
    resultados: list[ResultadoCadastroPessoa],
    usuario_rede: str,
    diretorio_logs: str | os.PathLike | None,
) -> str:
    pasta_logs = Path(diretorio_logs) if diretorio_logs else BASE_DIR / "logs"
    pasta_logs.mkdir(parents=True, exist_ok=True)
    data_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho = pasta_logs / f"log_cadastro_pessoas_{data_hora}.csv"

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

    fim = time.monotonic() + (timeout_ms / 1000)
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
    return consulta_concluida and (time.monotonic() - estado_desde) * 1000 >= estabilidade_resultado_ms


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


def selecionar_autocomplete(
    janela_sistema: FrameLocator,
    seletor_input: str,
    valor: str,
    *,
    texto_esperado: str | None = None,
    timeout_ms: int = 7000,
) -> None:
    if not valor:
        return

    campo = primeiro_visivel(janela_sistema, (seletor_input,), timeout_ms=timeout_ms)
    campo.click(timeout=timeout_ms)
    campo.fill("", timeout=timeout_ms)
    campo.press_sequentially(valor, delay=150, timeout=timeout_ms)

    texto_item = texto_esperado or valor
    candidatos = (
        janela_sistema.locator("tr.ui-autocomplete-item, li.ui-autocomplete-item").filter(has_text=re.compile(re.escape(texto_item), re.I)).first,
        janela_sistema.get_by_role("cell", name=re.compile(re.escape(texto_item), re.I)).first,
        janela_sistema.locator("tr.ui-autocomplete-item.ui-state-highlight, li.ui-autocomplete-item.ui-state-highlight").first,
        janela_sistema.locator("tr.ui-autocomplete-item, li.ui-autocomplete-item").first,
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
        campo.press("Enter", timeout=timeout_ms)
        return
    except Exception as exc:
        ultimo_erro = exc

    raise PlaywrightTimeoutError(f"Autocomplete sem opcao selecionavel para: {valor}") from ultimo_erro


def selecionar_selectonemenu(
    janela_sistema: FrameLocator,
    texto: str,
    *,
    indice_trigger: int = 0,
    panel_selector: str | None = None,
    timeout_ms: int = 7000,
) -> None:
    if not texto:
        return

    trigger = janela_sistema.locator(".ui-selectonemenu-trigger").nth(indice_trigger)
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


def mensagens_sistema(janela_sistema: FrameLocator) -> list[str]:
    locators = janela_sistema.locator(
        "#messagesInDialog .ui-messages-info-summary, "
        "#messagesInDialog .ui-messages-error-summary, "
        "#messagesInDialog .ui-messages-warn-summary"
    )
    mensagens: list[str] = []
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


def aguardar_mensagem_gravacao(
    janela_sistema: FrameLocator,
    *,
    sucessos: tuple[str, ...],
    erros_negocio: tuple[str, ...] = (),
    timeout_ms: int = 15000,
) -> tuple[str, str]:
    fim = time.monotonic() + timeout_ms / 1000

    while time.monotonic() < fim:
        for mensagem in mensagens_sistema(janela_sistema):
            mensagem_norm = normalizar_texto(mensagem)
            if any(normalizar_texto(sucesso) in mensagem_norm for sucesso in sucessos):
                return "sucesso", mensagem
            if any(normalizar_texto(erro) in mensagem_norm for erro in erros_negocio):
                return "erro_negocio", mensagem
            if "campo obrigatorio" in mensagem_norm or "invalido" in mensagem_norm or "erro" in mensagem_norm:
                return "erro", mensagem
        time.sleep(0.15)

    return "indefinido", "A gravacao nao retornou mensagem dentro do tempo limite."


# ============================================================
# SECAO: fluxo de Pessoa
# ============================================================

SELECTOR_PESQUISA_CPF = 'input[name="cpf:cpf:inputId"]'
SELECTOR_TABELA_PESSOAS = '[id="tabelaPessoaFisica:resultList_data"] > tr'
SELECTOR_NOME_PESSOA = '[id="nomePessoa:nomePessoa:inputId"]'
SELECTOR_NOME_MAE = 'input[name="nomeMae:nomeMae:inputId"]'
SELECTOR_DATA_NASCIMENTO = '[id="dataNascimento:dataNascimento:inputId_input"]'
SELECTOR_NACIONALIDADE = '[id="suggestionNacionalidade:suggestionNacionalidade:suggestion_input"]'
SELECTOR_NATURALIDADE = '[id="naturalidade:naturalidade:suggestion_input"]'
SELECTOR_RG = 'input[name="rg:rg:inputId"]'
SELECTOR_ORGAO = '[id="orgao:orgao:suggestion_input"]'
SELECTOR_UF_RG = '[id="ufRgPessoa:ufRgPessoa:suggestion_input"]'
SELECTOR_DDD = '[id="dddCelular:dddCelular:inputId_input"]'
SELECTOR_TELEFONE_CELULAR = '[id="telefoneCelular:telefoneCelular:inputId_input"]'
SELECTOR_CEP_CADASTRADO = '[id="suggestionCepCadastrado:suggestionCepCadastrado:suggestion_input"]'
SELECTOR_LOGRADOURO_NAO_CADASTRADO = '[id="logradouroNaoCadastrado:logradouroNaoCadastrado:inputId"]'
SELECTOR_BAIRRO_NAO_CADASTRADO = '[id="bairroNaoCadastrado:bairroNaoCadastrado:inputId"]'
SELECTOR_CEP_NAO_CADASTRADO = '[id="cepNaoCadastrado:cepNaoCadastrado:inputId_input"]'
SELECTOR_MUNICIPIO_NAO_CADASTRADO = '[id="suggestionCidadeNaoCadastrada:suggestionCidadeNaoCadastrada:suggestion_input"]'
SELECTOR_FECHAR_PAINEL_SUCESSO = ('a[href="#"].ui-dialog-titlebar-icon.ui-dialog-titlebar-close.ui-corner-all[role="button"]')



class PessoaFlow:
    def __init__(self, janela_sistema: FrameLocator):
        self.janela = janela_sistema

    def validar_tela_pesquisa(self) -> None:
        primeiro_visivel(self.janela, (SELECTOR_PESQUISA_CPF,), timeout_ms=10000)
        self.janela.get_by_role("button", name="Pesquisar").first.wait_for(
            state="visible",
            timeout=10000,
        )

    def pesquisar_por_cpf(self, cpf: str) -> tuple[str, Locator | None]:
        self.validar_tela_pesquisa()
        campo_cpf = primeiro_visivel(self.janela, (SELECTOR_PESQUISA_CPF,))
        preencher_input(campo_cpf, apenas_digitos(cpf))
        clicar_botao(self.janela, "Pesquisar")
        consulta_concluida = aguardar_ciclo_carregamento(self.janela)
        return self._aguardar_resultado_pesquisa(cpf, consulta_concluida=consulta_concluida)

    def processar(self, entrada: CadastroPessoaEntrada) -> FluxoResultado:
        estado, linha = self.pesquisar_por_cpf(entrada.cpf)

        if estado == "indefinido":
            return FluxoResultado(
                STATUS_CONFERIR_MANUAL,
                "Pesquisa de pessoa por CPF nao retornou estado conclusivo.",
            )

        if estado == "encontrado" and linha is not None:
            return FluxoResultado(
                STATUS_MANTIDO,
                "Cadastro ja existente para o CPF informado. Nenhuma alteracao realizada.",
            )

        if estado != "nao_encontrado":
            return FluxoResultado(
                STATUS_CONFERIR_MANUAL,
                f"Estado inesperado na pesquisa de pessoa: {estado}.",
            )

        clicar_botao(self.janela, "Novo")
        aguardar_ciclo_carregamento(self.janela, deteccao_ms=500)
        self._preencher_formulario(entrada)
        status_gravacao, mensagem = self._gravar_pessoa()
        self._retornar_para_pesquisa()

        if status_gravacao == "sucesso":
            return FluxoResultado(STATUS_CRIADO, mensagem)

        if status_gravacao == "indefinido":
            return FluxoResultado(STATUS_CONFERIR_MANUAL, mensagem)

        return FluxoResultado(STATUS_ERRO, mensagem)

    def _aguardar_resultado_pesquisa(
        self,
        cpf: str,
        *,
        timeout_ms: int = 90000,
        consulta_concluida: bool = False,
    ) -> tuple[str, Locator | None]:
        linhas = self.janela.locator(SELECTOR_TABELA_PESSOAS)
        inicio = time.monotonic()
        fim = inicio + timeout_ms / 1000
        estado_pendente: str | None = None
        estado_desde = inicio
        carregamento_observado = False

        while time.monotonic() < fim:
            try:
                carregando = existe_carregamento_visivel(self.janela)
            except Exception:
                carregando = False

            if carregando:
                carregamento_observado = True
                consulta_concluida = False
            elif carregamento_observado:
                consulta_concluida = True

            linha = self._linha_por_cpf(linhas, cpf)
            if linha is not None:
                return "encontrado", linha

            estado_atual: str | None = None
            if linha_vazia_visivel(linhas):
                estado_atual = "nao_encontrado"
            else:
                try:
                    if linhas.count() > 0 and linhas.first.is_visible(timeout=250):
                        estado_atual = "sem_cpf_exato"
                except Exception:
                    pass

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

    def _linha_por_cpf(self, linhas: Locator, cpf: str) -> Locator | None:
        total = linhas.count()
        for indice in range(total):
            linha = linhas.nth(indice)
            try:
                classe = linha.get_attribute("class", timeout=250) or ""
                if "ui-datatable-empty-message" in classe:
                    continue

                celulas = linha.locator("td")
                if celulas.count() < 5:
                    continue

                texto_cpf = celulas.nth(4).inner_text(timeout=500)
                if cpf_confere(texto_cpf, cpf):
                    return linha
            except Exception:
                continue

        return None

    def _preencher_formulario(self, entrada: CadastroPessoaEntrada) -> None:
        preencher_input(primeiro_visivel(self.janela, (SELECTOR_NOME_PESSOA,)), entrada.nome_pessoa)
        preencher_input(primeiro_visivel(self.janela, (SELECTOR_NOME_MAE,)), entrada.nome_mae)

        if entrada.sexo:
            sexo = self._normalizar_sexo(entrada.sexo)
            selecionar_selectonemenu(
                self.janela,
                sexo,
                indice_trigger=0,
                panel_selector='[id="sexo:sexo:inputId_panel"]',
            )

        preencher_input(primeiro_visivel(self.janela, (SELECTOR_DATA_NASCIMENTO,)), entrada.data_nascimento)
        selecionar_autocomplete(self.janela, SELECTOR_NACIONALIDADE, entrada.nacionalidade)
        selecionar_autocomplete(self.janela, SELECTOR_NATURALIDADE, entrada.naturalidade)
        preencher_input(primeiro_visivel(self.janela, (SELECTOR_RG,)), entrada.rg)
        selecionar_autocomplete(self.janela, SELECTOR_ORGAO, entrada.orgao_emissor)
        selecionar_autocomplete(self.janela, SELECTOR_UF_RG, entrada.uf_rg)
        preencher_input(primeiro_visivel(self.janela, (SELECTOR_PESQUISA_CPF,)), apenas_digitos(entrada.cpf))

        if entrada.ddd:
            preencher_input(primeiro_visivel(self.janela, (SELECTOR_DDD,)), entrada.ddd)
        if entrada.telefone_celular:
            preencher_input(primeiro_visivel(self.janela, (SELECTOR_TELEFONE_CELULAR,)), entrada.telefone_celular)
        if entrada.cep_cadastrado:
            selecionar_autocomplete(self.janela, SELECTOR_CEP_CADASTRADO, apenas_digitos(entrada.cep_cadastrado))

        if entrada.logradouro_nao_cadastrado:
            preencher_input(primeiro_visivel(self.janela, (SELECTOR_LOGRADOURO_NAO_CADASTRADO,)), entrada.logradouro_nao_cadastrado)
        if entrada.bairro_nao_cadastrado:
            preencher_input(primeiro_visivel(self.janela, (SELECTOR_BAIRRO_NAO_CADASTRADO,)), entrada.bairro_nao_cadastrado)
        if entrada.cep_nao_cadastrado:
            preencher_input(primeiro_visivel(self.janela, (SELECTOR_CEP_NAO_CADASTRADO,)), apenas_digitos(entrada.cep_nao_cadastrado))
        if entrada.municipio_nao_cadastrado:
            selecionar_autocomplete(self.janela, SELECTOR_MUNICIPIO_NAO_CADASTRADO, entrada.municipio_nao_cadastrado)

    def _gravar_pessoa(self) -> tuple[str, str]:
        clicar_botao(self.janela, "Gravar")
        aguardar_ciclo_carregamento(self.janela, deteccao_ms=500)
        return aguardar_mensagem_gravacao(
            self.janela,
            sucessos=("Pessoa incluída com sucesso.", "Pessoa alterada com sucesso.", "Pessoa atualizada com sucesso."),
        )

    def _retornar_para_pesquisa(self) -> None:
        for _ in range(3):
            try:
                self.validar_tela_pesquisa()
                return
            except Exception:
                if not clicar_voltar_se_visivel(self.janela):
                    break

    @staticmethod
    def _normalizar_sexo(valor: str) -> str:
        valor_norm = normalizar_texto(valor)
        if valor_norm.startswith("m"):
            return "Masculino"
        if valor_norm.startswith("f"):
            return "Feminino"
        return "Ignorado"

    def fechar_painel_sucesso_se_visivel(self, timeout_ms: int = 2000) -> bool:
        botoes_fechar = self.janela.locator(SELECTOR_FECHAR_PAINEL_SUCESSO)

        try:
            botoes_fechar.first.wait_for(state="attached", timeout=timeout_ms)
        except PlaywrightTimeoutError:
            return False

        total = botoes_fechar.count()
        for indice in range(total):
            botao = botoes_fechar.nth(indice)

            try:
                if not botao.is_visible(timeout=250):
                    continue

                botao.click(timeout=timeout_ms)

                try:
                    botao.wait_for(state="hidden", timeout=timeout_ms)
                except Exception:
                    pass

                return True
            except Exception:
                continue

        return False


# ============================================================
# SECAO: maestro central
# ============================================================

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


def navegar_ate_cadastro_pessoa(
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
                caminho=CAMINHO_MENU_CADASTRO_PESSOA,
            )
            primeiro_visivel(janela_sistema, (SELECTOR_PESQUISA_CPF,), timeout_ms=15000)
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

    raise RuntimeError("Falha ao navegar ate Cadastro de Pessoa.")


def garantir_tela_pesquisa_pessoa(
    context: BrowserContext,
    page_atual: Page,
    janela_atual: FrameLocator,
    usuario_rede: str,
    senha: str,
    *,
    url_aghu: str = AGHU_URL,
) -> tuple[Page, FrameLocator]:
    try:
        PessoaFlow(janela_atual).validar_tela_pesquisa()
        return page_atual, janela_atual
    except Exception:
        pass

    try:
        janela_sistema = navegar_menu_aghu(
            page=page_atual,
            caminho=CAMINHO_MENU_CADASTRO_PESSOA,
        )
        PessoaFlow(janela_sistema).validar_tela_pesquisa()
        return page_atual, janela_sistema
    except Exception:
        page = trocar_aba_aghux(
            context=context,
            page_atual=page_atual,
            usuario_rede=usuario_rede,
            senha=senha,
            url_aghu=url_aghu,
        )
        return navegar_ate_cadastro_pessoa(
            context=context,
            page_atual=page,
            usuario_rede=usuario_rede,
            senha=senha,
            url_aghu=url_aghu,
        )


def _resumo_fluxo(resultado: FluxoResultado | None) -> str:
    if resultado is None:
        return ""
    return f"{resultado.status}: {resultado.detalhes}"


def processar_cadastro(
    janela_sistema: FrameLocator,
    entrada: CadastroPessoaEntrada,
) -> ResultadoCadastroPessoa:
    entrada = normalizar_entrada(entrada)

    pessoa_flow = PessoaFlow(janela_sistema)
    pessoa = pessoa_flow.processar(entrada)

    return ResultadoCadastroPessoa(
        cpf=entrada.cpf,
        nome_pessoa=entrada.nome_pessoa,
        status=pessoa.status,
        detalhes=pessoa.detalhes,
        pessoa=_resumo_fluxo(pessoa),
    )


def processar_cadastros(
    context: BrowserContext,
    page_inicial: Page,
    janela_sistema_inicial: FrameLocator,
    cadastros: list[CadastroPessoaEntrada],
    usuario_rede: str,
    senha: str,
    *,
    resultados_prevalidacao: list[ResultadoCadastroPessoa | None] | None = None,
    url_aghu: str = AGHU_URL,
) -> list[ResultadoCadastroPessoa]:
    resultados: list[ResultadoCadastroPessoa] = []
    page = page_inicial
    janela_sistema = janela_sistema_inicial
    total = len(cadastros)

    if not resultados_prevalidacao:
        resultados_prevalidacao = []
        for cadastro in cadastros:
            erros = validar_entrada(cadastro)
            if erros:
                resultados_prevalidacao.append(
                    resultado_ignorado(
                        cadastro,
                        "Linha ignorada: " + "; ".join(erros) + ".",
                    )
                )
            else:
                resultados_prevalidacao.append(None)

    if len(resultados_prevalidacao) != total:
        raise ValueError(
            "A pre-validacao deve ter a mesma quantidade de cadastros."
        )

    for indice, (entrada, pre_resultado) in enumerate(zip(cadastros, resultados_prevalidacao)):
        entrada = normalizar_entrada(entrada)
        print("\n========================================")
        print(f"Processando [{indice + 1}/{total}]: CPF [{entrada.cpf}] | Nome [{entrada.nome_pessoa}]")

        if pre_resultado is not None:
            print(pre_resultado.detalhes)
            resultados.append(pre_resultado)
            continue

        resultado_linha: ResultadoCadastroPessoa | None = None

        for tentativa in range(2):
            try:
                page, janela_sistema = garantir_tela_pesquisa_pessoa(
                    context=context,
                    page_atual=page,
                    janela_atual=janela_sistema,
                    usuario_rede=usuario_rede,
                    senha=senha,
                    url_aghu=url_aghu,
                )
                resultado_linha = processar_cadastro(janela_sistema, entrada)

                if resultado_linha.status == STATUS_CRIADO:
                    PessoaFlow(janela_sistema).fechar_painel_sucesso_se_visivel()

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
                    page, janela_sistema = navegar_ate_cadastro_pessoa(
                        context=context,
                        page_atual=page,
                        usuario_rede=usuario_rede,
                        senha=senha,
                        url_aghu=url_aghu,
                    )
                    continue

                resultado_linha = ResultadoCadastroPessoa(
                    cpf=entrada.cpf,
                    nome_pessoa=entrada.nome_pessoa,
                    status=STATUS_ERRO,
                    detalhes=f"Falha tecnica definitiva durante o cadastro: {exc}",
                )

        if resultado_linha is None:
            resultado_linha = ResultadoCadastroPessoa(
                cpf=entrada.cpf,
                nome_pessoa=entrada.nome_pessoa,
                status=STATUS_ERRO,
                detalhes="Falha tecnica durante o cadastro.",
            )

        print(f"Resultado: [{resultado_linha.status}] {resultado_linha.detalhes}")
        resultados.append(resultado_linha)

    return resultados


def executar_cadastro_pessoas(
    cadastros: list[CadastroPessoaEntrada],
    usuario_rede: str,
    senha: str,
    *,
    url_aghu: str = AGHU_URL,
    mostrar_browser: bool = True,
    mostrar_console: bool = True,
    diretorio_logs: str | os.PathLike | None = None,
    gerar_csv_log: bool = True,
) -> list[ResultadoCadastroPessoa]:
    if not usuario_rede or not senha:
        raise ValueError("Preencha usuario de rede e senha.")
    if not url_aghu:
        raise ValueError("Informe o ambiente do AGHU.")

    cadastros = [normalizar_entrada(cadastro) for cadastro in cadastros]

    with controle_saida_terminal(mostrar_console):
        return _executar_cadastro_pessoas_com_saida_configurada(
            cadastros=cadastros,
            usuario_rede=usuario_rede,
            senha=senha,
            url_aghu=url_aghu,
            mostrar_browser=mostrar_browser,
            diretorio_logs=diretorio_logs,
            gerar_csv_log=gerar_csv_log,
        )


def _executar_cadastro_pessoas_com_saida_configurada(
    cadastros: list[CadastroPessoaEntrada],
    usuario_rede: str,
    senha: str,
    *,
    url_aghu: str,
    mostrar_browser: bool,
    diretorio_logs: str | os.PathLike | None,
    gerar_csv_log: bool,
) -> list[ResultadoCadastroPessoa]:
    resultados_prevalidacao: list[ResultadoCadastroPessoa | None] = []
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
        resultados = [resultado for resultado in resultados_prevalidacao if resultado is not None]
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
            page, janela_sistema = navegar_ate_cadastro_pessoa(
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
) -> tuple[list[ResultadoCadastroPessoa], Path]:
    cadastros = ler_planilha_cadastros(caminho_planilha)
    resultados = executar_cadastro_pessoas(
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
    cadastro: CadastroPessoaEntrada,
    *,
    url_aghu: str = AGHU_URL,
    mostrar_browser: bool = True,
    mostrar_console: bool = True,
    diretorio_logs: str | os.PathLike | None = None,
) -> ResultadoCadastroPessoa:
    resultados = executar_cadastro_pessoas(
        cadastros=[cadastro],
        usuario_rede=usuario_rede,
        senha=senha,
        url_aghu=url_aghu,
        mostrar_browser=mostrar_browser,
        mostrar_console=mostrar_console,
        diretorio_logs=diretorio_logs,
    )
    return resultados[0]


__all__ = [
    "CadastroPessoaEntrada",
    "ResultadoCadastroPessoa",
    "executar_cadastro_individual",
    "executar_cadastro_lote",
    "executar_cadastro_pessoas",
    "ler_planilha_cadastros",
    "salvar_relatorio_resultados",
]
