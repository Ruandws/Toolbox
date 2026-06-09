import os
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
from playwright.sync_api import BrowserContext, Page

from AddPrinterAGHU import (
    cadastrar_nova_impressora,
    consultar_dados_site_secundario,
    navegar_ate_cadastro_impressora,
)


BASE_DIR = Path(__file__).resolve().parent
AGHU_URL_PRODUCAO = "https://aghu.hub-unb.ebserh/aghu/pages/casca/casca.xhtml"


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

    colunas_obrigatorias = ["IPPC", "HostPrinter", "PrinterClass"]
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
    print(f"🔐 Checando a portaria do AGHUX com o usuário: {usuario_str} ...")
    try:
        campo_senha = page.locator("input[type='password']").first
        campo_senha.wait_for(state="visible", timeout=3000)
        
        print("🔑 Tela de login detectada! Injetando credenciais do técnico...")
        campo_usuario = page.locator("input[id*='usuario' i], input[id*='login' i], input[type='text']").first
        campo_usuario.fill(usuario_str)  
        campo_senha.fill(senha_str)      
        
        botao_entrar = page.locator("button, input[type='submit']").filter(has_text="Entrar").first
        botao_entrar.click()
        
        page.get_by_text("Outros Módulos", exact=True).locator("visible=true").first.wait_for(state="visible", timeout=10000)
        print("🔓 Entramos no prédio com sucesso!")
    except Exception:
        print("➡️ Nenhuma tela de login detectada (sessão já ativa). Seguindo direto pro menu...")

# ==========================================
# ISOLAMENTO DE SESSÃO (CLEAN STATE)
# ==========================================
def trocar_aba_aghux(context: BrowserContext, page_atual: Page, usuario_str: str, senha_str: str) -> Page:
    print("🔄 [Clean State] Destruindo aba antiga e abrindo uma aba nova virgem...")
    try:
        page_atual.close()
    except:
        pass 
        
    nova_page = context.new_page()
    #teste
    #nova_page.goto("http://10.6.0.153:8080/aghu/pages/casca/casca.xhtml")
    #Produção
    nova_page.goto(AGHU_URL_PRODUCAO)
    print(f"🌍 Ambiente acessado: {nova_page.url}")
    fazer_login(nova_page, usuario_str, senha_str)
    return nova_page

def navegar_ate_modulo(context: BrowserContext, page_atual: Page, usuario_str: str, senha_str: str):
    print("🗺️ Navegando até o módulo de Impressora por Computador...")
    page = page_atual
    
    for tentativa in range(2):
        try:
            if not page.get_by_text("Configuração", exact=True).locator("visible=true").first.is_visible():
                page.get_by_text("Outros Módulos", exact=True).locator("visible=true").first.click(timeout=5000)
            if not page.get_by_text("Impressão", exact=True).locator("visible=true").first.is_visible():
                page.get_by_text("Configuração", exact=True).locator("visible=true").first.click(timeout=5000)
            if not page.get_by_text("Cadastros", exact=True).locator("visible=true").first.is_visible():
                page.get_by_text("Impressão", exact=True).locator("visible=true").first.click(timeout=5000)
            if not page.get_by_text("Impressora por Computador", exact=True).locator("visible=true").first.is_visible():
                page.get_by_text("Cadastros", exact=True).locator("visible=true").first.click(timeout=5000)
            
            page.get_by_text("Impressora por Computador", exact=True).locator("visible=true").first.click(timeout=5000)
            
            janela_sistema = page.frame_locator("iframe").last
            janela_sistema.get_by_role("button", name="Pesquisar").first.wait_for(state="visible", timeout=15000)
            
            return page, janela_sistema
            
        except Exception as e:
            if tentativa == 0:
                print("⚠️ Falha ao navegar no menu. Acionando Clean State...")
                page = trocar_aba_aghux(context, page, usuario_str, senha_str)
            else:
                raise e

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
        ip_pc = str(linha['IPPC']).strip()
        impressora_alvo = str(linha['HostPrinter']).strip()
        classe_impressao = str(linha['PrinterClass']).strip()
        
        status_da_linha = "Erro"
        detalhes_da_linha = "Falha Desconhecida."
        impressora_fabricada_agora = False 
        passo_atual = "Iniciando"
        
        print(f"\n========================================")
        print(f"🔍 Investigando [{index + 1}/{len(planilha)}]: Computador [{ip_pc}] | Alvo [{impressora_alvo}]")
        
        for tentativa in range(3):
            try:
                passo_atual = "Buscando Computador"
                campo_computador = janela_sistema.locator("input[id*='computador' i], input.ui-autocomplete-input").locator("visible=true").first
                campo_computador.click()
                campo_computador.clear()
                campo_computador.press_sequentially(ip_pc, delay=150)

                # re.escape protege os pontos do IP. O \b garante que não há números extras depois (evita o .225 quando deveria ser .22).
                padrao_exato = re.compile(fr"\b{re.escape(ip_pc)}\b")

                #caixa_flutuante_pc = janela_sistema.locator("li, td, span").filter(has_text=ip_pc).locator("visible=true").first
                caixa_flutuante_pc = janela_sistema.locator("tr, li, td, span").filter(has_text=padrao_exato).locator("visible=true").first
                try:
                    caixa_flutuante_pc.wait_for(state="visible", timeout=6000)
                    caixa_flutuante_pc.click()
                except:
                    raise ValueError("Computador não encontrado")
                
                passo_atual = "Pesquisando na Tabela"
                janela_sistema.get_by_role("button", name="Pesquisar").click()
                linha_alvo = janela_sistema.get_by_role("row").filter(has_text=ip_pc).filter(has_text=classe_impressao).first
                
                linha_encontrada = False
                try:
                    linha_alvo.wait_for(state="visible", timeout=5000) 
                    linha_encontrada = True
                except:
                    linha_encontrada = False
                
                if linha_encontrada:
                    texto_da_linha = linha_alvo.inner_text()
                    if impressora_alvo in texto_da_linha:
                        print(f"✅ SUCESSO! A impressora já estava correta.")
                        status_da_linha = "Mantido"
                        detalhes_da_linha = "Impressora já estava correta no sistema."
                        janela_sistema.locator("button:has(.aghu-icon-cleaner-aghu)").first.click()
                        break
                    else:
                        passo_atual = "Editando Impressora Existente"
                        print(f"⚠️ DIVERGÊNCIA! Atualizando a impressora...")
                        botao_lapis = linha_alvo.locator("[title*='editar' i], [title*='alterar' i], .aghu-icon-edit").first
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
                        except:
                            raise ValueError("Impressora não existe") 
                        
                        janela_sistema.get_by_role("button", name="Gravar").click()
                        janela_sistema.get_by_role("button", name="Pesquisar").wait_for(state="visible")
                        print("🔄 Salvamento concluído!")
                        
                        status_da_linha = "Criado" if impressora_fabricada_agora else "Alterado"
                        detalhes_da_linha = "Impressora cadastrada no CUPS e atualizada." if impressora_fabricada_agora else "Vínculo atualizado com sucesso."
                        
                        janela_sistema.locator("button:has(.aghu-icon-cleaner-aghu)").first.click()
                        break
                else:
                    passo_atual = "Cadastrando Nova Impressora (Vinculando)"
                    print("🆕 Nenhum registro encontrado! Iniciando NOVO vínculo...")
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
                        caixa_flutuante_pc_novo.click()
                    except:
                        raise ValueError("Computador não encontrado")
                    
                    campo_impressora_novo = janela_sistema.locator("input[id*='impressora' i]").locator("visible=true").first
                    campo_impressora_novo.click()
                    campo_impressora_novo.clear()
                    campo_impressora_novo.press_sequentially(impressora_alvo, delay=150)
                    caixa_flutuante_imp_novo = janela_sistema.locator("li, td, span").filter(has_text=impressora_alvo).locator("visible=true").first
                    try:
                        caixa_flutuante_imp_novo.wait_for(state="visible", timeout=6000)
                        caixa_flutuante_imp_novo.click()
                    except:
                        raise ValueError("Impressora não existe") 
                    
                    campo_classe = janela_sistema.locator("input[id*='classe' i], input[id*='impressao' i]").locator("visible=true").last
                    classe_atual = str(campo_classe.input_value())
                    if classe_impressao.upper() not in classe_atual.upper():
                        try:
                            janela_sistema.locator("button:has(.aghu-icon-cleaner-aghu)").locator("visible=true").last.click(timeout=2000)
                        except:
                            campo_classe.clear() 
                        botao_lupa = janela_sistema.locator("button:has(.ui-icon-triangle-1-s)").locator("visible=true").last
                        botao_lupa.click()
                        caixa_flutuante_classe = janela_sistema.locator("li, td, span").filter(has_text=classe_impressao).locator("visible=true").first
                        caixa_flutuante_classe.wait_for(state="visible", timeout=5000)
                        caixa_flutuante_classe.click()

                    janela_sistema.get_by_role("button", name="Gravar").click()
                    janela_sistema.get_by_role("button", name="Pesquisar").wait_for(state="visible")
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
                        except:
                            pass 
                        try:
                            janela_sistema.locator("button:has(.aghu-icon-cleaner-aghu)").first.click(timeout=1500)
                        except:
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
                        except:
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