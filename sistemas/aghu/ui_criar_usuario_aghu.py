import sys
import threading
from collections import Counter
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

if getattr(sys, "frozen", False):
    from _launcher_runtime import bootstrap_playwright_browsers_path

    bootstrap_playwright_browsers_path()

from criar_usuario_aghu import (
    STATUS_CONFERIR_MANUALMENTE,
    STATUS_ERRO,
    STATUS_IGNORADO,
    STATUS_IMPORTADO,
    STATUS_JA_IMPORTADO,
    STATUS_NAO_ENCONTRADO,
    UsuarioImportacao,
    executar_importacao_usuarios,
    executar_importacao_lote,
)
from autenticador import AGHU_URL, AGHU_URL_HOMOLOGACAO

TIPO_INDIVIDUAL = "Unitária"
TIPO_LOTE = "Lote"


AMBIENTE_PRODUCAO = "Produção"
AMBIENTE_HOMOLOGACAO = "Homologação"
URLS_AMBIENTE_AGHU = {
    AMBIENTE_PRODUCAO: AGHU_URL,
    AMBIENTE_HOMOLOGACAO: AGHU_URL_HOMOLOGACAO,
}
MAX_USUARIOS_MANUAIS = 5
BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"


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
        self.geometry("820x760")
        self.minsize(720, 620)
        self.resizable(True, True)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.var_ambiente = tk.StringVar(value=AMBIENTE_HOMOLOGACAO)
        self.var_tipo_execucao = tk.StringVar(value=TIPO_INDIVIDUAL)
        self.var_browser = tk.BooleanVar(value=True)
        self.var_console = tk.BooleanVar(value=True)
        self.em_execucao = False
        self.linhas_usuarios_individual = []

        self.label_title = ctk.CTkLabel(
            self,
            text="AGHUX Bot - Importação de Usuário",
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

        self.frame_individual = self._criar_secao_execucao("Execução Unitária")
        self.frame_lote = self._criar_secao_execucao("Execução em Lote")

        self._criar_campos_acesso()
        self._criar_opcoes_execucao()
        self._criar_seletor_tipo_execucao()
        self._criar_campos_individual()
        self._criar_campos_lote()
        self._atualizar_tipo_execucao(TIPO_INDIVIDUAL)

        self.button_executar = ctk.CTkButton(
            self.frame_conteudo,
            text="Executar importação",
            command=self.iniciar_execucao,
            height=40,
            font=ctk.CTkFont(weight="bold"),
        )
        self.button_executar.grid(row=3, column=0, padx=0, pady=(12, 8), sticky="e")

        self.label_status = ctk.CTkLabel(
            self,
            text="Pronto para execução.",
            text_color="gray",
            wraplength=760,
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

    def _validar_opcoes_visibilidade(self, variavel_alvo: tk.BooleanVar) -> None:
        if not self.var_browser.get() and not self.var_console.get():
            variavel_alvo.set(True)
            messagebox.showwarning(
                "Acao bloqueada",
                "Para evitar processos invisiveis, mantenha o navegador ou o terminal ativo.",
            )

    def _criar_campos_individual(self) -> None:
        self.label_usuarios_individual = ctk.CTkLabel(
            self.frame_individual,
            text="Usuários:",
        )
        self.label_usuarios_individual.grid(
            row=1,
            column=0,
            padx=14,
            pady=(10, 8),
            sticky="ne",
        )

        self.frame_usuarios_individual = ctk.CTkFrame(
            self.frame_individual,
            fg_color="transparent",
        )
        self.frame_usuarios_individual.grid(
            row=1,
            column=1,
            columnspan=2,
            padx=14,
            pady=(8, 12),
            sticky="ew",
        )
        self.frame_usuarios_individual.grid_columnconfigure(0, weight=1)

        self.frame_cabecalho_usuarios = ctk.CTkFrame(
            self.frame_usuarios_individual,
            fg_color="transparent",
        )
        self.frame_cabecalho_usuarios.grid(row=0, column=0, sticky="ew")
        self.frame_cabecalho_usuarios.grid_columnconfigure(0, weight=1, minsize=130)
        self.frame_cabecalho_usuarios.grid_columnconfigure(1, weight=2, minsize=180)
        self.frame_cabecalho_usuarios.grid_columnconfigure(2, weight=2, minsize=180)
        self.frame_cabecalho_usuarios.grid_columnconfigure(3, minsize=42)

        for coluna, texto in enumerate(("Login", "Nome completo", "E-mail")):
            label = ctk.CTkLabel(
                self.frame_cabecalho_usuarios,
                text=texto,
                text_color="gray",
                font=ctk.CTkFont(size=12, weight="bold"),
            )
            label.grid(row=0, column=coluna, padx=(0, 8), pady=(0, 2), sticky="w")

        self.frame_linhas_usuarios = ctk.CTkFrame(
            self.frame_usuarios_individual,
            fg_color="transparent",
        )
        self.frame_linhas_usuarios.grid(row=1, column=0, sticky="ew")
        self.frame_linhas_usuarios.grid_columnconfigure(0, weight=1)

        self.frame_acoes_usuarios = ctk.CTkFrame(
            self.frame_usuarios_individual,
            fg_color="transparent",
        )
        self.frame_acoes_usuarios.grid(row=2, column=0, pady=(6, 0), sticky="ew")
        self.frame_acoes_usuarios.grid_columnconfigure(1, weight=1)

        self.button_adicionar_usuario = ctk.CTkButton(
            self.frame_acoes_usuarios,
            text="+ Adicionar usuário",
            width=160,
            height=32,
            command=self.adicionar_linha_usuario,
        )
        self.button_adicionar_usuario.grid(row=0, column=0, sticky="w")

        self.label_limite_usuarios = ctk.CTkLabel(
            self.frame_acoes_usuarios,
            text="",
            text_color=("#9A3412", "#FDBA74"),
        )
        self.label_limite_usuarios.grid(
            row=0,
            column=1,
            padx=(10, 0),
            sticky="w",
        )

        self.adicionar_linha_usuario()

    def adicionar_linha_usuario(self) -> None:
        if len(self.linhas_usuarios_individual) >= MAX_USUARIOS_MANUAIS:
            self._atualizar_estado_lista_usuarios()
            return

        frame_linha = ctk.CTkFrame(
            self.frame_linhas_usuarios,
            fg_color="transparent",
        )
        frame_linha.grid(
            row=len(self.linhas_usuarios_individual),
            column=0,
            pady=3,
            sticky="ew",
        )
        frame_linha.grid_columnconfigure(0, weight=1, minsize=130)
        frame_linha.grid_columnconfigure(1, weight=2, minsize=180)
        frame_linha.grid_columnconfigure(2, weight=2, minsize=180)
        frame_linha.grid_columnconfigure(3, minsize=42)

        linha = {"frame": frame_linha}

        entry_login = ctk.CTkEntry(
            frame_linha,
            placeholder_text="Login",
            height=32,
        )
        entry_login.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        entry_nome = ctk.CTkEntry(
            frame_linha,
            placeholder_text="Nome completo",
            height=32,
        )
        entry_nome.grid(row=0, column=1, padx=(0, 8), sticky="ew")

        entry_email = ctk.CTkEntry(
            frame_linha,
            placeholder_text="E-mail",
            height=32,
        )
        entry_email.grid(row=0, column=2, padx=(0, 8), sticky="ew")

        button_remover = ctk.CTkButton(
            frame_linha,
            text="\U0001F5D1",
            width=36,
            height=32,
            fg_color=("#E5E7EB", "#2B2B2B"),
            hover_color=("#D1D5DB", "#3A3A3A"),
            text_color=("#991B1B", "#FCA5A5"),
            command=lambda linha=linha: self.remover_linha_usuario(linha),
        )
        button_remover.grid(row=0, column=3, sticky="e")

        linha.update(
            {
                "login": entry_login,
                "nome_completo": entry_nome,
                "email": entry_email,
                "remover": button_remover,
            }
        )
        self.linhas_usuarios_individual.append(linha)
        self._atualizar_estado_lista_usuarios()

        if len(self.linhas_usuarios_individual) > 1:
            entry_login.focus()

    def remover_linha_usuario(self, linha_usuario) -> None:
        if len(self.linhas_usuarios_individual) <= 1:
            self._atualizar_estado_lista_usuarios()
            return

        if linha_usuario not in self.linhas_usuarios_individual:
            return

        linha_usuario["frame"].destroy()
        self.linhas_usuarios_individual.remove(linha_usuario)

        for indice, linha in enumerate(self.linhas_usuarios_individual):
            linha["frame"].grid_configure(row=indice)

        self._atualizar_estado_lista_usuarios()

    def coletar_usuarios_individuais(self) -> list[UsuarioImportacao]:
        return [
            UsuarioImportacao(
                login=linha["login"].get(),
                nome_completo=linha["nome_completo"].get(),
                email=linha["email"].get(),
            )
            for linha in self.linhas_usuarios_individual
        ]

    def _atualizar_estado_lista_usuarios(self) -> None:
        limite_atingido = len(self.linhas_usuarios_individual) >= MAX_USUARIOS_MANUAIS
        estado_campos = "disabled" if self.em_execucao else "normal"
        estado_adicionar = (
            "disabled" if self.em_execucao or limite_atingido else "normal"
        )
        estado_remover = (
            "normal"
            if not self.em_execucao and len(self.linhas_usuarios_individual) > 1
            else "disabled"
        )

        self.button_adicionar_usuario.configure(state=estado_adicionar)
        self.label_limite_usuarios.configure(
            text="Limite de 5 usuários atingido." if limite_atingido else ""
        )

        for linha in self.linhas_usuarios_individual:
            linha["login"].configure(state=estado_campos)
            linha["nome_completo"].configure(state=estado_campos)
            linha["email"].configure(state=estado_campos)
            linha["remover"].configure(state=estado_remover)

    def iniciar_execucao(self) -> None:
        tipo = self.var_tipo_execucao.get()

        if tipo == TIPO_INDIVIDUAL:
            self.iniciar_execucao_individual()
        else:
            self.iniciar_execucao_lote()

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

    def _credenciais_e_url(self) -> tuple[str, str, str]:
        usuario_rede = self.entry_usuario_rede.get().strip()
        senha = self.entry_senha.get()
        url_aghu = obter_url_ambiente_aghu(self.var_ambiente.get())

        if not usuario_rede or not senha:
            raise ValueError("Preencha usuário de rede e senha.")

        return usuario_rede, senha, url_aghu

    def _bloquear_execucao(self, texto_botao: str) -> None:
        self.em_execucao = True
        self.button_executar.configure(state="disabled", text=texto_botao)
        self.segment_tipo_execucao.configure(state="disabled")
        self.option_ambiente.configure(state="disabled")
        self.entry_usuario_rede.configure(state="disabled")
        self.entry_senha.configure(state="disabled")
        self.entry_planilha_lote.configure(state="disabled")
        self.entry_relatorio_lote.configure(state="disabled")
        self.checkbox_browser.configure(state="disabled")
        self.checkbox_console.configure(state="disabled")
        self.button_planilha_lote.configure(state="disabled")
        self.button_relatorio_lote.configure(state="disabled")
        self._atualizar_estado_lista_usuarios()

    def _liberar_execucao(self) -> None:
        self.em_execucao = False
        self.button_executar.configure(state="normal", text="Executar importação")
        self.segment_tipo_execucao.configure(state="normal")
        self.option_ambiente.configure(state="normal")
        self.entry_usuario_rede.configure(state="normal")
        self.entry_senha.configure(state="normal")
        self.entry_planilha_lote.configure(state="normal")
        self.entry_relatorio_lote.configure(state="normal")
        self.checkbox_browser.configure(state="normal")
        self.checkbox_console.configure(state="normal")
        self.button_planilha_lote.configure(state="normal")
        self.button_relatorio_lote.configure(state="normal")
        self._atualizar_estado_lista_usuarios()
        
    def _usuarios_individuais_incompletos(
        self,
        usuarios: list[UsuarioImportacao],
    ) -> bool:
        return any(
            not usuario.login.strip()
            or not usuario.nome_completo.strip()
            or not usuario.email.strip()
            for usuario in usuarios
        )

    def iniciar_execucao_individual(self) -> None:
        if self.em_execucao:
            return

        try:
            usuario_rede, senha, url_aghu = self._credenciais_e_url()
            usuarios = self.coletar_usuarios_individuais()
            mostrar_browser = bool(self.var_browser.get())
            mostrar_console = bool(self.var_console.get())

            if self._usuarios_individuais_incompletos(usuarios):
                raise ValueError(
                    "Preencha login, nome completo e e-mail de todos os usuários."
                )
        except Exception as exc:
            self._mostrar_status(f"Erro: {exc}", "red")
            return

        self._mostrar_status("Executando importação unitária...", "blue")
        self._bloquear_execucao("Executando...")

        thread = threading.Thread(
            target=self._executar_individual_thread,
            args=(
                usuario_rede,
                senha,
                usuarios,
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
        usuarios: list[UsuarioImportacao],
        url_aghu: str,
        mostrar_browser: bool,
        mostrar_console: bool,
    ) -> None:
        try:
            resultados = executar_importacao_usuarios(
                usuarios=usuarios,
                usuario_rede=usuario_rede,
                senha=senha,
                url_aghu=url_aghu,
                mostrar_browser=mostrar_browser,
                mostrar_console=mostrar_console,
                diretorio_logs=LOGS_DIR,
            )
            if len(resultados) == 1:
                resultado = resultados[0]
                mensagem = (
                    f"{resultado.login}: {resultado.status} - {resultado.detalhes}"
                )
            else:
                mensagem = self._resumir_resultados(
                    resultados,
                    prefixo="Execução unitária concluída",
                )
            self.after(0, self._finalizar_execucao, mensagem, self._cor_resultado(resultados))
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

        self._mostrar_status("Executando lote...", "blue")
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
            resultados, relatorio = executar_importacao_lote(
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
            self.after(0, self._finalizar_execucao, mensagem, self._cor_resultado(resultados))
        except Exception as exc:
            self.after(0, self._finalizar_execucao, f"Erro: {exc}", "red")

    def _resumir_resultados(
        self,
        resultados,
        prefixo: str = "Lote concluído",
    ) -> str:
        contagem = Counter(resultado.status for resultado in resultados)
        total = len(resultados)

        return (
            f"{prefixo}. Total: {total}. "
            f"Importados: {contagem[STATUS_IMPORTADO]}. "
            f"Já importados: {contagem[STATUS_JA_IMPORTADO]}. "
            f"Não encontrados: {contagem[STATUS_NAO_ENCONTRADO]}. "
            f"Ignorados: {contagem[STATUS_IGNORADO]}. "
            f"Conferir manualmente: {contagem[STATUS_CONFERIR_MANUALMENTE]}. "
            f"Erros: {contagem[STATUS_ERRO]}."
        )

    def _cor_resultado(self, resultados) -> str:
        contagem = Counter(resultado.status for resultado in resultados)

        if contagem[STATUS_ERRO]:
            return "red"

        if contagem[STATUS_IGNORADO] or contagem[STATUS_CONFERIR_MANUALMENTE]:
            return "orange"

        return "green"

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
