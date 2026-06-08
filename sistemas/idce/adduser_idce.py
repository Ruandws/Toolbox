import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://idce.hub-unb.ebserh.gov.br/")
    #Para Realizar Login
    page.locator("iframe[name=\"Login\"]").content_frame.locator("#txtUsuario").click()
    page.locator("iframe[name=\"Login\"]").content_frame.locator("#txtUsuario").fill("usuario")
    page.locator("iframe[name=\"Login\"]").content_frame.locator("#txtSenha").click()
    page.locator("iframe[name=\"Login\"]").content_frame.locator("#txtSenha").fill("senha")
    page.locator("iframe[name=\"Login\"]").content_frame.get_by_role("link", name="Confirmar").click()

    ##Procedimento 1:Cadastro de Usuário
    #Fluxo base pra chegar na tela de 'Importar Usuário':
    page.get_by_role("link", name="Arquivos").click() 
    page.get_by_role("link", name="Seguranças").click()
    page.get_by_role("link", name="Usuários", exact=True).click()
    page.locator("iframe[name=\"Usuarios\"]").content_frame.get_by_role("link", name="Importar").click()
        #Na tela de import
    page.locator("iframe[name=\"SegUsuarioImportacao\"]").content_frame.get_by_role("textbox", name="Informe o nome do usuário").click()
    page.locator("iframe[name=\"SegUsuarioImportacao\"]").content_frame.get_by_role("textbox", name="Informe o nome do usuário").fill("ruan victor de jesus andrade")
    page.locator("iframe[name=\"SegUsuarioImportacao\"]").content_frame.get_by_role("button", name="Pesquisar").click()
        #Aqui os seletores do playwrigth não são recomendados. Melhor mesclar com css. De qualquer modo, se precisar, segue a estrutura da tela:
            #Tudo está dentro deste frame
    locator("iframe[name=\"SegUsuarioImportacao\"]").content_frame.locator("#box_geral")
            #Há a tabela, que está divida em 3 cabeçalhos de colunas, sendo :
                #Id
    locator("iframe[name=\"SegUsuarioImportacao\"]").content_frame.get_by_role("columnheader", name="Id")
                #Nome
    locator("iframe[name=\"SegUsuarioImportacao\"]").content_frame.get_by_role("columnheader", name="Nome")
                #Botões "Importar"
    locator("iframe[name=\"SegUsuarioImportacao\"]").content_frame.get_by_role("columnheader").nth(2)
            ###Adendo : Os seletores dos botões no Playwright são dinâmicos. Isso é problemático. Absolutamente utilizar css.
                # Exemplo prático: ´Se cada botão apresenta um 'ctl...' diferente, como raios poderiamos identificá-los corretamente à partir de usuários diferentes?´
    locator("iframe[name=\"SegUsuarioImportacao\"]").content_frame.locator("#gvDadosSegGrupo_ctl00_ctl04_btnImportar")
            #Caso o usuário já tenha sido importado, será exibido Alerta Popup:
                #Seletor do Texto exibido
    locator("iframe[name=\"SegUsuarioImportacao\"]").content_frame.get_by_text("Usuário já importado!")
                #Seletor do botão Ok do popup.
    get_by_role("link", name="OK")
                #A automação deve clicar nele :
    page.get_by_role("link", name="OK").click()
        #Continuando...
        #Importado o usuário, deve-se Localizá-lo
    ##Procedimento 2 : Localizar o usuário importado.
    # Na tela 'Usuários', clicar em 'Localizar'.
        #Seletor de 'Localizar' :
    locator("iframe[name=\"Usuarios\"]").content_frame.get_by_role("link", name="Localizar")
        #É aberto o Painel de "Busca de Usuários" :
    locator("iframe[name=\"SegUsuarioBusca\"]").content_frame.locator("#Panel1")
        #Se a pesquisar for feita à partir de Login, ir direto para o "Input de texto a pesquisar"
        #Se a pesquisa for feita à partir do Nome Completo, clicar no 'Seletor Dropdown de pesquisa':
            #Seletor dropdown : 
    locator("iframe[name=\"SegUsuarioBusca\"]").content_frame.get_by_role("link", name="Nome")
            #Ao clicar nele, ele exibirá a opção de 'Pesquisa por Nome' 
                #Seletor do dropdown de 'Pesquisa por nome' :
    locator("iframe[name=\"SegUsuarioBusca\"]").content_frame.locator("#rfdSubMenu1780606473212").get_by_text("Nome").click()
        #Após selecionar "Nome" ou "Login", preencher o 'Nome' ou o 'Login' no Input de pesquisa.
            #Seletor Input de texto a pesquisar:
    locator("iframe[name=\"SegUsuarioBusca\"]").content_frame.locator("#txtTextoProcurado")
    page.locator("iframe[name=\"SegUsuarioBusca\"]").content_frame.locator("#txtTextoProcurado").fill(USUARIO)
            #Botão Pesquisar:
    page.locator("iframe[name=\"SegUsuarioBusca\"]").content_frame.get_by_role("button", name="Buscar").click()
        #Abaixo do Painel de "Busca de Usuários", teremos a tabela com os resultados da busca.
            #Seletor da Tabela:
    locator("iframe[name=\"SegUsuarioBusca\"]").content_frame.locator("#GridViewPesquisa")
            #A tabela, como de praxe, possui colunas e linhas :
                #Coluna "Nome de usuário"
    page.locator("iframe[name=\"SegUsuarioBusca\"]").content_frame.get_by_role("columnheader", name="Nome de usuário").click()
                #Coluna "Nome"
    page.locator("iframe[name=\"SegUsuarioBusca\"]").content_frame.get_by_role("columnheader", name="Nome", exact=True).click()
                #Se a pesquisa for feita através de usuário : Na coluna de Nome de usuário, deve-se procurar pelo usuário buscado:
    locator("iframe[name=\"SegUsuarioBusca\"]").content_frame.get_by_role("cell", name="JOAO.DUARTE")
                #Se a pesquisa for feita através de Nome Completo : Na coluna de Nome, deve-se procurar pelo nome :
    locator("iframe[name=\"SegUsuarioBusca\"]").content_frame.get_by_role("cell", name="JOÃO DE DEUS PEREIRA DUARTE")
        #Encontrado o usuário, clicar em "Selecionar"
            #Seletor "Selecionar" :
    locator("iframe[name=\"SegUsuarioBusca\"]").content_frame.get_by_role("link", name="Selecionar")
    ##Procedimento 3 : Conceder acessos básicos "HUB"
        #Novamente estrutura de tabela; possui colunas e linhas :
            #Seletor "Adicionar"
    locator("iframe[name=\"Usuarios\"]").content_frame.locator("#RadMultiPage2").get_by_role("link", name="Adicionar")
        #É exibido CRUD para concessão de acessos.
            #Seletor do CRUD:
    page.locator("iframe[name=\"UsuarioUnidadeCRUD\"]").content_frame.locator("#box_geral_modalidade_crud")
            #Dropdown de Unidades Disponíveis para Seleção :
    page.locator("iframe[name=\"UsuarioUnidadeCRUD\"]").content_frame.get_by_text("select").click()
            #Ao abrir, selecione "HUB" :
    page.locator("iframe[name=\"UsuarioUnidadeCRUD\"]").content_frame.get_by_text("HUB").click()
            #Mover Todos os acessos disponíveis para a lista de acessos do usuário :
    page.locator("iframe[name=\"UsuarioUnidadeCRUD\"]").content_frame.get_by_role("link", name="All to Right").click()
            #Salvar ;
    page.locator("iframe[name=\"UsuarioUnidadeCRUD\"]").content_frame.get_by_role("link", name="Gravar").click()

    ##Procedimento 4 : Configurar Acessos de Grupos:
        #Fluxo base pra chegar na tela 'Grupo dos usuários':
    page.get_by_role("link", name="Arquivos").click()
    page.get_by_role("link", name="Seguranças").click()
    page.get_by_role("link", name="Grupos dos usuários").click()
        #Seletor da Box Geral:
    page.locator("iframe[name=\"GruposUsuarios\"]").content_frame.locator("#box_geral")
        #Seletor do Input de Pesquisa (Nome Completo):
    page.locator("iframe[name=\"GruposUsuarios\"]").content_frame.locator("input[name=\"RadTextBox1\"]").click()
        #Preencher com o Nome Completo do Colaborador:
    page.locator("iframe[name=\"GruposUsuarios\"]").content_frame.locator("input[name=\"RadTextBox1\"]").fill(usuario)
        #Botão 'Localizar':
    page.locator("iframe[name=\"GruposUsuarios\"]").content_frame.get_by_role("button", name="Localizar").click()
        ##Adendo : Deve-se assegurar que o nome selecionado é ESTRITAMENTE o MESMO PESQUISADO. Pode conflitar na situação de haver colaborador com usuário normal e outro adm.
            #Seletor da Tabela de resultado da pesquisa de usuário
    locator("iframe[name=\"GruposUsuarios\"]").content_frame.locator("#GridLeft")
            #Clicar no usuário correto:
    page.locator("iframe[name=\"GruposUsuarios\"]").content_frame.get_by_role("cell", name="ADM RUAN VICTOR DE JESUS").click()
        #Seletor da Tabela de Acessos a Conceder :
    locator("iframe[name=\"GruposUsuarios\"]").content_frame.locator("#GridRight")
        #Estrutura Padrão de tabela: Possui Colunas e Linhas
            #Seletor Cabeçalho Checkboxes : 
    page.locator("iframe[name=\"GruposUsuarios\"]").content_frame.get_by_role("columnheader").nth(1)
        #Seletor Cabeçalho Nome : 
    page.locator("iframe[name=\"GruposUsuarios\"]").content_frame.locator("#gvDadosSegGrupo_ctl00_Header").get_by_role("columnheader", name="Nome")
        ##Adendo Final : Há duas opções; Acesso como "Médico Solicitante" e Acesso como "Médico Solicitante Residente":
            #Se Médico Solicitante :     
                #Seletor Linha de Checkboxes :
    locator("iframe[name=\"GruposUsuarios\"]").content_frame.locator("#gvDadosSegGrupo_ctl00__8 > td").first
                #Seletor Checkbox : 
    page.locator("iframe[name=\"GruposUsuarios\"]").content_frame.locator("#gvDadosSegGrupo_ctl00_ctl20_ChkBox").click()
            #Se Médico Solicitante Residente : 
                #Seletor Linha de Checkboxes :
    page.locator("iframe[name=\"GruposUsuarios\"]").content_frame.locator("#gvDadosSegGrupo_ctl00__9 > td").first.click()
                #Seletor Checkbox : 
    page.locator("iframe[name=\"GruposUsuarios\"]").content_frame.locator("#gvDadosSegGrupo_ctl00_ctl22_ChkBox").click()
        #Findanda a concessão de acesso, deve-se Gravar.
            #Seletor Botão Gravar :
    page.locator("iframe[name=\"GruposUsuarios\"]").content_frame.get_by_role("link", name="Gravar")
    
    #Encerrado fluxo de Cadastro. 
    #Se for continuar fluxo, looping recomeça à partir da linha 22.








    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
