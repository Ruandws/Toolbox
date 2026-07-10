# test_unit_consultor_sti.py — Testes unitários para consultor_sti.py
#
# Testa funções puras de validação, normalização, planilha e relatório.

from datetime import datetime

import pytest

import consultor_sti
from consultor_sti import (
    NO_USER_FOUND_MESSAGE,
    SEARCH_TYPE_CPF,
    SEARCH_TYPE_FULL_NAME,
    STATUS_ERRO,
    STATUS_NAO_ENCONTRADO,
    STATUS_SUCESSO,
    USER_FOUND_MESSAGE,
    SearchResult,
    build_report_row,
    build_row,
    classify_result_status,
    extract_cpf_digits,
    format_cpf,
    format_single_result,
    generate_report_filename,
    get_available_report_path,
    get_report_headers,
    identify_search_column,
    is_empty_row,
    is_valid_cpf_digits,
    make_unique_headers,
    normalize_column_name,
    normalize_cpf,
    normalize_search_type,
    prepare_batch_search_value,
    prepare_search_value,
    result_color,
    summarize_batch_results,
    validate_spreadsheet_extension,
)


class FakeBrowser:
    def __init__(self):
        self.context = FakeContext()
        self.closed = False

    def new_context(self):
        return self.context

    def close(self):
        self.closed = True


class FakeChromium:
    def __init__(self):
        self.launch_kwargs = None
        self.browser = FakeBrowser()

    def launch(self, **kwargs):
        self.launch_kwargs = kwargs
        return self.browser


class FakeContext:
    def __init__(self):
        self.page = object()
        self.closed = False

    def new_page(self):
        return self.page

    def close(self):
        self.closed = True


class FakePlaywrightManager:
    def __init__(self):
        self.chromium = FakeChromium()

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False


# ---------------------------------------------------------------------------
# normalize_column_name
# ---------------------------------------------------------------------------


class TestNormalizeColumnName:
    def test_acentos_removidos(self):
        assert normalize_column_name("Usuário") == "usuario"

    def test_none_retorna_vazio(self):
        assert normalize_column_name(None) == ""

    def test_espacos_preservados_como_lower(self):
        assert normalize_column_name("  CPF Usuário  ") == "cpf usuario"


# ---------------------------------------------------------------------------
# normalize_search_type
# ---------------------------------------------------------------------------


class TestNormalizeSearchType:
    def test_cpf(self):
        assert normalize_search_type("CPF") == SEARCH_TYPE_CPF

    def test_nome_completo(self):
        assert normalize_search_type("Nome Completo") == SEARCH_TYPE_FULL_NAME

    def test_nome(self):
        assert normalize_search_type("nome") == SEARCH_TYPE_FULL_NAME

    def test_tipo_invalido(self):
        with pytest.raises(ValueError, match="Tipo de pesquisa inválido"):
            normalize_search_type("email")


# ---------------------------------------------------------------------------
# identify_search_column
# ---------------------------------------------------------------------------


class TestIdentifySearchColumn:
    def test_encontra_coluna_cpf(self):
        headers = ["Nome", "cpf", "Email"]
        resultado = identify_search_column(headers, "cpf")
        assert resultado == "cpf"

    def test_encontra_coluna_nome(self):
        headers = ["Login", "Nome Completo", "Status"]
        resultado = identify_search_column(headers, "nome completo")
        assert resultado == "Nome Completo"

    def test_coluna_nao_encontrada(self):
        headers = ["A", "B", "C"]

        with pytest.raises(ValueError, match="Coluna de pesquisa"):
            identify_search_column(headers, "cpf")


# ---------------------------------------------------------------------------
# extract_cpf_digits / is_valid_cpf_digits / normalize_cpf / format_cpf
# ---------------------------------------------------------------------------


class TestCPF:
    CPF_VALIDO = "52998224725"  # CPF válido para testes

    def test_extract_digits_formatado(self):
        assert extract_cpf_digits("529.982.247-25") == "52998224725"

    def test_extract_digits_none(self):
        assert extract_cpf_digits(None) == ""

    def test_extract_digits_float_inteiro(self):
        assert extract_cpf_digits(52998224725.0) == "52998224725"

    def test_is_valid_cpf_valido(self):
        assert is_valid_cpf_digits(self.CPF_VALIDO) is True

    def test_is_valid_cpf_repetido(self):
        assert is_valid_cpf_digits("11111111111") is False

    def test_is_valid_cpf_curto(self):
        assert is_valid_cpf_digits("123") is False

    def test_normalize_cpf_valido(self):
        assert normalize_cpf("529.982.247-25") == self.CPF_VALIDO

    def test_normalize_cpf_vazio(self):
        with pytest.raises(ValueError, match="CPF válido"):
            normalize_cpf("")

    def test_normalize_cpf_invalido(self):
        with pytest.raises(ValueError, match="dígitos verificadores"):
            normalize_cpf("12345678901")

    def test_format_cpf(self):
        assert format_cpf(self.CPF_VALIDO) == "529.982.247-25"


# ---------------------------------------------------------------------------
# prepare_search_value / prepare_batch_search_value
# ---------------------------------------------------------------------------


class TestPrepareSearchValue:
    CPF_VALIDO = "52998224725"

    def test_cpf_valido(self):
        resultado = prepare_search_value("cpf", "529.982.247-25")
        assert resultado == self.CPF_VALIDO

    def test_nome_com_numeros_levanta_erro(self):
        with pytest.raises(ValueError, match="sem números"):
            prepare_search_value("nome completo", "João 123")

    def test_nome_normaliza_espacos(self):
        resultado = prepare_search_value("nome", "  João   Silva  ")
        assert resultado == "João Silva"

    def test_valor_vazio(self):
        with pytest.raises(ValueError, match="não informado"):
            prepare_search_value("cpf", "")

    def test_batch_cpf_com_padding(self):
        # CPF com menos de 11 dígitos recebe padding no lote
        resultado = prepare_batch_search_value("cpf", "529.982.247-25")
        assert resultado == self.CPF_VALIDO


# ---------------------------------------------------------------------------
# validate_spreadsheet_extension
# ---------------------------------------------------------------------------


class TestValidateSpreadsheetExtension:
    def test_xlsx_valido(self):
        assert validate_spreadsheet_extension("dados.xlsx") == ".xlsx"

    def test_csv_invalido(self):
        with pytest.raises(ValueError, match="não suportado"):
            validate_spreadsheet_extension("dados.csv")


class TestHeadlessMode:
    def test_run_automation_usa_headless_quando_browser_oculto(self, monkeypatch):
        playwright = FakePlaywrightManager()
        monkeypatch.setattr(consultor_sti, "sync_playwright", lambda: playwright)
        monkeypatch.setattr(consultor_sti, "login_to_system", lambda *_args: None)
        monkeypatch.setattr(consultor_sti, "open_search_users_page", lambda *_args: None)
        monkeypatch.setattr(
            consultor_sti,
            "search_user_prepared_value",
            lambda *_args: SearchResult(message=NO_USER_FOUND_MESSAGE),
        )

        consultor_sti.run_automation(
            "tecnico",
            "senha",
            "cpf",
            "52998224725",
            mostrar_browser=False,
        )

        assert playwright.chromium.launch_kwargs["headless"] is True

    def test_run_batch_automation_usa_browser_visual_por_padrao(
        self,
        monkeypatch,
        tmp_path,
    ):
        playwright = FakePlaywrightManager()
        monkeypatch.setattr(consultor_sti, "sync_playwright", lambda: playwright)
        monkeypatch.setattr(
            consultor_sti,
            "read_spreadsheet",
            lambda _path: (["cpf"], [{"cpf": "52998224725"}]),
        )
        monkeypatch.setattr(
            consultor_sti,
            "build_report_path",
            lambda *_args: tmp_path / "relatorio.xlsx",
        )
        monkeypatch.setattr(consultor_sti, "login_to_system", lambda *_args: None)
        monkeypatch.setattr(consultor_sti, "open_search_users_page", lambda *_args: None)
        monkeypatch.setattr(
            consultor_sti,
            "search_user_prepared_value",
            lambda *_args: SearchResult(message=NO_USER_FOUND_MESSAGE),
        )
        monkeypatch.setattr(consultor_sti, "write_report", lambda *_args: None)

        consultor_sti.run_batch_automation(
            "tecnico",
            "senha",
            "cpf",
            "entrada.xlsx",
            str(tmp_path),
        )

        assert playwright.chromium.launch_kwargs["headless"] is False


# ---------------------------------------------------------------------------
# generate_report_filename
# ---------------------------------------------------------------------------


class TestGenerateReportFilename:
    def test_formato_correto(self):
        now = datetime(2026, 6, 22, 14, 30, 0)
        nome = generate_report_filename(".xlsx", now)
        assert nome.startswith("Resultado_")
        assert nome.endswith(".xlsx")
        assert "22_06_26" in nome

    def test_extensao_sem_ponto(self):
        nome = generate_report_filename("xlsx")
        assert nome.endswith(".xlsx")


# ---------------------------------------------------------------------------
# get_available_report_path
# ---------------------------------------------------------------------------


class TestGetAvailableReportPath:
    def test_caminho_livre(self, tmp_path):
        caminho = tmp_path / "relatorio.xlsx"
        assert get_available_report_path(caminho) == caminho

    def test_caminho_ocupado_incrementa(self, tmp_path):
        caminho = tmp_path / "relatorio.xlsx"
        caminho.touch()
        novo = get_available_report_path(caminho)
        assert novo.name == "relatorio_2.xlsx"


# ---------------------------------------------------------------------------
# make_unique_headers / build_row / is_empty_row
# ---------------------------------------------------------------------------


class TestPlanilhaUtils:
    def test_make_unique_headers_basico(self):
        headers = make_unique_headers(["A", "B", "C"])
        assert headers == ["A", "B", "C"]

    def test_make_unique_headers_duplicados(self):
        headers = make_unique_headers(["Nome", "Nome", "Nome"])
        assert headers == ["Nome", "Nome_2", "Nome_3"]

    def test_make_unique_headers_none(self):
        headers = make_unique_headers([None, "B"])
        assert headers[0] == "coluna_1"

    def test_make_unique_headers_vazio_levanta(self):
        with pytest.raises(ValueError):
            make_unique_headers([])

    def test_build_row(self):
        row = build_row(["A", "B"], ["x", "y"])
        assert row == {"A": "x", "B": "y"}

    def test_build_row_menos_valores(self):
        row = build_row(["A", "B", "C"], ["x"])
        assert row["C"] == ""

    def test_is_empty_row_true(self):
        assert is_empty_row([None, "", "  "]) is True

    def test_is_empty_row_false(self):
        assert is_empty_row(["dado"]) is False


# ---------------------------------------------------------------------------
# SearchResult / get_report_headers / build_report_row / format_single_result
# ---------------------------------------------------------------------------


class TestSearchResult:
    def test_criacao_basica(self):
        result = SearchResult(message="OK")
        assert result.full_name == ""
        assert result.user_login == ""

    def test_report_headers_cpf(self):
        headers = get_report_headers("cpf")
        assert "Nome Completo" in headers
        assert "usuário" in headers

    def test_report_headers_nome(self):
        headers = get_report_headers("nome completo")
        assert "Nome Completo" not in headers

    def test_report_headers_com_email(self):
        headers = get_report_headers("cpf", collect_email=True)
        assert headers == [
            "Nome Completo",
            "usuário",
            "E-mail",
            "Relatório",
        ]

    def test_build_report_row_cpf(self):
        result = SearchResult(
            message="Usuário encontrado",
            full_name="João",
            user_login="joao",
        )
        row = build_report_row("cpf", result)
        assert row["Nome Completo"] == "João"

    def test_build_report_row_com_email(self):
        result = SearchResult(
            message="Usuário encontrado",
            user_login="ana.maria",
            email="ana.maria@hubrasil.gov.br",
        )
        row = build_report_row("nome completo", result, collect_email=True)
        assert row["E-mail"] == "ana.maria@hubrasil.gov.br"

    def test_format_single_result_nao_encontrado(self):
        result = SearchResult(message=NO_USER_FOUND_MESSAGE)
        assert format_single_result(result, "cpf") == NO_USER_FOUND_MESSAGE

    def test_format_single_result_encontrado_cpf(self):
        result = SearchResult(
            message="Usuário encontrado",
            full_name="Ana Maria",
            user_login="ana.maria",
        )
        texto = format_single_result(result, "cpf")
        assert "Ana Maria" in texto
        assert "ana.maria" in texto

    def test_format_single_result_com_email(self):
        result = SearchResult(
            message="Usuário encontrado",
            user_login="ana.maria",
            email="ana.maria@hubrasil.gov.br",
        )
        texto = format_single_result(result, "nome completo")
        assert "ana.maria@hubrasil.gov.br" in texto


class TestResumoLote:
    def test_classify_result_status_sucesso(self):
        result = SearchResult(message=USER_FOUND_MESSAGE)
        assert classify_result_status(result) == STATUS_SUCESSO

    def test_classify_result_status_nao_encontrado(self):
        result = SearchResult(message=NO_USER_FOUND_MESSAGE)
        assert classify_result_status(result) == STATUS_NAO_ENCONTRADO

    def test_classify_result_status_multiplos_conta_como_nao_encontrado(self):
        result = SearchResult(message="Mais de um usuário encontrado")
        assert classify_result_status(result) == STATUS_NAO_ENCONTRADO

    def test_classify_result_status_erro(self):
        result = SearchResult(message="Erro: falha ao pesquisar")
        assert classify_result_status(result) == STATUS_ERRO

    def test_summarize_batch_results_quebra_por_status(self):
        resultados = [
            SearchResult(message=USER_FOUND_MESSAGE),
            SearchResult(message=USER_FOUND_MESSAGE),
            SearchResult(message=NO_USER_FOUND_MESSAGE),
            SearchResult(message="Erro: falha ao pesquisar"),
        ]

        resumo = summarize_batch_results(resultados)

        assert resumo == (
            "Total: 4. Sucesso: 2. Não encontrado: 1. Erro: 1."
        )

    def test_summarize_batch_results_lista_vazia(self):
        assert summarize_batch_results([]) == (
            "Total: 0. Sucesso: 0. Não encontrado: 0. Erro: 0."
        )

    def test_result_color_vermelho_quando_ha_erro(self):
        resultados = [
            SearchResult(message=USER_FOUND_MESSAGE),
            SearchResult(message="Erro: falha ao pesquisar"),
        ]
        assert result_color(resultados) == "red"

    def test_result_color_laranja_quando_nao_encontrado_sem_erro(self):
        resultados = [
            SearchResult(message=USER_FOUND_MESSAGE),
            SearchResult(message=NO_USER_FOUND_MESSAGE),
        ]
        assert result_color(resultados) == "orange"

    def test_result_color_verde_quando_tudo_sucesso(self):
        resultados = [SearchResult(message=USER_FOUND_MESSAGE)]
        assert result_color(resultados) == "green"

    def test_result_color_unitario_laranja_para_multiplos_encontrados(self):
        resultado = [SearchResult(message="Mais de um usuário encontrado")]
        assert result_color(resultado) == "orange"

    def test_result_color_unitario_vermelho_para_erro(self):
        resultado = [SearchResult(message="Erro: falha ao pesquisar")]
        assert result_color(resultado) == "red"
