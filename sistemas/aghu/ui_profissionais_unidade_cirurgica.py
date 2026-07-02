import threading
from collections import Counter
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from autenticador import AGHU_URL, AGHU_URL_HOMOLOGACAO
from profissionais_unidade_cirurgica_aghu import (
    CadastroProfissionalUnidadeEntrada,
    FUNCOES_PROFISSIONAL,
    LOGS_DIR,
    STATUS_CONFERIR_MANUAL,
    STATUS_CRIADO,
    STATUS_ERRO,
    STATUS_FUNCIONARIO_NAO_ENCONTRADO,
    STATUS_IGNORADO,
    STATUS_MANTIDO,
    UNIDADES_FUNCIONAIS,
    executar_cadastro_individual,
    executar_cadastro_lote,
    validar_entrada,
)


TIPO_INDIVIDUAL = "Unitária"
TIPO_LOTE = "Lote"

AMBIENTE_PRODUCAO = "Produção"
AMBIENTE_HOMOLOGACAO = "Homologação"
URLS_AMBIENTE_AGHU = {
    AMBIENTE_PRODUCAO: AGHU_URL,
    AMBIENTE_HOMOLOGACAO: AGHU_URL_HOMOLOGACAO,
}


def obter_url_ambiente_aghu(ambiente: str) -> str:
    return URLS_AMBIENTE_AGHU.get(ambiente, AGHU_URL)


def caminho_relatorio_padrao(base: str = "") -> str:
    nome = (
        "relatorio_profissionais_unidade_cirurgica_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )

    if base:
        caminho_base = Path(base)
        diretorio = caminho_base.parent if caminho_base.suffix else caminho_base
        return str(diretorio / nome)

    return str(Path.cwd() / nome)


class AghuProfissionaisUnidadeCirurgicaApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        unidade_inicial = UNIDADES_FUNCIONAIS[0]
        funcao_inicial = FUNCOES_PROFISSIONAL[0]

        self.title("AGHUX Bot - Profissionais da Unidade Cirúrgica")
        self.geometry("900x720")
        self.minsize(760, 620)
        self.resizable(True, True)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.var_ambiente = tk.StringVar(value=AMBIENTE_HOMOLOGACAO)
        self.var_tipo_execucao = tk.StringVar(value=TIPO_INDIVIDUAL)
        self.var_browser = tk.BooleanVar(value=True)
        self.var_console = tk.BooleanVar(value=True)
        self.var_unidade_funcional = tk.StringVar(value=unidade_inicial)
        self.var_funcao = tk.StringVar(value=funcao_inicial)
        self.em_execucao = False

        self.label_title = ctk.CTkLabel(
            self,
            text="AGHUX Bot - Profissionais da Unidade Cirúrgica",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self.label_title.grid(row=0, column=0, padx=20, pady=(22, 10))

        self.frame_conteudo = ctk.CTkScrollableFrame(self)
        self.frame_conteudo.grid(row=1, column=0, padx=20, pady=8, sticky="nsew")
        self.frame_conteudo.grid_columnconfigure(0, weight=1)

        self.frame_acesso = self._criar_secao("Acesso", 0)
        self.frame_tipo_execucao = self._criar_secao("Tipo de Execução", 1)

        self.frame_execucao = ctk.CTkFrame(self.frame_conteudo, fg_color="transparent")
        self.frame_execucao.grid(row=2, column=0, padx=0, pady=8, sticky="ew")
        self.frame_execucao.grid_columnconfigure(0, weight=1)

        self.frame_individual = self._criar_secao_execucao("Cadastro Unitário")
        self.frame_lote = self._criar_secao_execucao("Cadastro em Lote")

        self._criar_campos_acesso()
        self._criar_opcoes_execucao()
        self._criar_seletor_tipo_execucao()
        self._criar_campos_individual()
        self._criar_campos_lote()
        self._atualizar_tipo_execucao(TIPO_INDIVIDUAL)

        self.button_executar = ctk.CTkButton(
            self.frame_conteudo,
            text="Executar cadastro",
            command=self.iniciar_execucao,
            height=40,
            font=ctk.CTkFont(weight="bold"),
        )
        self.button_executar.grid(row=3, column=0, padx=0, pady=(12, 8), sticky="e")

        self.label_status = ctk.CTkLabel(
            self,
            text="Pronto para execução.",
            text_color="gray",
            wraplength=840,
            justify="left",
        )
        self.label_status.grid(row=2, column=0, padx=20, pady=(8, 18), sticky="ew")

    def _criar_secao(self, titulo: str, row: int) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.frame_conteudo)
        frame.grid(row=row, column=0, padx=0, pady=8, sticky="ew")
        frame.grid_columnconfigure(1, weight=1)

        label = ctk.CTkLabel(
            frame,
            text=titulo,
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        label.grid(row=0, column=0, columnspan=3, padx=14, pady=(12, 8), sticky="w")
        return frame

    def _criar_secao_execucao(self, titulo: str) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.frame_execucao)
        frame.grid_columnconfigure(1, weight=1)

        label = ctk.CTkLabel(
            frame,
            text=titulo,
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        label.grid(row=0, column=0, columnspan=3, padx=14, pady=(12, 8), sticky="w")
        return frame

    def _criar_seletor_tipo_execucao(self) -> None:
        self.label_tipo_execucao = ctk.CTkLabel(
            self.frame_tipo_execucao,
            text="Tipo:",
        )
        self.label_tipo_execucao.grid(row=1, column=0, padx=14, pady=8, sticky="e")

        self.segment_tipo_execucao = ctk.CTkSegmentedButton(
            self.frame_tipo_execucao,
            values=[TIPO_INDIVIDUAL, TIPO_LOTE],
            variable=self.var_tipo_execucao,
            command=self._atualizar_tipo_execucao,
            height=36,
            selected_color=("#1F6AA5", "#144870"),
            selected_hover_color=("#155E96", "#0F3A5A"),
            unselected_color=("#D9D9D9", "#333333"),
            unselected_hover_color=("#C9C9C9", "#3D3D3D"),
        )
        self.segment_tipo_execucao.grid(
            row=1,
            column=1,
            columnspan=2,
            padx=14,
            pady=8,
            sticky="ew",
        )
        self.segment_tipo_execucao.set(TIPO_INDIVIDUAL)

    def _atualizar_tipo_execucao(self, tipo: str) -> None:
        self.frame_individual.grid_remove()
        self.frame_lote.grid_remove()

        if tipo == TIPO_INDIVIDUAL:
            self.frame_individual.grid(row=0, column=0, sticky="ew")
        else:
            self.frame_lote.grid(row=0, column=0, sticky="ew")

        if hasattr(self, "segment_tipo_execucao"):
            for valor, btn in self.segment_tipo_execucao._buttons_dict.items():
                if valor == tipo:
                    btn.configure(text_color="white")
                else:
                    btn.configure(text_color=("#1F6AA5", "#3B8ED0"))

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
            wraplength=820,
            justify="left",
        )
        self.label_alerta_producao.grid(row=0, column=0, padx=12, pady=8, sticky="ew")
        self._atualizar_alerta_ambiente(self.var_ambiente.get())

    def _criar_opcoes_execucao(self) -> None:
        self.checkbox_browser = ctk.CTkCheckBox(
            self.frame_acesso,
            text="Exibir Navegador (Modo Visual)",
            variable=self.var_browser,
            command=lambda: self._validar_opcoes_visibilidade(self.var_browser),
        )
        self.checkbox_browser.grid(
            row=5,
            column=1,
            columnspan=2,
            padx=14,
            pady=(8, 6),
            sticky="w",
        )

        self.checkbox_console = ctk.CTkCheckBox(
            self.frame_acesso,
            text="Exibir Terminal de processos (logs)",
            variable=self.var_console,
            command=lambda: self._validar_opcoes_visibilidade(self.var_console),
        )
        self.checkbox_console.grid(
            row=6,
            column=1,
            columnspan=2,
            padx=14,
            pady=(6, 14),
            sticky="w",
        )

    def _criar_campos_individual(self) -> None:
        self.entry_profissional = self._criar_linha_entry(
            self.frame_individual,
            row=1,
            label="Profissional:",
            placeholder="Nome do profissional no AGHUX",
        )

        self.label_unidade = ctk.CTkLabel(
            self.frame_individual,
            text="Unidade Funcional:",
        )
        self.label_unidade.grid(row=2, column=0, padx=14, pady=8, sticky="e")

        self.option_unidade_funcional = ctk.CTkOptionMenu(
            self.frame_individual,
            values=list(UNIDADES_FUNCIONAIS),
            variable=self.var_unidade_funcional,
        )
        self.option_unidade_funcional.grid(
            row=2,
            column=1,
            columnspan=2,
            padx=14,
            pady=8,
            sticky="ew",
        )

        self.label_funcao = ctk.CTkLabel(self.frame_individual, text="Função:")
        self.label_funcao.grid(row=3, column=0, padx=14, pady=8, sticky="e")

        self.option_funcao = ctk.CTkOptionMenu(
            self.frame_individual,
            values=list(FUNCOES_PROFISSIONAL),
            variable=self.var_funcao,
        )
        self.option_funcao.grid(
            row=3,
            column=1,
            columnspan=2,
            padx=14,
            pady=(8, 14),
            sticky="ew",
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
        self.entry_planilha_lote.grid(row=1, column=1, padx=14, pady=8, sticky="ew")

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
        self.entry_relatorio_lote.grid(row=2, column=1, padx=14, pady=8, sticky="ew")

        self.button_relatorio_lote = ctk.CTkButton(
            self.frame_lote,
            text="Selecionar",
            width=110,
            command=self.selecionar_relatorio_lote,
        )
        self.button_relatorio_lote.grid(row=2, column=2, padx=14, pady=8)

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

    def _validar_opcoes_visibilidade(self, variavel_alvo: tk.BooleanVar) -> None:
        if not self.var_browser.get() and not self.var_console.get():
            variavel_alvo.set(True)
            messagebox.showwarning(
                "Ação bloqueada",
                "Para evitar processos invisíveis, mantenha o navegador ou o terminal ativo.",
                parent=self,
            )

    def _on_ambiente_changed(self, ambiente: str) -> None:
        self._atualizar_alerta_ambiente(ambiente)

        if ambiente == AMBIENTE_PRODUCAO:
            messagebox.showwarning(
                "Atenção: Ambiente de Produção",
                (
                    "Você selecionou o ambiente de Produção.\n\n"
                    "Tenha cautela: as alterações serão aplicadas no AGHUX de produção."
                ),
                parent=self,
            )

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

    def iniciar_execucao(self) -> None:
        if self.var_tipo_execucao.get() == TIPO_LOTE:
            self.iniciar_execucao_lote()
        else:
            self.iniciar_execucao_individual()

    def _credenciais_e_url(self) -> tuple[str, str, str]:
        usuario_rede = self.entry_usuario_rede.get().strip()
        senha = self.entry_senha.get()
        url_aghu = obter_url_ambiente_aghu(self.var_ambiente.get())

        if not usuario_rede or not senha:
            raise ValueError("Preencha usuário de rede e senha.")

        return usuario_rede, senha, url_aghu

    def _cadastro_individual(self) -> CadastroProfissionalUnidadeEntrada:
        return CadastroProfissionalUnidadeEntrada(
            profissional=self.entry_profissional.get().strip(),
            unidade_funcional=self.var_unidade_funcional.get(),
            funcao=self.var_funcao.get(),
        )

    def _bloquear_execucao(self, texto_botao: str) -> None:
        self.em_execucao = True
        self.button_executar.configure(state="disabled", text=texto_botao)
        self.segment_tipo_execucao.configure(state="disabled")
        self.checkbox_browser.configure(state="disabled")
        self.checkbox_console.configure(state="disabled")
        self.option_ambiente.configure(state="disabled")
        self.option_unidade_funcional.configure(state="disabled")
        self.option_funcao.configure(state="disabled")
        self.button_planilha_lote.configure(state="disabled")
        self.button_relatorio_lote.configure(state="disabled")

    def _liberar_execucao(self) -> None:
        self.em_execucao = False
        self.button_executar.configure(state="normal", text="Executar cadastro")
        self.segment_tipo_execucao.configure(state="normal")
        self.checkbox_browser.configure(state="normal")
        self.checkbox_console.configure(state="normal")
        self.option_ambiente.configure(state="normal")
        self.option_unidade_funcional.configure(state="normal")
        self.option_funcao.configure(state="normal")
        self.button_planilha_lote.configure(state="normal")
        self.button_relatorio_lote.configure(state="normal")

    def iniciar_execucao_individual(self) -> None:
        if self.em_execucao:
            return

        try:
            usuario_rede, senha, url_aghu = self._credenciais_e_url()
            cadastro = self._cadastro_individual()
            erros = validar_entrada(cadastro)
            if erros:
                raise ValueError("; ".join(erros))

            mostrar_browser = bool(self.var_browser.get())
            mostrar_console = bool(self.var_console.get())
        except Exception as exc:
            self._mostrar_status(f"Erro: {exc}", "red")
            return

        self._mostrar_status("Executando cadastro de profissional...", "blue")
        self._bloquear_execucao("Executando...")

        thread = threading.Thread(
            target=self._executar_individual_thread,
            args=(
                usuario_rede,
                senha,
                cadastro,
                url_aghu,
                mostrar_browser,
                mostrar_console,
            ),
            daemon=True,
        )
        thread.start()

    def _executar_individual_thread(
        self,
        usuario_rede: str,
        senha: str,
        cadastro: CadastroProfissionalUnidadeEntrada,
        url_aghu: str,
        mostrar_browser: bool,
        mostrar_console: bool,
    ) -> None:
        try:
            resultado = executar_cadastro_individual(
                usuario_rede=usuario_rede,
                senha=senha,
                cadastro=cadastro,
                url_aghu=url_aghu,
                mostrar_browser=mostrar_browser,
                mostrar_console=mostrar_console,
                diretorio_logs=LOGS_DIR,
            )
            mensagem = (
                f"{resultado.profissional}: {resultado.status} - "
                f"{resultado.detalhes}"
            )
            if resultado.status == STATUS_FUNCIONARIO_NAO_ENCONTRADO:
                mensagem = "Execução Encerrada : Funcionário não encontrado"
            cor = (
                "red"
                if resultado.status in {
                    STATUS_ERRO,
                    STATUS_CONFERIR_MANUAL,
                    STATUS_IGNORADO,
                    STATUS_FUNCIONARIO_NAO_ENCONTRADO,
                }
                else "green"
            )
            self.after(0, self._finalizar_execucao, mensagem, cor)
        except Exception as exc:
            self.after(0, self._finalizar_execucao, f"Erro: {exc}", "red")

    def iniciar_execucao_lote(self) -> None:
        if self.em_execucao:
            return

        try:
            usuario_rede, senha, url_aghu = self._credenciais_e_url()
            caminho_planilha = self.entry_planilha_lote.get().strip()
            caminho_relatorio = self.entry_relatorio_lote.get().strip()
            mostrar_browser = bool(self.var_browser.get())
            mostrar_console = bool(self.var_console.get())

            if not caminho_planilha:
                raise ValueError("Informe a planilha .xlsx de lote.")

            if not caminho_relatorio:
                caminho_relatorio = caminho_relatorio_padrao(caminho_planilha)
                self.entry_relatorio_lote.insert(0, caminho_relatorio)

            if Path(caminho_planilha).suffix.lower() != ".xlsx":
                raise ValueError("A planilha de lote deve ser um arquivo .xlsx.")

            if Path(caminho_relatorio).suffix.lower() != ".xlsx":
                raise ValueError("O relatório de saída deve ser um arquivo .xlsx.")
        except Exception as exc:
            self._mostrar_status(f"Erro: {exc}", "red")
            return

        self._mostrar_status("Executando lote de profissionais...", "blue")
        self._bloquear_execucao("Executando...")

        thread = threading.Thread(
            target=self._executar_lote_thread,
            args=(
                usuario_rede,
                senha,
                caminho_planilha,
                caminho_relatorio,
                url_aghu,
                mostrar_browser,
                mostrar_console,
            ),
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
        mostrar_browser: bool,
        mostrar_console: bool,
    ) -> None:
        try:
            resultados, relatorio = executar_cadastro_lote(
                usuario_rede=usuario_rede,
                senha=senha,
                caminho_planilha=caminho_planilha,
                caminho_relatorio=caminho_relatorio,
                url_aghu=url_aghu,
                mostrar_browser=mostrar_browser,
                mostrar_console=mostrar_console,
                diretorio_logs=LOGS_DIR,
            )
            resumo = self._resumir_resultados(resultados)
            mensagem = f"{resumo} Relatório: {relatorio}"
            cor = (
                "red"
                if any(
                    resultado.status in {
                        STATUS_ERRO,
                        STATUS_CONFERIR_MANUAL,
                    }
                    for resultado in resultados
                )
                else "green"
            )
            self.after(0, self._finalizar_execucao, mensagem, cor)
        except Exception as exc:
            self.after(0, self._finalizar_execucao, f"Erro: {exc}", "red")

    def _resumir_resultados(self, resultados) -> str:
        contagem = Counter(resultado.status for resultado in resultados)
        total = len(resultados)

        return (
            f"Lote concluído. Total: {total}. "
            f"Criados: {contagem[STATUS_CRIADO]}. "
            f"Mantidos: {contagem[STATUS_MANTIDO]}. "
            f"Funcionários não encontrados: "
            f"{contagem[STATUS_FUNCIONARIO_NAO_ENCONTRADO]}. "
            f"Conferir manualmente: {contagem[STATUS_CONFERIR_MANUAL]}. "
            f"Ignorados: {contagem[STATUS_IGNORADO]}. "
            f"Erros: {contagem[STATUS_ERRO]}."
        )

    def _finalizar_execucao(self, mensagem: str, cor: str) -> None:
        self._mostrar_status(mensagem, cor)
        self._liberar_execucao()

    def _mostrar_status(self, mensagem: str, cor: str) -> None:
        self.label_status.configure(text=mensagem, text_color=cor)


def executar_interface() -> None:
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    app = AghuProfissionaisUnidadeCirurgicaApp()
    app.mainloop()


if __name__ == "__main__":
    executar_interface()
