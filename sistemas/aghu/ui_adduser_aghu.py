import threading
from collections import Counter
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk

from adduser_aghu import (
    STATUS_ERRO,
    STATUS_IGNORADO,
    STATUS_IMPORTADO,
    STATUS_JA_IMPORTADO,
    STATUS_NAO_ENCONTRADO,
    executar_importacao_individual,
    executar_importacao_lote,
)
from autenticador import AGHU_URL, AGHU_URL_HOMOLOGACAO


AMBIENTE_PRODUCAO = "Produção"
AMBIENTE_HOMOLOGACAO = "Homologação"
URLS_AMBIENTE_AGHU = {
    AMBIENTE_PRODUCAO: AGHU_URL,
    AMBIENTE_HOMOLOGACAO: AGHU_URL_HOMOLOGACAO,
}


def obter_url_ambiente_aghu(ambiente: str) -> str:
    return URLS_AMBIENTE_AGHU.get(ambiente, AGHU_URL)


def caminho_relatorio_padrao(base: str = "") -> str:
    nome = f"relatorio_importacao_usuario_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    if base:
        caminho_base = Path(base)
        diretorio = caminho_base.parent if caminho_base.suffix else caminho_base
        return str(diretorio / nome)

    return str(Path.cwd() / nome)


class AghuImportUserApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AGHUX Bot - Importação de Usuário")
        self.geometry("820x720")
        self.resizable(False, False)
        self.grid_columnconfigure(0, weight=1)

        self.var_ambiente = tk.StringVar(value=AMBIENTE_PRODUCAO)
        self.em_execucao = False

        self.label_title = ctk.CTkLabel(
            self,
            text="AGHUX Bot - Importação de Usuário",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self.label_title.grid(row=0, column=0, padx=20, pady=(22, 10))

        self.frame_acesso = self._criar_secao("Acesso", 1)
        self.frame_individual = self._criar_secao("Execução Individual", 2)
        self.frame_lote = self._criar_secao("Execução em Lote", 3)

        self._criar_campos_acesso()
        self._criar_campos_individual()
        self._criar_campos_lote()

        self.label_status = ctk.CTkLabel(
            self,
            text="Pronto para execução.",
            text_color="gray",
            wraplength=760,
            justify="left",
        )
        self.label_status.grid(row=4, column=0, padx=20, pady=(10, 18), sticky="ew")

    def _criar_secao(self, titulo: str, row: int) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self)
        frame.grid(row=row, column=0, padx=20, pady=8, sticky="ew")
        frame.grid_columnconfigure(1, weight=1)

        label = ctk.CTkLabel(
            frame,
            text=titulo,
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        label.grid(row=0, column=0, columnspan=3, padx=14, pady=(12, 8), sticky="w")

        return frame

    def _criar_campos_acesso(self) -> None:
        self.label_usuario_rede = ctk.CTkLabel(
            self.frame_acesso,
            text="Usuário de rede:",
        )
        self.label_usuario_rede.grid(row=1, column=0, padx=14, pady=8, sticky="e")

        self.entry_usuario_rede = ctk.CTkEntry(
            self.frame_acesso,
            placeholder_text="Usuário de rede",
        )
        self.entry_usuario_rede.grid(
            row=1,
            column=1,
            columnspan=2,
            padx=14,
            pady=8,
            sticky="ew",
        )
        self.entry_usuario_rede.focus()

        self.label_senha = ctk.CTkLabel(self.frame_acesso, text="Senha:")
        self.label_senha.grid(row=2, column=0, padx=14, pady=8, sticky="e")

        self.entry_senha = ctk.CTkEntry(
            self.frame_acesso,
            placeholder_text="Senha",
            show="*",
        )
        self.entry_senha.grid(
            row=2,
            column=1,
            columnspan=2,
            padx=14,
            pady=8,
            sticky="ew",
        )

        self.label_ambiente = ctk.CTkLabel(self.frame_acesso, text="Ambiente:")
        self.label_ambiente.grid(row=3, column=0, padx=14, pady=8, sticky="e")

        self.option_ambiente = ctk.CTkOptionMenu(
            self.frame_acesso,
            values=list(URLS_AMBIENTE_AGHU.keys()),
            variable=self.var_ambiente,
            command=self._on_ambiente_changed,
        )
        self.option_ambiente.grid(
            row=3,
            column=1,
            columnspan=2,
            padx=14,
            pady=8,
            sticky="ew",
        )

        self.frame_alerta_producao = ctk.CTkFrame(
            self.frame_acesso,
            fg_color=("#FFF4CE", "#3A2D00"),
            border_color=("#D79A00", "#8A6500"),
            border_width=1,
        )
        self.frame_alerta_producao.grid_columnconfigure(0, weight=1)

        self.label_alerta_producao = ctk.CTkLabel(
            self.frame_alerta_producao,
            text=(
                "Atenção: você está executando no Ambiente de Produção. "
                "As alterações serão aplicadas no AGHUX de produção."
            ),
            text_color=("#5C3B00", "#FFE8A3"),
            wraplength=720,
            justify="left",
        )
        self.label_alerta_producao.grid(
            row=0,
            column=0,
            padx=12,
            pady=8,
            sticky="ew",
        )

        self._atualizar_alerta_ambiente(self.var_ambiente.get())

    def _criar_campos_individual(self) -> None:
        self.entry_login_individual = self._criar_linha_entry(
            self.frame_individual,
            row=1,
            label="Login:",
            placeholder="Login",
        )
        self.entry_nome_individual = self._criar_linha_entry(
            self.frame_individual,
            row=2,
            label="Nome Completo:",
            placeholder="Nome completo",
        )
        self.entry_email_individual = self._criar_linha_entry(
            self.frame_individual,
            row=3,
            label="E-mail:",
            placeholder="E-mail",
        )

        self.button_individual = ctk.CTkButton(
            self.frame_individual,
            text="Importar Usuário",
            command=self.iniciar_execucao_individual,
            height=36,
            font=ctk.CTkFont(weight="bold"),
        )
        self.button_individual.grid(
            row=4,
            column=1,
            columnspan=2,
            padx=14,
            pady=(10, 14),
            sticky="e",
        )

    def _criar_campos_lote(self) -> None:
        self.label_planilha_lote = ctk.CTkLabel(
            self.frame_lote,
            text="Planilha .xlsx:",
        )
        self.label_planilha_lote.grid(row=1, column=0, padx=14, pady=8, sticky="e")

        self.entry_planilha_lote = ctk.CTkEntry(
            self.frame_lote,
            placeholder_text="Arquivo .xlsx",
        )
        self.entry_planilha_lote.grid(
            row=1,
            column=1,
            padx=14,
            pady=8,
            sticky="ew",
        )

        self.button_planilha_lote = ctk.CTkButton(
            self.frame_lote,
            text="Selecionar",
            width=110,
            command=self.selecionar_planilha_lote,
        )
        self.button_planilha_lote.grid(row=1, column=2, padx=14, pady=8)

        self.label_relatorio_lote = ctk.CTkLabel(
            self.frame_lote,
            text="Relatório:",
        )
        self.label_relatorio_lote.grid(row=2, column=0, padx=14, pady=8, sticky="e")

        self.entry_relatorio_lote = ctk.CTkEntry(
            self.frame_lote,
            placeholder_text="Arquivo .xlsx de saída",
        )
        self.entry_relatorio_lote.grid(
            row=2,
            column=1,
            padx=14,
            pady=8,
            sticky="ew",
        )

        self.button_relatorio_lote = ctk.CTkButton(
            self.frame_lote,
            text="Selecionar",
            width=110,
            command=self.selecionar_relatorio_lote,
        )
        self.button_relatorio_lote.grid(row=2, column=2, padx=14, pady=8)

        self.button_lote = ctk.CTkButton(
            self.frame_lote,
            text="Executar Lote",
            command=self.iniciar_execucao_lote,
            height=36,
            font=ctk.CTkFont(weight="bold"),
        )
        self.button_lote.grid(
            row=3,
            column=1,
            columnspan=2,
            padx=14,
            pady=(10, 14),
            sticky="e",
        )

    def _criar_linha_entry(
        self,
        frame: ctk.CTkFrame,
        row: int,
        label: str,
        placeholder: str,
    ) -> ctk.CTkEntry:
        label_widget = ctk.CTkLabel(frame, text=label)
        label_widget.grid(row=row, column=0, padx=14, pady=8, sticky="e")

        entry = ctk.CTkEntry(frame, placeholder_text=placeholder)
        entry.grid(row=row, column=1, columnspan=2, padx=14, pady=8, sticky="ew")
        return entry

    def _on_ambiente_changed(self, ambiente: str) -> None:
        self._atualizar_alerta_ambiente(ambiente)

    def _atualizar_alerta_ambiente(self, ambiente: str) -> None:
        if ambiente == AMBIENTE_PRODUCAO:
            self.frame_alerta_producao.grid(
                row=4,
                column=0,
                columnspan=3,
                padx=14,
                pady=(0, 10),
                sticky="ew",
            )
            return

        self.frame_alerta_producao.grid_remove()

    def selecionar_planilha_lote(self) -> None:
        caminho = filedialog.askopenfilename(
            title="Selecione a planilha de lote",
            filetypes=(("Excel", "*.xlsx"),),
        )

        if not caminho:
            return

        self.entry_planilha_lote.delete(0, "end")
        self.entry_planilha_lote.insert(0, caminho)

        if not self.entry_relatorio_lote.get().strip():
            self.entry_relatorio_lote.insert(0, caminho_relatorio_padrao(caminho))

    def selecionar_relatorio_lote(self) -> None:
        caminho = filedialog.asksaveasfilename(
            title="Salvar relatório como",
            defaultextension=".xlsx",
            initialfile=Path(caminho_relatorio_padrao()).name,
            filetypes=(("Excel", "*.xlsx"),),
        )

        if caminho:
            self.entry_relatorio_lote.delete(0, "end")
            self.entry_relatorio_lote.insert(0, caminho)

    def _credenciais_e_url(self) -> tuple[str, str, str]:
        usuario_rede = self.entry_usuario_rede.get().strip()
        senha = self.entry_senha.get()
        url_aghu = obter_url_ambiente_aghu(self.var_ambiente.get())

        if not usuario_rede or not senha:
            raise ValueError("Preencha usuário de rede e senha.")

        return usuario_rede, senha, url_aghu

    def _bloquear_execucao(self, texto_botao: str) -> None:
        self.em_execucao = True
        self.button_individual.configure(state="disabled")
        self.button_lote.configure(state="disabled")
        self.button_planilha_lote.configure(state="disabled")
        self.button_relatorio_lote.configure(state="disabled")
        self.button_individual.configure(text=texto_botao)
        self.button_lote.configure(text=texto_botao)

    def _liberar_execucao(self) -> None:
        self.em_execucao = False
        self.button_individual.configure(state="normal", text="Importar Usuário")
        self.button_lote.configure(state="normal", text="Executar Lote")
        self.button_planilha_lote.configure(state="normal")
        self.button_relatorio_lote.configure(state="normal")

    def iniciar_execucao_individual(self) -> None:
        if self.em_execucao:
            return

        try:
            usuario_rede, senha, url_aghu = self._credenciais_e_url()
            login = self.entry_login_individual.get().strip()
            nome_completo = self.entry_nome_individual.get().strip()
            email = self.entry_email_individual.get().strip()

            if not login or not nome_completo or not email:
                raise ValueError("Preencha Login, Nome Completo e E-mail.")
        except Exception as exc:
            self._mostrar_status(f"Erro: {exc}", "red")
            return

        self._mostrar_status("Executando importação individual...", "blue")
        self._bloquear_execucao("Executando...")

        thread = threading.Thread(
            target=self._executar_individual_thread,
            args=(usuario_rede, senha, login, nome_completo, email, url_aghu),
            daemon=True,
        )
        thread.start()

    def _executar_individual_thread(
        self,
        usuario_rede: str,
        senha: str,
        login: str,
        nome_completo: str,
        email: str,
        url_aghu: str,
    ) -> None:
        try:
            resultado = executar_importacao_individual(
                usuario_rede=usuario_rede,
                senha=senha,
                login=login,
                nome_completo=nome_completo,
                email=email,
                url_aghu=url_aghu,
                mostrar_browser=True,
            )
            mensagem = f"{resultado.login}: {resultado.status} - {resultado.detalhes}"
            self.after(0, self._finalizar_execucao, mensagem, "green")
        except Exception as exc:
            self.after(0, self._finalizar_execucao, f"Erro: {exc}", "red")

    def iniciar_execucao_lote(self) -> None:
        if self.em_execucao:
            return

        try:
            usuario_rede, senha, url_aghu = self._credenciais_e_url()
            caminho_planilha = self.entry_planilha_lote.get().strip()
            caminho_relatorio = self.entry_relatorio_lote.get().strip()

            if not caminho_planilha:
                raise ValueError("Informe a planilha .xlsx de lote.")

            if not caminho_relatorio:
                caminho_relatorio = caminho_relatorio_padrao(caminho_planilha)
                self.entry_relatorio_lote.insert(0, caminho_relatorio)

            if Path(caminho_planilha).suffix.lower() != ".xlsx":
                raise ValueError("A planilha de lote deve ser um arquivo .xlsx.")
        except Exception as exc:
            self._mostrar_status(f"Erro: {exc}", "red")
            return

        self._mostrar_status("Executando lote...", "blue")
        self._bloquear_execucao("Executando...")

        thread = threading.Thread(
            target=self._executar_lote_thread,
            args=(usuario_rede, senha, caminho_planilha, caminho_relatorio, url_aghu),
            daemon=True,
        )
        thread.start()

    def _executar_lote_thread(
        self,
        usuario_rede: str,
        senha: str,
        caminho_planilha: str,
        caminho_relatorio: str,
        url_aghu: str,
    ) -> None:
        try:
            resultados, relatorio = executar_importacao_lote(
                usuario_rede=usuario_rede,
                senha=senha,
                caminho_planilha=caminho_planilha,
                caminho_relatorio=caminho_relatorio,
                url_aghu=url_aghu,
                mostrar_browser=True,
            )
            resumo = self._resumir_resultados(resultados)
            mensagem = f"{resumo} Relatório: {relatorio}"
            self.after(0, self._finalizar_execucao, mensagem, "green")
        except Exception as exc:
            self.after(0, self._finalizar_execucao, f"Erro: {exc}", "red")

    def _resumir_resultados(self, resultados) -> str:
        contagem = Counter(resultado.status for resultado in resultados)
        total = len(resultados)

        return (
            f"Lote concluído. Total: {total}. "
            f"Importados: {contagem[STATUS_IMPORTADO]}. "
            f"Já importados: {contagem[STATUS_JA_IMPORTADO]}. "
            f"Não encontrados: {contagem[STATUS_NAO_ENCONTRADO]}. "
            f"Ignorados: {contagem[STATUS_IGNORADO]}. "
            f"Erros: {contagem[STATUS_ERRO]}."
        )

    def _finalizar_execucao(self, mensagem: str, cor: str) -> None:
        self._mostrar_status(mensagem, cor)
        self._liberar_execucao()

    def _mostrar_status(self, mensagem: str, cor: str) -> None:
        self.label_status.configure(text=mensagem, text_color=cor)


if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    app = AghuImportUserApp()
    app.mainloop()
