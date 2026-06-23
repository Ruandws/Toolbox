# test_unit_menu.py — Testes unitários para menu.py
#
# Testa a lógica de parsing de itens de menu sem Playwright.

import pytest

from menu import _opcoes_texto_menu


# ---------------------------------------------------------------------------
# _opcoes_texto_menu
# ---------------------------------------------------------------------------


class TestOpcoesTextoMenu:
    def test_item_string(self):
        assert _opcoes_texto_menu("Módulos") == ("Módulos",)

    def test_item_sequencia(self):
        assert _opcoes_texto_menu(["A", "B"]) == ("A", "B")

    def test_sequencia_vazia_levanta_erro(self):
        with pytest.raises(ValueError, match="texto nao vazio"):
            _opcoes_texto_menu([])

    def test_item_vazio_levanta_erro(self):
        with pytest.raises(ValueError, match="texto nao vazio"):
            _opcoes_texto_menu([""])

    def test_item_none_em_lista_levanta_erro(self):
        with pytest.raises(ValueError):
            _opcoes_texto_menu([None])  # type: ignore[list-item]
