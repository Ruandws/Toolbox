# conftest.py — Configurações e fixtures globais de teste.
#
# Adiciona os diretórios dos sistemas ao sys.path para que os módulos possam
# ser importados nos testes sem a necessidade de instalação como pacote.

import sys
from pathlib import Path

import pytest

_RAIZ_PROJETO = Path(__file__).resolve().parent.parent
_SISTEMAS = _RAIZ_PROJETO / "sistemas"

# Registra cada subdiretório de sistemas no sys.path.
for _subdir in sorted(_SISTEMAS.iterdir()):
    if _subdir.is_dir() and not _subdir.name.startswith((".", "_")):
        _caminho = str(_subdir)

        if _caminho not in sys.path:
            sys.path.insert(0, _caminho)

# Registra subdiretórios aninhados (ex: Habilitar_impressora_em_computador).
for _subdir in sorted(_SISTEMAS.rglob("*")):
    if _subdir.is_dir() and not _subdir.name.startswith((".", "_")):
        _caminho = str(_subdir)

        if _caminho not in sys.path:
            sys.path.insert(0, _caminho)


# ---------------------------------------------------------------------------
# Fixtures globais
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_xlsx(tmp_path: Path):
    """Retorna uma factory para criar planilhas .xlsx temporárias."""
    import openpyxl

    def _criar(nome: str, cabecalhos: list[str], linhas: list[list]) -> Path:
        caminho = tmp_path / nome
        wb = openpyxl.Workbook()
        ws = wb.active

        ws.append(cabecalhos)

        for linha in linhas:
            ws.append(linha)

        wb.save(caminho)
        return caminho

    return _criar
