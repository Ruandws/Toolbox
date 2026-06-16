from playwright.sync_api import Page


CAMINHO_MENU_IMPRESSORA = (
    "Outros Módulos",
    "Configuração",
    "Impressão",
    "Cadastros",
)


def _locator_menu_visivel(page: Page, texto: str):
    return page.get_by_text(texto, exact=True).locator("visible=true").first


def _item_menu_visivel(page: Page, texto: str) -> bool:
    try:
        return _locator_menu_visivel(page, texto).is_visible()
    except Exception:
        return False


def _clicar_item_menu(page: Page, texto: str, timeout_ms: int) -> None:
    item = _locator_menu_visivel(page, texto)
    item.wait_for(state="visible", timeout=timeout_ms)
    item.click(timeout=timeout_ms)


def _garantir_proximo_nivel_visivel(
    page: Page,
    item_atual: str,
    proximo_item: str,
    timeout_ms: int,
) -> None:
    if _item_menu_visivel(page, proximo_item):
        return

    _clicar_item_menu(page, item_atual, timeout_ms)
    _locator_menu_visivel(page, proximo_item).wait_for(
        state="visible",
        timeout=timeout_ms,
    )


def navegar_menu_impressora(
    page: Page,
    item_final: str,
    timeout_menu_ms: int = 5000,
    timeout_tela_ms: int = 15000,
):
    caminho = (*CAMINHO_MENU_IMPRESSORA, item_final)

    for item_atual, proximo_item in zip(caminho, caminho[1:]):
        _garantir_proximo_nivel_visivel(
            page=page,
            item_atual=item_atual,
            proximo_item=proximo_item,
            timeout_ms=timeout_menu_ms,
        )

    _clicar_item_menu(page, item_final, timeout_menu_ms)

    janela_sistema = page.frame_locator("iframe").last
    janela_sistema.get_by_role("button", name="Pesquisar").first.wait_for(
        state="visible",
        timeout=timeout_tela_ms,
    )

    return janela_sistema