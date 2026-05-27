import customtkinter as ctk
import threading
from search_user import run_automation

class ExtratorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Extrator - Interface Visual")
        self.geometry("450x550")

        # Configurações do layout
        self.grid_columnconfigure(0, weight=1)

        # Título
        self.label_title = ctk.CTkLabel(
            self,
            text="Extrator: Pesquisa de Usuário",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.label_title.grid(row=0, column=0, padx=20, pady=(30, 20))

        # Container para os campos
        self.frame_inputs = ctk.CTkFrame(self)
        self.frame_inputs.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.frame_inputs.grid_columnconfigure(1, weight=1)

        # Campo: Login
        self.label_login = ctk.CTkLabel(self.frame_inputs, text="Login:")
        self.label_login.grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.entry_login = ctk.CTkEntry(self.frame_inputs, placeholder_text="Digite o login de TI")
        self.entry_login.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        # Campo: Senha
        self.label_password = ctk.CTkLabel(self.frame_inputs, text="Senha:")
        self.label_password.grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.entry_password = ctk.CTkEntry(self.frame_inputs, placeholder_text="Digite a senha de TI", show="*")
        self.entry_password.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        # Campo: Tipo de Pesquisa
        self.label_search_type = ctk.CTkLabel(self.frame_inputs, text="Pesquisar por:")
        self.label_search_type.grid(row=2, column=0, padx=10, pady=10, sticky="e")
        self.combo_search_type = ctk.CTkOptionMenu(
            self.frame_inputs,
            values=["CPF", "Nome Completo"]
        )
        self.combo_search_type.grid(row=2, column=1, padx=10, pady=10, sticky="ew")
        self.combo_search_type.set("CPF") # Default

        # Campo: Valor da Pesquisa
        self.label_search = ctk.CTkLabel(self.frame_inputs, text="Valor da Pesquisa:")
        self.label_search.grid(row=3, column=0, padx=10, pady=10, sticky="e")
        self.entry_search = ctk.CTkEntry(self.frame_inputs, placeholder_text="Digite o CPF ou Nome")
        self.entry_search.grid(row=3, column=1, padx=10, pady=10, sticky="ew")

        # Botão de Execução
        self.button_run = ctk.CTkButton(
            self,
            text="Executar Automação",
            command=self.start_automation,
            font=ctk.CTkFont(weight="bold")
        )
        self.button_run.grid(row=2, column=0, padx=20, pady=30)

        # Status
        self.label_status = ctk.CTkLabel(self, text="Pronto para execução.", text_color="gray")
        self.label_status.grid(row=3, column=0, padx=20, pady=10)

    def start_automation(self):
        login = self.entry_login.get().strip()
        password = self.entry_password.get().strip()
        search_type = self.combo_search_type.get()
        search_value = self.entry_search.get().strip()

        if not login or not password or not search_value:
            self.label_status.configure(text="Erro: Preencha todos os campos!", text_color="red")
            return

        self.label_status.configure(text="Iniciando automação...", text_color="blue")
        self.button_run.configure(state="disabled", text="Executando...")

        # Inicia a automação em uma thread separada para não bloquear a UI
        thread = threading.Thread(target=self.run_playwright_task, args=(login, password, search_type, search_value))
        thread.daemon = True
        thread.start()

    def run_playwright_task(self, login, password, search_type, search_value):
        try:
            result_msg = run_automation(login, password, search_type, search_value)
            
            # Se o resultado for "Nenhum..." a cor fica laranja, senão verde
            color = "orange" if "Nenhum" in result_msg else "green"
            
            # Atualiza UI a partir da thread
            self.after(0, self.finish_automation, result_msg, color)
        except Exception as e:
            error_msg = f"Erro: {str(e)}"
            self.after(0, self.finish_automation, error_msg, "red")

    def finish_automation(self, message, color):
        self.label_status.configure(text=message, text_color=color)
        self.button_run.configure(state="normal", text="Executar Automação")

if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = ExtratorApp()
    app.mainloop()
