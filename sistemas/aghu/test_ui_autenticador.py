import tkinter.messagebox as messagebox

import customtkinter as ctk  # type: ignore

from autenticador import URL_LOGIN_AGHU, autenticar_aghu


class AppTesteLogin(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        self.title("Teste de Login AGHU")
        self.geometry("420x260")
        self.resizable(False, False)

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.label_usuario = ctk.CTkLabel(self, text="Usuário")
        self.label_usuario.pack(padx=20, pady=(20, 5), anchor="w")

        self.entry_usuario = ctk.CTkEntry(self, width=380)
        self.entry_usuario.pack(padx=20)

        self.label_senha = ctk.CTkLabel(self, text="Senha")
        self.label_senha.pack(padx=20, pady=(15, 5), anchor="w")

        self.entry_senha = ctk.CTkEntry(self, width=380, show="*")
        self.entry_senha.pack(padx=20)

        self.botao_login = ctk.CTkButton(
            self,
            text="Testar Login",
            command=self._testar_login,
        )
        self.botao_login.pack(padx=20, pady=(25, 10))

        self.label_status = ctk.CTkLabel(self, text="")
        self.label_status.pack(padx=20, pady=(5, 0))

    def _testar_login(self) -> None:
        usuario = self.entry_usuario.get()
        senha = self.entry_senha.get()

        self.botao_login.configure(state="disabled")
        self.label_status.configure(text="Executando autenticação...")
        self.update_idletasks()

        resultado = autenticar_aghu(
            usuario=usuario,
            senha=senha,
            url_login=URL_LOGIN_AGHU,
            headless=False,
            timeout_ms=15000,
            tempo_tela_principal_segundos=3,
        )

        self.botao_login.configure(state="normal")
        self.label_status.configure(text=resultado.mensagem)

        if resultado.status == "sucesso":
            messagebox.showinfo("Autenticação", "Login Efetuado")
            return

        if resultado.status == "credenciais_invalidas":
            messagebox.showerror("Autenticação", "Usuário/Senha Inválido")
            return

        messagebox.showerror("Autenticação", resultado.mensagem)


if __name__ == "__main__":
    app = AppTesteLogin()
    app.mainloop()
