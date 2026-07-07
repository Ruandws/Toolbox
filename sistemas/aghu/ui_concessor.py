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
    executar_concessao_perfis,
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
        self.geometry("900x760")
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
        self.frame_perfis = self._criar_secao("Perfis da regra", 2)
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
        self.frame_perfis.grid(row=3, column=0, padx=0, pady=8, sticky="ew")

        self._criar_campos_acesso()
        self._criar_opcoes_execucao()
        self._criar_seletor_tipo_execucao()
        self._criar_campos_concessao(escopos, categorias)
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

    def _criar_campos_concessao(
        self,
        escopos: list[str],
        categorias: list[str],
    ) -> None:
        self.entry_login_alvo = self._criar_linha_entry(
            self.frame_concessao,
            row=1,
            label="Usuário alvo:",
            placeholder="Login do usuário",
        )
        self.entry_protocolo = self._criar_linha_entry(
            self.frame_concessao,
            row=2,
            label="Protocolo:",
            placeholder="Somente dígitos",
        )

        self.label_escopo = ctk.CTkLabel(self.frame_concessao, text="Escopo:")
        self.label_escopo.grid(row=3, column=0, padx=14, pady=8, sticky="e")

        self.option_escopo = ctk.CTkOptionMenu(
            self.frame_concessao,
            values=escopos,
            variable=self.var_escopo,
            command=self._on_escopo_changed,
        )
        self.option_escopo.grid(
            row=3,
            column=1,
            columnspan=2,
            padx=14,
            pady=8,
            sticky="ew",
        )

        self.label_categoria = ctk.CTkLabel(self.frame_concessao, text="Categoria:")
        self.label_categoria.grid(row=4, column=0, padx=14, pady=8, sticky="e")

        self.option_categoria = ctk.CTkOptionMenu(
            self.frame_concessao,
            values=categorias,
            variable=self.var_categoria,
            command=lambda _: self._atualizar_previa_perfis(),
        )
        self.option_categoria.grid(
            row=4,
            column=1,
            columnspan=2,
            padx=14,
            pady=(8, 14),
            sticky="ew",
        )

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

    def _entrada_concessao(self) -> ConcessaoPerfisEntrada:
        return ConcessaoPerfisEntrada(
            login=self.entry_login_alvo.get(),
            protocolo=self.entry_protocolo.get(),
            escopo=self.var_escopo.get(),
            categoria=self.var_categoria.get(),
        )

    def _bloquear_execucao(self, texto_botao: str) -> None:
        self.em_execucao = True
        self.button_executar.configure(state="disabled", text=texto_botao)
        self.segment_tipo_execucao.configure(state="disabled")
        self.checkbox_browser.configure(state="disabled")
        self.checkbox_console.configure(state="disabled")
        self.option_ambiente.configure(state="disabled")
        self.entry_usuario_rede.configure(state="disabled")
        self.entry_senha.configure(state="disabled")
        self.entry_login_alvo.configure(state="disabled")
        self.entry_protocolo.configure(state="disabled")
        self.option_escopo.configure(state="disabled")
        self.option_categoria.configure(state="disabled")
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
        self.entry_login_alvo.configure(state="normal")
        self.entry_protocolo.configure(state="normal")
        self.option_escopo.configure(state="normal")
        self.option_categoria.configure(state="normal")
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
            entrada = self._entrada_concessao()
            erros = validar_entrada(entrada)

            if erros:
                raise ValueError("; ".join(erros))

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
                entrada,
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
        entrada: ConcessaoPerfisEntrada,
        url_aghu: str,
        mostrar_browser: bool,
        mostrar_console: bool,
    ) -> None:
        try:
            resultado = executar_concessao_perfis(
                entrada=entrada,
                usuario_rede=usuario_rede,
                senha=senha,
                url_aghu=url_aghu,
                mostrar_browser=mostrar_browser,
                mostrar_console=mostrar_console,
                diretorio_logs=LOGS_DIR,
            )
            cor = (
                "red"
                if resultado.status in {STATUS_ERRO, STATUS_CONFERIR_MANUAL}
                else "green"
            )
            mensagem = (
                f"{resultado.login}: {resultado.status} - {resultado.detalhes}"
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

    def _resumir_resultados(self, resultados) -> str:
        contagem = Counter(resultado.status for resultado in resultados)
        total = len(resultados)

        return (
            f"Lote concluido. Total: {total}. "
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
