import re
from playwright.sync_api import sync_playwright, Page, BrowserContext

# ==========================================
# ROBÔ ESPECIALISTA: ALMOXARIFADO (CADASTRAR IMPRESSORA)
# ==========================================

def fazer_login(page_aghu: Page, usuario_str: str, senha_str: str):
    """Ensina o robô especialista a entrar no prédio principal do AGHUX."""
    print("🔐 Checando o acesso (tela de login do AGHUX)...")
    try:
        campo_usuario = page_aghu.locator("input[type='text'], input[id*='usuario'], input[id*='login']").first
        campo_usuario.wait_for(state="visible", timeout=3000)
        
        print("🔑 Tela de login detectada! Digitando credenciais...")
        campo_usuario.fill(usuario_str)  
        campo_senha = page_aghu.locator("input[type='password']").first
        campo_senha.fill(senha_str)      
        
        botao_entrar = page_aghu.locator("button, input[type='submit']").filter(has_text="Entrar").first
        botao_entrar.click()
        
        print("⏳ Aguardando a verificação de acesso...")
        page_aghu.get_by_text("Outros Módulos", exact=True).locator("visible=true").first.wait_for(state="visible", timeout=10000)
        print("🔓 Entramos no sistema com sucesso!")
    except Exception:
        print("➡️ Nenhuma tela de login detectada (ou a sessão já estava ativa). Seguindo...")

# ==========================================
# CAPÍTULO: SITE SECUNDÁRIO (CUPS)
# ==========================================

def consultar_dados_site_secundario(context: BrowserContext, impressora_alvo: str, classe_impressora: str) -> dict:
    """Abre o CUPS, extrai os dados, transforma (ETL) e retorna para o AGHUX."""
    print(f"\n🌐 Abrindo nova aba para consultar '{impressora_alvo}' no CUPS...")
    
    page_cups = context.new_page()
    page_cups.goto("https://10.6.0.121:631/printers/")
    
    print("⏳ Realizando pesquisa no servidor CUPS...")
    
    # Usando o atributo 'name' direto do HTML, imune a mudanças de idioma
    campo_busca = page_cups.locator("input[name='QUERY']").first
    campo_busca.wait_for(state="visible", timeout=10000)
    campo_busca.fill(impressora_alvo)
    
    # Clica no primeiro botão de Submit, independente se está escrito "Search" ou "Pesquisar"
    botao_busca = page_cups.locator("input[type='submit' i], input[type='SUBMIT']").first
    botao_busca.click()
    
    print("👀 Verificando os resultados da busca...")
    
    # Validação de Inexistência (Agnóstica de Idioma)
    linha_resultado = page_cups.get_by_role("row").filter(has_text=impressora_alvo).first
    
    try:
        linha_resultado.wait_for(state="visible", timeout=5000)
    except:
        page_cups.close()
        # O Maestro escuta exatamente este erro para saber o que fazer!
        raise ValueError("Não existe no CUPS")
        
    print("✅ Impressora encontrada no CUPS! Extraindo dados da tabela...")
    
    # Em tabelas HTML padrão do CUPS, pegamos as colunas (td) daquela linha
    colunas = linha_resultado.locator("td")
    cups_queue = colunas.nth(0).inner_text().strip()
    cups_desc = colunas.nth(1).inner_text().strip()
    cups_loc = colunas.nth(2).inner_text().strip()
    
    # --- PROCESSO DE TRANSFORMAÇÃO DE DADOS (ETL) ---
    print("🧠 Processando e organizando as informações (Regex)...")
    
    # Usa Regex para encontrar o padrão de um endereço IP dentro do campo Description
    ip_encontrado = ""
    match_ip = re.search(r'\b\d{1,3}(?:\.\d{1,3}){3}\b', cups_desc)
    
    if match_ip:
        ip_encontrado = match_ip.group()
        # Remove o IP e caracteres residuais (como traços soltos) do texto original
        extra_info = cups_desc.replace(ip_encontrado, "").strip(" -")
    else:
        ip_encontrado = "IP NÃO REGISTRADO"
        extra_info = cups_desc

    # Monta os dados exatamente como o AGHUX precisa
    descricao_aghux = f"{cups_loc} - {extra_info}".strip(" -")
    localizacao_aghux = f"{descricao_aghux}\n{ip_encontrado}"
    
    dados_extraidos = {
        "fila": cups_queue,
        "classe": classe_impressora,
        "descricao_aghux": descricao_aghux,
        "localizacao_aghux": localizacao_aghux
    }
    
    print(f"📦 Pacote de dados pronto: {dados_extraidos}")
    page_cups.close()
    print("🔒 Aba do CUPS encerrada. Voltando ao AGHUX...")
    
    return dados_extraidos


# ==========================================
# CAPÍTULO: NAVEGAÇÃO E CADASTRO NO AGHUX
# ==========================================

def navegar_ate_cadastro_impressora(page_aghu: Page):
    """Navega pelo menu até a sala de Impressoras."""
    print("\n🗺️ Navegando até o módulo de Cadastro de Impressoras (AGHUX)...")
    
    for tentativa in range(2):
        try:
            if not page_aghu.get_by_text("Configuração", exact=True).locator("visible=true").first.is_visible():
                page_aghu.get_by_text("Outros Módulos", exact=True).locator("visible=true").first.click(timeout=5000)
                
            if not page_aghu.get_by_text("Impressão", exact=True).locator("visible=true").first.is_visible():
                page_aghu.get_by_text("Configuração", exact=True).locator("visible=true").first.click(timeout=5000)
                
            if not page_aghu.get_by_text("Cadastros", exact=True).locator("visible=true").first.is_visible():
                page_aghu.get_by_text("Impressão", exact=True).locator("visible=true").first.click(timeout=5000)

            if not page_aghu.get_by_text("Impressora", exact=True).locator("visible=true").first.is_visible():
                page_aghu.get_by_text("Cadastros", exact=True).locator("visible=true").first.click(timeout=5000)
                
            # Clica no menu final "Impressora" (não o 'por Computador')
            page_aghu.get_by_text("Impressora", exact=True).locator("visible=true").first.click(timeout=5000)
            
            print("⏳ Aguardando a tela carregar dentro da janela (iframe)...")
            janela_sistema = page_aghu.frame_locator("iframe").last
            
            # O validador de que chegamos é o botão de Pesquisar estar visível
            janela_sistema.get_by_role("button", name="Pesquisar").first.wait_for(state="visible", timeout=15000)
            print("🎯 Chegamos na tela 'Impressora'!")
            return janela_sistema
            
        except Exception as e:
            if tentativa == 0:
                print("🔄 Dando 'F5' (Refresh) para limpar o menu travado...")
                page_aghu.reload()
                page_aghu.wait_for_timeout(3000)
            else:
                raise e

def cadastrar_nova_impressora(janela_sistema, dados: dict):
    """Realiza o preenchimento do formulário no AGHUX baseando-se nos dados do CUPS."""
    print(f"\n🛠️ Iniciando processo de cadastro da impressora: {dados['fila']}")
    
    # 1. Pesquisa prévia para habilitar o botão Novo
    janela_sistema.locator("input[id*='fila' i]").first.fill(dados['fila'])
    janela_sistema.get_by_role("button", name="Pesquisar").click()
    
    try:
        # Espera o texto de erro aparecer
        janela_sistema.get_by_text("Nenhum registro encontrado!").wait_for(state="visible", timeout=5000)
        print("✔️ Confirmado: Impressora não existe no AGHUX. Botão 'Novo' liberado!")
    except:
        print("⚠️ A impressora já apareceu na tabela do AGHUX! Abortando criação duplicada.")
        return # Encerra a função pois já existe
        
    # 2. Clica em Novo e espera a tela carregar
    janela_sistema.get_by_role("button", name="Novo").click()
    janela_sistema.get_by_role("button", name="Gravar").wait_for(state="visible")
    
    # 3. Preenche Fila
    print("⌨️ Preenchendo Fila...")
    janela_sistema.locator("input[id*='fila' i]").first.fill(dados['fila'])
    
    # 4. Selecionar Tipo da Impressora (Regra de Negócio: PDF -> Laser PCL | RAW -> Cod. Barras)
    print("🎛️ Selecionando Tipo de Impressora...")
    tipo_imp_selecao = "Laser PCL" if dados['classe'].upper() == "PDF" else "Cod. Barras"
    
    # Tenta usar o recurso nativo de select, se for um JSF complexo, usamos a estratégia de cliques visuais
    try:
        janela_sistema.locator("label:has-text('Tipo da Impressora') ~ div .ui-selectonemenu-trigger").first.click(timeout=2000)
        janela_sistema.locator("li").filter(has_text=tipo_imp_selecao).click()
    except:
        janela_sistema.locator("div.ui-selectonemenu-trigger").nth(0).click()
        janela_sistema.locator("li").filter(has_text=tipo_imp_selecao).first.click()

    # 5. Selecionar Tipo Cups (Regra: Exatamente igual ao PrinterClass)
    print("🎛️ Selecionando Tipo do CUPS...")
    try:
        janela_sistema.locator("label:has-text('Tipo do Cups') ~ div .ui-selectonemenu-trigger").first.click(timeout=2000)
        janela_sistema.locator("li").filter(has_text=dados['classe']).click()
    except:
        janela_sistema.locator("div.ui-selectonemenu-trigger").nth(1).click()
        janela_sistema.locator("li, td").filter(has_text=dados['classe']).first.click()

    # 6. Botão da Lupa (Servidor CUPS)
    print("🔍 Configurando o Servidor CUPS com proteção Anti-Homologação...")
    botao_lupa = janela_sistema.locator("button.ui-autocomplete-dropdown:has(.ui-icon-triangle-1-s)").first
    botao_lupa.click()
    
    # Filtra separadamente pelo IP e pelo nome, evitando problemas com espaços invisíveis ou colunas da tabela JSF
    item_servidor = janela_sistema.locator("tr, li").filter(has_text="10.6.0.121").filter(has_text="CUPS").filter(has_not_text="HOMOLOGAÇÃO").first
    item_servidor.wait_for(state="visible", timeout=5000)
    item_servidor.click()
    
    # 7. Preencher Descrição
    print("⌨️ Preenchendo Descrição...")
    janela_sistema.locator("input[id*='descricao' i]").first.fill(dados['descricao_aghux'])
    
    # 8. Preencher Localização (Textarea)
    print("⌨️ Preenchendo Localização (Multilinhas)...")
    janela_sistema.locator("textarea[id*='localizacao' i]").first.fill(dados['localizacao_aghux'])
    
    # 9. Salvar
    print("💾 Clicando em Gravar...")
    janela_sistema.get_by_role("button", name="Gravar").click()
    
    # Confirma que voltou para a tela inicial
    janela_sistema.get_by_role("button", name="Pesquisar").wait_for(state="visible")
    print("🎉 Sucesso! Impressora cadastrada e salva no AGHUX.")


# ==========================================
# MOTOR DE TESTE ISOLADO
# ==========================================
def testar_robo_especialista():
    """
    Simula um pedido de criação de impressora para testar o código de forma independente.
    """
    impressora_teste = "HUB-IMP-UCA_171" 
    classe_teste = "PDF" # Ou "RAW"
    
    from PrinterAGHU import obter_credenciais
    usuario, senha, mostrar_console, mostrar_browser = obter_credenciais()
    
    if not usuario or not senha:
        print("❌ Login cancelado pelo usuário. Encerrando o teste.")
        return

    with sync_playwright() as p:
        # ignore_https_errors=True é vital para acessar o CUPS
        browser = p.chromium.launch(headless=not mostrar_browser, slow_mo=500)
        context = browser.new_context(ignore_https_errors=True)
        
        page_aghu = context.new_page()
        print("🚀 Ligando motores... Acessando o AGHUX no monitor da esquerda...")
        page_aghu.goto("https://aghu.hub-unb.ebserh/aghu/pages/casca/casca.xhtml")
        
        fazer_login(page_aghu, usuario, senha)
        
        try:
            dados_processados = consultar_dados_site_secundario(context, impressora_teste, classe_teste)
            janela_sistema = navegar_ate_cadastro_impressora(page_aghu)
            cadastrar_nova_impressora(janela_sistema, dados_processados)
            
        except Exception as e:
            print(f"\n❌ O processo foi abortado com o erro: {e}")
        
        print("\n🏁 Fim do teste da esteira de automação.")
        page_aghu.pause() 
        browser.close()

if __name__ == "__main__":
    testar_robo_especialista()