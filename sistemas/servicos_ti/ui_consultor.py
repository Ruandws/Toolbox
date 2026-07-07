import threading
from tkinter import BooleanVar, StringVar, filedialog
import customtkinter as ctk
from consultor_sti import prepare_search_value, run_automation, run_batch_automation

TIPO_INDIVIDUAL = "Unitária"
TIPO_LOTE = "Lote"


class ConsultorSTI(ctk.CTk):
    # -----------------------------
    # Interface - Inicialização
    # -----------------------------

    # Inicializa janela principal.
    def __init__(self):
        super().__init__()

        self.title("Serviços TI - Consultor de Usuário")
        self.geometry("720x650")
        self.minsize(640, 520)
        self.resizable(True, True)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.collect_email_var = BooleanVar(value=False)
        self.var_browser = BooleanVar(value=True)
        self.var_tipo_execucao = StringVar(value=TIPO_INDIVIDUAL)
        self.em_execucao = False

        self.label_title = ctk.CTkLabel(
            self,
            text="Serviços TI: Consultor de Usuário",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self.label_title.grid(row=0, column=0, padx=20, pady=(22, 10))

        self.frame_conteudo = ctk.CTkScrollableFrame(self)
        self.frame_conteudo.grid(row=1, column=0, padx=20, pady=8, sticky="nsew")
        self.frame_conteudo.grid_columnconfigure(0, weight=1)

        self.frame_inputs = ctk.CTkFrame(self.frame_conteudo)
        self.frame_inputs.grid(row=0, column=0, padx=0, pady=8, sticky="ew")
        self.frame_inputs.grid_columnconfigure(1, weight=1)

        self.create_login_fields()
        self.create_search_type_field()
        self.create_execution_options()
        self.create_execution_type_selector()
        self.create_single_search_fields()
        self.create_batch_fields()
        self._atualizar_tipo_execucao(TIPO_INDIVIDUAL)

        self.button_run = ctk.CTkButton(
            self.frame_conteudo,
            text="Executar Automação",
            command=self.start_automation,
            height=40,
            font=ctk.CTkFont(weight="bold"),
        )
        self.button_run.grid(row=1, column=0, padx=0, pady=(12, 8), sticky="e")

        self.label_status = ctk.CTkLabel(
            self,
            text="Pronto para execução.",
            text_color="gray",
            wraplength=680,
            justify="left",
        )
        self.label_status.grid(row=2, column=0, padx=20, pady=(8, 18), sticky="ew")

    # -----------------------------
    # Interface - Componentes
    # -----------------------------

    # Cria campos de login.
    def create_login_fields(self):
        self.label_login = ctk.CTkLabel(self.frame_inputs, text="Login:")
        self.label_login.grid(row=0, column=0, padx=10, pady=10, sticky="e")

        self.entry_login = ctk.CTkEntry(
            self.frame_inputs,
            placeholder_text="Digite seu login",
        )
        self.entry_login.grid(
            row=0,
            column=1,
            columnspan=2,
            padx=10,
            pady=10,
            sticky="ew",
        )

        self.label_password = ctk.CTkLabel(self.frame_inputs, text="Senha:")
        self.label_password.grid(row=1, column=0, padx=10, pady=10, sticky="e")

        self.entry_password = ctk.CTkEntry(
            self.frame_inputs,
            placeholder_text="Digite sua senha",
            show="*",
        )
        self.entry_password.grid(
            row=1,
            column=1,
            columnspan=2,
            padx=10,
            pady=10,
            sticky="ew",
        )

    # Cria seleção de tipo.
    def create_search_type_field(self):
        self.label_search_type = ctk.CTkLabel(
            self.frame_inputs,
            text="Pesquisar por:",
        )
        self.label_search_type.grid(row=2, column=0, padx=10, pady=10, sticky="e")

        self.combo_search_type = ctk.CTkOptionMenu(
            self.frame_inputs,
            values=["CPF", "Nome Completo"],
            command=self.on_search_type_change,
        )
        self.combo_search_type.grid(
            row=2,
            column=1,
            padx=10,
            pady=10,
            sticky="ew",
        )
        self.combo_search_type.set("CPF")

        self.checkbox_collect_email = ctk.CTkCheckBox(
            self.frame_inputs,
            text="Coletar e-mail",
            variable=self.collect_email_var,
        )
        self.checkbox_collect_email.grid(
            row=2,
            column=2,
            padx=10,
            pady=10,
            sticky="w",
        )

    # Cria opcoes de execucao.
    def create_execution_options(self):
        self.checkbox_browser = ctk.CTkCheckBox(
            self.frame_inputs,
            text="Exibir Navegador (Modo Visual)",
            variable=self.var_browser,
        )
        self.checkbox_browser.grid(
            row=3,
            column=1,
            columnspan=2,
            padx=10,
            pady=10,
            sticky="w",
        )

    # Cria seletor explicito entre execucao unitaria e lote.
    def create_execution_type_selector(self):
        self.label_tipo_execucao = ctk.CTkLabel(
            self.frame_inputs,
            text="Tipo de execução:",
        )
        self.label_tipo_execucao.grid(row=4, column=0, padx=10, pady=10, sticky="e")

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
            row=4,
            column=1,
            columnspan=2,
            padx=10,
            pady=10,
            sticky="ew",
        )
        self.segment_tipo_execucao.set(TIPO_INDIVIDUAL)

    # Cria campos de pesquisa unitaria.
    def create_single_search_fields(self):
        self.label_single_title = ctk.CTkLabel(
            self.frame_inputs,
            text="Execução unitária",
            font=ctk.CTkFont(weight="bold"),
        )
        self.label_single_title.grid(
            row=5,
            column=0,
            columnspan=3,
            padx=10,
            pady=(20, 5),
            sticky="w",
        )

        self.label_search = ctk.CTkLabel(
            self.frame_inputs,
            text="Valor da Pesquisa:",
        )
        self.label_search.grid(row=6, column=0, padx=10, pady=10, sticky="e")

        self.entry_search = ctk.CTkEntry(
            self.frame_inputs,
            placeholder_text="Digite CPF com ou sem pontuação",
        )
        self.entry_search.grid(
            row=6,
            column=1,
            columnspan=2,
            padx=10,
            pady=10,
            sticky="ew",
        )

        self.widgets_individuais = [
            self.label_single_title,
            self.label_search,
            self.entry_search,
        ]

    # Cria campos para lote.
    def create_batch_fields(self):
        self.label_spreadsheet = ctk.CTkLabel(
            self.frame_inputs,
            text="Planilha:",
        )
        self.label_spreadsheet.grid(row=7, column=0, padx=10, pady=10, sticky="e")

        self.entry_spreadsheet = ctk.CTkEntry(
            self.frame_inputs,
            placeholder_text="Caminho do arquivo .xlsx",
        )
        self.entry_spreadsheet.grid(
            row=7,
            column=1,
            padx=10,
            pady=10,
            sticky="ew",
        )

        self.button_select_spreadsheet = ctk.CTkButton(
            self.frame_inputs,
            text="Selecionar",
            width=100,
            command=self.select_spreadsheet,
        )
        self.button_select_spreadsheet.grid(row=7, column=2, padx=10, pady=10)

        self.label_report_dir = ctk.CTkLabel(
            self.frame_inputs,
            text="Pasta relatório:",
        )
        self.label_report_dir.grid(row=8, column=0, padx=10, pady=10, sticky="e")

        self.entry_report_dir = ctk.CTkEntry(
            self.frame_inputs,
            placeholder_text="Pasta onde o relatório será salvo",
        )
        self.entry_report_dir.grid(
            row=8,
            column=1,
            padx=10,
            pady=10,
            sticky="ew",
        )

        self.button_select_report_dir = ctk.CTkButton(
            self.frame_inputs,
            text="Selecionar",
            width=100,
            command=self.select_report_directory,
        )
        self.button_select_report_dir.grid(row=8, column=2, padx=10, pady=10)

        self.label_batch_info = ctk.CTkLabel(
            self.frame_inputs,
            text=(
                "Tipo CPF/Nome aplicado a todas as linhas. "
                "Coluna de entrada identificada automaticamente. "
                "Zeros à esquerda em CPF completados apenas no lote."
            ),
            text_color="gray",
            wraplength=620,
        )
        self.label_batch_info.grid(
            row=9,
            column=0,
            columnspan=3,
            padx=10,
            pady=(0, 10),
            sticky="w",
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

    def on_search_type_change(self, selected_type):
        if selected_type == "CPF":
            self.entry_search.configure(
                placeholder_text="Digite CPF com ou sem pontuação",
            )
        else:
            self.entry_search.configure(
                placeholder_text="Digite o nome completo sem números",
            )

    # Seleciona arquivo de planilha.
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

    # Seleciona pasta para relatório.
    def select_report_directory(self):
        directory = filedialog.askdirectory(
            title="Selecione a pasta de relatório",
        )

        if directory:
            self.entry_report_dir.delete(0, "end")
            self.entry_report_dir.insert(0, directory)

     # Coleta e valida credenciais.
    def _credenciais_e_url(self) -> tuple[str, str]:
        login = self.entry_login.get().strip()
        # Senhas podem conter espacos significativos; nao normalizar com strip().
        password = self.entry_password.get()

        if not login or not password:
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

        search_type = self.combo_search_type.get()
        search_value = self.entry_search.get().strip()
        spreadsheet_path = self.entry_spreadsheet.get().strip()
        report_directory = self.entry_report_dir.get().strip()
        collect_email = self.collect_email_var.get()
        mostrar_browser = bool(self.var_browser.get())
        tipo_execucao = self.var_tipo_execucao.get()

        if tipo_execucao == TIPO_LOTE:
            if not spreadsheet_path or not report_directory:
                self.show_status(
                    "Erro: Para lote, informe planilha e pasta de relatório.",
                    "red",
                )
                return

            args = (
                "batch",
                login,
                password,
                search_type,
                spreadsheet_path,
                report_directory,
                collect_email,
                mostrar_browser,
            )
            status_text = "Iniciando automação em lote..."
        
        else:
            if not search_value:
                self.show_status(
                    "Erro: Informe o valor da pesquisa.",
                    "red",
                )
                return

            try:
                clean_search_value = prepare_search_value(
                    search_type,
                    search_value,
                )
            except ValueError as exc:
                self.show_status(f"Erro: {str(exc)}", "red")
                return

            args = (
                "single",
                login,
                password,
                search_type,
                clean_search_value,
                collect_email,
                mostrar_browser,
            )
            status_text = "Iniciando automação unitária..."

        self.show_status(status_text, "blue")
        self._bloquear_execucao()

        thread = threading.Thread(
            target=self.run_playwright_task,
            args=args,
            daemon=True,
        )
        thread.start()

    # Executa tarefa no Playwright.
    def run_playwright_task(self, execution_mode, *args):
        try:
            if execution_mode == "batch":
                result_msg = run_batch_automation(*args)
            else:
                result_msg = run_automation(*args)

            color = "orange" if "Nenhum" in result_msg else "green"
            self.after(0, self.finish_automation, result_msg, color)
        except Exception as e:
            error_text = str(e)

            if error_text.startswith("Login falhou:"):
                error_msg = error_text
            else:
                error_msg = f"Erro: {error_text}"

            self.after(0, self.finish_automation, error_msg, "red")

    # Bloqueia controles durante a execucao da automacao.
    def _bloquear_execucao(self):
        self.em_execucao = True
        self.button_run.configure(state="disabled", text="Executando...")
        self.segment_tipo_execucao.configure(state="disabled")
        self.entry_login.configure(state="disabled")
        self.entry_password.configure(state="disabled")
        self.combo_search_type.configure(state="disabled")
        self.checkbox_collect_email.configure(state="disabled")
        self.checkbox_browser.configure(state="disabled")
        self.entry_search.configure(state="disabled")
        self.entry_spreadsheet.configure(state="disabled")
        self.entry_report_dir.configure(state="disabled")
        self.button_select_spreadsheet.configure(state="disabled")
        self.button_select_report_dir.configure(state="disabled")

    # Libera controles apos sucesso ou erro.
    def _liberar_execucao(self):
        self.em_execucao = False
        self.button_run.configure(state="normal", text="Executar Automação")
        self.segment_tipo_execucao.configure(state="normal")
        self.entry_login.configure(state="normal")
        self.entry_password.configure(state="normal")
        self.combo_search_type.configure(state="normal")
        self.checkbox_collect_email.configure(state="normal")
        self.checkbox_browser.configure(state="normal")
        self.entry_search.configure(state="normal")
        self.entry_spreadsheet.configure(state="normal")
        self.entry_report_dir.configure(state="normal")
        self.button_select_spreadsheet.configure(state="normal")
        self.button_select_report_dir.configure(state="normal")

    # Finaliza execucao e atualiza UI.
    def finish_automation(self, message, color):
        self.show_status(message, color)
        self._liberar_execucao()

    # Atualiza mensagem de status.
    def show_status(self, message, color):
        self.label_status.configure(text=message, text_color=color)


if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = ConsultorSTI()
    app.mainloop()
