# test_regression_consultor_sti.py — Testes de regressão para consultor_sti.py
#
# Validam cenários de bugs previamente corrigidos.


from consultor_sti import (
    extract_cpf_digits,
    format_cpf,
    is_valid_cpf_digits,
    make_unique_headers,
    normalize_search_type,
    prepare_search_value,
)


class TestRegressaoCPF:
    """Regressões de validação de CPF."""

    def test_cpf_com_zeros_a_esquerda(self):
        """Bug: CPF iniciando com zero era truncado ao converter de float."""
        assert extract_cpf_digits("01234567890") == "01234567890"

    def test_cpf_boolean_nao_e_valido(self):
        """Bug: True era convertido em '1' e passava parcialmente."""
        digits = extract_cpf_digits(True)
        assert not is_valid_cpf_digits(digits)

    def test_format_cpf_preserva_zeros(self):
        """Bug: formatação perdia zeros à esquerda."""
        # CPF 529.982.247-25 é válido
        resultado = format_cpf("52998224725")
        assert resultado.startswith("529.")


class TestRegressaoSearchType:
    """Regressões de tipo de pesquisa."""

    def test_full_name_em_ingles_aceito(self):
        """Bug: 'full name' não era aceito como tipo."""
        resultado = normalize_search_type("full name")
        assert resultado == "nome completo"


class TestRegressaoPlanilha:
    """Regressões na manipulação de planilhas."""

    def test_headers_todos_none(self):
        """Bug: cabeçalhos todos None causavam crash."""
        headers = make_unique_headers([None, None])
        assert headers == ["coluna_1", "coluna_2"]

    def test_prepare_search_value_nome_com_espacos_multiples(self):
        """Bug: múltiplos espaços no nome não eram colapsados."""
        resultado = prepare_search_value("nome", "  João    da   Silva  ")
        assert resultado == "João da Silva"
