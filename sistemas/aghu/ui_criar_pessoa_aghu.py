import threading
from collections import Counter
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from cadastro_pessoa_aghu import (
    CadastroPessoaEntrada,
    STATUS_ATUALIZADO,
    STATUS_CONFERIR_MANUAL,
    STATUS_CRIADO,
    STATUS_ERRO,
    STATUS_IGNORADO,
    STATUS_MANTIDO,
    executar_cadastro_individual,
    executar_cadastro_lote,
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

SEXO_MASCULINO = "Masculino"
SEXO_FEMININO = "Feminino"
OPCOES_SEXO = (SEXO_MASCULINO, SEXO_FEMININO)

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"


CAMPOS_PESSOA = (
    ("nome_pessoa", "Nome da Pessoa:", "Nome completo"),
    ("nome_mae", "Nome da Mãe:", "Nome completo da mãe"),
    ("sexo", "Sexo:", "Masculino ou Feminino"),
    ("data_nascimento", "Data de Nascimento:", "dd/mm/aaaa"),
    ("nacionalidade", "Nacionalidade:", "Ex.: Brasileira"),
    ("naturalidade", "Naturalidade:", "Município/UF ou texto do AGHU"),
    ("rg", "Nro identidade:", "RG"),
    ("orgao_emissor", "Órgão Emissor:", "Ex.: SSP"),
    ("uf_rg", "UF:", "Ex.: DF"),
    ("cpf", "CPF:", "Somente números ou formatado"),
    ("ddd", "DDD:", "Ex.: 61"),
    ("telefone_celular", "Telefone Celular:", "Número do celular"),
    ("cep_cadastrado", "CEP Cadastrado:", "CEP já cadastrado no AGHU"),
    ("logradouro_nao_cadastrado", "Logradouro:", "Logradouro não cadastrado"),
    ("bairro_nao_cadastrado", "Bairro:", "Bairro não cadastrado"),
    ("cep_nao_cadastrado", "CEP Não Cadastrado:", "CEP não cadastrado"),
    ("municipio_nao_cadastrado", "Município:", "Município não cadastrado"),
)

def obter_url_ambiente_aghu(ambiente: str) -> str:
    return URLS_AMBIENTE_AGHU.get(ambiente, AGHU_URL)


def caminho_relatorio_padrao(base: str = "") -> str:
    nome = f"relatorio_cadastro_pessoas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    if base:
        caminho_base = Path(base)
        diretorio = caminho_base.parent if caminho_base.suffix else caminho_base
        return str(diretorio / nome)

    return str(Path.cwd() / nome)


class AghuCadastroPessoaApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AGHUX Bot - Cadastro de Pessoa")
        self.geometry("900x820")
        self.minsize(760, 650)
        self.resizable(True, True)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.var_ambiente = tk.StringVar(value=AMBIENTE_HOMOLOGACAO)
        self.var_tipo_execucao = tk.StringVar(value=TIPO_INDIVIDUAL)
        self.var_browser = tk.BooleanVar(value=True)
        self.var_console = tk.BooleanVar(value=True)
        self.var_sexo = tk.StringVar(value=SEXO_MASCULINO)
        self.segment_sexo: ctk.CTkSegmentedButton | None = None
        self.em_execucao = False
        self.entries_individual: dict[str, ctk.CTkEntry] = {}

        self.label_title = ctk.CTkLabel(
            self,
            text="AGHUX Bot - Cadastro de Pessoa",
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

    def _criar_subsecao(self, frame: ctk.CTkFrame, row: int, titulo: str) -> int:
        label = ctk.CTkLabel(
            frame,
            text=titulo,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        label.grid(row=row, column=0, columnspan=3, padx=14, pady=(18, 6), sticky="w")
        return row + 1

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
                "Ação bloqueada",
                "Para evitar processos invisíveis, mantenha o navegador ou o terminal ativo.",
                parent=self,
            )

    def _criar_campos_individual(self) -> None:
        row = 1
        row = self._criar_subsecao(self.frame_individual, row, "Pessoa")
        row = self._criar_grupo_campos(self.frame_individual, row, CAMPOS_PESSOA)

    def _criar_grupo_campos(
        self,
        frame: ctk.CTkFrame,
        row_inicial: int,
        campos: tuple[tuple[str, str, str], ...],
    ) -> int:
        row = row_inicial

        for nome_campo, label, placeholder in campos:
            if nome_campo == "sexo":
                self.segment_sexo = self._criar_linha_seletor_sexo(
                    frame=frame,
                    row=row,
                    label=label,
                )
            else:
                self.entries_individual[nome_campo] = self._criar_linha_entry(
                    frame=frame,
                    row=row,
                    label=label,
                    placeholder=placeholder,
                )

            row += 1

        return row

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
        label_widget.grid(row=row, column=0, padx=14, pady=6, sticky="e")

        entry = ctk.CTkEntry(frame, placeholder_text=placeholder)
        entry.grid(row=row, column=1, columnspan=2, padx=14, pady=6, sticky="ew")
        return entry
        
    
    def _criar_linha_seletor_sexo(
        self,
        frame: ctk.CTkFrame,
        row: int,
        label: str,
    ) -> ctk.CTkSegmentedButton:
        label_widget = ctk.CTkLabel(frame, text=label)
        label_widget.grid(row=row, column=0, padx=14, pady=6, sticky="e")

        segment = ctk.CTkSegmentedButton(
            frame,
            values=list(OPCOES_SEXO),
            variable=self.var_sexo,
            command=self._atualizar_visual_sexo,
            height=34,
            selected_color=("#1F6AA5", "#144870"),
            selected_hover_color=("#155E96", "#0F3A5A"),
            unselected_color=("#D9D9D9", "#333333"),
            unselected_hover_color=("#C9C9C9", "#3D3D3D"),
        )
        segment.grid(row=row, column=1, columnspan=2, padx=14, pady=6, sticky="ew")
        segment.set(SEXO_MASCULINO)

        self._atualizar_visual_segmented_button(segment, SEXO_MASCULINO)

        return segment


    def _atualizar_visual_sexo(self, sexo: str) -> None:
        if self.segment_sexo is None:
            return

        self._atualizar_visual_segmented_button(self.segment_sexo, sexo)


    def _atualizar_visual_segmented_button(
        self,
        segment: ctk.CTkSegmentedButton,
        valor_selecionado: str,
    ) -> None:
        for valor, btn in segment._buttons_dict.items():
            if valor == valor_selecionado:
                btn.configure(text_color="white")
            else:
                btn.configure(text_color=("#1F6AA5", "#3B8ED0"))

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
        tipo = self.var_tipo_execucao.get()

        if tipo == TIPO_INDIVIDUAL:
            self.iniciar_execucao_individual()
        else:
            self.iniciar_execucao_lote()

    def _credenciais_e_url(self) -> tuple[str, str, str]:
        usuario_rede = self.entry_usuario_rede.get().strip()
        senha = self.entry_senha.get()
        url_aghu = obter_url_ambiente_aghu(self.var_ambiente.get())

        if not usuario_rede or not senha:
            raise ValueError("Preencha usuário de rede e senha.")

        return usuario_rede, senha, url_aghu

    def _cadastro_individual(self) -> CadastroPessoaEntrada:
        dados = {
            nome_campo: entry.get().strip()
            for nome_campo, entry in self.entries_individual.items()
        }

        sexo = self.var_sexo.get().strip()

        if sexo not in OPCOES_SEXO:
            raise ValueError("Selecione o sexo: Masculino ou Feminino.")

        dados["sexo"] = sexo

        return CadastroPessoaEntrada(**dados)

        return CadastroPessoaEntrada(**dados)

    def _bloquear_execucao(self, texto_botao: str) -> None:
        self.em_execucao = True
        self.button_executar.configure(state="disabled", text=texto_botao)
        self.segment_tipo_execucao.configure(state="disabled")
        self.checkbox_browser.configure(state="disabled")
        self.checkbox_console.configure(state="disabled")
        self.option_ambiente.configure(state="disabled")
        self.button_planilha_lote.configure(state="disabled")
        self.button_relatorio_lote.configure(state="disabled")

    def _liberar_execucao(self) -> None:
        self.em_execucao = False
        self.button_executar.configure(state="normal", text="Executar cadastro")
        self.segment_tipo_execucao.configure(state="normal")
        self.checkbox_browser.configure(state="normal")
        self.checkbox_console.configure(state="normal")
        self.option_ambiente.configure(state="normal")
        self.button_planilha_lote.configure(state="normal")
        self.button_relatorio_lote.configure(state="normal")

    def iniciar_execucao_individual(self) -> None:
        if self.em_execucao:
            return

        try:
            usuario_rede, senha, url_aghu = self._credenciais_e_url()
            cadastro = self._cadastro_individual()
            mostrar_browser = bool(self.var_browser.get())
            mostrar_console = bool(self.var_console.get())
        except Exception as exc:
            self._mostrar_status(f"Erro: {exc}", "red")
            return

        self._mostrar_status("Executando cadastro individual...", "blue")
        self._bloquear_execucao("Executando...")

        thread = threading.Thread(
            target=self._executar_individual_thread,
            args=(
                usuario_rede,
                senha,
                cadastro,
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
        cadastro: CadastroPessoaEntrada,
        url_aghu: str,
        mostrar_browser: bool,
        mostrar_console: bool,
    ) -> None:
        try:
            resultado = executar_cadastro_individual(
                usuario_rede=usuario_rede,
                senha=senha,
                cadastro=cadastro,
                url_aghu=url_aghu,
                mostrar_browser=mostrar_browser,
                mostrar_console=mostrar_console,
                diretorio_logs=LOGS_DIR,
            )
            mensagem = (
                f"{resultado.cpf or resultado.nome_pessoa}: "
                f"{resultado.status} - {resultado.detalhes}"
            )
            cor = "green" if resultado.status not in {STATUS_ERRO, STATUS_IGNORADO} else "red"
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
            resultados, relatorio = executar_cadastro_lote(
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
            self.after(0, self._finalizar_execucao, mensagem, "green")
        except Exception as exc:
            self.after(0, self._finalizar_execucao, f"Erro: {exc}", "red")

    def _resumir_resultados(self, resultados) -> str:
        contagem = Counter(resultado.status for resultado in resultados)
        total = len(resultados)

        return (
            f"Lote concluído. Total: {total}. "
            f"Criados: {contagem[STATUS_CRIADO]}. "
            f"Atualizados: {contagem[STATUS_ATUALIZADO]}. "
            f"Mantidos: {contagem[STATUS_MANTIDO]}. "
            f"Conferir manualmente: {contagem[STATUS_CONFERIR_MANUAL]}. "
            f"Ignorados: {contagem[STATUS_IGNORADO]}. "
            f"Erros: {contagem[STATUS_ERRO]}."
        )

    def _finalizar_execucao(self, mensagem: str, cor: str) -> None:
        self._mostrar_status(mensagem, cor)
        self._liberar_execucao()

    def _mostrar_status(self, mensagem: str, cor: str) -> None:
        self.label_status.configure(text=mensagem, text_color=cor)


if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    app = AghuCadastroPessoaApp()
    app.mainloop()
