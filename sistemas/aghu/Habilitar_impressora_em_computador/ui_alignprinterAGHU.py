import ctypes
import os
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from playwright.sync_api import sync_playwright

sys.path.append(str(Path(__file__).resolve().parent.parent))

from PrinterAGHU import (
    fazer_login,
    navegar_ate_modulo,
    processar_computadores,
    validate_spreadsheet_extension,
)
from autenticador import AGHU_URL, AGHU_URL_HOMOLOGACAO

BASE_DIR = Path(__file__).resolve().parent
AMBIENTE_PRODUCAO = "Produção"
AMBIENTE_HOMOLOGACAO = "Homologação"
URLS_AMBIENTE_AGHU = {
    AMBIENTE_PRODUCAO: AGHU_URL,
    AMBIENTE_HOMOLOGACAO: AGHU_URL_HOMOLOGACAO,
}


def obter_url_ambiente_aghu(ambiente: str) -> str:
    return URLS_AMBIENTE_AGHU.get(ambiente, AGHU_URL)


def esconder_console_windows() -> None:
    if os.name != "nt":
        return

    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 0)


def executar_automacao_aghu(
    usuario: str,
    senha: str,
    mostrar_console: bool,
    mostrar_browser: bool,
    caminho_planilha_entrada: str,
    diretorio_relatorio: str,
    url_aghu: str = AGHU_URL,
) -> str:
    if not usuario or not senha:
        raise ValueError("Preencha usuário de rede e senha.")

    if not url_aghu:
        raise ValueError("Informe o ambiente do AGHU.")

    if not mostrar_console:
        esconder_console_windows()

    os.chdir(BASE_DIR)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=not mostrar_browser,
            slow_mo=500,
        )
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        try:
            page.goto(url_aghu)
            print(f"🌍 Ambiente acessado: {page.url}")

            fazer_login(page, usuario, senha, url_aghu=url_aghu)
            page, janela_sistema = navegar_ate_modulo(
                context,
                page,
                usuario,
                senha,
                url_aghu=url_aghu,
            )

            caminho_relatorio = processar_computadores(
                context,
                page,
                janela_sistema,
                caminho_planilha_entrada,
                usuario,
                senha,
                diretorio_relatorio,
                url_aghu=url_aghu,
            )
        finally:
            browser.close()

    return f"Processo concluido. Relatorio salvo em: {caminho_relatorio}"


class AghuPrinterApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AGHUX Bot - Impressoras")
        self.geometry("760x590")
        self.resizable(False, False)
        self.grid_columnconfigure(0, weight=1)

        self.var_browser = tk.BooleanVar(value=True)
        self.var_console = tk.BooleanVar(value=True)
        self.var_ambiente = tk.StringVar(value=AMBIENTE_PRODUCAO)

        self.label_title = ctk.CTkLabel(
            self,
            text="AGHUX Bot - Impressoras",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self.label_title.grid(row=0, column=0, padx=20, pady=(28, 16))

        self.frame_inputs = ctk.CTkFrame(self)
        self.frame_inputs.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.frame_inputs.grid_columnconfigure(1, weight=1)

        self.create_login_fields()
        self.create_environment_fields()
        self.create_execution_options()
        self.create_spreadsheet_fields()

        self.button_run = ctk.CTkButton(
            self,
            text="Iniciar Robô",
            command=self.start_automation,
            font=ctk.CTkFont(weight="bold"),
            height=38,
        )
        self.button_run.grid(row=2, column=0, padx=20, pady=(24, 12))

        self.label_status = ctk.CTkLabel(
            self,
            text="Pronto para execução.",
            text_color="gray",
            wraplength=680,
        )
        self.label_status.grid(row=3, column=0, padx=20, pady=(8, 16))

    def create_login_fields(self) -> None:
        self.label_user = ctk.CTkLabel(self.frame_inputs, text="Usuário de Rede:")
        self.label_user.grid(row=0, column=0, padx=12, pady=(16, 8), sticky="e")

        self.entry_user = ctk.CTkEntry(
            self.frame_inputs,
            placeholder_text="Digite seu usuário de rede",
        )
        self.entry_user.grid(
            row=0,
            column=1,
            columnspan=2,
            padx=12,
            pady=(16, 8),
            sticky="ew",
        )
        self.entry_user.focus()

        self.label_password = ctk.CTkLabel(self.frame_inputs, text="Senha:")
        self.label_password.grid(row=1, column=0, padx=12, pady=8, sticky="e")

        self.entry_password = ctk.CTkEntry(
            self.frame_inputs,
            placeholder_text="Digite sua senha",
            show="*",
        )
        self.entry_password.grid(
            row=1,
            column=1,
            columnspan=2,
            padx=12,
            pady=8,
            sticky="ew",
        )

    def create_environment_fields(self) -> None:
        self.label_environment = ctk.CTkLabel(self.frame_inputs, text="Ambiente:")
        self.label_environment.grid(row=2, column=0, padx=12, pady=8, sticky="e")

        self.option_environment = ctk.CTkOptionMenu(
            self.frame_inputs,
            values=list(URLS_AMBIENTE_AGHU.keys()),
            variable=self.var_ambiente,
            command=self.on_environment_changed,
        )
        self.option_environment.grid(
            row=2,
            column=1,
            columnspan=2,
            padx=12,
            pady=8,
            sticky="ew",
        )

        self.frame_environment_alert = ctk.CTkFrame(
            self.frame_inputs,
            fg_color=("#FFF4CE", "#3A2D00"),
            border_color=("#D79A00", "#8A6500"),
            border_width=1,
        )
        self.frame_environment_alert.grid_columnconfigure(0, weight=1)

        self.label_environment_alert = ctk.CTkLabel(
            self.frame_environment_alert,
            text=(
                "Atenção: você está alterando para o Ambiente de Produção. "
                "As alterações serão executadas no AGHUX de produção."
            ),
            text_color=("#5C3B00", "#FFE8A3"),
            wraplength=680,
            justify="left",
        )
        self.label_environment_alert.grid(
            row=0,
            column=0,
            padx=12,
            pady=8,
            sticky="ew",
        )

        self.update_environment_alert(self.var_ambiente.get())

    def on_environment_changed(self, ambiente: str) -> None:
        self.update_environment_alert(ambiente)

    def update_environment_alert(self, ambiente: str) -> None:
        if ambiente == AMBIENTE_PRODUCAO:
            self.frame_environment_alert.grid(
                row=3,
                column=0,
                columnspan=3,
                padx=12,
                pady=(0, 8),
                sticky="ew",
            )
            return

        self.frame_environment_alert.grid_remove()

    def create_execution_options(self) -> None:
        self.checkbox_browser = ctk.CTkCheckBox(
            self.frame_inputs,
            text="Exibir Navegador (Modo Visual)",
            variable=self.var_browser,
            command=self.validate_visibility_options_from_browser,
        )
        self.checkbox_browser.grid(
            row=4,
            column=1,
            columnspan=2,
            padx=12,
            pady=(14, 6),
            sticky="w",
        )

        self.checkbox_console = ctk.CTkCheckBox(
            self.frame_inputs,
            text="Exibir Terminal de processos (logs)",
            variable=self.var_console,
            command=self.validate_visibility_options_from_console,
        )
        self.checkbox_console.grid(
            row=5,
            column=1,
            columnspan=2,
            padx=12,
            pady=(6, 14),
            sticky="w",
        )

    def create_spreadsheet_fields(self) -> None:
        self.label_spreadsheet_in = ctk.CTkLabel(
            self.frame_inputs,
            text="Planilha entrada:",
        )
        self.label_spreadsheet_in.grid(row=6, column=0, padx=12, pady=10, sticky="e")

        self.entry_spreadsheet_in = ctk.CTkEntry(
            self.frame_inputs,
            placeholder_text="Arquivo .xlsx",
        )
        self.entry_spreadsheet_in.grid(
            row=6,
            column=1,
            padx=12,
            pady=10,
            sticky="ew",
        )

        self.button_select_spreadsheet_in = ctk.CTkButton(
            self.frame_inputs,
            text="Selecionar",
            width=110,
            command=self.select_input_spreadsheet,
        )
        self.button_select_spreadsheet_in.grid(row=6, column=2, padx=12, pady=10)

        self.label_report_dir = ctk.CTkLabel(
            self.frame_inputs,
            text="Pasta relatorio:",
        )
        self.label_report_dir.grid(
            row=7,
            column=0,
            padx=12,
            pady=(10, 16),
            sticky="e",
        )

        self.entry_report_dir = ctk.CTkEntry(
            self.frame_inputs,
            placeholder_text="Pasta onde o relatorio XLSX sera salvo",
        )
        self.entry_report_dir.grid(
            row=7,
            column=1,
            padx=12,
            pady=(10, 16),
            sticky="ew",
        )

        self.button_select_report_dir = ctk.CTkButton(
            self.frame_inputs,
            text="Selecionar",
            width=110,
            command=self.select_report_directory,
        )
        self.button_select_report_dir.grid(
            row=7,
            column=2,
            padx=12,
            pady=(10, 16),
        )

    def validate_visibility_options_from_browser(self) -> None:
        if not self.var_browser.get() and not self.var_console.get():
            self.var_browser.set(True)
            messagebox.showwarning(
                "Ação bloqueada",
                "Para evitar processos invisíveis, mantenha o navegador ou o terminal ativo.",
            )

    def validate_visibility_options_from_console(self) -> None:
        if not self.var_console.get() and not self.var_browser.get():
            self.var_console.set(True)
            messagebox.showwarning(
                "Ação bloqueada",
                "Para evitar processos invisíveis, mantenha o navegador ou o terminal ativo.",
            )

    def select_input_spreadsheet(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Selecione a planilha de entrada",
            filetypes=(
                ("Planilhas", "*.xlsx"),
            ),
        )

        if file_path:
            self.entry_spreadsheet_in.delete(0, "end")
            self.entry_spreadsheet_in.insert(0, file_path)

            if not self.entry_report_dir.get().strip():
                self.entry_report_dir.insert(0, str(Path(file_path).parent))

    def select_report_directory(self) -> None:
        directory = filedialog.askdirectory(
            title="Selecione a pasta de relatorio",
        )

        if directory:
            self.entry_report_dir.delete(0, "end")
            self.entry_report_dir.insert(0, directory)

    def start_automation(self) -> None:
        usuario = self.entry_user.get().strip()
        senha = self.entry_password.get().strip()
        caminho_entrada = self.entry_spreadsheet_in.get().strip()
        diretorio_relatorio = self.entry_report_dir.get().strip()
        mostrar_console = bool(self.var_console.get())
        mostrar_browser = bool(self.var_browser.get())
        ambiente = self.var_ambiente.get()
        url_aghu = obter_url_ambiente_aghu(ambiente)

        if not usuario or not senha:
            self.show_status("Erro: preencha usuário de rede e senha.", "red")
            return

        if not caminho_entrada:
            self.show_status("Erro: informe a planilha de entrada.", "red")
            return

        if not diretorio_relatorio:
            self.show_status("Erro: informe a pasta de relatorio.", "red")
            return

        try:
            validate_spreadsheet_extension(caminho_entrada)
            if not Path(diretorio_relatorio).expanduser().is_dir():
                raise NotADirectoryError(
                    f"A pasta de relatorio nao existe: {diretorio_relatorio}"
                )
        except Exception as exc:
            self.show_status(f"Erro: {exc}", "red")
            return

        self.show_status("Iniciando automação...", "blue")
        self.button_run.configure(state="disabled", text="Executando...")

        thread = threading.Thread(
            target=self.run_playwright_task,
            args=(
                usuario,
                senha,
                mostrar_console,
                mostrar_browser,
                caminho_entrada,
                diretorio_relatorio,
                url_aghu,
            ),
            daemon=True,
        )
        thread.start()

    def run_playwright_task(
        self,
        usuario: str,
        senha: str,
        mostrar_console: bool,
        mostrar_browser: bool,
        caminho_entrada: str,
        diretorio_relatorio: str,
        url_aghu: str,
    ) -> None:
        try:
            result_msg = executar_automacao_aghu(
                usuario=usuario,
                senha=senha,
                mostrar_console=mostrar_console,
                mostrar_browser=mostrar_browser,
                caminho_planilha_entrada=caminho_entrada,
                diretorio_relatorio=diretorio_relatorio,
                url_aghu=url_aghu,
            )
            self.after(0, self.finish_automation, result_msg, "green")
        except Exception as exc:
            self.after(0, self.finish_automation, f"Erro: {exc}", "red")

    def finish_automation(self, message: str, color: str) -> None:
        self.show_status(message, color)
        self.button_run.configure(state="normal", text="Iniciar Robô")

    def show_status(self, message: str, color: str) -> None:
        self.label_status.configure(text=message, text_color=color)


if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    app = AghuPrinterApp()
    app.mainloop()
