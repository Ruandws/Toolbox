import ctypes
import os
import sys
import threading
from tkinter import BooleanVar, StringVar, filedialog
from pathlib import Path

import customtkinter as ctk  # type: ignore[import-untyped]
from prorrogador_sti import (
    STATUS_NAO_ENCONTRADO,
    classify_batch_row_status,
    normalize_expiration_date,
    prepare_user_value,
    run_automation,
    run_batch_automation,
    run_multi_automation
)

_TERMINAL_ALLOCATED_BY_APP = False
_STDOUT_BEFORE_CONSOLE = None
_STDERR_BEFORE_CONSOLE = None

TIPO_INDIVIDUAL = "Unitária"
TIPO_LOTE = "Lote"
MAX_USUARIOS_MANUAIS = 5

# Exibe terminal no Windows quando o app estiver sem console anexado.
def set_terminal_visibility(show_terminal: bool) -> None:
    global _TERMINAL_ALLOCATED_BY_APP, _STDOUT_BEFORE_CONSOLE, _STDERR_BEFORE_CONSOLE

    if os.name != "nt":
        return

    try:
        kernel32 = ctypes.windll.kernel32
        has_console = bool(kernel32.GetConsoleWindow())

        if show_terminal:
            if has_console:
                return

            if kernel32.AllocConsole():
                _TERMINAL_ALLOCATED_BY_APP = True
                _STDOUT_BEFORE_CONSOLE = sys.stdout
                _STDERR_BEFORE_CONSOLE = sys.stderr
                sys.stdout = open(
                    "CONOUT$",
                    "w",
                    encoding="utf-8",
                    buffering=1
                )
                sys.stderr = open(
                    "CONOUT$",
                    "w",
                    encoding="utf-8",
                    buffering=1
                )

            return

        if _TERMINAL_ALLOCATED_BY_APP and has_console:
            conout_stdout = sys.stdout
            conout_stderr = sys.stderr
            sys.stdout = _STDOUT_BEFORE_CONSOLE or sys.__stdout__
            sys.stderr = _STDERR_BEFORE_CONSOLE or sys.__stderr__
            _STDOUT_BEFORE_CONSOLE = None
            _STDERR_BEFORE_CONSOLE = None
            try:
                conout_stdout.close()
                conout_stderr.close()
            except Exception:
                pass
            kernel32.FreeConsole()
            _TERMINAL_ALLOCATED_BY_APP = False

    except Exception:
        return

class ProrrogadorSTI(ctk.CTk):

    # -----------------------------
    # Interface - Inicialização
    # -----------------------------

    # Inicializa janela principal.
    def __init__(self):
        super().__init__()

        self.title("Serviços TI - Prorrogação de Usuário")
        self.geometry("720x760")
        self.minsize(640, 520)
        self.resizable(True, True)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.var_browser = BooleanVar(value=True)
        self.var_tipo_execucao = StringVar(value=TIPO_INDIVIDUAL)
        self.em_execucao = False
        self.linhas_usuarios_individual = []

        self.label_title = ctk.CTkLabel(
            self,
            text="Serviços TI: Prorrogação de Usuário",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.label_title.grid(
            row=0,
            column=0,
            padx=20,
            pady=(22, 10)
        )

        self.frame_conteudo = ctk.CTkScrollableFrame(self)
        self.frame_conteudo.grid(
            row=1,
            column=0,
            padx=20,
            pady=8,
            sticky="nsew"
        )
        self.frame_conteudo.grid_columnconfigure(0, weight=1)

        self.frame_inputs = ctk.CTkFrame(self.frame_conteudo)
        self.frame_inputs.grid(
            row=0,
            column=0,
            padx=0,
            pady=8,
            sticky="ew"
        )
        self.frame_inputs.grid_columnconfigure(1, weight=1)

        self.create_login_fields()
        self.create_execution_options()
        self.create_execution_type_selector()
        self.create_single_user_fields()
        self.create_batch_fields()
        self._atualizar_tipo_execucao(TIPO_INDIVIDUAL)

        self.button_run = ctk.CTkButton(
            self.frame_conteudo,
            text="Executar Automação",
            command=self.start_automation,
            height=40,
            font=ctk.CTkFont(weight="bold")
        )
        self.button_run.grid(
            row=1,
            column=0,
            padx=0,
            pady=(12, 8),
            sticky="e"
        )

        self.textbox_resultado = ctk.CTkTextbox(
            self,
            height=150,
            wrap="word",
            state="disabled"
        )
        self.textbox_resultado.grid(
            row=2,
            column=0,
            padx=20,
            pady=(0, 8),
            sticky="ew"
        )
        self.textbox_resultado.grid_remove()

        self.label_status = ctk.CTkLabel(
            self,
            text="Pronto para execução.",
            text_color="gray",
            wraplength=680,
            justify="left"
        )
        self.label_status.grid(
            row=3,
            column=0,
            padx=20,
            pady=(8, 18),
            sticky="ew"
        )

    # -----------------------------
    # Interface - Componentes
    # -----------------------------

    # Cria campos de login.
    def create_login_fields(self):
        self.label_login = ctk.CTkLabel(
            self.frame_inputs,
            text="Login:"
        )
        self.label_login.grid(
            row=0,
            column=0,
            padx=10,
            pady=10,
            sticky="e"
        )

        self.entry_login = ctk.CTkEntry(
            self.frame_inputs,
            placeholder_text="Digite seu login"
        )
        self.entry_login.grid(
            row=0,
            column=1,
            columnspan=2,
            padx=10,
            pady=10,
            sticky="ew"
        )

        self.label_password = ctk.CTkLabel(
            self.frame_inputs,
            text="Senha:"
        )
        self.label_password.grid(
            row=1,
            column=0,
            padx=10,
            pady=10,
            sticky="e"
        )

        self.entry_password = ctk.CTkEntry(
            self.frame_inputs,
            placeholder_text="Digite sua senha",
            show="*"
        )
        self.entry_password.grid(
            row=1,
            column=1,
            columnspan=2,
            padx=10,
            pady=10,
            sticky="ew"
        )

        self.label_date = ctk.CTkLabel(
            self.frame_inputs,
            text="Nova data:"
        )
        self.label_date.grid(
            row=2,
            column=0,
            padx=10,
            pady=10,
            sticky="e"
        )

        self.entry_date = ctk.CTkEntry(
            self.frame_inputs,
            placeholder_text="dd/mm/aaaa"
        )
        self.entry_date.bind(
            "<KeyRelease>",
            self.format_expiration_date_input
        )
        self.entry_date.grid(
            row=2,
            column=1,
            columnspan=2,
            padx=10,
            pady=10,
            sticky="ew"
        )

    # Cria opções de execução.
    def create_execution_options(self):
        self.label_execution_options = ctk.CTkLabel(
            self.frame_inputs,
            text="Opções de execução",
            font=ctk.CTkFont(weight="bold")
        )
        self.label_execution_options.grid(
            row=3,
            column=0,
            columnspan=3,
            padx=10,
            pady=(20, 5),
            sticky="w"
        )

        self.checkbox_browser = ctk.CTkCheckBox(
            self.frame_inputs,
            text="Exibir navegador (Modo Visual)",
            variable=self.var_browser
        )
        self.checkbox_browser.grid(
            row=4,
            column=1,
            columnspan=2,
            padx=10,
            pady=8,
            sticky="w"
        )

        self.var_show_terminal_logs = BooleanVar(value=False)
        self.switch_terminal_logs = ctk.CTkSwitch(
            self.frame_inputs,
            text="Exibir terminal/logs de execução",
            variable=self.var_show_terminal_logs
        )
        self.switch_terminal_logs.grid(
            row=5,
            column=1,
            columnspan=2,
            padx=10,
            pady=8,
            sticky="w"
        )
        
    # Cria seletor explicito entre execucao unitaria e lote.
    def create_execution_type_selector(self):
        self.label_tipo_execucao = ctk.CTkLabel(
            self.frame_inputs,
            text="Tipo de execução:"
        )
        self.label_tipo_execucao.grid(
            row=6,
            column=0,
            padx=10,
            pady=10,
            sticky="e"
        )

        self.segment_tipo_execucao = ctk.CTkSegmentedButton(
            self.frame_inputs,
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
            row=6,
            column=1,
            columnspan=2,
            padx=10,
            pady=10,
            sticky="ew"
        )
        self.segment_tipo_execucao.set(TIPO_INDIVIDUAL)

    # Mascara no campo "Nova data". Insere automaticamente "/" conforme digitacao.
    def format_expiration_date_input(self, event=None):
        raw_value = self.entry_date.get()
        digits = "".join(
            char for char in raw_value
            if char.isdigit()
        )[:8]

        if len(digits) <= 2:
            formatted_value = digits
        elif len(digits) <= 4:
            formatted_value = f"{digits[:2]}/{digits[2:]}"
        else:
            formatted_value = f"{digits[:2]}/{digits[2:4]}/{digits[4:]}"

        if raw_value == formatted_value:
            return

        self.entry_date.delete(0, "end")
        self.entry_date.insert(0, formatted_value)
        self.entry_date.icursor("end")

    # Cria lista dinâmica de usuários para execução unitária.
    def create_single_user_fields(self):
        self.label_single_title = ctk.CTkLabel(
            self.frame_inputs,
            text="Execução unitária",
            font=ctk.CTkFont(weight="bold")
        )
        self.label_single_title.grid(
            row=7,
            column=0,
            columnspan=3,
            padx=10,
            pady=(20, 5),
            sticky="w"
        )

        self.label_search = ctk.CTkLabel(
            self.frame_inputs,
            text="Usuários alvo:"
        )
        self.label_search.grid(
            row=8,
            column=0,
            padx=10,
            pady=(10, 0),
            sticky="ne"
        )

        self.frame_usuarios = ctk.CTkFrame(
            self.frame_inputs,
            fg_color="transparent"
        )
        self.frame_usuarios.grid(
            row=8,
            column=1,
            columnspan=2,
            padx=10,
            pady=(8, 4),
            sticky="ew"
        )
        self.frame_usuarios.grid_columnconfigure(0, weight=1)

        # Container das linhas de usuário
        self.frame_linhas = ctk.CTkFrame(
            self.frame_usuarios,
            fg_color="transparent"
        )
        self.frame_linhas.grid(row=0, column=0, sticky="ew")
        self.frame_linhas.grid_columnconfigure(0, weight=1)

        # Rodapé: botão adicionar + aviso de limite
        self.frame_acoes = ctk.CTkFrame(
            self.frame_usuarios,
            fg_color="transparent"
        )
        self.frame_acoes.grid(row=1, column=0, pady=(6, 0), sticky="ew")
        self.frame_acoes.grid_columnconfigure(1, weight=1)

        self.button_adicionar = ctk.CTkButton(
            self.frame_acoes,
            text="+ Adicionar usuário",
            width=160,
            height=32,
            command=self.adicionar_linha_usuario
        )
        self.button_adicionar.grid(row=0, column=0, sticky="w")

        self.label_limite = ctk.CTkLabel(
            self.frame_acoes,
            text="",
            text_color=("#9A3412", "#FDBA74")
        )
        self.label_limite.grid(row=0, column=1, padx=(10, 0), sticky="w")

        self.widgets_individuais = [
            self.label_single_title,
            self.label_search,
            self.frame_usuarios,
        ]

        self.adicionar_linha_usuario()

    # Adiciona uma nova linha de usuário à lista.
    def adicionar_linha_usuario(self) -> None:
        if len(self.linhas_usuarios_individual) >= MAX_USUARIOS_MANUAIS:
            self._atualizar_estado_lista()
            return

        frame_linha = ctk.CTkFrame(
            self.frame_linhas,
            fg_color="transparent"
        )
        frame_linha.grid(
            row=len(self.linhas_usuarios_individual),
            column=0,
            pady=3,
            sticky="ew"
        )
        frame_linha.grid_columnconfigure(0, weight=1)
        frame_linha.grid_columnconfigure(1, minsize=40)

        entry_valor = ctk.CTkEntry(
            frame_linha,
            placeholder_text="Digite o usuário alvo",
            height=32
        )
        entry_valor.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        linha = {"frame": frame_linha, "valor": entry_valor}

        button_remover = ctk.CTkButton(
            frame_linha,
            text="\U0001F5D1",
            width=36,
            height=32,
            fg_color=("#E5E7EB", "#2B2B2B"),
            hover_color=("#D1D5DB", "#3A3A3A"),
            text_color=("#991B1B", "#FCA5A5"),
            command=lambda linha_param=linha: self.remover_linha_usuario(linha_param)
        )
        button_remover.grid(row=0, column=1, sticky="e")

        linha["remover"] = button_remover
        self.linhas_usuarios_individual.append(linha)
        self._atualizar_estado_lista()

        if len(self.linhas_usuarios_individual) > 1:
            entry_valor.focus()

    # Remove uma linha de usuário da lista.
    def remover_linha_usuario(self, linha_usuario) -> None:
        if len(self.linhas_usuarios_individual) <= 1:
            self._atualizar_estado_lista()
            return

        if linha_usuario not in self.linhas_usuarios_individual:
            return

        linha_usuario["frame"].destroy()
        self.linhas_usuarios_individual.remove(linha_usuario)

        for indice, linha in enumerate(self.linhas_usuarios_individual):
            linha["frame"].grid_configure(row=indice)

        self._atualizar_estado_lista()

    # Coleta os valores de usuário da lista para envio ao backend.
    def coletar_usuarios(self) -> list:
        return [
            linha["valor"].get().strip()
            for linha in self.linhas_usuarios_individual
        ]

    # Atualiza estados visuais da lista (botão adicionar, lixeiras, aviso de limite).
    def _atualizar_estado_lista(self) -> None:
        limite_atingido = len(self.linhas_usuarios_individual) >= MAX_USUARIOS_MANUAIS
        em_execucao = self.em_execucao

        estado_adicionar = "disabled" if em_execucao or limite_atingido else "normal"
        estado_campos = "disabled" if em_execucao else "normal"
        estado_remover = (
            "normal"
            if not em_execucao and len(self.linhas_usuarios_individual) > 1
            else "disabled"
        )

        self.button_adicionar.configure(state=estado_adicionar)
        self.label_limite.configure(
            text=(
                f"Limite de {MAX_USUARIOS_MANUAIS} usuários atingido."
                if limite_atingido
                else ""
            )
        )

        for linha in self.linhas_usuarios_individual:
            linha["valor"].configure(state=estado_campos)
            linha["remover"].configure(state=estado_remover)

    # Cria campos para lote.
    def create_batch_fields(self):
        self.label_spreadsheet = ctk.CTkLabel(
            self.frame_inputs,
            text="Planilha:"
        )
        self.label_spreadsheet.grid(
            row=9,
            column=0,
            padx=10,
            pady=10,
            sticky="e"
        )

        self.entry_spreadsheet = ctk.CTkEntry(
            self.frame_inputs,
            placeholder_text="Caminho do arquivo .xlsx"
        )
        self.entry_spreadsheet.grid(
            row=9,
            column=1,
            padx=10,
            pady=10,
            sticky="ew"
        )

        self.button_select_spreadsheet = ctk.CTkButton(
            self.frame_inputs,
            text="Selecionar",
            width=100,
            command=self.select_spreadsheet
        )
        self.button_select_spreadsheet.grid(
            row=9,
            column=2,
            padx=10,
            pady=10
        )

        self.label_report_dir = ctk.CTkLabel(
            self.frame_inputs,
            text="Pasta relatório:"
        )
        self.label_report_dir.grid(
            row=10,
            column=0,
            padx=10,
            pady=10,
            sticky="e"
        )

        self.entry_report_dir = ctk.CTkEntry(
            self.frame_inputs,
            placeholder_text="Pasta onde o relatório será salvo"
        )
        self.entry_report_dir.grid(
            row=10,
            column=1,
            padx=10,
            pady=10,
            sticky="ew"
        )

        self.button_select_report_dir = ctk.CTkButton(
            self.frame_inputs,
            text="Selecionar",
            width=100,
            command=self.select_report_directory
        )
        self.button_select_report_dir.grid(
            row=10,
            column=2,
            padx=10,
            pady=10
        )

        self.label_batch_info = ctk.CTkLabel(
            self.frame_inputs,
            text=(
                "Para lote, informe planilha e pasta de relatório."
            ),
            text_color="gray",
            wraplength=620
        )
        self.label_batch_info.grid(
            row=11,
            column=0,
            columnspan=3,
            padx=10,
            pady=(0, 10),
            sticky="w"
        )

        self.widgets_lote = [
            self.label_spreadsheet,
            self.entry_spreadsheet,
            self.button_select_spreadsheet,
            self.label_report_dir,
            self.entry_report_dir,
            self.button_select_report_dir,
            self.label_batch_info,
        ]

    # -----------------------------
    # Lógica - Eventos
    # -----------------------------

    # Alterna campos visiveis conforme tipo de execucao selecionado.
    def _atualizar_tipo_execucao(self, tipo: str):
        for widget in self.widgets_individuais:
            widget.grid_remove()

        for widget in self.widgets_lote:
            widget.grid_remove()

        widgets_visiveis = (
            self.widgets_individuais
            if tipo == TIPO_INDIVIDUAL
            else self.widgets_lote
        )

        for widget in widgets_visiveis:
            widget.grid()

        self._atualizar_visual_segmented_button(tipo)

    # Ajusta contraste do CTkSegmentedButton no tema claro/escuro.
    def _atualizar_visual_segmented_button(self, valor_selecionado: str):
        if "segment_tipo_execucao" not in self.__dict__:
            return

        for valor, button in self.segment_tipo_execucao._buttons_dict.items():
            if valor == valor_selecionado:
                button.configure(text_color="white")
            else:
                button.configure(text_color=("#1F6AA5", "#3B8ED0"))

     # Seleciona arquivo de planilha e sugere pasta padrão do relatório.
    def select_spreadsheet(self):
        file_path = filedialog.askopenfilename(
            title="Selecione a planilha",
            filetypes=(
                ("Excel / Planilhas", "*.xlsx"),
            ),
        )

        if file_path:
            self.entry_spreadsheet.delete(0, "end")
            self.entry_spreadsheet.insert(0, file_path)

            if not self.entry_report_dir.get().strip():
                self.entry_report_dir.insert(0, str(Path(file_path).parent))

    # Seleciona pasta para relatório.
    def select_report_directory(self):
        directory = filedialog.askdirectory(
            title="Selecione a pasta de relatório"
        )

        if directory:
            self.entry_report_dir.delete(0, "end")
            self.entry_report_dir.insert(0, directory)

    # Coleta e valida login e senha.
    def _credenciais_e_url(self) -> tuple[str, str]:
        login = self.entry_login.get().strip()
        # Senhas podem conter espacos significativos; nao normalizar com strip().
        password = self.entry_password.get()

        if not login or not password.strip():
            raise ValueError("Preencha login e senha.")

        return login, password

    # Inicia processo de automação.
    def start_automation(self):
        if self.em_execucao:
            return

        try:
            login, password = self._credenciais_e_url()
        except ValueError as exc:
            self.show_status(f"Erro: {exc}", "red")
            return

        expiration_date = self.entry_date.get().strip()
        spreadsheet_path = self.entry_spreadsheet.get().strip()
        report_directory = self.entry_report_dir.get().strip()
        show_terminal_logs = bool(self.var_show_terminal_logs.get())
        mostrar_browser = bool(self.var_browser.get())
        tipo_execucao = self.var_tipo_execucao.get()

        if not expiration_date:
            self.show_status(
                "Erro: Preencha a nova data.",
                "red"
            )
            return

        if not mostrar_browser and not show_terminal_logs:
            self.show_status(
                "Erro: Para executar em modo headless, habilite também "
                "terminal/logs de execução.",
                "red"
            )
            return

        try:
            normalized_expiration_date = normalize_expiration_date(
                expiration_date
            )
        except ValueError as exc:
            self.show_status(
                f"Erro: {str(exc)}",
                "red"
            )
            return

        if tipo_execucao == TIPO_LOTE:
            if not spreadsheet_path or not report_directory:
                self.show_status(
                    "Erro: Para lote, informe planilha e pasta de relatório.",
                    "red"
                )
                return

            args = (
                "batch",
                login,
                password,
                spreadsheet_path,
                report_directory,
                normalized_expiration_date,
                show_terminal_logs,
                mostrar_browser
            )
            status_text = "Iniciando automação em lote..."
        else:
            usuarios_brutos = self.coletar_usuarios()
            usuarios_validos = []

            for valor in usuarios_brutos:
                if not valor:
                    continue

                try:
                    prepared_user = prepare_user_value(valor)
                except ValueError as exc:
                    self.show_status(
                        f"Erro em '{valor}': {str(exc)}",
                        "red"
                    )
                    return

                usuarios_validos.append(prepared_user)

            if not usuarios_validos:
                self.show_status(
                    "Erro: Informe ao menos um usuário alvo.",
                    "red"
                )
                return

            args = (
                "multi",
                login,
                password,
                normalized_expiration_date,
                usuarios_validos,
                show_terminal_logs,
                mostrar_browser,
            )
            status_text = "Iniciando automação unitária..."
        set_terminal_visibility(show_terminal_logs)
        self.show_status(status_text, "blue")
        self.mostrar_resultado_detalhado("")
        self._bloquear_execucao()

        thread = threading.Thread(
            target=self.run_playwright_task,
            args=args,
            daemon=True
        )
        thread.start()

    # Executa tarefa no Playwright.
    def run_playwright_task(self, execution_mode, *args):
        try:
            if execution_mode == "batch":
                result_msg = run_batch_automation(*args)
                detail = ""
                color = (
                    "orange"
                    if classify_batch_row_status(result_msg) == STATUS_NAO_ENCONTRADO
                    else "green"
                )
            elif execution_mode == "multi":
                result_msg, color, detail = run_multi_automation(*args)
            else:
                result_msg = run_automation(*args)
                detail = ""
                color = (
                    "orange"
                    if classify_batch_row_status(result_msg) == STATUS_NAO_ENCONTRADO
                    else "green"
                )

            self.after(
                0,
                self.finish_automation,
                result_msg,
                color,
                detail
            )
        except Exception as e:
            error_msg = f"Erro: {str(e)}"

            self.after(
                0,
                self.finish_automation,
                error_msg,
                "red",
                ""
            )

    # Bloqueia controles durante a execucao da automacao.
    def _bloquear_execucao(self):
        self.em_execucao = True
        self.button_run.configure(
            state="disabled",
            text="Executando..."
        )
        self.segment_tipo_execucao.configure(state="disabled")
        self.entry_login.configure(state="disabled")
        self.entry_password.configure(state="disabled")
        self.entry_date.configure(state="disabled")
        self.entry_spreadsheet.configure(state="disabled")
        self.entry_report_dir.configure(state="disabled")
        self.button_select_spreadsheet.configure(state="disabled")
        self.button_select_report_dir.configure(state="disabled")
        self.checkbox_browser.configure(state="disabled")
        self.switch_terminal_logs.configure(state="disabled")
        self._atualizar_estado_lista()

    # Libera controles apos sucesso ou erro.
    def _liberar_execucao(self):
        self.em_execucao = False
        self.button_run.configure(
            state="normal",
            text="Executar Automação"
        )
        self.segment_tipo_execucao.configure(state="normal")
        self.entry_login.configure(state="normal")
        self.entry_password.configure(state="normal")
        self.entry_date.configure(state="normal")
        self.entry_spreadsheet.configure(state="normal")
        self.entry_report_dir.configure(state="normal")
        self.button_select_spreadsheet.configure(state="normal")
        self.button_select_report_dir.configure(state="normal")
        self.checkbox_browser.configure(state="normal")
        self.switch_terminal_logs.configure(state="normal")
        self._atualizar_estado_lista()

    # Finaliza execucao e atualiza UI.
    def finish_automation(self, message, color, detail=""):
        self.show_status(message, color)
        self.mostrar_resultado_detalhado(detail)
        self._liberar_execucao()

    # Atualiza mensagem de status.
    def show_status(self, message, color):
        self.label_status.configure(
            text=message,
            text_color=color
        )

    # Exibe ou oculta o detalhamento por usuário da execução unitária.
    def mostrar_resultado_detalhado(self, texto: str) -> None:
        if not texto:
            self.textbox_resultado.grid_remove()
            return

        self.textbox_resultado.configure(state="normal")
        self.textbox_resultado.delete("1.0", "end")
        self.textbox_resultado.insert("1.0", texto)
        self.textbox_resultado.configure(state="disabled")
        self.textbox_resultado.grid()

if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    app = ProrrogadorSTI()
    app.mainloop()
