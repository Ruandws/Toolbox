from playwright.sync_api import Playwright, sync_playwright

def run_automation(login: str, password: str, search_type: str, search_value: str) -> str:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=False
        )

        context = browser.new_context()

        page = context.new_page()

        # Login
        page.goto(
            "https://servicosti.ebserh.gov.br/#/login",
            wait_until="networkidle"
        )

        page.get_by_role("textbox").first.fill(login)

        page.locator('input[type="password"]').fill(password)

        page.get_by_role(
            "button",
            name="Entrar"
        ).click()
        
        #Delay
        page.wait_for_timeout(3000)

        page.goto(
            "https://servicosti.ebserh.gov.br/#/pesquisa-usuarios",
            wait_until="networkidle"
        )

        # 1. Localiza o input e garante que ele já renderizou na tela
        input_campo = page.locator('input[ng-model="parametro"]')
        input_campo.wait_for(state="visible")

        # 2. Preenche o valor (CPF / Nome)
        input_campo.fill(search_value)

        # 3. Clica no botão Pesquisar
        page.get_by_role("button", name="Pesquisar").click()

        # 4. Avalia os resultados da tabela
        try:
            # espera resultados renderizarem
            page.locator("tbody tr").first.wait_for(timeout=5000)
            
            # captura linhas da tabela
            rows = page.locator("tbody tr")
            count = rows.count()

            if count == 0:
                result_msg = "Nenhum usuário encontrado"
            elif count > 1:
                result_msg = "Mais de um usuário encontrado"
            else:
                row = rows.first
                nome = row.locator("td").nth(3).inner_text().strip()
                user_login = row.locator("td").nth(4).inner_text().strip()
                result_msg = f"Usuário encontrado!\nNome: {nome}\nLogin: {user_login}"
        except Exception:
            # Se não apareceu nada na tabela dentro de 5s, assumimos nenhum resultado
            result_msg = "Nenhum usuário encontrado"

        context.close()
        browser.close()
        return result_msg