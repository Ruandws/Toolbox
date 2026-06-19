from collections.abc import Sequence

from playwright.sync_api import Page


# ==========================================
# LOCATORS DE MENU
# ==========================================


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


# ==========================================
# NAVEGACAO GENERICA
# ==========================================

def navegar_menu_aghu(
    page: Page,
    caminho: Sequence[str],
    timeout_menu_ms: int = 5000,
):
    """Percorre um caminho completo de menu e retorna o ultimo iframe."""
    if isinstance(caminho, str) or not caminho:
        raise ValueError("Informe o caminho do menu como sequencia de itens.")

    caminho = tuple(caminho)

    for item_atual, proximo_item in zip(caminho, caminho[1:]):
        _garantir_proximo_nivel_visivel(
            page=page,
            item_atual=item_atual,
            proximo_item=proximo_item,
            timeout_ms=timeout_menu_ms,
        )

    _clicar_item_menu(page, caminho[-1], timeout_menu_ms)

    return page.frame_locator("iframe").last
