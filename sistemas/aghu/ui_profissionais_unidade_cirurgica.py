import threading
from collections import Counter
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from playwright.sync_api import sync_playwright

from autenticador import AGHU_URL, AGHU_URL_HOMOLOGACAO
from profissionais_unidade_cirurgica_aghu import (
    CadastroProfissionalUnidadeEntrada,
    FUNCAO_MEDICO_RESIDENTE,
    LOGS_DIR,
    STATUS_CONFERIR_MANUAL,
    STATUS_CRIADO,
    STATUS_ERRO,
    STATUS_FUNCIONARIO_NAO_ENCONTRADO,
    STATUS_IGNORADO,
    STATUS_MANTIDO,
    UNIDADES_FUNCIONAIS,
    executar_cadastros_profissionais,
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
MAX_USUARIOS_UNITARIOS = 5
COLUNAS_ACESSOS_UNITARIOS = 3


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
        self.vars_unidades_funcionais = {}
        self.checkboxes_unidades_funcionais = []
        self.linhas_profissionais_individual = []
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
        self.frame_individual.grid_columnconfigure(0, weight=1)
        self._criar_secao_acessos_individual()
        self._criar_secao_usuarios_individual()

    def _criar_secao_acessos_individual(self) -> None:
        self.frame_acessos_individual = ctk.CTkFrame(self.frame_individual)
        self.frame_acessos_individual.grid(
            row=1,
            column=0,
            columnspan=3,
            padx=14,
            pady=(0, 10),
            sticky="ew",
        )

        for coluna in range(COLUNAS_ACESSOS_UNITARIOS):
            self.frame_acessos_individual.grid_columnconfigure(coluna, weight=1)

        self.label_acessos_individual = ctk.CTkLabel(
            self.frame_acessos_individual,
            text="ACESSOS (serão aplicados a todos os usuários abaixo)",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.label_acessos_individual.grid(
            row=0,
            column=0,
            columnspan=COLUNAS_ACESSOS_UNITARIOS,
            padx=12,
            pady=(12, 6),
            sticky="w",
        )

        self.vars_unidades_funcionais = {}
        self.checkboxes_unidades_funcionais = []

        for indice, unidade in enumerate(UNIDADES_FUNCIONAIS):
            variavel = tk.BooleanVar(value=indice == 0)
            checkbox = ctk.CTkCheckBox(
                self.frame_acessos_individual,
                text=unidade,
                variable=variavel,
            )
            checkbox.grid(
                row=1 + indice // COLUNAS_ACESSOS_UNITARIOS,
                column=indice % COLUNAS_ACESSOS_UNITARIOS,
                padx=12,
                pady=4,
                sticky="w",
            )
            self.vars_unidades_funcionais[unidade] = variavel
            self.checkboxes_unidades_funcionais.append(checkbox)

        linha_aviso = (
            1
            + ((len(UNIDADES_FUNCIONAIS) - 1) // COLUNAS_ACESSOS_UNITARIOS)
            + 1
        )
        self.label_aviso_acessos_individual = ctk.CTkLabel(
            self.frame_acessos_individual,
            text="As seleções acima serão aplicadas a todos os usuários abaixo.",
            text_color="gray",
            font=ctk.CTkFont(size=12),
        )
        self.label_aviso_acessos_individual.grid(
            row=linha_aviso,
            column=0,
            columnspan=COLUNAS_ACESSOS_UNITARIOS,
            padx=12,
            pady=(6, 12),
            sticky="w",
        )

    def _criar_secao_usuarios_individual(self) -> None:
        self.frame_usuarios_individual = ctk.CTkFrame(self.frame_individual)
        self.frame_usuarios_individual.grid(
            row=2,
            column=0,
            columnspan=3,
            padx=14,
            pady=(0, 14),
            sticky="ew",
        )
        self.frame_usuarios_individual.grid_columnconfigure(0, weight=1)

        self.label_usuarios_individual = ctk.CTkLabel(
            self.frame_usuarios_individual,
            text="USUÁRIOS (até 5)",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.label_usuarios_individual.grid(
            row=0,
            column=0,
            padx=12,
            pady=(12, 6),
            sticky="w",
        )

        self.frame_cabecalho_profissionais = ctk.CTkFrame(
            self.frame_usuarios_individual,
            fg_color="transparent",
        )
        self.frame_cabecalho_profissionais.grid(row=1, column=0, padx=12, sticky="ew")
        self.frame_cabecalho_profissionais.grid_columnconfigure(0, minsize=42)
        self.frame_cabecalho_profissionais.grid_columnconfigure(1, weight=1)
        self.frame_cabecalho_profissionais.grid_columnconfigure(2, minsize=42)

        for coluna, texto in enumerate(("#", "Profissional")):
            label = ctk.CTkLabel(
                self.frame_cabecalho_profissionais,
                text=texto,
                text_color="gray",
                font=ctk.CTkFont(size=12, weight="bold"),
            )
            label.grid(row=0, column=coluna, padx=(0, 8), pady=(0, 2), sticky="w")

        self.frame_linhas_profissionais = ctk.CTkFrame(
            self.frame_usuarios_individual,
            fg_color="transparent",
        )
        self.frame_linhas_profissionais.grid(row=2, column=0, padx=12, sticky="ew")
        self.frame_linhas_profissionais.grid_columnconfigure(0, weight=1)

        self.frame_acoes_profissionais = ctk.CTkFrame(
            self.frame_usuarios_individual,
            fg_color="transparent",
        )
        self.frame_acoes_profissionais.grid(
            row=3,
            column=0,
            padx=12,
            pady=(8, 12),
            sticky="ew",
        )
        self.frame_acoes_profissionais.grid_columnconfigure(1, weight=1)

        self.button_adicionar_usuario = ctk.CTkButton(
            self.frame_acoes_profissionais,
            text="+ Adicionar usuário",
            width=170,
            height=32,
            command=self._adicionar_linha_profissional,
        )
        self.button_adicionar_usuario.grid(row=0, column=0, sticky="w")

        self.label_contador_usuarios = ctk.CTkLabel(
            self.frame_acoes_profissionais,
            text="",
            text_color="gray",
        )
        self.label_contador_usuarios.grid(row=0, column=1, sticky="e")

        self._adicionar_linha_profissional()

    def _adicionar_linha_profissional(self) -> None:
        if len(self.linhas_profissionais_individual) >= MAX_USUARIOS_UNITARIOS:
            self._atualizar_estado_linhas_profissionais()
            return

        frame_linha = ctk.CTkFrame(
            self.frame_linhas_profissionais,
            fg_color="transparent",
        )
        frame_linha.grid(
            row=len(self.linhas_profissionais_individual),
            column=0,
            pady=3,
            sticky="ew",
        )
        frame_linha.grid_columnconfigure(0, minsize=42)
        frame_linha.grid_columnconfigure(1, weight=1)
        frame_linha.grid_columnconfigure(2, minsize=42)

        linha = {"frame": frame_linha}

        label_indice = ctk.CTkLabel(
            frame_linha,
            text=str(len(self.linhas_profissionais_individual) + 1),
            text_color="gray",
            width=30,
        )
        label_indice.grid(row=0, column=0, padx=(0, 8), sticky="w")

        entry_profissional = ctk.CTkEntry(
            frame_linha,
            placeholder_text="Nome do profissional no AGHUX",
            height=32,
        )
        entry_profissional.grid(row=0, column=1, padx=(0, 8), sticky="ew")

        button_remover = ctk.CTkButton(
            frame_linha,
            text="\U0001F5D1",
            width=36,
            height=32,
            fg_color=("#E5E7EB", "#2B2B2B"),
            hover_color=("#D1D5DB", "#3A3A3A"),
            text_color=("#991B1B", "#FCA5A5"),
            command=lambda linha=linha: self._remover_linha_profissional(linha),
        )
        button_remover.grid(row=0, column=2, sticky="e")

        linha.update(
            {
                "indice": label_indice,
                "profissional": entry_profissional,
                "remover": button_remover,
            }
        )
        self.linhas_profissionais_individual.append(linha)
        self._atualizar_estado_linhas_profissionais()

        if len(self.linhas_profissionais_individual) > 1:
            entry_profissional.focus()

    def _remover_linha_profissional(self, linha_profissional) -> None:
        if len(self.linhas_profissionais_individual) <= 1:
            self._atualizar_estado_linhas_profissionais()
            return

        if linha_profissional not in self.linhas_profissionais_individual:
            return

        linha_profissional["frame"].destroy()
        self.linhas_profissionais_individual.remove(linha_profissional)

        for indice, linha in enumerate(self.linhas_profissionais_individual):
            linha["frame"].grid_configure(row=indice)

        self._atualizar_estado_linhas_profissionais()

    def _atualizar_estado_linhas_profissionais(self) -> None:
        limite_atingido = (
            len(self.linhas_profissionais_individual) >= MAX_USUARIOS_UNITARIOS
        )
        estado_campos = "disabled" if self.em_execucao else "normal"
        estado_adicionar = (
            "disabled" if self.em_execucao or limite_atingido else "normal"
        )
        estado_remover = (
            "normal"
            if not self.em_execucao and len(self.linhas_profissionais_individual) > 1
            else "disabled"
        )

        self.button_adicionar_usuario.configure(state=estado_adicionar)
        self.label_contador_usuarios.configure(
            text=(
                f"{len(self.linhas_profissionais_individual)} / "
                f"{MAX_USUARIOS_UNITARIOS} usuários"
            )
        )

        for indice, linha in enumerate(self.linhas_profissionais_individual, start=1):
            linha["indice"].configure(text=str(indice))
            linha["profissional"].configure(state=estado_campos)
            linha["remover"].configure(state=estado_remover)

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

    def _unidades_funcionais_selecionadas(self) -> list[str]:
        return [
            unidade
            for unidade, variavel in self.vars_unidades_funcionais.items()
            if variavel.get()
        ]

    def _profissionais_unitarios(self) -> list[str]:
        profissionais = [
            linha["profissional"].get().strip()
            for linha in self.linhas_profissionais_individual
            if linha["profissional"].get().strip()
        ]

        if not profissionais:
            raise ValueError("Informe ao menos um profissional.")

        return profissionais

    def _cadastros_individuais(self) -> list[CadastroProfissionalUnidadeEntrada]:
        profissionais = self._profissionais_unitarios()
        unidades_funcionais = self._unidades_funcionais_selecionadas()

        if not unidades_funcionais:
            raise ValueError("Selecione ao menos uma Unidade Funcional.")

        cadastros = [
            CadastroProfissionalUnidadeEntrada(
                profissional=profissional,
                unidade_funcional=unidade_funcional,
                funcao=FUNCAO_MEDICO_RESIDENTE,
            )
            for profissional in profissionais
            for unidade_funcional in unidades_funcionais
        ]

        for cadastro in cadastros:
            erros = validar_entrada(cadastro)
            if erros:
                raise ValueError("; ".join(erros))

        return cadastros

    def _cadastro_individual(self) -> CadastroProfissionalUnidadeEntrada:
        return self._cadastros_individuais()[0]

    def _bloquear_execucao(self, texto_botao: str) -> None:
        self.em_execucao = True
        self.button_executar.configure(state="disabled", text=texto_botao)
        self.segment_tipo_execucao.configure(state="disabled")
        self.entry_usuario_rede.configure(state="disabled")
        self.entry_senha.configure(state="disabled")
        self.option_ambiente.configure(state="disabled")
        self.checkbox_browser.configure(state="disabled")
        self.checkbox_console.configure(state="disabled")
        for checkbox in self.checkboxes_unidades_funcionais:
            checkbox.configure(state="disabled")
        self._atualizar_estado_linhas_profissionais()
        self.entry_planilha_lote.configure(state="disabled")
        self.button_planilha_lote.configure(state="disabled")
        self.entry_relatorio_lote.configure(state="disabled")
        self.button_relatorio_lote.configure(state="disabled")

    def _liberar_execucao(self) -> None:
        self.em_execucao = False
        self.button_executar.configure(state="normal", text="Executar cadastro")
        self.segment_tipo_execucao.configure(state="normal")
        self.entry_usuario_rede.configure(state="normal")
        self.entry_senha.configure(state="normal")
        self.option_ambiente.configure(state="normal")
        self.checkbox_browser.configure(state="normal")
        self.checkbox_console.configure(state="normal")
        for checkbox in self.checkboxes_unidades_funcionais:
            checkbox.configure(state="normal")
        self._atualizar_estado_linhas_profissionais()
        self.entry_planilha_lote.configure(state="normal")
        self.button_planilha_lote.configure(state="normal")
        self.entry_relatorio_lote.configure(state="normal")
        self.button_relatorio_lote.configure(state="normal")

    def iniciar_execucao_individual(self) -> None:
        if self.em_execucao:
            return

        try:
            usuario_rede, senha, url_aghu = self._credenciais_e_url()
            cadastros = self._cadastros_individuais()
            mostrar_browser = bool(self.var_browser.get())
            mostrar_console = bool(self.var_console.get())
        except Exception as exc:
            self._mostrar_status(f"Erro: {exc}", "red")
            return

        self._mostrar_status(
            "Executando cadastro unitário de profissionais...",
            "blue",
        )
        self._bloquear_execucao("Executando...")

        thread = threading.Thread(
            target=self._executar_individual_thread,
            args=(
                usuario_rede,
                senha,
                cadastros,
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
        cadastros: list[CadastroProfissionalUnidadeEntrada],
        url_aghu: str,
        mostrar_browser: bool,
        mostrar_console: bool,
    ) -> None:
        try:
            resultados = self._executar_com_playwright(
                mostrar_browser,
                lambda context, page: executar_cadastros_profissionais(
                    cadastros=cadastros,
                    usuario_rede=usuario_rede,
                    senha=senha,
                    context=context,
                    page=page,
                    url_aghu=url_aghu,
                    mostrar_console=mostrar_console,
                    diretorio_logs=LOGS_DIR,
                ),
            )
            mensagem = self._resumir_resultados(
                resultados,
                prefixo="Execução unitária concluída",
                rotulo_total="Total processado",
            )
            cor = (
                "red"
                if any(
                    resultado.status
                    in {
                        STATUS_ERRO,
                        STATUS_CONFERIR_MANUAL,
                        STATUS_IGNORADO,
                        STATUS_FUNCIONARIO_NAO_ENCONTRADO,
                    }
                    for resultado in resultados
                )
                else "green"
            )
            self.after(0, self._finalizar_execucao, mensagem, cor)
        except Exception as exc:
            self.after(0, self._finalizar_execucao, f"Erro: {exc}", "red")

    def _executar_com_playwright(self, mostrar_browser: bool, acao):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=not mostrar_browser,
                slow_mo=500,
            )
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()

            try:
                return acao(context, page)
            finally:
                browser.close()

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
            resultados, relatorio = self._executar_com_playwright(
                mostrar_browser,
                lambda context, page: executar_cadastro_lote(
                    usuario_rede=usuario_rede,
                    senha=senha,
                    caminho_planilha=caminho_planilha,
                    caminho_relatorio=caminho_relatorio,
                    context=context,
                    page=page,
                    url_aghu=url_aghu,
                    mostrar_console=mostrar_console,
                    diretorio_logs=LOGS_DIR,
                ),
            )
            resumo = self._resumir_resultados(resultados)
            mensagem = f"{resumo} Relatório: {relatorio}"
            status_resultados = {resultado.status for resultado in resultados}
            if status_resultados & {STATUS_ERRO, STATUS_CONFERIR_MANUAL}:
                cor = "red"
            elif status_resultados & {
                STATUS_FUNCIONARIO_NAO_ENCONTRADO,
                STATUS_IGNORADO,
            }:
                cor = "yellow"
            else:
                cor = "green"
            self.after(0, self._finalizar_execucao, mensagem, cor)
        except Exception as exc:
            self.after(0, self._finalizar_execucao, f"Erro: {exc}", "red")

    def _resumir_resultados(
        self,
        resultados,
        prefixo: str = "Lote concluído",
        rotulo_total: str = "Total",
    ) -> str:
        contagem = Counter(resultado.status for resultado in resultados)
        total = len(resultados)

        return (
            f"{prefixo}. {rotulo_total}: {total}. "
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
