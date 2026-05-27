from playwright.sync_api import sync_playwright


def run_automation(
    login: str,
    password: str,
    search_value: str,
    expiration_date: str
) -> str:

    with sync_playwright() as playwright:

        browser = playwright.chromium.launch(
            headless=False
        )

        context = browser.new_context()

        page = context.new_page()

        # LOGIN
        page.goto(
            "https://servicosti.ebserh.gov.br/#/login",
            wait_until="networkidle"
        )

        page.get_by_role("textbox").first.fill(login)

        page.locator(
            'input[type="password"]'
        ).fill(password)

        page.get_by_role(
            "button",
            name="Entrar"
        ).click()

        page.wait_for_timeout(3000)

        # ABRE PÁGINA DO USUÁRIO
        user_url = (
            f"https://servicosti.ebserh.gov.br/#/usuarios/{search_value}"
        )

        page.goto(
            user_url,
            wait_until="networkidle"
        )

        page.wait_for_timeout(3000)

        date_input = page.get_by_role(
            "textbox",
            name="__/__/____"
        ).first

        # Clica no campo
        date_input.click()

        # Fecha datepicker
        page.keyboard.press("Escape")

        # Seleciona tudo
        date_input.press("ControlOrMeta+A")

        # Limpa conteúdo
        date_input.fill("")

        # Insere nova data
        date_input.type(expiration_date)

        # Atualiza dados
        page.get_by_role(
            "button",
            name="Atualizar dados"
        ).click()

        context.close()
        browser.close()

        return (
            f"Data prorrogada para {expiration_date}"
        )