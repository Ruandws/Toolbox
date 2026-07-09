import threading
from collections import Counter
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from autenticador import AGHU_URL, AGHU_URL_HOMOLOGACAO
from concessor_aghu import (
    ConcessaoPerfisEntrada,
    LOGS_DIR,
    STATUS_CONFERIR_MANUAL,
    STATUS_CONCEDIDO,
    STATUS_ERRO,
    STATUS_IGNORADO,
    STATUS_JA_EXISTENTE,
    STATUS_USUARIO_NAO_ENCONTRADO,
    carregar_catalogo_regras,
    executar_concessao_lote,
    executar_concessoes_perfis,
    validar_entrada,
)

AMBIENTE_PRODUCAO = "Produção"
AMBIENTE_HOMOLOGACAO = "Homologação"
URLS_AMBIENTE_AGHU = {
    AMBIENTE_PRODUCAO: AGHU_URL,
    AMBIENTE_HOMOLOGACAO: AGHU_URL_HOMOLOGACAO,
}


def obter_url_ambiente_aghu(ambiente: str) -> str:
    return URLS_AMBIENTE_AGHU.get(ambiente, AGHU_URL)


TIPO_INDIVIDUAL = "Unitaria"
TIPO_LOTE = "Lote"
MAX_USUARIOS_UNITARIOS = 5


def caminho_relatorio_padrao(base: str = "") -> str:
    nome = (
        "relatorio_concessao_perfis_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )

    if base:
        caminho_base = Path(base)
        diretorio = caminho_base.parent if caminho_base.suffix else caminho_base
        return str(diretorio / nome)

    return str(Path.cwd() / nome)


class AghuConcessorPerfisApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.catalogo = carregar_catalogo_regras()
        escopos = list(self.catalogo.escopos())
        escopo_inicial = escopos[0] if escopos else ""
        categorias = list(self.catalogo.categorias(escopo_inicial))
        categoria_inicial = categorias[0] if categorias else ""

        self.title("AGHUX Bot - Concessão de Perfis")
        self.geometry("900x780")
        self.minsize(780, 640)
        self.resizable(True, True)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.var_ambiente = tk.StringVar(value=AMBIENTE_HOMOLOGACAO)
        self.var_tipo_execucao = tk.StringVar(value=TIPO_INDIVIDUAL)
        self.var_browser = tk.BooleanVar(value=True)
        self.var_console = tk.BooleanVar(value=True)
        self.var_escopo = tk.StringVar(value=escopo_inicial)
        self.var_categoria = tk.StringVar(value=categoria_inicial)
        self.linhas_usuarios_concessao = []
        self.em_execucao = False

        self.label_title = ctk.CTkLabel(
            self,
            text="AGHUX Bot - Concessão de Perfis",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self.label_title.grid(row=0, column=0, padx=20, pady=(22, 10))

        self.frame_conteudo = ctk.CTkScrollableFrame(self)
        self.frame_conteudo.grid(row=1, column=0, padx=20, pady=8, sticky="nsew")
        self.frame_conteudo.grid_columnconfigure(0, weight=1)

        self.frame_acesso = self._criar_secao("Acesso", 0)
        self.frame_concessao = self._criar_secao("Tipo de Execucao", 1)
        self.frame_perfis = self._criar_secao("Perfis da regra (Acesso padrão)", 2)
        self.frame_tipo_execucao = self.frame_concessao

        self.frame_execucao = ctk.CTkFrame(
            self.frame_conteudo,
            fg_color="transparent",
        )
        self.frame_execucao.grid(row=2, column=0, padx=0, pady=8, sticky="ew")
        self.frame_execucao.grid_columnconfigure(0, weight=1)

        self.frame_individual = self._criar_secao_execucao("Concessao unitaria")
        self.frame_lote = self._criar_secao_execucao("Concessao em lote")
        self.frame_concessao = self.frame_individual
        self.frame_concessao.grid_columnconfigure(0, weight=1)
        self.frame_perfis.grid(row=3, column=0, padx=0, pady=8, sticky="ew")

        self._criar_campos_acesso()
        self._criar_opcoes_execucao()
        self._criar_seletor_tipo_execucao()
        self._criar_secao_acesso_padrao(escopos, categorias)
        self._criar_secao_usuarios_individual()
        self._criar_campos_lote()
        self._criar_previa_perfis()
        self._atualizar_previa_perfis()
        self._atualizar_tipo_execucao(TIPO_INDIVIDUAL)

        self.button_executar = ctk.CTkButton(
            self.frame_conteudo,
            text="Executar concessão",
            command=self.iniciar_execucao,
            height=40,
            font=ctk.CTkFont(weight="bold"),
        )
        self.button_executar.grid(row=4, column=0, padx=0, pady=(12, 8), sticky="e")

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
            self.frame_perfis.grid(row=3, column=0, padx=0, pady=8, sticky="ew")
        else:
            self.frame_lote.grid(row=0, column=0, sticky="ew")
            self.frame_perfis.grid_remove()

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

    def _criar_secao_acesso_padrao(
        self,
        escopos: list[str],
        categorias: list[str],
    ) -> None:
        self.frame_acesso_padrao = ctk.CTkFrame(self.frame_concessao)
        self.frame_acesso_padrao.grid(
            row=1,
            column=0,
            columnspan=3,
            padx=14,
            pady=(0, 10),
            sticky="ew",
        )
        self.frame_acesso_padrao.grid_columnconfigure(1, weight=1)

        self.label_acesso_padrao = ctk.CTkLabel(
            self.frame_acesso_padrao,
            text="ACESSO PADRÃO (aplicado a todos os usuários abaixo)",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.label_acesso_padrao.grid(
            row=0,
            column=0,
            columnspan=3,
            padx=12,
            pady=(12, 6),
            sticky="w",
        )

        self.label_escopo = ctk.CTkLabel(self.frame_acesso_padrao, text="Escopo:")
        self.label_escopo.grid(row=1, column=0, padx=12, pady=6, sticky="e")

        self.option_escopo = ctk.CTkOptionMenu(
            self.frame_acesso_padrao,
            values=escopos,
            variable=self.var_escopo,
            command=self._on_escopo_changed,
        )
        self.option_escopo.grid(
            row=1,
            column=1,
            columnspan=2,
            padx=12,
            pady=6,
            sticky="ew",
        )

        self.label_categoria = ctk.CTkLabel(self.frame_acesso_padrao, text="Categoria:")
        self.label_categoria.grid(row=2, column=0, padx=12, pady=(6, 12), sticky="e")

        self.option_categoria = ctk.CTkOptionMenu(
            self.frame_acesso_padrao,
            values=categorias,
            variable=self.var_categoria,
            command=lambda _: self._atualizar_previa_perfis(),
        )
        self.option_categoria.grid(
            row=2,
            column=1,
            columnspan=2,
            padx=12,
            pady=(6, 12),
            sticky="ew",
        )

    def _criar_secao_usuarios_individual(self) -> None:
        self.frame_usuarios_concessao = ctk.CTkFrame(self.frame_concessao)
        self.frame_usuarios_concessao.grid(
            row=2,
            column=0,
            columnspan=3,
            padx=14,
            pady=(0, 14),
            sticky="ew",
        )
        self.frame_usuarios_concessao.grid_columnconfigure(0, weight=1)

        self.label_usuarios_concessao = ctk.CTkLabel(
            self.frame_usuarios_concessao,
            text=f"USUÁRIOS (até {MAX_USUARIOS_UNITARIOS})",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.label_usuarios_concessao.grid(
            row=0,
            column=0,
            padx=12,
            pady=(12, 6),
            sticky="w",
        )

        self.frame_cabecalho_usuarios_concessao = ctk.CTkFrame(
            self.frame_usuarios_concessao,
            fg_color="transparent",
        )
        self.frame_cabecalho_usuarios_concessao.grid(
            row=1,
            column=0,
            padx=12,
            sticky="ew",
        )
        self.frame_cabecalho_usuarios_concessao.grid_columnconfigure(0, minsize=32)
        self.frame_cabecalho_usuarios_concessao.grid_columnconfigure(1, weight=2)
        self.frame_cabecalho_usuarios_concessao.grid_columnconfigure(2, weight=1)
        self.frame_cabecalho_usuarios_concessao.grid_columnconfigure(3, minsize=120)

        for coluna, texto in enumerate(("#", "Usuário alvo", "Protocolo", "Acesso próprio")):
            label = ctk.CTkLabel(
                self.frame_cabecalho_usuarios_concessao,
                text=texto,
                text_color="gray",
                font=ctk.CTkFont(size=12, weight="bold"),
            )
            label.grid(row=0, column=coluna, padx=(0, 8), pady=(0, 2), sticky="w")

        self.frame_linhas_usuarios_concessao = ctk.CTkFrame(
            self.frame_usuarios_concessao,
            fg_color="transparent",
        )
        self.frame_linhas_usuarios_concessao.grid(row=2, column=0, padx=12, sticky="ew")
        self.frame_linhas_usuarios_concessao.grid_columnconfigure(0, weight=1)

        self.frame_acoes_usuarios_concessao = ctk.CTkFrame(
            self.frame_usuarios_concessao,
            fg_color="transparent",
        )
        self.frame_acoes_usuarios_concessao.grid(
            row=3,
            column=0,
            padx=12,
            pady=(8, 12),
            sticky="ew",
        )
        self.frame_acoes_usuarios_concessao.grid_columnconfigure(1, weight=1)

        self.button_adicionar_usuario = ctk.CTkButton(
            self.frame_acoes_usuarios_concessao,
            text="+ Adicionar usuário",
            width=170,
            height=32,
            command=self._adicionar_linha_usuario_concessao,
        )
        self.button_adicionar_usuario.grid(row=0, column=0, sticky="w")

        self.label_contador_usuarios = ctk.CTkLabel(
            self.frame_acoes_usuarios_concessao,
            text="",
            text_color="gray",
        )
        self.label_contador_usuarios.grid(row=0, column=1, sticky="e")

        self.linhas_usuarios_concessao = []
        self._adicionar_linha_usuario_concessao()

    def _adicionar_linha_usuario_concessao(self) -> None:
        if len(self.linhas_usuarios_concessao) >= MAX_USUARIOS_UNITARIOS:
            self._atualizar_estado_linhas_usuarios_concessao()
            return

        indice = len(self.linhas_usuarios_concessao)

        frame_linha = ctk.CTkFrame(
            self.frame_linhas_usuarios_concessao,
            fg_color="transparent",
        )
        frame_linha.grid(row=indice, column=0, pady=3, sticky="ew")
        frame_linha.grid_columnconfigure(0, weight=1)

        frame_principal = ctk.CTkFrame(frame_linha, fg_color="transparent")
        frame_principal.grid(row=0, column=0, sticky="ew")
        frame_principal.grid_columnconfigure(0, minsize=32)
        frame_principal.grid_columnconfigure(1, weight=2)
        frame_principal.grid_columnconfigure(2, weight=1)
        frame_principal.grid_columnconfigure(3, minsize=120)
        frame_principal.grid_columnconfigure(4, minsize=36)
        frame_principal.grid_columnconfigure(5, minsize=36)

        linha: dict = {"container": frame_linha}

        label_indice = ctk.CTkLabel(
            frame_principal,
            text=str(indice + 1),
            text_color="gray",
            width=30,
        )
        label_indice.grid(row=0, column=0, padx=(0, 8), sticky="w")

        entry_login = ctk.CTkEntry(
            frame_principal,
            placeholder_text="Login do usuário",
            height=32,
        )
        entry_login.grid(row=0, column=1, padx=(0, 8), sticky="ew")

        entry_protocolo = ctk.CTkEntry(
            frame_principal,
            placeholder_text="Protocolo",
            height=32,
        )
        entry_protocolo.grid(row=0, column=2, padx=(0, 8), sticky="ew")

        var_proprio = tk.BooleanVar(value=False)
        checkbox_proprio = ctk.CTkCheckBox(
            frame_principal,
            text="Acesso próprio",
            variable=var_proprio,
            command=lambda linha_ref=linha: self._on_toggle_acesso_proprio(linha_ref),
        )
        checkbox_proprio.grid(row=0, column=3, padx=(0, 8), sticky="w")

        button_reset = ctk.CTkButton(
            frame_principal,
            text="↺",
            width=36,
            height=32,
            fg_color=("#E5E7EB", "#2B2B2B"),
            hover_color=("#D1D5DB", "#3A3A3A"),
            command=lambda linha_ref=linha: self._resetar_acesso_proprio(linha_ref),
        )
        button_reset.grid(row=0, column=4, sticky="e")
        button_reset.grid_remove()

        button_remover = ctk.CTkButton(
            frame_principal,
            text="\U0001F5D1",
            width=36,
            height=32,
            fg_color=("#E5E7EB", "#2B2B2B"),
            hover_color=("#D1D5DB", "#3A3A3A"),
            text_color=("#991B1B", "#FCA5A5"),
            command=lambda linha_ref=linha: self._remover_linha_usuario_concessao(linha_ref),
        )
        button_remover.grid(row=0, column=5, sticky="e")

        escopos = list(self.catalogo.escopos())
        escopo_inicial = escopos[0] if escopos else ""
        categorias = list(self.catalogo.categorias(escopo_inicial))
        categoria_inicial = categorias[0] if categorias else ""
        var_escopo_proprio = tk.StringVar(value=escopo_inicial)
        var_categoria_proprio = tk.StringVar(value=categoria_inicial)

        frame_proprio = ctk.CTkFrame(frame_linha, fg_color="transparent")
        frame_proprio.grid(row=1, column=0, padx=(38, 0), pady=(4, 0), sticky="ew")
        frame_proprio.grid_columnconfigure(1, weight=1)
        frame_proprio.grid_columnconfigure(3, weight=1)

        label_escopo_proprio = ctk.CTkLabel(frame_proprio, text="Escopo:")
        label_escopo_proprio.grid(row=0, column=0, padx=(0, 6), sticky="e")

        option_escopo_proprio = ctk.CTkOptionMenu(
            frame_proprio,
            values=escopos,
            variable=var_escopo_proprio,
            command=lambda escopo, linha_ref=linha: self._on_escopo_proprio_changed(
                linha_ref,
                escopo,
            ),
        )
        option_escopo_proprio.grid(row=0, column=1, padx=(0, 12), sticky="ew")

        label_categoria_proprio = ctk.CTkLabel(frame_proprio, text="Categoria:")
        label_categoria_proprio.grid(row=0, column=2, padx=(0, 6), sticky="e")

        option_categoria_proprio = ctk.CTkOptionMenu(
            frame_proprio,
            values=categorias,
            variable=var_categoria_proprio,
        )
        option_categoria_proprio.grid(row=0, column=3, sticky="ew")

        frame_proprio.grid_remove()

        linha.update(
            {
                "principal": frame_principal,
                "indice": label_indice,
                "login": entry_login,
                "protocolo": entry_protocolo,
                "var_proprio": var_proprio,
                "checkbox_proprio": checkbox_proprio,
                "button_reset": button_reset,
                "button_remover": button_remover,
                "frame_proprio": frame_proprio,
                "var_escopo_proprio": var_escopo_proprio,
                "var_categoria_proprio": var_categoria_proprio,
                "option_escopo_proprio": option_escopo_proprio,
                "option_categoria_proprio": option_categoria_proprio,
            }
        )
        self.linhas_usuarios_concessao.append(linha)
        self._atualizar_estado_linhas_usuarios_concessao()

        if indice > 0:
            entry_login.focus()

    def _remover_linha_usuario_concessao(self, linha_usuario: dict) -> None:
        if len(self.linhas_usuarios_concessao) <= 1:
            self._atualizar_estado_linhas_usuarios_concessao()
            return

        if linha_usuario not in self.linhas_usuarios_concessao:
            return

        linha_usuario["container"].destroy()
        self.linhas_usuarios_concessao.remove(linha_usuario)

        for indice, linha in enumerate(self.linhas_usuarios_concessao):
            linha["container"].grid_configure(row=indice)

        self._atualizar_estado_linhas_usuarios_concessao()

    def _on_toggle_acesso_proprio(self, linha_usuario: dict) -> None:
        if linha_usuario["var_proprio"].get():
            linha_usuario["frame_proprio"].grid()
            linha_usuario["button_reset"].grid()
        else:
            linha_usuario["frame_proprio"].grid_remove()
            linha_usuario["button_reset"].grid_remove()

    def _resetar_acesso_proprio(self, linha_usuario: dict) -> None:
        linha_usuario["var_proprio"].set(False)
        self._on_toggle_acesso_proprio(linha_usuario)

    def _on_escopo_proprio_changed(self, linha_usuario: dict, escopo: str) -> None:
        categorias = list(self.catalogo.categorias(escopo))
        categoria = categorias[0] if categorias else ""
        linha_usuario["option_categoria_proprio"].configure(values=categorias)
        linha_usuario["var_categoria_proprio"].set(categoria)
        linha_usuario["option_categoria_proprio"].set(categoria)

    def _atualizar_estado_linhas_usuarios_concessao(self) -> None:
        limite_atingido = (
            len(self.linhas_usuarios_concessao) >= MAX_USUARIOS_UNITARIOS
        )
        estado_campos = "disabled" if self.em_execucao else "normal"
        estado_adicionar = (
            "disabled" if self.em_execucao or limite_atingido else "normal"
        )
        estado_remover = (
            "normal"
            if not self.em_execucao and len(self.linhas_usuarios_concessao) > 1
            else "disabled"
        )

        self.button_adicionar_usuario.configure(state=estado_adicionar)
        self.label_contador_usuarios.configure(
            text=(
                f"{len(self.linhas_usuarios_concessao)} / "
                f"{MAX_USUARIOS_UNITARIOS} usuários"
            )
        )

        for indice, linha in enumerate(self.linhas_usuarios_concessao, start=1):
            linha["indice"].configure(text=str(indice))
            linha["login"].configure(state=estado_campos)
            linha["protocolo"].configure(state=estado_campos)
            linha["checkbox_proprio"].configure(state=estado_campos)
            linha["option_escopo_proprio"].configure(state=estado_campos)
            linha["option_categoria_proprio"].configure(state=estado_campos)
            linha["button_reset"].configure(state=estado_campos)
            linha["button_remover"].configure(state=estado_remover)

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
            text="Relatorio:",
        )
        self.label_relatorio_lote.grid(row=2, column=0, padx=14, pady=8, sticky="e")

        self.entry_relatorio_lote = ctk.CTkEntry(
            self.frame_lote,
            placeholder_text="Arquivo .xlsx de saida",
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

    def _criar_previa_perfis(self) -> None:
        self.text_perfis = ctk.CTkTextbox(self.frame_perfis, height=130)
        self.text_perfis.grid(
            row=1,
            column=0,
            columnspan=3,
            padx=14,
            pady=(0, 14),
            sticky="ew",
        )
        self.text_perfis.configure(state="disabled")

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
            title="Salvar relatorio como",
            defaultextension=".xlsx",
            initialfile=Path(caminho_relatorio_padrao()).name,
            filetypes=(("Excel", "*.xlsx"),),
        )

        if caminho:
            self.entry_relatorio_lote.delete(0, "end")
            self.entry_relatorio_lote.insert(0, caminho)

    def _on_escopo_changed(self, escopo: str) -> None:
        categorias = list(self.catalogo.categorias(escopo))
        categoria = categorias[0] if categorias else ""
        self.option_categoria.configure(values=categorias)
        self.var_categoria.set(categoria)
        self.option_categoria.set(categoria)
        self._atualizar_previa_perfis()

    def _atualizar_previa_perfis(self) -> None:
        escopo = self.var_escopo.get()
        categoria = self.var_categoria.get()

        try:
            regra = self.catalogo.obter_regra(escopo, categoria)
            linhas = []

            if regra.perfis_conceder:
                linhas.append("Conceder: " + ", ".join(regra.perfis_conceder))

            if regra.perfis_bloqueados:
                linhas.append("Bloqueados: " + ", ".join(regra.perfis_bloqueados))

            if regra.perfis_validacao_ura:
                linhas.append(
                    "Validação URA/STCOR: "
                    + ", ".join(regra.perfis_validacao_ura)
                )

            if regra.observacoes:
                linhas.append("Observações: " + " | ".join(regra.observacoes))

            texto = "\n".join(linhas) if linhas else "Nenhum perfil na regra selecionada."
        except Exception as exc:
            texto = f"Erro ao carregar regra: {exc}"

        self.text_perfis.configure(state="normal")
        self.text_perfis.delete("1.0", "end")
        self.text_perfis.insert("1.0", texto)
        self.text_perfis.configure(state="disabled")

    def _credenciais_e_url(self) -> tuple[str, str, str]:
        usuario_rede = self.entry_usuario_rede.get().strip()
        senha = self.entry_senha.get()
        url_aghu = obter_url_ambiente_aghu(self.var_ambiente.get())

        if not usuario_rede or not senha:
            raise ValueError("Preencha usuário de rede e senha.")

        return usuario_rede, senha, url_aghu

    def _resolver_acesso_efetivo(self, linha_usuario: dict) -> tuple[str, str]:
        if linha_usuario["var_proprio"].get():
            return (
                linha_usuario["var_escopo_proprio"].get(),
                linha_usuario["var_categoria_proprio"].get(),
            )

        return self.var_escopo.get(), self.var_categoria.get()

    def _entradas_concessao_individuais(self) -> list[ConcessaoPerfisEntrada]:
        entradas: list[ConcessaoPerfisEntrada] = []

        for linha in self.linhas_usuarios_concessao:
            login = linha["login"].get().strip()
            protocolo = linha["protocolo"].get().strip()

            if not login and not protocolo:
                continue

            escopo, categoria = self._resolver_acesso_efetivo(linha)
            entradas.append(
                ConcessaoPerfisEntrada(
                    login=login,
                    protocolo=protocolo,
                    escopo=escopo,
                    categoria=categoria,
                )
            )

        if not entradas:
            raise ValueError("Informe ao menos um usuário.")

        for entrada in entradas:
            erros = validar_entrada(entrada)
            if erros:
                raise ValueError("; ".join(erros))

        return entradas

    def _bloquear_execucao(self, texto_botao: str) -> None:
        self.em_execucao = True
        self.button_executar.configure(state="disabled", text=texto_botao)
        self.segment_tipo_execucao.configure(state="disabled")
        self.checkbox_browser.configure(state="disabled")
        self.checkbox_console.configure(state="disabled")
        self.option_ambiente.configure(state="disabled")
        self.entry_usuario_rede.configure(state="disabled")
        self.entry_senha.configure(state="disabled")
        self.option_escopo.configure(state="disabled")
        self.option_categoria.configure(state="disabled")
        self._atualizar_estado_linhas_usuarios_concessao()
        self.entry_planilha_lote.configure(state="disabled")
        self.entry_relatorio_lote.configure(state="disabled")
        self.button_planilha_lote.configure(state="disabled")
        self.button_relatorio_lote.configure(state="disabled")

    def _liberar_execucao(self) -> None:
        self.em_execucao = False
        self.segment_tipo_execucao.configure(state="normal")
        self.button_executar.configure(state="normal", text="Executar concessão")
        self.checkbox_browser.configure(state="normal")
        self.checkbox_console.configure(state="normal")
        self.option_ambiente.configure(state="normal")
        self.entry_usuario_rede.configure(state="normal")
        self.entry_senha.configure(state="normal")
        self.option_escopo.configure(state="normal")
        self.option_categoria.configure(state="normal")
        self._atualizar_estado_linhas_usuarios_concessao()
        self.entry_planilha_lote.configure(state="normal")
        self.entry_relatorio_lote.configure(state="normal")
        self.button_planilha_lote.configure(state="normal")
        self.button_relatorio_lote.configure(state="normal")

    def iniciar_execucao(self) -> None:
        if self.var_tipo_execucao.get() == TIPO_LOTE:
            self.iniciar_execucao_lote()
        else:
            self.iniciar_execucao_individual()

    def iniciar_execucao_individual(self) -> None:
        if self.em_execucao:
            return

        try:
            usuario_rede, senha, url_aghu = self._credenciais_e_url()
            entradas = self._entradas_concessao_individuais()
            mostrar_browser = bool(self.var_browser.get())
            mostrar_console = bool(self.var_console.get())
        except Exception as exc:
            self._mostrar_status(f"Erro: {exc}", "red")
            return

        self._mostrar_status("Executando concessão de perfis...", "blue")
        self._bloquear_execucao("Executando...")

        thread = threading.Thread(
            target=self._executar_thread,
            args=(
                usuario_rede,
                senha,
                entradas,
                url_aghu,
                mostrar_browser,
                mostrar_console,
            ),
            daemon=True,
        )
        thread.start()

    def _executar_thread(
        self,
        usuario_rede: str,
        senha: str,
        entradas: list[ConcessaoPerfisEntrada],
        url_aghu: str,
        mostrar_browser: bool,
        mostrar_console: bool,
    ) -> None:
        try:
            resultados = executar_concessoes_perfis(
                concessoes=entradas,
                usuario_rede=usuario_rede,
                senha=senha,
                url_aghu=url_aghu,
                mostrar_browser=mostrar_browser,
                mostrar_console=mostrar_console,
                diretorio_logs=LOGS_DIR,
            )

            if len(resultados) == 1:
                resultado = resultados[0]
                cor = (
                    "red"
                    if resultado.status in {STATUS_ERRO, STATUS_CONFERIR_MANUAL}
                    else "green"
                )
                mensagem = (
                    f"{resultado.login}: {resultado.status} - {resultado.detalhes}"
                )
            else:
                mensagem = self._resumir_resultados(
                    resultados,
                    prefixo="Execução unitária concluída",
                    rotulo_total="Total processado",
                )
                cor = (
                    "red"
                    if any(resultado.status == STATUS_ERRO for resultado in resultados)
                    else "green"
                )

            self.after(0, self._finalizar_execucao, mensagem, cor)
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
                raise ValueError("O relatorio de saida deve ser um arquivo .xlsx.")
        except Exception as exc:
            self._mostrar_status(f"Erro: {exc}", "red")
            return

        self._mostrar_status("Executando lote de concessao de perfis...", "blue")
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
            resultados, relatorio = executar_concessao_lote(
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
            mensagem = f"{resumo} Relatorio: {relatorio}"
            cor = (
                "red"
                if any(resultado.status == STATUS_ERRO for resultado in resultados)
                else "green"
            )
            self.after(0, self._finalizar_execucao, mensagem, cor)
        except Exception as exc:
            self.after(0, self._finalizar_execucao, f"Erro: {exc}", "red")

    def _resumir_resultados(
        self,
        resultados,
        prefixo: str = "Lote concluido",
        rotulo_total: str = "Total",
    ) -> str:
        contagem = Counter(resultado.status for resultado in resultados)
        total = len(resultados)

        return (
            f"{prefixo}. {rotulo_total}: {total}. "
            f"Concedidos: {contagem[STATUS_CONCEDIDO]}. "
            f"Ja existentes: {contagem[STATUS_JA_EXISTENTE]}. "
            f"Usuarios nao encontrados: {contagem[STATUS_USUARIO_NAO_ENCONTRADO]}. "
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

    app = AghuConcessorPerfisApp()
    app.mainloop()


if __name__ == "__main__":
    executar_interface()
