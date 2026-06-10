import threading
from tkinter import filedialog
import customtkinter as ctk  # type: ignore[import-untyped]
from prorrogador_sti import (
    normalize_expiration_date,
    prepare_user_value, 
    run_automation, 
    run_batch_automation
)

class ExtratorApp(ctk.CTk):

    # -----------------------------
    # Interface - Inicialização
    # -----------------------------

    # Inicializa janela principal.
    def __init__(self):
        super().__init__()

        self.title("Extrator - Interface Visual")
        self.geometry("720x680")
        self.grid_columnconfigure(0, weight=1)

        self.label_title = ctk.CTkLabel(
            self,
            text="Extrator: Prorrogação de Usuário",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.label_title.grid(
            row=0,
            column=0,
            padx=20,
            pady=(30, 20)
        )

        self.frame_inputs = ctk.CTkFrame(self)
        self.frame_inputs.grid(
            row=1,
            column=0,
            padx=20,
            pady=10,
            sticky="ew"
        )
        self.frame_inputs.grid_columnconfigure(1, weight=1)

        self.create_login_fields()
        self.create_single_user_fields()
        self.create_batch_fields()

        self.button_run = ctk.CTkButton(
            self,
            text="Executar Automação",
            command=self.start_automation,
            font=ctk.CTkFont(weight="bold")
        )
        self.button_run.grid(
            row=2,
            column=0,
            padx=20,
            pady=30
        )

        self.label_status = ctk.CTkLabel(
            self,
            text="Pronto para execução.",
            text_color="gray",
            wraplength=640
        )
        self.label_status.grid(
            row=3,
            column=0,
            padx=20,
            pady=10
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
    
    #Máscara no campo "Nova data". Insere automaticamente "/" conforme digitação.
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

    # Cria campos de usuário único.
    def create_single_user_fields(self):
        self.label_single_title = ctk.CTkLabel(
            self.frame_inputs,
            text="Execução individual",
            font=ctk.CTkFont(weight="bold")
        )
        self.label_single_title.grid(
            row=3,
            column=0,
            columnspan=3,
            padx=10,
            pady=(20, 5),
            sticky="w"
        )

        self.label_search = ctk.CTkLabel(
            self.frame_inputs,
            text="Usuário alvo:"
        )
        self.label_search.grid(
            row=4,
            column=0,
            padx=10,
            pady=10,
            sticky="e"
        )

        self.entry_search = ctk.CTkEntry(
            self.frame_inputs,
            placeholder_text="Digite o usuário alvo"
        )
        self.entry_search.grid(
            row=4,
            column=1,
            columnspan=2,
            padx=10,
            pady=10,
            sticky="ew"
        )

    # Cria campos para lote.
    def create_batch_fields(self):
        self.label_batch_title = ctk.CTkLabel(
            self.frame_inputs,
            text="Execução em lote via planilha",
            font=ctk.CTkFont(weight="bold")
        )
        self.label_batch_title.grid(
            row=5,
            column=0,
            columnspan=3,
            padx=10,
            pady=(20, 5),
            sticky="w"
        )

        self.label_spreadsheet = ctk.CTkLabel(
            self.frame_inputs,
            text="Planilha:"
        )
        self.label_spreadsheet.grid(
            row=6,
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
            row=6,
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
            row=6,
            column=2,
            padx=10,
            pady=10
        )

        self.label_report_dir = ctk.CTkLabel(
            self.frame_inputs,
            text="Pasta relatório:"
        )
        self.label_report_dir.grid(
            row=7,
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
            row=7,
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
            row=7,
            column=2,
            padx=10,
            pady=10
        )

        self.label_batch_info = ctk.CTkLabel(
            self.frame_inputs,
            text=(
                "Para lote, informe planilha e pasta de relatório. "
                "A coluna de usuários será identificada automaticamente. "
                "Linhas com usuário vazio ou inválido entram como erro no relatório "
                "e não acionam o Playwright. "
                "O XLSX gerado conterá apenas as colunas usuário e relatório."
            ),
            text_color="gray",
            wraplength=620
        )
        self.label_batch_info.grid(
            row=8,
            column=0,
            columnspan=3,
            padx=10,
            pady=(0, 10),
            sticky="w"
        )

    # -----------------------------
    # Lógica - Eventos
    # -----------------------------

    # Seleciona arquivo de planilha.
    def select_spreadsheet(self):
        file_path = filedialog.askopenfilename(
            title="Selecione a planilha",
            filetypes=(
                ("Planilhas", "*.xlsx"),
            )
        )

        if file_path:
            self.entry_spreadsheet.delete(0, "end")
            self.entry_spreadsheet.insert(0, file_path)

    # Seleciona pasta para relatório.
    def select_report_directory(self):
        directory = filedialog.askdirectory(
            title="Selecione a pasta de relatório"
        )

        if directory:
            self.entry_report_dir.delete(0, "end")
            self.entry_report_dir.insert(0, directory)

    # Inicia processo de automação.
    def start_automation(self):
        login = self.entry_login.get().strip()
        password = self.entry_password.get().strip()
        search_value = self.entry_search.get().strip()
        expiration_date = self.entry_date.get().strip()
        spreadsheet_path = self.entry_spreadsheet.get().strip()
        report_directory = self.entry_report_dir.get().strip()

        if not login or not password or not expiration_date:
            self.show_status(
                "Erro: Preencha login, senha e nova data.",
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

        is_batch = bool(spreadsheet_path or report_directory)

        if is_batch:
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
                normalized_expiration_date
            )
            status_text = "Iniciando automação em lote..."
        else:
            if not search_value:
                self.show_status(
                    "Erro: Informe o usuário alvo ou uma planilha para lote.",
                    "red"
                )
                return

            try:
                prepared_search_value = prepare_user_value(search_value)
            except ValueError as exc:
                self.show_status(
                    f"Erro: {str(exc)}",
                    "red"
                )
                return

            args = (
                "single",
                login,
                password,
                prepared_search_value,
                normalized_expiration_date
            )
            status_text = "Iniciando automação individual..."

        self.show_status(status_text, "blue")

        self.button_run.configure(
            state="disabled",
            text="Executando..."
        )

        thread = threading.Thread(
            target=self.run_playwright_task,
            args=args
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

            self.after(
                0,
                self.finish_automation,
                result_msg,
                "green"
            )
        except Exception as e:
            error_msg = f"Erro: {str(e)}"

            self.after(
                0,
                self.finish_automation,
                error_msg,
                "red"
            )

    # Finaliza execução e atualiza UI.
    def finish_automation(self, message, color):
        self.show_status(message, color)

        self.button_run.configure(
            state="normal",
            text="Executar Automação"
        )

    # Atualiza mensagem de status.
    def show_status(self, message, color):
        self.label_status.configure(
            text=message,
            text_color=color
        )

if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    app = ExtratorApp()
    app.mainloop()
