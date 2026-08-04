# RFC-008 — Importação e Cadastro de Usuários no AGHUX (`criar_usuario_aghu` / `ui_criar_usuario_aghu`)

- **Status:** Estável
- **Autor:** Ruan
- **Data:** 2026-02-15
- **Atualizado em:** 2026-08-04
- **Arquivos:** `criar_usuario_aghu.py` (Núcleo) / `ui_criar_usuario_aghu.py` (Interface Gráfica)
- **Depende de:** `autenticador.py` (RFC-005)
- **Depende de:** `menu.py` (RFC-004)
- **Chamado por:** `ui_criar_usuario_aghu.py` (Interface Gráfica) e scripts de automação CLI/Lote

---

## 1. Resumo

`criar_usuario_aghu.py` e `ui_criar_usuario_aghu.py` constituem o módulo de automação responsável pela consulta, importação e provisionamento de usuários no sistema AGHUX (módulo de acesso).

O motor robótico (`criar_usuario_aghu.py`) consome dados de usuários no formato `UsuarioImportacao` (contendo unicamente `login`, `nome_completo` e `email`), valida credenciais e formatos, interage com a interface JSF do AGHUX via Playwright, pesquisa a existência prévia do usuário no sistema e, quando necessário, realiza a busca e importação a partir da base do Identity Manager / LDAP corporativo, preenchendo o formulário de cadastro e ativando a conta.

A interface gráfica (`ui_criar_usuario_aghu.py`), desenvolvida em `customtkinter`, atua como camada de apresentação desktop thread-safe. Ela oferece dois modos de operação (Unitária para até 5 usuários simultâneos em grade dinâmica e Lote via planilha `.xlsx`), além de seletor de ambiente (Produção / Homologação), controle visual de execução (browser/console) e geração automática de relatórios `.xlsx` auditáveis e logs CSV.

---

## 2. Mudanças incorporadas nesta revisão

Esta revisão reescreve integralmente a RFC-008 para alinhar a documentação com o código real do repositório:

| Área | Situação na RFC antiga (fictícia) | Situação real no código atual |
|---|---|---|
| Nome do arquivo | `RFC-008_criar_usuario_aghu.md` (hífen) | Renomeado para `RFC_008_criar_usuario_aghu.md` (padrão com underscore) |
| Modelo de dados | `UsuarioImportacao` com 7 campos (`nome`, `cpf`, `login`, `email`, `matricula`, `perfil`, `vinculo`) e validação Módulo 11 de CPF | `UsuarioImportacao` com 3 campos reais: `login`, `nome_completo`, `email`. Não existem campos nem validações de CPF, matrícula, perfil ou vínculo |
| Status de resultado | Status em inglês/maiúsculo (`SUCESSO`, `JA_EXISTE`, `ERRO_VALIDACAO`, `ERRO_EXECUCAO`) e objeto com `timestamp` | 6 valores reais minúsculos: `importado`, `ja_importado`, `nao_encontrado`, `erro`, `ignorado`, `conferir_manualmente`. Estrutura achatada em `ResultadoImportacao` |
| Constantes e Seletores | Constantes genéricas fabricadas (`TIMEOUT_PADRAO`, `URL_AGHUX_LOGIN`, seletores `#username_input`, `input[id*="cpf"]`) | Constantes e seletores reais: `TEMPO_MAXIMO_CONSULTA_USUARIO_MS = 130000`, `TEMPO_MAXIMO_GRAVACAO_USUARIO_MS = 10000`, `SELECTOR_PESQUISA_LOGIN`, `SELECTOR_IMPORTACAO_LOGIN`, `SELECTOR_CADASTRO_NOME`, `SELECTOR_CADASTRO_EMAIL` |
| Autenticação e Navegação | Lógica local manual e seletores de login de CPF | Delegados a `autenticador.py` (`autenticar_aghu_page`, `exigir_login_valido`) e `menu.py` (`navegar_menu_aghu` com `CAMINHO_MENU_CADASTRO_USUARIO`) |
| Normalização de Login | Caixa baixa (`lower`) | `.strip().upper()` (maiúsculas), com suporte a sublinhado (`_`), ponto, hífen e letras/números |
| Biblioteca de UI | `tkinter` / `ttk` nativo com `ScrolledText` | `customtkinter` (`CTk`, `CTkSegmentedButton`, `CTkScrollableFrame`, `CTkOptionMenu`), sem `ScrolledText` ou barra de progresso |
| Alerta de Produção | Alerta com fundo vermelho | Alerta em tonalidade Âmbar/Amarelo (`#FFF4CE` / `#3A2D00`), conforme padrão visual do projeto |
| Métodos da UI | Nomes fictícios (`_atualizar_status_ui`, `_bloquear_interface`) | Nomes reais: `_mostrar_status`, `_bloquear_execucao`, `_liberar_execucao`, `_validar_opcoes_visibilidade` |
| Regras de UI | Checkboxes de visibilidade independentes | Regra de mútua obrigatoriedade entre browser visual e terminal de logs |

---

## 3. Motivação

O cadastramento manual de novos usuários no AGHUX é um procedimento operacional repetitivo que envolve consultar a base local do AGHUX, alternar para a busca no Identity Manager/LDAP corporativo quando não localizado, importar a conta encontrada, preencher nome completo, e-mail institucional e marcar a opção de usuário ativo.

A automação centraliza esse fluxo em um pipeline auditável com tratamento de falhas transientes (Clean State via nova aba de navegador), validação rigorosa pré-execução (fail-fast sem instanciar browser para dados inválidos) e emissão de relatórios consolidados.

A separação em duas camadas (`criar_usuario_aghu.py` para as regras de negócio e automação Playwright; `ui_criar_usuario_aghu.py` para a interface desktop responsiva) garante reutilização por scripts automatizados ou por operadores via GUI.

---

## 4. Arquitetura e Fluxo de Dados

```text
[ui_criar_usuario_aghu.py / Chamador CLI]
        │
        ├─► Entrada de Dados (Planilha .xlsx ou Formulário Unitário da UI)
        │        │
        │        └─► ler_planilha_usuarios / coletar_usuarios_individuais
        │
        ├─► Validação Pré-Execução (Fail-Fast síncrono)
        │        ├─ _validar_lote_usuarios / _preparar_usuario_importacao
        │        ├─ Verifica campos obrigatórios em branco (Login, Nome Completo, E-mail)
        │        ├─ Valida formato de login (sem espaços, regex ^[A-Za-z0-9._-]+$)
        │        ├─ Valida e-mail (regex ^[^@\s]+@[^@\s]+\.[^@\s]+$) e espaços em nome/e-mail
        │        └─ Registros inválidos ──► Status: "ignorado" (sem abrir navegador)
        │
        └─► Registros Válidos ──► executar_importacao_usuarios
                 │
                 ├─ Playwright sync_playwright() → Launch Chromium (Headless ou Visual)
                 ├─ browser.new_context(ignore_https_errors=True) → page.goto(url_aghu)
                 ├─ fazer_login(page, usuario_rede, senha, url_aghu=url_aghu)
                 │     └─ autenticar_aghu_page + exigir_login_valido (autenticador.py)
                 │
                 ├─ navegar_ate_cadastro_usuario(context, page, ...)
                 │     └─ navegar_menu_aghu (menu.py: Outros Módulos → Configuração → Acesso → Usuario)
                 │
                 └─ Para cada usuário válido:
                       │
                       ├─ garantir_tela_pesquisa_usuario
                       │
                       ├─ importar_usuario(janela_sistema, usuario)
                       │     ├─ 1. Pesquisa no AGHUX por Login (SELECTOR_PESQUISA_LOGIN)
                       │     │    ├─ Encontrado ──► Status: "ja_importado"
                       │     │    └─ Indefinido ──► Status: "conferir_manualmente"
                       │     │
                       │     ├─ 2. Não encontrado localmente ──► Clica em "Importar Usuário"
                       │     │
                       │     ├─ 3. Pesquisa no Identity Manager (SELECTOR_IMPORTACAO_LOGIN)
                       │     │    ├─ Não encontrado / Linha ausente ──► Status: "nao_encontrado"
                       │     │    └─ Indefinido ──► Status: "conferir_manualmente"
                       │     │
                       │     ├─ 4. Localizado no Identity Manager ──► Clica em "Adicionar"
                       │     │
                       │     ├─ 5. Preenche Cadastro (Nome, E-mail, Marca Ativo) e clica em "Gravar"
                       │     │    ├─ Sucesso ("Usuário incluído com sucesso") ──► Status: "importado"
                       │     │    ├─ Mensagem de Duplicado ──► Status: "ja_importado"
                       │     │    ├─ Mensagem de Erro ──► Status: "erro"
                       │     │    └─ Timeout / Sem mensagem ──► Status: "conferir_manualmente"
                       │     │
                       │     └─ Em caso de falha técnica de browser/DOM no laço:
                       │          ├─ 1ª tentativa: Aciona Clean State (trocar_aba_aghux + renavega)
                       │          └─ 2ª tentativa: Registra Status: "erro" (Falha técnica definitiva)
                       │
                       └─ Consolidação de Resultados:
                            ├─ Salva relatório .xlsx (salvar_relatorio_resultados)
                            └─ Gera log CSV com header auditável (_gerar_csv_logs)
```

---

## 5. Dependências

### 5.1 Blocos de Importação Reais

#### 5.1.1 Núcleo de Automação (`criar_usuario_aghu.py`)

```python
import ctypes
import os
import re
import time
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Literal

import pandas as pd
from playwright.sync_api import BrowserContext, FrameLocator, Locator, Page, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from autenticador import AGHU_URL, autenticar_aghu_page, exigir_login_valido
from menu import navegar_menu_aghu
```

#### 5.1.2 Interface Gráfica (`ui_criar_usuario_aghu.py`)

```python
import threading
import tkinter as tk
from collections import Counter
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from autenticador import AGHU_URL, AGHU_URL_HOMOLOGACAO
from criar_usuario_aghu import (
    STATUS_CONFERIR_MANUALMENTE,
    STATUS_ERRO,
    STATUS_IGNORADO,
    STATUS_IMPORTADO,
    STATUS_JA_IMPORTADO,
    STATUS_NAO_ENCONTRADO,
    UsuarioImportacao,
    executar_importacao_lote,
    executar_importacao_usuarios,
)
```

### 5.2 Tabela de Responsabilidades por Dependência

| Item | Origem | Responsabilidade |
|---|---|---|
| `autenticador.py` (RFC-005) | Interna | Prover `AGHU_URL`, `AGHU_URL_HOMOLOGACAO`, executar `autenticar_aghu_page` e validar via `exigir_login_valido` |
| `menu.py` (RFC-004) | Interna | Executar `navegar_menu_aghu` para percorrer o caminho `Outros Módulos → Configuração → Acesso → Usuario` |
| `playwright` | Terceiros | Automação de navegador Chromium em modo síncrono |
| `customtkinter` | Terceiros | Framework moderno para interface gráfica responsiva |
| `pandas` / `openpyxl` | Terceiros | Leitura de planilhas de lote e exportação de relatórios `.xlsx` e logs `.csv` |

---

## 6. Constantes e Seletores de Módulo

### 6.1 Constantes de Regra de Negócio e Sistema

| Constante | Valor | Uso / Descrição |
|---|---|---|
| `BASE_DIR` | `Path(__file__).resolve().parent` | Diretório base dos scripts |
| `CAMINHO_MENU_CADASTRO_USUARIO` | `("Outros Módulos", "Configuração", "Acesso", "Usuario")` | Caminho de menu no AGHUX |
| `COLUNAS_OBRIGATORIAS_PLANILHA` | `("Login", "Nome Completo", "E-mail")` | Nomes canônicos das colunas obrigatórias |
| `ALIASES_COLUNAS_PLANILHA` | `dict[str, tuple[str, ...]]` | Mapeamento de aliases aceitos por coluna na planilha |
| `PADRAO_EMAIL_MINIMO` | `re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")` | Regex de formato básico de e-mail |
| `PADRAO_LOGIN_VALIDO` | `re.compile(r"^[A-Za-z0-9._-]+$")` | Regex de caracteres válidos no login corporativo |
| `TEMPO_MAXIMO_CONSULTA_USUARIO_MS` | `130000` (130 s) | Timeout máximo para consultas no AGHUX |
| `TEMPO_MAXIMO_GRAVACAO_USUARIO_MS` | `10000` (10 s) | Timeout máximo para confirmação de gravação |
| `TEMPO_DETECCAO_WIDGET_CARREGAMENTO_MS` | `2000` (2 s) | Janela de detecção do widget "Aguarde..." |
| `TEMPO_ESTABILIDADE_RESULTADO_MS` | `250` ms | Tempo de confirmação visual para resultado de tabela |
| `MAX_USUARIOS_MANUAIS` | `5` | Limite máximo de linhas na interface gráfica unitária |

### 6.2 Seletores CSS / DOM do AGHUX

| Constante Seletor | Valor CSS | Descrição no DOM |
|---|---|---|
| `SELECTOR_PESQUISA_LOGIN` | `'[id="nomeOuLogin:nomeOuLogin:inputId"]'` | Campo de texto de pesquisa por login na tela principal |
| `SELECTOR_IMPORTACAO_LOGIN` | `'[id="nomeOuLoginNaoCadastrado:nomeOuLoginNaoCadastrado:inputId"]'` | Campo de pesquisa de login na modal do Identity Manager |
| `SELECTOR_CADASTRO_NOME` | `'input[name="nome:nome:inputId"]'` | Campo de preenchimento de Nome Completo no formulário |
| `SELECTOR_CADASTRO_EMAIL` | `'input[name="email:email:inputId"]'` | Campo de preenchimento de E-mail no formulário |
| `SELECTOR_TABELA_USUARIOS` | `'[id="tabelaUsuarios:resultList_data"] > tr'` | Linhas da tabela de resultados de usuários cadastrados |
| `SELECTOR_TABELA_IDENTITY` | `'[id="tabelaUsuariosIdentityManager:resultList_data"] > tr'` | Linhas da tabela de resultados no Identity Manager |
| `TEXTO_NENHUM_REGISTRO` | `"Nenhum registro encontrado!"` | Texto indicador de ausência de registros na tabela JSF |

---

## 7. Modelo de Dados e Status de Resultado

### 7.1 Dataclass `UsuarioImportacao`

```python
@dataclass(frozen=True)
class UsuarioImportacao:
    login: str
    nome_completo: str
    email: str
```

> **Atenção:** Não existem campos de CPF, Matrícula, Perfil ou Vínculo nesta estrutura.

### 7.2 Dataclass `ResultadoImportacao`

```python
@dataclass(frozen=True)
class ResultadoImportacao:
    login: str
    nome_completo: str
    email: str
    status: StatusImportacao
    detalhes: str
```

### 7.3 Valores de `StatusImportacao`

```python
StatusImportacao = Literal[
    "importado",
    "ja_importado",
    "nao_encontrado",
    "erro",
    "ignorado",
    "conferir_manualmente",
]
```

| Status | Significado Operacional |
|---|---|
| `importado` | Usuário localizado no Identity Manager, cadastrado e ativado com sucesso no AGHUX |
| `ja_importado` | Usuário já constava cadastrado previamente no AGHUX ou o sistema retornou alerta de duplicidade |
| `nao_encontrado` | Usuário não foi localizado na base do Identity Manager / LDAP corporativo |
| `erro` | Ocorreu erro de gravação retornado pelo AGHUX ou falha técnica não recuperável |
| `ignorado` | Linha rejeitada no fail-fast pré-execução (campos obrigatórios ausentes ou formatos inválidos) |
| `conferir_manualmente` | A consulta ou gravação expirou ou não retornou estado conclusivo no DOM |

---

## 8. API Pública do Núcleo (`criar_usuario_aghu.py`)

### 8.1 `ler_planilha_usuarios(caminho_planilha: str) -> list[UsuarioImportacao]`

Lê um arquivo `.xlsx` de lote, verifica a presença das colunas obrigatórias (`Login`, `Nome Completo`, `E-mail`) aceitando variações via `ALIASES_COLUNAS_PLANILHA`, e retorna uma lista de instâncias `UsuarioImportacao`. Lança `FileNotFoundError` se o arquivo não existir ou `ValueError` caso a extensão ou colunas sejam inválidas.

### 8.2 `fazer_login(page: Page, usuario_rede: str, senha: str, *, url_aghu: str = AGHU_URL) -> ResultadoLogin`

Wrapper de login local que chama `autenticar_aghu_page` do `autenticador.py` e valida a sessão com `exigir_login_valido`.

### 8.3 `trocar_aba_aghux(context: BrowserContext, page_atual: Page, usuario_rede: str, senha: str, *, url_aghu: str = AGHU_URL) -> Page`

Implementa o mecanismo de Clean State do módulo: fecha a página atual, cria uma nova página limpa no contexto, navega para `url_aghu` e executa a reautenticação.

### 8.4 `navegar_ate_cadastro_usuario(context: BrowserContext, page_atual: Page, usuario_rede: str, senha: str, *, url_aghu: str = AGHU_URL) -> tuple[Page, FrameLocator]`

Utiliza `navegar_menu_aghu` (`menu.py`) para acessar `CAMINHO_MENU_CADASTRO_USUARIO`. Valida a presença de `SELECTOR_PESQUISA_LOGIN` e do botão "Pesquisar". Realiza até 2 tentativas acionando Clean State em caso de falha inicial.

### 8.5 `garantir_tela_pesquisa_usuario(context: BrowserContext, page_atual: Page, janela_atual: FrameLocator, usuario_rede: str, senha: str, *, url_aghu: str = AGHU_URL) -> tuple[Page, FrameLocator]`

Garante idempotência no estado da tela entre processamentos de linhas: se a tela de pesquisa estiver visível, mantém a execução; caso contrário, renavega via menu ou aciona Clean State.

### 8.6 `importar_usuario(janela_sistema: FrameLocator, usuario: UsuarioImportacao) -> ResultadoImportacao`

Executa a sequência completa de automação no DOM para uma conta:
1. Pesquisa no AGHUX pelo login.
2. Se já existir, retorna `ja_importado`.
3. Se não existir, abre a modal de importação.
4. Pesquisa no Identity Manager.
5. Se não encontrar, retorna `nao_encontrado`.
6. Se encontrar, clica em "Adicionar", preenche os campos do formulário, ativa a conta e clica em "Gravar".
7. Retorna o `ResultadoImportacao` conforme a mensagem capturada no DOM.

### 8.7 `processar_usuarios(context, page_inicial, janela_sistema_inicial, usuarios, usuario_rede, senha, *, url_aghu=AGHU_URL, ...) -> list[ResultadoImportacao]`

Laço principal de processamento de uma lista de `UsuarioImportacao`. Para cada item, executa a importação com até 2 tentativas contra falhas técnicas (usando Clean State na primeira falha).

### 8.8 `executar_importacao_usuarios(usuarios, usuario_rede, senha, *, url_aghu=AGHU_URL, mostrar_browser=True, mostrar_console=True, diretorio_logs=None, gerar_csv_log=True) -> list[ResultadoImportacao]`

Ponto de entrada principal para orquestração:
1. Executa `_validar_lote_usuarios` (fail-fast pré-browser).
2. Se houver usuários válidos, inicializa o Playwright/Chromium.
3. Autentica no AGHUX, navega até o módulo, processa os registros válidos e combina os resultados com os ignorados respeitando a ordem original.
4. Exporta logs em CSV e retorna a lista consolidada.

### 8.9 `executar_importacao_lote(...) -> tuple[list[ResultadoImportacao], Path]`

Orquestra a leitura da planilha `.xlsx`, dispara `executar_importacao_usuarios` e salva o relatório final de saída `.xlsx` formatado via `salvar_relatorio_resultados`.

### 8.10 `executar_importacao_individual(...) -> ResultadoImportacao`

Wrapper para processamento de um único usuário via `executar_importacao_usuarios`.

---

## 9. Funções Auxiliares e Regras Internas

### 9.1 Saneamento e Normalização

- `_normalizar_login(valor)`: Aplica `.strip().upper()`. O login é convertido para maiúsculas e valida os caracteres `^[A-Za-z0-9._-]+$`.
- `_normalizar_nome_completo(valor)`: Colapsa múltiplos espaços em branco internos e remove espaços nas extremidades.
- `_validar_usuario(usuario)`: Retorna a lista de erros de validação da linha (campos em branco, caracteres inválidos em login, formato mínimo de e-mail ou espaços embutidos indevidos).

### 9.2 Manipulação do DOM e Widgets JSF

- `_primeiro_visivel(janela_sistema, seletores, timeout_ms)`: Tenta localizar o primeiro seletor visível dentre uma lista.
- `_aguardar_ciclo_carregamento_consulta(janela_sistema)`: Monitora os spinners/widgets de "Aguarde..." do AGHUX para garantir estabilidade antes de ler tabelas.
- `_aguardar_mensagem_gravacao(janela_sistema, timeout_ms)`: Monitora `#messagesInDialog` e captura mensagens de sucesso ("Usuário incluído com sucesso"), duplicidade ("Já existe um usuário com este") ou erro.

---

## 10. Interface Gráfica Desktop (`ui_criar_usuario_aghu.py`)

### 10.1 Visão Geral e Tecnologia

A interface foi implementada utilizando a biblioteca `customtkinter` (classe `AghuImportUserApp` herdando de `ctk.CTk`), oferecendo um visual moderno em modo escuro/claro com componentes responsivos:
- **Campos de Acesso:** Usuário de rede, Senha e Seletor de Ambiente (`Produção` e `Homologação`).
- **Painel de Alerta de Ambiente:** Exibe aviso visual destacado em **Âmbar/Amarelo** (`#FFF4CE` / `#3A2D00`) quando o ambiente de **Produção** estiver selecionado.
- **Seletor de Tipo de Execução:** `CTkSegmentedButton` alternando entre `Unitária` e `Lote`.
- **Modo Unitário:** Grade dinâmica editável permitindo incluir de 1 até 5 linhas de usuários (`MAX_USUARIOS_MANUAIS = 5`).
- **Modo Lote:** Seletores de arquivos de entrada `.xlsx` e caminho do relatório final.
- **Opções de Visibilidade (Regra de Mútua Obrigatoriedade):** Checkboxes "Exibir Navegador (Modo Visual)" e "Exibir Terminal de processos (logs)". Se o operador tentar desmarcar ambos, a aplicação exibe um `messagebox.showwarning` e força a permanência de ao menos uma opção ativa para evitar processos invisíveis em segundo plano.

### 10.2 Tabela de Métodos da Classe `AghuImportUserApp`

| Método da UI | Tipo | Finalidade e Comportamento |
|---|---|---|
| `__init__` | Construtor | Inicializa a janela principal (`820x760`), variáveis de controle, layout em grid e renderiza todas as seções |
| `_criar_campos_acesso` | Privado | Constrói os campos de credencial, seletor de ambiente e o quadro de alerta de Produção |
| `_on_ambiente_changed` | Evento | Dispara pop-up de aviso quando o ambiente é alterado para "Produção" |
| `_atualizar_alerta_ambiente` | Privado | Exibe ou oculta o painel amarelo de alerta de Produção conforme o valor do combobox |
| `_criar_opcoes_execucao` | Privado | Constrói os checkboxes de visibilidade de Browser e Console |
| `_validar_opcoes_visibilidade` | Privado | Enforça a regra de mútua obrigatoriedade (impede desativar Browser e Console simultaneamente) |
| `_criar_seletor_tipo_execucao` | Privado | Constrói o `CTkSegmentedButton` para alternar entre Execução Unitária e Lote |
| `_atualizar_tipo_execucao` | Privado | Alterna a visibilidade dos frames `frame_individual` e `frame_lote` |
| `_criar_campos_individual` | Privado | Constrói a grade de cadastro manual com cabeçalhos ("Login", "Nome completo", "E-mail") |
| `adicionar_linha_usuario` | Público | Adiciona uma nova linha de campos na grade manual (respeitando o limite de 5) |
| `remover_linha_usuario` | Público | Destrói a linha selecionada e reordena os índices das linhas remanescentes |
| `coletar_usuarios_individuais` | Público | Extrai os dados digitados na grade e retorna `list[UsuarioImportacao]` |
| `_atualizar_estado_lista_usuarios` | Privado | Atualiza a viabilidade dos botões "+ Adicionar usuário" e ícones de lixeira conforme o limite e estado de execução |
| `_criar_campos_lote` | Privado | Constrói os campos de seleção de planilha `.xlsx` e relatório de saída |
| `selecionar_planilha_lote` | Evento | Abre caixa de diálogo `askopenfilename` para selecionar a planilha Excel |
| `selecionar_relatorio_lote` | Evento | Abre caixa de diálogo `asksaveasfilename` para definir o destino do relatório |
| `_credenciais_e_url` | Privado | Coleta e valida se usuário de rede, senha e URL de ambiente foram preenchidos |
| `_bloquear_execucao` | Privado | Desabilita todos os controles e entradas da interface durante a execução da thread |
| `_liberar_execucao` | Privado | Reabilita os controles da interface após o término da execução |
| `_mostrar_status` | Privado | Atualiza o texto e a cor da label de status no rodape da aplicação |
| `iniciar_execucao` | Handler | Ponto de entrada que direciona para execução unitária ou em lote |
| `iniciar_execucao_individual` | Handler | Valida credenciais e linhas manuais e dispara a `_executar_individual_thread` |
| `_executar_individual_thread` | Worker | Executa `executar_importacao_usuarios` em segundo plano (`threading.Thread`) |
| `iniciar_execucao_lote` | Handler | Valida arquivos `.xlsx` e dispara a `_executar_lote_thread` |
| `_executar_lote_thread` | Worker | Executa `executar_importacao_lote` em segundo plano (`threading.Thread`) |
| `_finalizar_execucao` | Privado | Callback thread-safe acionado via `self.after` para restaurar a UI e exibir o resultado final |
| `_resumir_resultados` | Utilitário | Gera string resumida com contadores de status para exibição no rodapé e pop-up |

---

## 11. Recuperação de Falhas Técnicas

O módulo emprega uma estratégia em camadas para resiliência contra instabilidades de rede e do AGHUX:

1. **Retries com Clean State:** No processamento de cada usuário (`processar_usuarios`), a primeira falha técnica de DOM/timeout dispara `trocar_aba_aghux`. A aba antiga com estado corrompido é encerrada, uma nova aba é instanciada no contexto, reautenticada via `autenticar_aghu_page` e a navegação até a tela de usuários é refeita antes da segunda tentativa.
2. **Isolamento por Linha:** Uma falha definitiva em determinado usuário não interrompe o lote. O erro é anotado em seu `ResultadoImportacao` e o motor prossegue para os demais registros.
3. **Idempotência de Navegação:** `garantir_tela_pesquisa_usuario` verifica a prontidão dos seletores de busca antes de interagir, evitando retrabalho de navegação quando o formulário já estiver pronto.

---

## 12. Relatórios de Auditoria e Logs

Ao concluir a execução, o sistema produz dois tipos de registros auditáveis:

### 12.1 Relatório em Planilha Excel (`.xlsx`)

Gerado por `salvar_relatorio_resultados` / `executar_importacao_lote`:
- **Formatação:** Congelamento da primeira linha (`freeze_panes = "A2"`), ativação de filtros automáticos (`auto_filter`) e ajuste automático da largura de colunas.
- **Colunas:** `Login`, `Nome Completo`, `E-mail`, `Status`, `Detalhes`.

### 12.2 Log de Auditoria em CSV (`_gerar_csv_logs`)

Salvo no diretório `logs/log_resultado_{YYYYMMDD_HHMMSS}.csv`:
- Contém o cabeçalho de auditoria de primeira linha: `Atualizado por: <usuario_rede>`.
- Codificação UTF-8 com BOM (`utf-8-sig`) e separador ponto e vírgula (`;`).

---

## 13. Contratos entre RFCs

### 13.1 Contrato com RFC-005 (`autenticador.py`)

- `criar_usuario_aghu.py` importa `AGHU_URL`, `AGHU_URL_HOMOLOGACAO`, `autenticar_aghu_page` e `exigir_login_valido`.
- A validação de credenciais, tratamento de sessão ativa e exceções de login pertencem exclusivamente ao `autenticador.py`.

### 13.2 Contrato com RFC-004 (`menu.py`)

- `criar_usuario_aghu.py` declara a constante local `CAMINHO_MENU_CADASTRO_USUARIO = ("Outros Módulos", "Configuração", "Acesso", "Usuario")`.
- A travessia da árvore de menus é realizada chamando `navegar_menu_aghu(page=page, caminho=CAMINHO_MENU_CADASTRO_USUARIO)`.

---

## 14. Considerações Operacionais e Boas Práticas

1. **Credenciais Corporativas:** A senha do operador nunca é gravada em logs ou arquivos de relatório.
2. **Ambiente de Execução:** O operador deve atentar para a seleção de ambiente na UI. O alerta na cor âmbar na interface previne inserções acidentais em Produção.
3. **Saneamento Pré-Playwright:** O fail-fast economiza tempo e recursos ao impedir a abertura do navegador para planilhas contendo erros grosseiros de digitação ou campos obrigatórios ausentes.
4. **Respeito às Regras da UI:** A trava de mútua obrigatoriedade garante que a automação não rode em modo "fantasma" sem qualquer visibilidade de erros.

---

## 15. Estado Atual da RFC

Esta RFC reflete com fidelidade o código-fonte atual dos arquivos `criar_usuario_aghu.py` e `ui_criar_usuario_aghu.py`. Todas as inconsistências da versão anterior (modelo de 7 campos, CPF, status em inglês, seletores fictícios e Tkinter nativo) foram totalmente eliminadas e substituídas pela especificação técnica real.
