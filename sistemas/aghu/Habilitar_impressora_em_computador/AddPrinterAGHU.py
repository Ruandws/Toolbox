import re
from playwright.sync_api import BrowserContext, Page

#Imports de classes utilitárias públicas.
from autenticador import autenticar_aghu_page, exigir_login_valido
from menu import navegar_menu_impressora

# ==========================================
# ROBÔ ESPECIALISTA: ALMOXARIFADO (CADASTRAR IMPRESSORA)
# ==========================================

def fazer_login(page_aghu: Page, usuario_str: str, senha_str: str):
    """Autentica no AGHUX usando o autenticador centralizado."""
    print("Checando autenticação no AGHUX.")

    resultado = autenticar_aghu_page(
        page=page_aghu,
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
    except Exception:
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
    """Navega pelo menu até a tela de Cadastro de Impressoras."""
    print("\n🗺️ Navegando até o módulo de Cadastro de Impressoras (AGHUX)...")

    for tentativa in range(2):
        try:
            janela_sistema = navegar_menu_impressora(
                page=page_aghu,
                item_final="Impressora",
            )

            print("🎯 Chegamos na tela 'Impressora'!")
            return janela_sistema

        except Exception as erro:
            if tentativa == 0:
                print("🔄 Dando 'F5' para limpar o menu travado...")
                page_aghu.reload()
                page_aghu.wait_for_timeout(3000)
            else:
                raise erro

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
    except Exception:
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
    except Exception:
        janela_sistema.locator("div.ui-selectonemenu-trigger").nth(0).click()
        janela_sistema.locator("li").filter(has_text=tipo_imp_selecao).first.click()

    # 5. Selecionar Tipo Cups (Regra: Exatamente igual ao PrinterClass)
    print("🎛️ Selecionando Tipo do CUPS...")
    try:
        janela_sistema.locator("label:has-text('Tipo do Cups') ~ div .ui-selectonemenu-trigger").first.click(timeout=2000)
        janela_sistema.locator("li").filter(has_text=dados['classe']).click()
    except Exception:
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
