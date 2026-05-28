import threading
from tkinter import filedialog

import customtkinter as ctk

from consultor_sti import run_automation, run_batch_automation


class ExtratorApp(ctk.CTk):
    # -----------------------------
    # Interface - Inicialização
    # -----------------------------

    # Inicializa janela principal.
    def __init__(self):
        super().__init__()

        self.title("Extrator - Interface Visual")
        self.geometry("720x650")
        self.grid_columnconfigure(0, weight=1)

        self.label_title = ctk.CTkLabel(
            self,
            text="Extrator: Pesquisa de Usuário",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self.label_title.grid(row=0, column=0, padx=20, pady=(30, 20))

        self.frame_inputs = ctk.CTkFrame(self)
        self.frame_inputs.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.frame_inputs.grid_columnconfigure(1, weight=1)

        self.create_login_fields()
        self.create_search_type_field()
        self.create_single_search_fields()
        self.create_batch_fields()

        self.button_run = ctk.CTkButton(
            self,
            text="Executar Automação",
            command=self.start_automation,
            font=ctk.CTkFont(weight="bold"),
        )
        self.button_run.grid(row=2, column=0, padx=20, pady=30)

        self.label_status = ctk.CTkLabel(
            self,
            text="Pronto para execução.",
            text_color="gray",
            wraplength=640,
        )
        self.label_status.grid(row=3, column=0, padx=20, pady=10)

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
            columnspan=2,
            padx=10,
            pady=10,
            sticky="ew",
        )
        self.combo_search_type.set("CPF")

    # Cria campos de pesquisa única.
    def create_single_search_fields(self):
        self.label_single_title = ctk.CTkLabel(
            self.frame_inputs,
            text="Execução individual",
            font=ctk.CTkFont(weight="bold"),
        )
        self.label_single_title.grid(
            row=3,
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
        self.label_search.grid(row=4, column=0, padx=10, pady=10, sticky="e")

        self.entry_search = ctk.CTkEntry(
            self.frame_inputs,
            placeholder_text="Digite apenas números para CPF",
        )
        self.entry_search.grid(
            row=4,
            column=1,
            columnspan=2,
            padx=10,
            pady=10,
            sticky="ew",
        )
        self.entry_search.bind("<KeyRelease>", self.sanitize_search_entry)

    # Cria campos para lote.
    def create_batch_fields(self):
        self.label_batch_title = ctk.CTkLabel(
            self.frame_inputs,
            text="Execução em lote via planilha",
            font=ctk.CTkFont(weight="bold"),
        )
        self.label_batch_title.grid(
            row=5,
            column=0,
            columnspan=3,
            padx=10,
            pady=(20, 5),
            sticky="w",
        )

        self.label_spreadsheet = ctk.CTkLabel(
            self.frame_inputs,
            text="Planilha:",
        )
        self.label_spreadsheet.grid(row=6, column=0, padx=10, pady=10, sticky="e")

        self.entry_spreadsheet = ctk.CTkEntry(
            self.frame_inputs,
            placeholder_text="Caminho do arquivo .xlsx ou .csv",
        )
        self.entry_spreadsheet.grid(
            row=6,
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
        self.button_select_spreadsheet.grid(row=6, column=2, padx=10, pady=10)

        self.label_report_dir = ctk.CTkLabel(
            self.frame_inputs,
            text="Pasta relatório:",
        )
        self.label_report_dir.grid(row=7, column=0, padx=10, pady=10, sticky="e")

        self.entry_report_dir = ctk.CTkEntry(
            self.frame_inputs,
            placeholder_text="Pasta onde o relatório será salvo",
        )
        self.entry_report_dir.grid(
            row=7,
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
        self.button_select_report_dir.grid(row=7, column=2, padx=10, pady=10)

        self.label_batch_info = ctk.CTkLabel(
            self.frame_inputs,
            text=(
                "Para lote, selecione a planilha e a pasta de relatório. "
                "O tipo CPF/Nome Completo acima será usado para todas as linhas. "
                "A coluna de entrada será identificada automaticamente."
            ),
            text_color="gray",
            wraplength=620,
        )
        self.label_batch_info.grid(
            row=8,
            column=0,
            columnspan=3,
            padx=10,
            pady=(0, 10),
            sticky="w",
        )

    # -----------------------------
    # Lógica - Eventos
    # -----------------------------

    # Atualiza estado do tipo.
    def on_search_type_change(self, selected_type):
        if selected_type == "CPF":
            self.entry_search.configure(
                placeholder_text="Digite apenas números para CPF",
            )
        else:
            self.entry_search.configure(
                placeholder_text="Digite o nome completo sem números",
            )

        self.sanitize_search_entry()

    # Sanitiza entrada de pesquisa.
    def sanitize_search_entry(self, event=None):
        search_type = self.combo_search_type.get()
        current_value = self.entry_search.get()

        if search_type == "CPF":
            sanitized_value = "".join(
                char for char in current_value
                if char.isdigit()
            )
        else:
            sanitized_value = "".join(
                char for char in current_value
                if not char.isdigit()
            )

        if sanitized_value != current_value:
            cursor_position = self.entry_search.index("insert")
            self.entry_search.delete(0, "end")
            self.entry_search.insert(0, sanitized_value)
            self.entry_search.icursor(
                min(cursor_position, len(sanitized_value))
            )

    # Seleciona arquivo de planilha.
    def select_spreadsheet(self):
        file_path = filedialog.askopenfilename(
            title="Selecione a planilha",
            filetypes=(
                ("Planilhas", "*.xlsx *.csv"),
                ("Excel", "*.xlsx"),
                ("CSV", "*.csv"),
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

    # Inicia processo de automação.
    def start_automation(self):
        login = self.entry_login.get().strip()
        password = self.entry_password.get().strip()
        search_type = self.combo_search_type.get()
        search_value = self.entry_search.get().strip()
        spreadsheet_path = self.entry_spreadsheet.get().strip()
        report_directory = self.entry_report_dir.get().strip()

        if not login or not password:
            self.show_status(
                "Erro: Preencha login e senha.",
                "red",
            )
            return

        is_batch = bool(spreadsheet_path or report_directory)

        if is_batch:
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
            )
            status_text = "Iniciando automação em lote..."
        else:
            if not search_value:
                self.show_status(
                    "Erro: Informe o valor da pesquisa ou uma planilha para lote.",
                    "red",
                )
                return

            args = (
                "single",
                login,
                password,
                search_type,
                search_value,
            )
            status_text = "Iniciando automação individual..."

        self.show_status(status_text, "blue")
        self.button_run.configure(state="disabled", text="Executando...")

        thread = threading.Thread(
            target=self.run_playwright_task,
            args=args,
        )
        thread.daemon = True
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
            error_msg = f"Erro: {str(e)}"
            self.after(0, self.finish_automation, error_msg, "red")

    # Finaliza execução e atualiza UI.
    def finish_automation(self, message, color):
        self.show_status(message, color)
        self.button_run.configure(state="normal", text="Executar Automação")

    # Atualiza mensagem de status.
    def show_status(self, message, color):
        self.label_status.configure(text=message, text_color=color)


if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = ExtratorApp()
    app.mainloop()
