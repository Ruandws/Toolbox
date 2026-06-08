import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://aghu.hub-unb.ebserh/aghu/pages/casca/casca.xhtml")
    #Login do Sistema
    page.locator("[id=\"usuario:usuario:inputId\"]").click()
    page.get_by_role("textbox", name="Senha").click()
    page.get_by_role("button", name="Entrar").click()
    # Navegar até "Usuário" (Menu Lateral)
    page.locator("a").filter(has_text="Outros Módulos").click()
    page.locator("a").filter(has_text=re.compile(r"^Configuração$")).click()
    page.locator("a").filter(has_text=re.compile(r"^Acesso$")).click()
    page.locator("a").filter(has_text=re.compile(r"^Usuario$")).click()
    #É aberta a aba "Pesquisar Usuários" e exibido o campo de pesquisa
    page.locator("iframe[name=\"i_frame_usuario\"]").content_frame.get_by_role("textbox").click()
    #Seletor para inserção do usuário a pesquisar.
    page.locator("iframe[name=\"i_frame_usuario\"]").content_frame.get_by_role("textbox").fill(usuario)
    #Seletor do Botão "Pesquisar".
    locator("iframe[name=\"i_frame_usuario\"]").content_frame.get_by_role("button", name="Pesquisar")

    #4 Cenários: 1_Usuário já importado, 2_Usuário não importado, 3_Mais de um resultado, 4_Nenhum usuário encontrado (mesmo após tentar encontrá-lo)

    #Cenário 1: Se o usuário já tiver sido importado.
        # * Confirmar se o usuário em "Login" é o mesmo que inicialmente foi buscado.
        ## Seletor do Cabeçalho da coluna "Login": 
        locator("iframe[name=\"i_frame_usuario\"]").content_frame.get_by_role("columnheader", name="Login")
        #Seletor da linha da tabela correspondente ao usuário. Este DEVE ser EXATAMENTE o mesmo login pesquisado.
        locator("iframe[name=\"i_frame_usuario\"]").content_frame.get_by_role("gridcell", name="ANDRADE.RUAN")
            #! Adicionar Filtro : Pode ser que seja exibido mais de um resultado. Ex : 2 linhas, exibindo 1° "lais.lima" e 2° "lais.lima.5".


    #Cenário 2: Se o usuário não tiver sido importado.
            # Retomando após a pesquisa de usuário apontar "Nenum registro encontrado!"
            # Seletor de "nenhum registro encontrado :
            locator("iframe[name=\"i_frame_usuario\"]").content_frame.get_by_role("gridcell", name="Nenhum registro encontrado!")

            #Seletor para importar o usuário :
            locator("iframe[name=\"i_frame_usuario\"]").content_frame.get_by_role("button", name="Importar Usuário")
            #Após clicar em "Importar", será exibido outro campo de pesquisa. Insira novamente o usuário neste.
            locator("iframe[name=\"i_frame_usuario\"]").content_frame.locator("[id=\"nomeOuLoginNaoCadastrado:nomeOuLoginNaoCadastrado:inputId\"]").fill(usuario)
            #Seletor do Botão "Pesquisar", para pesquisar.
            locator("iframe[name=\"i_frame_usuario\"]").content_frame.get_by_role("button", name="Pesquisar")
            #Seletor do ícone de "Importar usuário" para importar.
            locator("iframe[name=\"i_frame_usuario\"]").content_frame.get_by_role("link", name="Adicionar")

            #O sistema te redireciona pra tela de "Cadastro de Usuário".
            #Seletor para validar que está nesta tela mesmo :
            locator("iframe[name=\"i_frame_usuario\"]").content_frame.get_by_text("Cadastro de Usuarios")

            #Preencher campos : Nome, E-mail, ativar checkbox e grave.
            #Seletor nome
            locator("iframe[name=\"i_frame_usuario\"]").content_frame.get_by_text("Cadastro de Usuarios")
            #Seletor Email
            locator("iframe[name=\"i_frame_usuario\"]").content_frame.locator("input[name=\"email:email:inputId\"]")
            #Seletor checkbox "Ativo"
            locator("iframe[name=\"i_frame_usuario\"]").content_frame.locator(".ui-chkbox-icon").first
            #Seletor botão "Gravar"
            locator("iframe[name=\"i_frame_usuario\"]").content_frame.get_by_role("button", name="Gravar")
            
            #Mensagem do Sistema que valida a importação : Diversos Locators. Escolher qual o melhor pra este contexto :
            locator("iframe[name=\"i_frame_usuario\"]").content_frame.get_by_text("Mensagens do Sistema")
            locator("iframe[name=\"i_frame_usuario\"]").content_frame.locator("#messagesInDialog")
            locator("iframe[name=\"i_frame_usuario\"]").content_frame.locator("#messagesInDialog div").filter(has_text="Usuário alterado com sucesso")
            locator("iframe[name=\"i_frame_usuario\"]").content_frame.locator("div").filter(has_text="Usuário alterado com sucesso").nth(2)
            
            
            
            #O icone está em uma linha, na coluna de cabeçalho "Ações".Eis o seletor
            locator("iframe[name=\"i_frame_usuario\"]").content_frame.get_by_role("columnheader", name="Ações")





    ## Se não for encontrado nenhum usuário :
    locator("iframe[name=\"i_frame_usuario\"]").content_frame.get_by_role("gridcell", name="Nenhum registro encontrado!")
        # Retornar à "Importação de Usuário"
    
    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
