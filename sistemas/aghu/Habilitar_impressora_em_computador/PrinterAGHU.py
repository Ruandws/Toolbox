import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pandas as pd
from playwright.sync_api import BrowserContext, Page

#Imports de classes utilitárias públicas.
from autenticador import AGHU_URL, autenticar_aghu_page, exigir_login_valido
from menu import navegar_menu_aghu



from AddPrinterAGHU import (
    cadastrar_nova_impressora,
    consultar_dados_site_secundario,
    navegar_ate_cadastro_impressora,
)


BASE_DIR = Path(__file__).resolve().parent

# ==========================================
# CAMINHOS DO PROCEDIMENTO
# ==========================================

CAMINHO_MENU_IMPRESSORA_POR_COMPUTADOR = (
    "Outros Módulos",
    "Configuração",
    "Impressão",
    "Cadastros",
    "Impressora por Computador",
)
COLUNAS_OBRIGATORIAS_PLANILHA = ["IPPC", "HostPrinter", "PrinterClass"]
CARACTERES_DE_VALOR = r"A-Za-z0-9_.-"
TABELA_COMPUTADOR_IMPRESSORA_SELECTOR = (
    '[id="tabelaComputadorImpressora:resultList_data"]'
)
MENSAGEM_ERRO_PESQUISA_INDEFINIDA = (
    "Conferir manualmente: pesquisa nao retornou nem linhas nem mensagem de "
    "nenhum registro encontrado."
)


def _normalizar_busca(valor: object) -> str:
    return re.sub(r"\s+", " ", str(valor or "").strip()).casefold()


def _normalizar_texto_simples(valor: object) -> str:
    return _normalizar_busca(valor)


def _criar_regex_valor_exato(valor: object, flags: int = re.IGNORECASE) -> re.Pattern:
    valor_normalizado = _normalizar_busca(valor)
    return re.compile(
        rf"(?<![{CARACTERES_DE_VALOR}])"
        rf"{re.escape(valor_normalizado)}"
        rf"(?![{CARACTERES_DE_VALOR}])",
        flags,
    )


def _contem_valor_exato(texto: object, valor: object) -> bool:
    valor_normalizado = _normalizar_busca(valor)

    if not valor_normalizado:
        return False

    texto_normalizado = _normalizar_busca(texto)
    padrao = _criar_regex_valor_exato(valor_normalizado, flags=0)

    return bool(padrao.search(texto_normalizado))


def _valor_exato(valor_atual: object, valor_esperado: object) -> bool:
    return _normalizar_busca(valor_atual) == _normalizar_busca(valor_esperado)


def _regex_ip_celula(ip_pc: str) -> re.Pattern:
    return re.compile(rf"^\s*{re.escape(str(ip_pc).strip())}\s*$")


def _ip_celula_confere(valor_celula: object, ip_pc: str) -> bool:
    return bool(_regex_ip_celula(ip_pc).match(str(valor_celula or "")))


def _classe_impressao_aghu(tipo_cups: str) -> str:
    if _valor_exato(tipo_cups, "PDF"):
        return "A"

    return str(tipo_cups or "").strip()


def _tbody_resultados(janela_sistema):
    return janela_sistema.locator(TABELA_COMPUTADOR_IMPRESSORA_SELECTOR)


def _linhas_resultado(tbody):
    return tbody.locator("> tr[data-ri]")


def _linha_vazia_resultado(tbody):
    return tbody.locator(
        "> tr.ui-datatable-empty-message",
        has_text="Nenhum registro encontrado!",
    )


def _texto_celula(linha_tabela, indice: int) -> str:
    try:
        celulas = linha_tabela.locator("td")
        if indice >= celulas.count():
            return ""

        return celulas.nth(indice).inner_text(timeout=1000).strip()
    except Exception:
        return ""


def _aguardar_estado_resultado_pesquisa(
    janela_sistema,
    timeout_ms: int = 7000,
) -> tuple[str, object]:
    tbody = _tbody_resultados(janela_sistema)
    linhas = _linhas_resultado(tbody)
    linha_vazia = _linha_vazia_resultado(tbody)
    fim = time.monotonic() + (timeout_ms / 1000)

    while time.monotonic() < fim:
        try:
            if linhas.count() > 0 and linhas.first.is_visible(timeout=250):
                return "linhas", linhas
        except Exception:
            pass

        try:
            if linha_vazia.is_visible(timeout=250):
                return "vazio", linhas
        except Exception:
            pass

        time.sleep(0.15)

    return "indefinido", linhas


def _registro_confere_tipo_e_classe(registro: dict, tipo_cups_esperado: str) -> bool:
    if not _valor_exato(registro.get("tipo_cups", ""), tipo_cups_esperado):
        return False

    classe_esperada = _classe_impressao_aghu(tipo_cups_esperado)

    if not classe_esperada:
        return True

    return _valor_exato(registro.get("classe", ""), classe_esperada)


def _registro_eh_pdf(registro: dict) -> bool:
    return _registro_confere_tipo_e_classe(registro, "PDF")


def _decidir_acao_linhas(
    registros_linhas: list[dict],
    impressora_alvo: str,
    classe_impressao: str,
) -> tuple[str, dict | None]:
    linha_pdf = None

    for registro in registros_linhas:
        if _valor_exato(registro.get("fila", ""), impressora_alvo):
            if _registro_confere_tipo_e_classe(registro, classe_impressao):
                return "mantido", registro

            return "conferir", registro

        if _registro_eh_pdf(registro):
            linha_pdf = registro

    if linha_pdf is not None:
        return "alterar", linha_pdf

    return "incluir", None


def _coletar_linhas_computador(janela_sistema, ip_pc: str) -> tuple[str, list[dict]]:
    estado_pesquisa, linhas_tabela = _aguardar_estado_resultado_pesquisa(janela_sistema)
    registros_linhas = []

    if estado_pesquisa != "linhas":
        return estado_pesquisa, registros_linhas

    for indice in range(linhas_tabela.count()):
        linha_tabela = linhas_tabela.nth(indice)

        try:
            if not linha_tabela.is_visible(timeout=1000):
                continue

            texto_linha = linha_tabela.inner_text(timeout=1000)
        except Exception:
            continue

        ip_linha = _texto_celula(linha_tabela, 1)

        if not _ip_celula_confere(ip_linha, ip_pc):
            continue

        registros_linhas.append(
            {
                "linha": linha_tabela,
                "texto": texto_linha,
                "ip": ip_linha,
                "computador": _texto_celula(linha_tabela, 2),
                "descricao": _texto_celula(linha_tabela, 3),
                "classe": _texto_celula(linha_tabela, 4),
                "fila": _texto_celula(linha_tabela, 5),
                "tipo_cups": _texto_celula(linha_tabela, 6),
            }
        )

    return estado_pesquisa, registros_linhas


def _extrair_ips(texto: object) -> list[str]:
    return re.findall(
        r"(?<!\S)(\d{1,3}(?:\.\d{1,3}){3})(?!\S)",
        str(texto or ""),
    )


def _validar_computador_selecionado(
    campo_computador,
    ip_pc: str,
    texto_item_selecionado: str,
) -> tuple[bool, str]:
    try:
        valor_campo = campo_computador.input_value(timeout=1000).strip()
    except Exception:
        valor_campo = ""

    textos = [texto for texto in (valor_campo, texto_item_selecionado) if texto]
    ips_encontrados = []

    for texto in textos:
        ips_encontrados.extend(_extrair_ips(texto))

    if ips_encontrados:
        ips_divergentes = [ip for ip in ips_encontrados if ip != ip_pc]
        if not ips_divergentes and ip_pc in ips_encontrados:
            return True, ""

        return False, ips_divergentes[0] if ips_divergentes else ips_encontrados[0]

    if _ip_celula_confere(valor_campo, ip_pc):
        return True, ""

    return False, valor_campo or texto_item_selecionado or "nao identificado"


def _mensagem_dialog(janela_sistema, seletor: str):
    return janela_sistema.locator(
        f'#msgDialog[aria-hidden="false"] #messagesInDialog {seletor}'
    )


def _aguardar_resultado_gravacao(
    janela_sistema,
    page: Page | None = None,
    timeout_ms: int = 10000,
) -> tuple[str, str]:
    containers = [janela_sistema]

    if page is not None:
        containers.append(page)

    mensagens_sucesso = [
        _mensagem_dialog(container, "span.ui-messages-info-summary")
        for container in containers
    ]
    mensagens_erro = [
        _mensagem_dialog(container, "span.ui-messages-error-summary")
        for container in containers
    ]
    fim = time.monotonic() + (timeout_ms / 1000)

    while time.monotonic() < fim:
        for mensagem_erro in mensagens_erro:
            try:
                if mensagem_erro.count() > 0 and mensagem_erro.first.is_visible(timeout=250):
                    return "erro", mensagem_erro.first.inner_text(timeout=1000).strip()
            except Exception:
                pass

        for mensagem_sucesso in mensagens_sucesso:
            try:
                if mensagem_sucesso.count() > 0 and mensagem_sucesso.first.is_visible(timeout=250):
                    return "sucesso", mensagem_sucesso.first.inner_text(timeout=1000).strip()
            except Exception:
                pass

        time.sleep(0.15)

    return "indefinido", ""


def _erro_classe_pdf_duplicada(mensagem: str) -> bool:
    mensagem_normalizada = _normalizar_texto_simples(mensagem)
    return (
        "existe uma impressora cadastrada" in mensagem_normalizada
        and "classe a" in mensagem_normalizada
    )


def _aguardar_botao_pesquisar_se_possivel(janela_sistema) -> None:
    try:
        janela_sistema.get_by_role("button", name="Pesquisar").wait_for(
            state="visible",
            timeout=3000,
        )
    except Exception:
        pass


def _limpar_estado_formulario(janela_sistema, page: Page | None = None) -> None:
    containers = [janela_sistema]

    if page is not None:
        containers.append(page)

    for container in containers:
        try:
            container.locator(
                '#msgDialog[aria-hidden="false"] a.ui-dialog-titlebar-close, '
                '#msgDialog[aria-hidden="false"] .ui-dialog-titlebar-close'
            ).first.click(timeout=1000)
            break
        except Exception:
            pass

    try:
        janela_sistema.get_by_role("button", name="Cancelar").click(timeout=1000)
    except Exception:
        pass

    try:
        janela_sistema.locator("button:has(.aghu-icon-cleaner-aghu)").first.click(timeout=1500)
    except Exception:
        pass

def _valor_planilha_em_branco(valor: object) -> bool:
    try:
        if pd.isna(valor):
            return True
    except (TypeError, ValueError):
        pass

    return str(valor).strip() == ""


def _campos_obrigatorios_planilha_em_branco(linha: pd.Series) -> list[str]:
    return [
        coluna
        for coluna in COLUNAS_OBRIGATORIAS_PLANILHA
        if _valor_planilha_em_branco(linha.get(coluna, ""))
    ]     

def ler_planilha(caminho_arquivo: str) -> pd.DataFrame:
    caminho = Path(caminho_arquivo)

    if not caminho.exists():
        raise FileNotFoundError(f"Planilha não encontrada: {caminho}")

    extensao = caminho.suffix.lower()

    if extensao in {".xlsx", ".xlsm"}:
        df = pd.read_excel(caminho, dtype=str, engine="openpyxl")
    elif extensao == ".csv":
        try:
            df = pd.read_csv(caminho, sep=";", dtype=str, encoding="utf-8-sig")
        except UnicodeDecodeError:
            df = pd.read_csv(caminho, sep=";", dtype=str, encoding="latin1")
    else:
        raise ValueError("Formato inválido. Use .xlsx, .xlsm ou .csv.")

    df.columns = df.columns.str.strip()
    df = df.fillna("")

    colunas_obrigatorias = COLUNAS_OBRIGATORIAS_PLANILHA
    colunas_faltantes = [
        coluna for coluna in colunas_obrigatorias if coluna not in df.columns
    ]

    if colunas_faltantes:
        raise ValueError(
            "Planilha inválida. Colunas obrigatórias ausentes: "
            + ", ".join(colunas_faltantes)
        )

    return df


def fazer_login(page: Page, usuario_str: str, senha_str: str):
    print(f"Checando autenticação no AGHUX com o usuário: {usuario_str}")

    resultado = autenticar_aghu_page(
        page=page,
        usuario=usuario_str,
        senha=senha_str,
        timeout_ms=15000,
    )

    if resultado.status == "sessao_ativa":
        print("Sessão já estava ativa.")
    elif resultado.status == "sucesso":
        print("Login efetuado com sucesso.")
    else:
        print(f"Falha de autenticação: {resultado.mensagem}")

    exigir_login_valido(resultado)
    return resultado

# ==========================================
# ISOLAMENTO DE SESSÃO (CLEAN STATE)
# ==========================================
def trocar_aba_aghux(context: BrowserContext, page_atual: Page, usuario_str: str, senha_str: str) -> Page:
    print("[Clean State] Fechando aba atual e abrindo nova aba limpa.")

    try:
        page_atual.close()
    except Exception:
        pass

    nova_page = context.new_page()
    nova_page.goto(AGHU_URL)
    print(f"Ambiente acessado: {nova_page.url}")

    resultado = autenticar_aghu_page(
        page=nova_page,
        usuario=usuario_str,
        senha=senha_str,
        timeout_ms=15000,
    )

    if resultado.status == "sessao_ativa":
        print("Sessão reaproveitada na nova aba.")
    elif resultado.status == "sucesso":
        print("Login efetuado na nova aba.")
    else:
        print(f"Falha ao autenticar nova aba: {resultado.mensagem}")

    exigir_login_valido(resultado)
    return nova_page


def navegar_ate_modulo(
    context: BrowserContext,
    page_atual: Page,
    usuario_str: str,
    senha_str: str,
):
    print("🗺️ Navegando até o módulo de Impressora por Computador...")
    page = page_atual

    for tentativa in range(2):
        try:
            janela_sistema = navegar_menu_aghu(
                page=page,
                caminho=CAMINHO_MENU_IMPRESSORA_POR_COMPUTADOR,
            )
            janela_sistema.get_by_role("button", name="Pesquisar").first.wait_for(
                state="visible",
                timeout=15000,
            )

            return page, janela_sistema

        except Exception as erro:
            if tentativa == 0:
                print("⚠️ Falha ao navegar no menu. Acionando Clean State...")
                page = trocar_aba_aghux(context, page, usuario_str, senha_str)
            else:
                raise erro

    raise RuntimeError("Falha ao navegar até o módulo de Impressora por Computador.")

# ==========================================
# CAPÍTULO 3: O CÉREBRO MAESTRO
# ==========================================
def processar_computadores(
    context: BrowserContext,
    page_inicial: Page,
    janela_sistema_inicial,
    planilha: pd.DataFrame,
    usuario_str: str,
    senha_str: str,
    diretorio_logs: str | os.PathLike | None = None,
) -> str:
    logs_do_diario = [] 
    
    page = page_inicial
    janela_sistema = janela_sistema_inicial
    
    for index, linha in planilha.iterrows():
        ip_pc = str(linha["IPPC"]).strip()
        impressora_alvo = str(linha["HostPrinter"]).strip()
        classe_impressao = str(linha["PrinterClass"]).strip()

        campos_em_branco = _campos_obrigatorios_planilha_em_branco(linha)

        if campos_em_branco:
            status_da_linha = "Erro"
            detalhes_da_linha = (
                "Linha ignorada: campos obrigatorios em branco: "
                f"{', '.join(campos_em_branco)}."
            )

            print("\n========================================")
            print(
                f"⏭️ Ignorando linha [{int(str(index)) + 1}/{len(planilha)}]: "
                f"{detalhes_da_linha}"
            )  # type: ignore

            logs_do_diario.append({
                "HostPC": linha.get("HostPC", ""),
                "IPPC": ip_pc,
                "HostPrinter": impressora_alvo,
                "IPPrinter": linha.get("IPPrinter", ""),
                "PrinterClass": classe_impressao,
                "Status": status_da_linha,
                "Detalhes": detalhes_da_linha,
            })

            continue
        
        status_da_linha = "Erro"
        detalhes_da_linha = "Falha Desconhecida."
        impressora_fabricada_agora = False 
        passo_atual = "Iniciando"
        
        print("\n========================================")
        print(f"🔍 Investigando [{int(str(index)) + 1}/{len(planilha)}]: Computador [{ip_pc}] | Alvo [{impressora_alvo}]")  # type: ignore
        
        for tentativa in range(3):
            try:
                passo_atual = "Buscando Computador"
                campo_computador = janela_sistema.locator("input[id*='computador' i], input.ui-autocomplete-input").locator("visible=true").first
                campo_computador.click()
                campo_computador.clear()
                campo_computador.press_sequentially(ip_pc, delay=150)

                # Usa limites de valor para evitar falso positivo em IPs ou nomes com sufixo.
                padrao_exato = _criar_regex_valor_exato(ip_pc)

                #caixa_flutuante_pc = janela_sistema.locator("li, td, span").filter(has_text=ip_pc).locator("visible=true").first
                caixa_flutuante_pc = janela_sistema.locator("tr, li, td, span").filter(has_text=padrao_exato).locator("visible=true").first
                try:
                    caixa_flutuante_pc.wait_for(state="visible", timeout=6000)
                    caixa_flutuante_pc.click()
                except Exception:
                    raise ValueError("Computador não encontrado")
                
                passo_atual = "Pesquisando na Tabela"
                janela_sistema.get_by_role("button", name="Pesquisar").click()
                estado_pesquisa, registros_linhas = _coletar_linhas_computador(
                    janela_sistema=janela_sistema,
                    ip_pc=ip_pc,
                )

                if estado_pesquisa == "indefinido":
                    print("Pesquisa sem estado final claro. Conferir manualmente.")
                    status_da_linha = "Erro"
                    detalhes_da_linha = MENSAGEM_ERRO_PESQUISA_INDEFINIDA
                    _limpar_estado_formulario(janela_sistema, page)
                    break

                if estado_pesquisa == "linhas" and not registros_linhas:
                    print("Pesquisa retornou linhas, mas nenhuma com o IP esperado.")
                    status_da_linha = "Erro"
                    detalhes_da_linha = (
                        "Conferir manualmente: pesquisa retornou linhas, mas nenhuma "
                        f"com o IP esperado [{ip_pc}]."
                    )
                    _limpar_estado_formulario(janela_sistema, page)
                    break

                decisao_linha, registro_linha = _decidir_acao_linhas(
                    registros_linhas=registros_linhas,
                    impressora_alvo=impressora_alvo,
                    classe_impressao=classe_impressao,
                )

                if decisao_linha == "conferir":
                    tipo_cups_atual = (
                        str(registro_linha.get("tipo_cups") or "nao identificado")
                        if registro_linha
                        else "nao identificado"
                    )
                    print("Tipo do Cups divergente. Conferir manualmente.")
                    status_da_linha = "Erro"
                    detalhes_da_linha = (
                        "Conferir manualmente: impressora ja vinculada ao computador "
                        f"com Tipo do Cups [{tipo_cups_atual}], diferente da planilha "
                        f"[{classe_impressao}]."
                    )
                    janela_sistema.locator("button:has(.aghu-icon-cleaner-aghu)").first.click()
                    break

                linha_encontrada = decisao_linha in {"mantido", "alterar"}
                linha_alvo = registro_linha["linha"] if linha_encontrada and registro_linha else None

                if linha_encontrada and linha_alvo is None:
                    raise RuntimeError("Linha da tabela para decisao nao localizada.")
                
                if linha_encontrada:
                    if decisao_linha == "mantido":
                        print("✅ SUCESSO! A impressora já estava correta.")
                        status_da_linha = "Mantido"
                        detalhes_da_linha = "Impressora já estava correta no sistema."
                        janela_sistema.locator("button:has(.aghu-icon-cleaner-aghu)").first.click()
                        break
                    else:
                        passo_atual = "Editando Impressora Existente"
                        print("⚠️ DIVERGÊNCIA! Atualizando a impressora...")
                        botao_lapis = linha_alvo.locator(
                            'td.first-column.auto-adjust a[title="editar"], '
                            '[title*="editar" i], [title*="alterar" i], .aghu-icon-edit'
                        ).first
                        botao_lapis.click()
                        janela_sistema.get_by_role("button", name="Gravar").wait_for(state="visible")
                        
                        janela_sistema.locator("button:has(.aghu-icon-cleaner-aghu)").click()
                        campo_impressora = janela_sistema.locator("input[id*='impressora' i]").locator("visible=true").first
                        campo_impressora.click()
                        campo_impressora.clear()
                        campo_impressora.press_sequentially(impressora_alvo, delay=150)
                        
                        caixa_flutuante_imp = janela_sistema.locator("li, td, span").filter(has_text=impressora_alvo).locator("visible=true").first
                        try:
                            caixa_flutuante_imp.wait_for(state="visible", timeout=6000)
                            caixa_flutuante_imp.click()
                        except Exception:
                            raise ValueError("Impressora não existe") 
                        
                        janela_sistema.get_by_role("button", name="Gravar").click()
                        resultado_gravacao, mensagem_gravacao = _aguardar_resultado_gravacao(
                            janela_sistema,
                            page,
                        )

                        if resultado_gravacao == "erro":
                            print(f"Erro retornado pelo AGHU: {mensagem_gravacao}")
                            status_da_linha = "Erro"
                            detalhes_da_linha = (
                                "Conferir manualmente: AGHU retornou erro ao alterar: "
                                f"{mensagem_gravacao}"
                            )
                            _limpar_estado_formulario(janela_sistema, page)
                            break

                        if resultado_gravacao == "indefinido":
                            print("Gravacao sem sucesso ou erro conhecido. Conferir manualmente.")
                            status_da_linha = "Erro"
                            detalhes_da_linha = (
                                "Conferir manualmente: gravacao nao retornou sucesso "
                                "nem erro conhecido."
                            )
                            _limpar_estado_formulario(janela_sistema, page)
                            break

                        _aguardar_botao_pesquisar_se_possivel(janela_sistema)
                        print("🔄 Salvamento concluído!")
                        
                        status_da_linha = "Criado" if impressora_fabricada_agora else "Alterado"
                        detalhes_da_linha = "Impressora cadastrada no CUPS e atualizada." if impressora_fabricada_agora else "Vínculo atualizado com sucesso."
                        
                        janela_sistema.locator("button:has(.aghu-icon-cleaner-aghu)").first.click()
                        break
                else:
                    passo_atual = "Cadastrando Nova Impressora (Vinculando)"
                    if registros_linhas:
                        print("Vinculos existentes nao sao PDF. Iniciando NOVO vinculo...")
                    else:
                        print("Nenhum registro encontrado. Iniciando NOVO vinculo...")
                    janela_sistema.get_by_role("button", name="Novo").click()
                    janela_sistema.get_by_role("button", name="Gravar").wait_for(state="visible")
                    
                    campo_computador_novo = janela_sistema.locator("input[id*='computador' i], input.ui-autocomplete-input").locator("visible=true").first
                    campo_computador_novo.click()
                    campo_computador_novo.clear()
                    campo_computador_novo.press_sequentially(ip_pc, delay=150)

                    caixa_flutuante_pc_novo = janela_sistema.locator("tr, li, td, span").filter(has_text=padrao_exato).locator("visible=true").first
                    #caixa_flutuante_pc_novo = janela_sistema.locator("li, td, span").filter(has_text=ip_pc).locator("visible=true").first
                    try:
                        caixa_flutuante_pc_novo.wait_for(state="visible", timeout=6000)
                        texto_computador_selecionado = caixa_flutuante_pc_novo.inner_text(timeout=1000)
                        caixa_flutuante_pc_novo.click()
                    except Exception:
                        raise ValueError("Computador não encontrado")
                    
                    computador_confere, computador_selecionado = _validar_computador_selecionado(
                        campo_computador_novo,
                        ip_pc,
                        texto_computador_selecionado,
                    )
                    if not computador_confere:
                        raise ValueError(
                            "Conferir manualmente: computador selecionado diverge "
                            f"do IP esperado. Esperado: {ip_pc}; selecionado: "
                            f"{computador_selecionado}."
                        )

                    campo_impressora_novo = janela_sistema.locator("input[id*='impressora' i]").locator("visible=true").first
                    campo_impressora_novo.click()
                    campo_impressora_novo.clear()
                    campo_impressora_novo.press_sequentially(impressora_alvo, delay=150)
                    caixa_flutuante_imp_novo = janela_sistema.locator("li, td, span").filter(has_text=impressora_alvo).locator("visible=true").first
                    try:
                        caixa_flutuante_imp_novo.wait_for(state="visible", timeout=6000)
                        caixa_flutuante_imp_novo.click()
                    except Exception:
                        raise ValueError("Impressora não existe") 
                    
                    campo_classe = janela_sistema.locator("input[id*='classe' i], input[id*='impressao' i]").locator("visible=true").last
                    classe_atual = str(campo_classe.input_value())
                    classe_aghu = _classe_impressao_aghu(classe_impressao)
                    if classe_aghu.upper() not in classe_atual.upper():
                        try:
                            janela_sistema.locator("button:has(.aghu-icon-cleaner-aghu)").locator("visible=true").last.click(timeout=2000)
                        except Exception:
                            campo_classe.clear() 
                        botao_lupa = janela_sistema.locator("button:has(.ui-icon-triangle-1-s)").locator("visible=true").last
                        botao_lupa.click()
                        caixa_flutuante_classe = janela_sistema.locator("li, td, span").filter(has_text=classe_aghu).locator("visible=true").first
                        caixa_flutuante_classe.wait_for(state="visible", timeout=5000)
                        caixa_flutuante_classe.click()

                    janela_sistema.get_by_role("button", name="Gravar").click()
                    resultado_gravacao, mensagem_gravacao = _aguardar_resultado_gravacao(
                        janela_sistema,
                        page,
                    )

                    if resultado_gravacao == "erro":
                        print(f"Erro retornado pelo AGHU: {mensagem_gravacao}")
                        status_da_linha = "Erro"
                        if _erro_classe_pdf_duplicada(mensagem_gravacao):
                            detalhes_da_linha = (
                                "Conferir manualmente: AGHU bloqueou inclusao porque "
                                "ja existe impressora na classe A/PDF para o computador."
                            )
                        else:
                            detalhes_da_linha = (
                                "Conferir manualmente: AGHU retornou erro ao incluir: "
                                f"{mensagem_gravacao}"
                            )
                        _limpar_estado_formulario(janela_sistema, page)
                        break

                    if resultado_gravacao == "indefinido":
                        print("Gravacao sem sucesso ou erro conhecido. Conferir manualmente.")
                        status_da_linha = "Erro"
                        detalhes_da_linha = (
                            "Conferir manualmente: gravacao nao retornou sucesso "
                            "nem erro conhecido."
                        )
                        _limpar_estado_formulario(janela_sistema, page)
                        break

                    _aguardar_botao_pesquisar_se_possivel(janela_sistema)
                    print("🔄 Cadastro finalizado com sucesso!")
                    
                    status_da_linha = "Criado" if impressora_fabricada_agora else "Vinculado"
                    detalhes_da_linha = "Impressora nova identificada no CUPS, criada e vinculada no AGHU." if impressora_fabricada_agora else "Vínculo criado com sucesso."
                    
                    janela_sistema.locator("button:has(.aghu-icon-cleaner-aghu)").first.click()
                    break

            except Exception as erro:
                if isinstance(erro, ValueError):
                    mensagem_erro = str(erro)
                    
                    if mensagem_erro == "Impressora não existe":
                        print("🚨 ALERTA: A impressora não está no AGHUX! Chamando o Robô Estoquista...")
                        sucesso_estoquista = False
                        erro_estoquista = ""
                        
                        for tentativa_estoque in range(3):
                            try:
                                print(f"👷 [Estoquista - Tentativa {tentativa_estoque + 1}/3] Isolando ambiente...")
                                page = trocar_aba_aghux(context, page, usuario_str, senha_str)
                                
                                dados_cups = consultar_dados_site_secundario(context, impressora_alvo, classe_impressao)
                                janela_cadastro_imp = navegar_ate_cadastro_impressora(page)
                                cadastrar_nova_impressora(janela_cadastro_imp, dados_cups)
                                
                                sucesso_estoquista = True
                                break 
                                
                            except Exception as e_cups:
                                erro_estoquista = str(e_cups)
                                print(f"⚠️ O Estoquista tropeçou: {erro_estoquista}")
                        
                        if sucesso_estoquista:
                            print("🔙 O Estoquista terminou! Maestro criando nova aba limpa para retomar o vínculo...")
                            page = trocar_aba_aghux(context, page, usuario_str, senha_str)
                            page, janela_sistema = navegar_ate_modulo(context, page, usuario_str, senha_str)
                            impressora_fabricada_agora = True
                            print("🔄 Estoque abastecido! Gastando uma Vida do Vinculador para tentar de novo...")
                            continue 
                        else:
                            if "Não existe no CUPS" in erro_estoquista:
                                status_da_linha = "Inexistente"
                                detalhes_da_linha = "Fila de impressão não encontrada no Servidor CUPS."
                            else:
                                status_da_linha = "Erro"
                                detalhes_da_linha = f"Falha no Almoxarifado após 3 tentativas: {erro_estoquista}"
                            print(f"❌ O Estoquista falhou definitivamente: {status_da_linha} - {detalhes_da_linha}")
                            break 
                    
                    else:
                        if "Computador não encontrado" in mensagem_erro:
                            status_da_linha = "Inexistente"
                            detalhes_da_linha = "Computador não cadastrado no AGHUX."
                        else:
                            status_da_linha = "Erro"
                            detalhes_da_linha = mensagem_erro
                            
                        print(f"❌ Identificado erro sem salvação imediata: {status_da_linha}")
                        try:
                            janela_sistema.get_by_role("button", name="Cancelar").click(timeout=1000)
                        except Exception:
                            pass 
                        try:
                            janela_sistema.locator("button:has(.aghu-icon-cleaner-aghu)").first.click(timeout=1500)
                        except Exception:
                            pass
                        break 
                
                else:
                    print(f"❌ O navegador congelou ou não achou o elemento no passo: '{passo_atual}'")
                    if tentativa < 2:
                        print(f"⚡ Pegando o Desfibrilador! Iniciando tentativa {tentativa + 2}/3 em nova aba...")
                        try:
                            page = trocar_aba_aghux(context, page, usuario_str, senha_str)
                            page, janela_sistema = navegar_ate_modulo(context, page, usuario_str, senha_str)
                            print("🔄 Sistema ressuscitado em nova aba limpa. Retomando a missão!")
                        except Exception as e_recup:
                            print(f"⚠️ A ressuscitação falhou: {e_recup}")
                    else:
                        status_da_linha = "Erro"
                        detalhes_da_linha = f"Falha de sistema ou rede no passo '{passo_atual}' após 3 tentativas."
                        print("🚨 As 3 vidas acabaram. O sistema está instável.")
                        try:
                            page = trocar_aba_aghux(context, page, usuario_str, senha_str)
                            page, janela_sistema = navegar_ate_modulo(context, page, usuario_str, senha_str)
                        except Exception:
                            pass
                        break

        print(f"📝 Anotando no diário: [{status_da_linha}] {detalhes_da_linha}")
        logs_do_diario.append({
            "HostPC": linha.get('HostPC', ''),
            "IPPC": ip_pc,
            "HostPrinter": impressora_alvo,
            "IPPrinter": linha.get('IPPrinter', ''),
            "PrinterClass": classe_impressao,
            "Status": status_da_linha,
            "Detalhes": detalhes_da_linha
        })
            
    print("\n🏁 Fim da leitura! Construindo a estante de arquivos...")
    df_logs = pd.DataFrame(logs_do_diario)
    pasta_logs = Path(diretorio_logs) if diretorio_logs else BASE_DIR / "logs"
    pasta_logs.mkdir(parents=True, exist_ok=True)
    data_hora_atual = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_arquivo_log = pasta_logs / f"log_resultado_{data_hora_atual}.csv"
    
    # -------------------------------------------------------------
    # NOVA LÓGICA DE AUDITORIA (Cabeçalho manual + Append de Dados)
    # -------------------------------------------------------------
    # 1. Escreve a linha do operador abrindo o arquivo do zero ('w')
    with nome_arquivo_log.open('w', encoding='utf-8-sig') as f:
        f.write(f"Atualizado por: {usuario_str}\n")
        
    # 2. Cola o Dataframe embaixo, no modo 'a' (Append/Adicionar)
    df_logs.to_csv(nome_arquivo_log, index=False, sep=";", encoding="utf-8-sig", mode='a')
    
    print(f"📊 Relatório gerado com sucesso: {nome_arquivo_log}")
    return str(nome_arquivo_log)

