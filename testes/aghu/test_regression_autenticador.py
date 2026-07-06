# test_regression_autenticador.py — Testes de regressão para autenticador.py
#
# Garantem que comportamentos previamente corrigidos continuam funcionando.

import pytest

import autenticador
from autenticador import ResultadoLogin, exigir_login_valido


class PageAutenticadorFake:
    def __init__(self) -> None:
        self.url = "https://aghu.example.com/login"
        self.tempo_aguardado_ms = 0

    def goto(self, url, wait_until, timeout) -> None:
        self.url = url

    def wait_for_load_state(self, state, timeout) -> None:
        return None

    def wait_for_timeout(self, timeout_ms) -> None:
        self.tempo_aguardado_ms += timeout_ms


class TestRegressaoExigirLoginValido:
    """Regressões em exigir_login_valido."""

    def test_todos_status_de_falha_levantam_runtime_error(self):
        """Bug: alguns status de falha não levantavam exceção."""
        status_falha = ["credenciais_invalidas", "timeout", "erro"]

        for status in status_falha:
            resultado = ResultadoLogin(status=status, mensagem="teste")

            with pytest.raises(RuntimeError):
                exigir_login_valido(resultado)

    def test_resultado_com_url_final_preserva_mensagem(self):
        """Bug: mensagem era descartada quando url_final estava presente."""
        resultado = ResultadoLogin(
            status="erro",
            mensagem="Falha específica",
            url_final="https://aghu.example.com",
        )

        with pytest.raises(RuntimeError, match="Falha específica"):
            exigir_login_valido(resultado)


class TestRegressaoAutenticarAghuPage:
    """Regressões em autenticar_aghu_page."""

    def test_timeout_pos_submit_usa_limite_fixo_do_autenticador(self, monkeypatch):
        """Bug: timeout externo curto encerrava cedo a confirmacao pos-submit."""
        page = PageAutenticadorFake()

        def monotonic_fake():
            return page.tempo_aguardado_ms / 1000

        monkeypatch.setattr(autenticador.time, "monotonic", monotonic_fake)
        monkeypatch.setattr(autenticador, "_erro_autenticacao_visivel", lambda *_, **__: False)
        monkeypatch.setattr(autenticador, "_login_efetuado", lambda *_, **__: False)
        monkeypatch.setattr(autenticador, "_tela_login_visivel", lambda *_, **__: True)
        monkeypatch.setattr(autenticador, "_preencher_credenciais", lambda *_, **__: None)
        monkeypatch.setattr(autenticador, "_clicar_entrar", lambda *_, **__: None)

        resultado = autenticador.autenticar_aghu_page(
            page=page,
            usuario="usuario",
            senha="senha",
            url_login="https://aghu.example.com/login",
            timeout_ms=1000,
            tempo_tela_principal_segundos=0,
        )

        assert resultado.status == "timeout"
        assert "limite fixo de 10s" in resultado.mensagem
        assert page.tempo_aguardado_ms == autenticador.TIMEOUT_RESULTADO_AUTENTICADOR_MS
