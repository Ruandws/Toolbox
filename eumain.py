import customtkinter as ctk
import threading

from extend_user import run_automation


class ExtratorApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("Extrator - Interface Visual")
        self.geometry("450x550")

        # Configuração layout
        self.grid_columnconfigure(0, weight=1)

        # Título
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

        # Frame principal
        self.frame_inputs = ctk.CTkFrame(self)

        self.frame_inputs.grid(
            row=1,
            column=0,
            padx=20,
            pady=10,
            sticky="ew"
        )

        self.frame_inputs.grid_columnconfigure(1, weight=1)

        # Login
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
            padx=10,
            pady=10,
            sticky="ew"
        )

        # Senha
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
            padx=10,
            pady=10,
            sticky="ew"
        )

        # Usuário alvo
        self.label_search = ctk.CTkLabel(
            self.frame_inputs,
            text="Usuário alvo:"
        )

        self.label_search.grid(
            row=2,
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
            row=2,
            column=1,
            padx=10,
            pady=10,
            sticky="ew"
        )

        # Nova data
        self.label_date = ctk.CTkLabel(
            self.frame_inputs,
            text="Nova data:"
        )

        self.label_date.grid(
            row=3,
            column=0,
            padx=10,
            pady=10,
            sticky="e"
        )

        self.entry_date = ctk.CTkEntry(
            self.frame_inputs,
            placeholder_text="dd/mm/aaaa"
        )

        self.entry_date.grid(
            row=3,
            column=1,
            padx=10,
            pady=10,
            sticky="ew"
        )

        # Botão
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

        # Status
        self.label_status = ctk.CTkLabel(
            self,
            text="Pronto para execução.",
            text_color="gray"
        )

        self.label_status.grid(
            row=3,
            column=0,
            padx=20,
            pady=10
        )

    def start_automation(self):

        login = self.entry_login.get().strip()
        password = self.entry_password.get().strip()
        search_value = self.entry_search.get().strip()
        expiration_date = self.entry_date.get().strip()

        if (
            not login
            or not password
            or not search_value
            or not expiration_date
        ):
            self.label_status.configure(
                text="Erro: Preencha todos os campos!",
                text_color="red"
            )
            return

        self.label_status.configure(
            text="Iniciando automação...",
            text_color="blue"
        )

        self.button_run.configure(
            state="disabled",
            text="Executando..."
        )

        thread = threading.Thread(
            target=self.run_playwright_task,
            args=(
                login,
                password,
                search_value,
                expiration_date
            )
        )

        thread.daemon = True
        thread.start()

    def run_playwright_task(
        self,
        login,
        password,
        search_value,
        expiration_date
    ):

        try:

            result_msg = run_automation(
                login,
                password,
                search_value,
                expiration_date
            )

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

    def finish_automation(self, message, color):

        self.label_status.configure(
            text=message,
            text_color=color
        )

        self.button_run.configure(
            state="normal",
            text="Executar Automação"
        )


if __name__ == "__main__":

    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    app = ExtratorApp()
    app.mainloop()
