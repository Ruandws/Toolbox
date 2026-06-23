# test_unit_prorrogador_sti.py — Testes unitários para prorrogador_sti.py
#
# Testa funções puras de validação, normalização, planilha e relatório.

from datetime import date, datetime
from pathlib import Path

import pytest

from prorrogador_sti import (
    REPORT_COLUMN_NAME,
    REPORT_COLUMN_USER,
    REPORT_HEADERS,
    USER_COLUMN_CANDIDATES,
    build_report_row,
    build_row,
    build_user_url,
    generate_report_filename,
    get_available_report_path,
    get_report_headers,
    identify_user_column,
    is_empty_row,
    make_unique_headers,
    normalize_column_name,
    normalize_expiration_date,
    normalize_user_value,
    prepare_user_value,
    validate_spreadsheet_extension,
)


# ---------------------------------------------------------------------------
# normalize_column_name
# ---------------------------------------------------------------------------


class TestNormalizeColumnName:
    def test_acentos_removidos(self):
        assert normalize_column_name("Usuário") == "usuario"

    def test_none_retorna_vazio(self):
        assert normalize_column_name(None) == ""


# ---------------------------------------------------------------------------
# normalize_user_value
# ---------------------------------------------------------------------------


class TestNormalizeUserValue:
    def test_string_normal(self):
        assert normalize_user_value("joao.silva") == "joao.silva"

    def test_none_retorna_vazio(self):
        assert normalize_user_value(None) == ""

    def test_inteiro(self):
        assert normalize_user_value(12345) == "12345"

    def test_float_inteiro(self):
        assert normalize_user_value(123.0) == "123"


# ---------------------------------------------------------------------------
# prepare_user_value
# ---------------------------------------------------------------------------


class TestPrepareUserValue:
    def test_usuario_valido(self):
        assert prepare_user_value("joao.silva") == "joao.silva"

    def test_usuario_vazio(self):
        with pytest.raises(ValueError, match="não informado"):
            prepare_user_value("")

    def test_usuario_com_espacos(self):
        with pytest.raises(ValueError, match="espaços"):
            prepare_user_value("joao silva")

    def test_usuario_booleano(self):
        with pytest.raises(ValueError, match="booleano"):
            prepare_user_value(True)

    def test_caracteres_invalidos(self):
        with pytest.raises(ValueError, match="letras"):
            prepare_user_value("joao<>silva")


# ---------------------------------------------------------------------------
# build_user_url
# ---------------------------------------------------------------------------


class TestBuildUserUrl:
    def test_url_basica(self):
        url = build_user_url("joao.silva")
        assert "joao.silva" in url
        assert url.startswith("https://servicosti.ebserh.gov.br/")


# ---------------------------------------------------------------------------
# normalize_expiration_date
# ---------------------------------------------------------------------------


class TestNormalizeExpirationDate:
    def test_data_formato_correto(self):
        assert normalize_expiration_date("22/06/2026") == "22/06/2026"

    def test_data_somente_digitos(self):
        assert normalize_expiration_date("22062026") == "22/06/2026"

    def test_data_datetime(self):
        dt = datetime(2026, 6, 22)
        assert normalize_expiration_date(dt) == "22/06/2026"

    def test_data_date(self):
        d = date(2026, 6, 22)
        assert normalize_expiration_date(d) == "22/06/2026"

    def test_data_none(self):
        with pytest.raises(ValueError, match="não informada"):
            normalize_expiration_date(None)

    def test_data_vazia(self):
        with pytest.raises(ValueError, match="não informada"):
            normalize_expiration_date("")

    def test_data_booleano(self):
        with pytest.raises(ValueError, match="booleano"):
            normalize_expiration_date(True)

    def test_data_formato_invalido(self):
        with pytest.raises(ValueError, match="dd/mm/aaaa"):
            normalize_expiration_date("2026-06-22")

    def test_data_irreal(self):
        with pytest.raises(ValueError, match="data real"):
            normalize_expiration_date("32/13/2026")


# ---------------------------------------------------------------------------
# identify_user_column
# ---------------------------------------------------------------------------


class TestIdentifyUserColumn:
    def test_encontra_usuario(self):
        headers = ["Nome", "usuário", "Data"]
        assert identify_user_column(headers) == "usuário"

    def test_encontra_login(self):
        headers = ["Nome", "login", "Status"]
        assert identify_user_column(headers) == "login"

    def test_nao_encontrada(self):
        headers = ["A", "B"]

        with pytest.raises(ValueError, match="Coluna de usuários"):
            identify_user_column(headers)


# ---------------------------------------------------------------------------
# Planilha utils (reutilizados de consultor — validação cruzada)
# ---------------------------------------------------------------------------


class TestPlanilhaUtils:
    def test_make_unique_headers_duplicados(self):
        headers = make_unique_headers(["Col", "Col"])
        assert headers == ["Col", "Col_2"]

    def test_build_row_basico(self):
        row = build_row(["A", "B"], ["x", "y"])
        assert row == {"A": "x", "B": "y"}

    def test_is_empty_row(self):
        assert is_empty_row([None, "", "  "]) is True
        assert is_empty_row(["x"]) is False


# ---------------------------------------------------------------------------
# generate_report_filename / get_available_report_path
# ---------------------------------------------------------------------------


class TestRelatorio:
    def test_generate_report_filename(self):
        now = datetime(2026, 6, 22, 14, 0, 0)
        nome = generate_report_filename(".xlsx", now)
        assert nome.startswith("Resultado_")
        assert nome.endswith(".xlsx")

    def test_get_available_report_path_livre(self, tmp_path):
        caminho = tmp_path / "r.xlsx"
        assert get_available_report_path(caminho) == caminho

    def test_get_available_report_path_ocupado(self, tmp_path):
        caminho = tmp_path / "r.xlsx"
        caminho.touch()
        novo = get_available_report_path(caminho)
        assert novo.name == "r_2.xlsx"


# ---------------------------------------------------------------------------
# build_report_row / get_report_headers
# ---------------------------------------------------------------------------


class TestReportRow:
    def test_build_report_row(self):
        row = build_report_row("joao.silva", "Prorrogado com sucesso")
        assert row[REPORT_COLUMN_USER] == "joao.silva"
        assert row[REPORT_COLUMN_NAME] == "Prorrogado com sucesso"

    def test_build_report_row_none(self):
        row = build_report_row(None, None)
        assert row[REPORT_COLUMN_USER] == ""

    def test_get_report_headers(self):
        headers = get_report_headers()
        assert headers == list(REPORT_HEADERS)


# ---------------------------------------------------------------------------
# validate_spreadsheet_extension
# ---------------------------------------------------------------------------


class TestValidateExtension:
    def test_xlsx_ok(self):
        assert validate_spreadsheet_extension("a.xlsx") == ".xlsx"

    def test_csv_invalido(self):
        with pytest.raises(ValueError):
            validate_spreadsheet_extension("a.csv")
