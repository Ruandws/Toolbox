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
    page.locator("iframe[name=\"i_frame_usuario\"]").content_frame.get_by_role("textbox").fill(usuario).
        #Se encontrar o usuário : Seletor do Cabeçalho da coluna "Login": 
        locator("iframe[name=\"i_frame_usuario\"]").content_frame.get_by_role("columnheader", name="Login")
        #Seletor da linha da tabela correspondente ao usuário. Este DEVE ser EXATAMENTE o mesmo login pesquisado.
        locator("iframe[name=\"i_frame_usuario\"]").content_frame.get_by_role("gridcell", name="ANDRADE.RUAN")
            #! Adicionar Filtro : Pode ser que seja exibido mais de um resultado. Ex : 2 linhas, exibindo 1° "lais.lima" e 2° "lais.lima.5"

        #Seletor Cabeçalho : Coluna :  Ações
        locator("iframe[name=\"i_frame_usuario\"]").content_frame.get_by_role("columnheader", name="Ações")

        #Seletor "Editar Perfil"
        #Seletor "editar"
        