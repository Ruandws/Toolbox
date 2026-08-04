# RFC-003 — Interface Gráfica e Empacotador de Execução (ui_alignprinterAGHU)

- **Status:** Estável
- **Autor:** Pedro e Ruan
- **Data:** 2026-06
- **Atualizado em:** 2026-08-04
- **Arquivo:** `ui_alignprinterAGHU.py`
- **Depende de:** `PrinterAGHU.py` (RFC-001)
- **Depende de:** `autenticador.py`
- **Depende indiretamente de:** `AddPrinterAGHU.py` (RFC-002)
- **Depende indiretamente de:** `menu.py` (RFC-004)
- **Chamado por:** operador (ponto de entrada direto); não é chamado por outro módulo Python

---

## 1. Resumo

`ui_alignprinterAGHU.py` é a **camada de interface gráfica e empacotamento operacional** da automação de impressoras do AGHUX. Ele não implementa a regra principal de vínculo nem o cadastro mestre de impressoras. Em vez disso, coleta credenciais e caminhos, configura opções de execução, inicia o Playwright, chama o Maestro (`PrinterAGHU.py`, RFC-001) e exibe a mensagem de conclusão retornada pelo núcleo.

A UI também importa `AGHU_URL` e `AGHU_URL_HOMOLOGACAO` de `autenticador.py`, refletindo a centralização das URLs e da autenticação. O operador escolhe o ambiente na interface, e a URL resolvida é enviada ao Maestro para login, navegação, processamento e retries em Clean State.

Quando empacotado como executável congelado (PyInstaller), o arquivo contém um bloco de bootstrap que configura o ambiente do Playwright antes de qualquer importação dependente de browsers — papel de **Empacotador de Execução** citado neste título.

---

## 2. Mudanças incorporadas nesta revisão

| Área | Situação atual |
|---|---|
| URL do AGHUX | Importada de `autenticador.py` como `AGHU_URL` e `AGHU_URL_HOMOLOGACAO` |
| Seletor de ambiente | `CTkOptionMenu` permite escolher `Produção` ou `Homologação`; Produção é o padrão |
| Alerta de Produção | Painel visível quando `Produção` está selecionado, avisando que alterações serão feitas no AGHUX produtivo |
| Constante antiga | Não há `AGHU_URL_PRODUCAO` na UI atual |
| Execução | `executar_automacao_aghu` cria Playwright, browser, context e page, e recebe `url_aghu` |
| Browser | `headless=not mostrar_browser` e `slow_mo=500 if mostrar_browser else 0` |
| Contexto | `browser.new_context(ignore_https_errors=True)` |
| Entrada | Aceita apenas `.xlsx` no seletor de arquivo |
| Saída | Campo de **diretório** (pasta), não arquivo; o nome do relatório é definido pelo Maestro |
| Relatório | Retorno direto de `processar_computadores` — string com o caminho salvo |
| Antiprocesso invisível | Impede navegador e terminal desativados simultaneamente |
| Bootstrap executável | Bloco `if getattr(sys, "frozen", False)` configura browsers do Playwright antes da importação |

---

## 3. Motivação

A automação precisa ser operada por usuário técnico, com credenciais de rede, seleção de arquivo de entrada e escolha da pasta de destino do relatório. Essas tarefas são de interface e não pertencem ao núcleo de processamento.

Esta camada separa o uso humano do processamento automatizado. O Maestro continua responsável por navegar e corrigir vínculos, enquanto a UI cuida de experiência operacional: campos de login, seleção de ambiente, seleção de planilha e pasta, opção de exibir navegador, opção de exibir terminal, prevenção de processo invisível, execução em thread e exibição do caminho do relatório gerado.

---

## 4. Arquitetura e Fluxo de Dados

```text
[Operador]
    │
    └─► AghuPrinterApp (customtkinter)
          │
          ├─► Coleta:
          │     ├─ Usuário de rede
          │     ├─ Senha
          │     ├─ Ambiente (Produção ou Homologação)
          │     ├─ Exibir navegador
          │     ├─ Exibir terminal
          │     ├─ Planilha de entrada (.xlsx)
          │     └─ Pasta de relatório (diretório)
          │
          ├─► start_automation()
          │     ├─ Valida campos obrigatórios
          │     ├─ Valida extensão da planilha de entrada
          │     ├─ Valida se pasta de relatório existe
          │     ├─ Desabilita botão de execução
          │     └─ Inicia thread daemon
          │
          └─► run_playwright_task()
                │
                └─► executar_automacao_aghu(...)
                      ├─ Oculta console se necessário
                      ├─ Cria os.chdir(BASE_DIR)
                      ├─ Abre Chromium com Playwright
                      │     slow_mo=500 se mostrar_browser, senão 0
                      ├─ Cria BrowserContext com ignore_https_errors=True
                      ├─ Acessa url_aghu
                      ├─ Chama fazer_login(..., url_aghu=url_aghu) do Maestro
                      ├─ Chama navegar_ate_modulo(..., url_aghu=url_aghu) do Maestro
                      ├─ Chama processar_computadores(..., url_aghu=url_aghu) do Maestro
                      ├─ Fecha browser em finally
                      └─ Retorna "Processo concluido. Relatorio salvo em: {caminho}"
```

---

## 5. Dependências

### 5.1 `PrinterAGHU.py`

A UI importa:

```python
from PrinterAGHU import (
    fazer_login,
    navegar_ate_modulo,
    processar_computadores,
    validate_spreadsheet_extension,
)
```

| Item | Responsabilidade |
|---|---|
| `fazer_login` | Autentica a sessão usando o autenticador centralizado |
| `navegar_ate_modulo` | Navega até o módulo **Impressora por Computador** e retorna `(page, janela_sistema)` |
| `processar_computadores` | Processa cada linha da planilha, gerencia vínculos e gera o XLSX de auditoria; retorna o caminho do arquivo gerado |
| `validate_spreadsheet_extension` | Valida a extensão do arquivo de entrada antes de iniciar a automação; lança `ValueError` se inválida |

Essas funções executam o núcleo da automação. A UI não acessa diretamente funções do Almoxarifado.

### 5.2 `autenticador.py`

A UI importa:

```python
from autenticador import AGHU_URL, AGHU_URL_HOMOLOGACAO
```

| Item | Responsabilidade |
|---|---|
| `AGHU_URL` | URL padrão do AGHUX em Produção |
| `AGHU_URL_HOMOLOGACAO` | URL do AGHUX em Homologação |

As URLs do AGHUX não são constantes soltas dentro do fluxo de execução. Elas vêm do autenticador centralizado, que também é usado pelo Maestro e pelo Almoxarifado. A UI monta um mapa de ambiente e resolve a URL por `obter_url_ambiente_aghu`.

### 5.3 `AddPrinterAGHU.py`

A dependência é indireta. A UI chama o Maestro; o Maestro chama o Almoxarifado quando precisa cadastrar uma impressora ausente.

### 5.4 `menu.py`

A dependência é indireta. O Maestro e o Almoxarifado importam `navegar_menu_aghu` de `menu.py` (RFC-004) para percorrer caminhos completos de menu declarados nos próprios procedimentos. A UI não interage diretamente com a navegação de menu.

---

## 6. Constantes Globais

| Constante | Valor / Função |
|---|---|
| `BASE_DIR` | Diretório do arquivo `ui_alignprinterAGHU.py` |
| `AGHU_URL` | Importada de `autenticador.py`; URL padrão de Produção |
| `AGHU_URL_HOMOLOGACAO` | Importada de `autenticador.py`; URL de Homologação |
| `AMBIENTE_PRODUCAO` | Rótulo `Produção` usado no seletor da UI |
| `AMBIENTE_HOMOLOGACAO` | Rótulo `Homologação` usado no seletor da UI |
| `URLS_AMBIENTE_AGHU` | Mapa entre rótulo de ambiente e URL efetiva |

Não existe `LOGS_DIR` nesta UI. Não existe `AGHU_URL_PRODUCAO` nesta UI. Qualquer referência a esses nomes deve ser substituída por `AGHU_URL` ou pelo mapa `URLS_AMBIENTE_AGHU`, conforme o caso.

O helper `obter_url_ambiente_aghu(ambiente)` retorna a URL correspondente ao rótulo selecionado, com fallback para `AGHU_URL` se o valor recebido não estiver no mapa.

---

## 7. Bloco de Bootstrap para Executável Congelado

Imediatamente após os imports de biblioteca padrão, antes de importar o Playwright, o arquivo contém:

```python
if getattr(sys, "frozen", False):
    from _launcher_runtime import bootstrap_playwright_browsers_path
    bootstrap_playwright_browsers_path()
```

E, após os imports de Playwright:

```python
sys.path.append(str(Path(__file__).resolve().parent.parent))
```

Este bloco é executado **somente quando o script roda como executável empacotado** (PyInstaller/Nuitka, onde `sys.frozen` é `True`). Ele delega a `_launcher_runtime` a configuração das variáveis de ambiente e caminhos necessários para o Playwright localizar os browsers empacotados junto ao executável.

A linha `sys.path.append` expande o `sys.path` para incluir o diretório pai do módulo, permitindo que as importações de `PrinterAGHU` e `autenticador` funcionem independentemente do diretório de trabalho corrente.

> **Nota operacional:** `_launcher_runtime` é um módulo gerado pelo processo de empacotamento. Ele não deve ser criado ou editado manualmente. Em modo não-congelado (execução via `python ui_alignprinterAGHU.py`), esse bloco é ignorado.

---

## 8. Funções do Módulo

### 8.1 Funções Privadas

#### `obter_url_ambiente_aghu(ambiente: str) → str`

Helper local que consulta `URLS_AMBIENTE_AGHU` e retorna a URL correspondente ao rótulo de ambiente selecionado. Se o rótulo não for reconhecido, usa `AGHU_URL` como fallback.

Usado exclusivamente em `start_automation` para resolver a URL antes de criar a thread de execução.

#### `esconder_console_windows() → None`

Oculta a janela do console apenas em Windows (`os.name == "nt"`) usando:

```python
ctypes.windll.kernel32.GetConsoleWindow()
ctypes.windll.user32.ShowWindow(hwnd, 0)
```

Em outros sistemas operacionais, retorna sem ação. É chamada dentro de `executar_automacao_aghu` quando o operador desmarca **Exibir Terminal de processos (logs)**.

### 8.2 Funções Públicas

#### `executar_automacao_aghu(...) → str`

É o adaptador entre UI e núcleo de automação.

Assinatura:

```python
executar_automacao_aghu(
    usuario: str,
    senha: str,
    mostrar_console: bool,
    mostrar_browser: bool,
    caminho_planilha_entrada: str,
    diretorio_relatorio: str,
    url_aghu: str = AGHU_URL,
) -> str
```

> **Atenção:** o parâmetro de destino do relatório é `diretorio_relatorio: str` — um **diretório** (pasta), não um arquivo. O nome do arquivo XLSX é definido pelo Maestro em `processar_computadores`.

Fluxo interno:

1. Valida usuário e senha.
2. Valida se `url_aghu` foi informado.
3. Oculta console se `mostrar_console` for falso.
4. Executa `os.chdir(BASE_DIR)`.
5. Abre Playwright.
6. Abre Chromium com:

```python
headless=not mostrar_browser
slow_mo=500 if mostrar_browser else 0
```

7. Cria contexto com:

```python
ignore_https_errors=True
```

8. Cria nova página.
9. Acessa `url_aghu`.
10. Chama `fazer_login(page, usuario, senha, url_aghu=url_aghu)` do Maestro.
11. Chama `navegar_ate_modulo(context, page, usuario, senha, url_aghu=url_aghu)`.
12. Chama `processar_computadores(context, page, janela_sistema, caminho_planilha_entrada, usuario, senha, diretorio_relatorio, url_aghu=url_aghu)`.
13. Fecha o browser em `finally`.
14. Retorna a string de conclusão fornecida por `processar_computadores`.

Retorno:

```text
"Processo concluido. Relatorio salvo em: {caminho_relatorio}"
```

onde `caminho_relatorio` é o caminho absoluto do XLSX gerado pelo Maestro, conforme retornado diretamente por `processar_computadores`.

---

## 9. Classe `AghuPrinterApp`

Classe principal da interface gráfica, derivada de `ctk.CTk`.

Características da janela:

| Propriedade | Valor |
|---|---|
| Título | `AGHUX Bot - Impressoras` |
| Tamanho | `760x590` |
| Redimensionável | Não |
| Coluna principal | `grid_columnconfigure(0, weight=1)` |
| Tema | Definido no `__main__` como `System` |
| Cor padrão | Definida no `__main__` como `blue` |

Campos criados:

| Grupo | Elementos |
|---|---|
| Login | Usuário de rede, senha mascarada |
| Ambiente | Seletor `Produção`/`Homologação` e painel de alerta para Produção |
| Execução | Checkboxes de navegador e terminal |
| Planilhas | Entrada (arquivo `.xlsx`) e pasta de relatório com botões de seleção |
| Controle | Botão `Iniciar Robô` e label de status |

### 9.1 Métodos de montagem

| Método | Responsabilidade |
|---|---|
| `create_login_fields` | Monta campos de usuário e senha |
| `create_environment_fields` | Monta seletor de ambiente e painel de alerta de Produção |
| `create_execution_options` | Monta checkboxes de navegador/terminal |
| `create_spreadsheet_fields` | Monta campos de planilha de entrada e pasta de relatório |
| `on_environment_changed` | Atualiza o alerta quando o operador troca o ambiente |
| `update_environment_alert` | Exibe o painel quando o ambiente é Produção e oculta em Homologação |

### 9.2 Métodos de seleção de arquivo e pasta

| Método | Responsabilidade |
|---|---|
| `select_input_spreadsheet` | Abre `askopenfilename` filtrando **apenas `.xlsx`**; se o campo de pasta estiver vazio, preenche automaticamente com o diretório pai da planilha selecionada |
| `select_report_directory` | Abre `askdirectory` para o operador escolher a pasta onde o relatório XLSX será salvo |

> **Atenção:** `select_report_directory` usa `filedialog.askdirectory`, **não** um save-dialog de arquivo. O resultado é um caminho de diretório onde o arquivo XLSX será gravado.

### 9.3 Métodos de execução

| Método | Responsabilidade |
|---|---|
| `start_automation` | Valida formulário, desabilita botão e cria thread daemon |
| `run_playwright_task` | Executa `executar_automacao_aghu` fora da thread principal da UI |
| `finish_automation` | Atualiza status final e reabilita botão |
| `show_status` | Atualiza texto e cor do label de status |

### 9.4 Seletor de ambiente

O seletor de ambiente é um `CTkOptionMenu` controlado por `self.var_ambiente`, com `Produção` selecionado por padrão.

Mapeamento atual:

| Opção | URL |
|---|---|
| `Produção` | `AGHU_URL` |
| `Homologação` | `AGHU_URL_HOMOLOGACAO` |

Quando `Produção` está selecionado, a UI exibe um painel persistente com o alerta:

```text
Atenção: você está alterando para o Ambiente de Produção. As alterações serão executadas no AGHUX de produção.
```

Ao iniciar a automação, `start_automation` resolve `url_aghu = obter_url_ambiente_aghu(ambiente)` e passa a URL para a thread de execução.

---

## 10. Regra Anti-Zombie

A UI impede que o operador desmarque simultaneamente:

```text
Exibir Navegador (Modo Visual)
Exibir Terminal de processos (logs)
```

Se isso ocorrer, a última opção alterada é reativada e a UI exibe:

```text
Para evitar processos invisíveis, mantenha o navegador ou o terminal ativo.
```

Essa regra evita execução invisível: Chromium em headless sem console aparente, o que dificultaria supervisão ou interrupção manual.

---

## 11. Validações de Formulário

Antes de iniciar a thread, `start_automation` valida na seguinte ordem:

| Campo | Mensagem em erro |
|---|---|
| Usuário ou senha vazios | `Erro: preencha usuário de rede e senha.` |
| Planilha de entrada vazia | `Erro: informe a planilha de entrada.` |
| Pasta de relatório vazia | `Erro: informe a pasta de relatorio.` |
| Extensão da planilha inválida | `Erro: <mensagem de validate_spreadsheet_extension>` |
| Pasta de relatório não existe no sistema de arquivos | `Erro: <mensagem de NotADirectoryError>` |

A validação de extensão usa `validate_spreadsheet_extension` importada de `PrinterAGHU.py`. A validação de pasta usa `Path(diretorio_relatorio).expanduser().is_dir()`, lançando `NotADirectoryError` se o caminho não for um diretório existente.

Durante a execução, exceções de qualquer etapa são capturadas em `run_playwright_task` e enviadas para `finish_automation` com status vermelho.

---

## 12. Contrato com o Maestro (RFC-001)

A UI entrega ao Maestro:

| Item | Origem |
|---|---|
| `context` | `browser.new_context(ignore_https_errors=True)` |
| `page` | `context.new_page()` já aberta em `url_aghu` |
| `url_aghu` | URL resolvida pelo seletor `Produção`/`Homologação` |
| `usuario` | Campo de usuário da interface |
| `senha` | Campo de senha da interface |
| `caminho_planilha_entrada` | Caminho string do arquivo `.xlsx` de entrada |
| `diretorio_relatorio` | Caminho string da pasta onde o Maestro gravará o XLSX |

A UI chama:

```python
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
```

A UI não chama o Almoxarifado diretamente. O repasse de `url_aghu` garante que retries e Clean States no Maestro permaneçam no ambiente escolhido pelo operador.

---

## 13. Relatório Final

O núcleo (`processar_computadores`) gera o relatório XLSX e retorna o caminho do arquivo gerado. A UI exibe esse caminho diretamente ao operador.

A string de retorno é:

```text
"Processo concluido. Relatorio salvo em: {caminho_relatorio}"
```

onde `caminho_relatorio` é o valor retornado por `processar_computadores` — o caminho absoluto do XLSX gravado pelo Maestro no `diretorio_relatorio` informado.

---

## 14. Execução como Script

Quando executado diretamente:

```python
if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    app = AghuPrinterApp()
    app.mainloop()
```

A UI é inicializada com tema do sistema e cor padrão azul.

---

## 15. Recuperação de Falhas Técnicas

Falhas durante a execução são tratadas na UI apenas como captura e exibição de mensagem:

| Momento | Ação |
|---|---|
| Validação pré-execução (`start_automation`) | Exibe mensagem de erro em vermelho e interrompe; botão permanece ativo |
| Durante a execução (`run_playwright_task`) | Qualquer exceção não tratada é capturada; `finish_automation` exibe `Erro: <mensagem>` em vermelho e reabilita o botão |

A recuperação técnica de falhas de navegação, aba instável e delegação ao Almoxarifado ocorre exclusivamente dentro do Maestro (RFC-001, §11). A UI não tenta reabrir o browser nem reexecutar a automação automaticamente.

O botão **Iniciar Robô** é reabilitado em qualquer desfecho (sucesso ou erro), permitindo nova tentativa sem reiniciar o aplicativo.

---

## 16. API Pública do Módulo

| Função | Responsabilidade |
|---|---|
| `executar_automacao_aghu(usuario, senha, mostrar_console, mostrar_browser, caminho_planilha_entrada, diretorio_relatorio, url_aghu)` | Inicia o Playwright, autentica, executa a automação via Maestro e retorna a mensagem de conclusão com o caminho do relatório |

A classe `AghuPrinterApp` é o ponto de entrada da interface gráfica. Nenhuma outra função deste módulo é projetada para uso externo.

---

## 17. Contratos entre RFCs

### 17.1 Contrato com RFC-001 (Maestro)

| Item | Fornecido pela UI | Usado pelo Maestro |
|---|---|---|
| `BrowserContext` | `browser.new_context(ignore_https_errors=True)` | Abre novas abas em Clean State |
| `Page` | `context.new_page()` apontada para `url_aghu` | Login e navegação |
| `url_aghu` | Resolvida pelo seletor de ambiente | Propagada em todos retries e Clean States |
| `caminho_planilha_entrada` | String com caminho do `.xlsx` | Leitura e validação pelo Maestro |
| `diretorio_relatorio` | String com caminho do diretório de saída | Gravação do XLSX auditável |
| Retorno | — | Caminho do XLSX gerado, exibido pela UI ao operador |

### 17.2 Contrato com RFC-002 (Almoxarifado)

A UI não interage com RFC-002. O Maestro delega ao Almoxarifado quando necessário. A UI não tem ciência desse fluxo.

---

## 18. Considerações Operacionais

1. `ui_alignprinterAGHU.py` cria o `Browser`, `BrowserContext` e `Page`; o Maestro recebe esses objetos já prontos.
2. O `slow_mo` do Chromium é `500 ms` apenas quando o navegador está visível (`mostrar_browser=True`); em modo headless é `0`.
3. O parâmetro `url_aghu` deve ser propagado pela UI para todas as chamadas ao Maestro, garantindo que retries e Clean States permaneçam no ambiente selecionado.
4. O campo de relatório coleta um **diretório** (pasta), não um arquivo. O operador não informa nome de arquivo; o Maestro define o nome com timestamp.
5. O seletor de entrada aceita exclusivamente `.xlsx`. Arquivos `.xlsm` e `.csv` não são aceitos pelo diálogo de seleção da UI.
6. O bootstrap de executável congelado (`_launcher_runtime`) deve ser executado **antes** de qualquer `import` do Playwright. A ordem de importações no topo do arquivo é intencional e não deve ser reordenada.
7. A thread de execução é daemon: encerrar a janela durante a execução interrompe a thread sem limpeza controlada do browser.

---

## 19. Limitações Conhecidas

| Limitação | Impacto |
|---|---|
| Execução usa thread daemon sem botão de cancelamento | Interrupção controlada pela UI ainda não existe |
| Ocultação de console só funciona em Windows | Em outros sistemas, `esconder_console_windows` não tem efeito |
| Leitura e validação da planilha ocorrem no Maestro, não na UI | Erros de colunas ausentes são reportados apenas após o browser abrir |
| Não há reexecução automática em caso de falha | O operador deve reiniciar manualmente clicando em **Iniciar Robô** |

---

## 20. Estado Atual da RFC

Esta RFC passa a refletir o código atual de `ui_alignprinterAGHU.py`, incluindo:

- Uso de `AGHU_URL` e `AGHU_URL_HOMOLOGACAO` vindos de `autenticador.py`, seletor Produção/Homologação com alerta de Produção.
- Criação do Playwright na camada de UI, execução em thread daemon.
- Assinatura correta de `executar_automacao_aghu` com `diretorio_relatorio: str`.
- Ausência de funções de leitura/normalização de planilha na UI; a leitura e a geração do relatório .xlsx ocorrem inteiramente no Maestro (`ler_planilha`/`write_xlsx_report`).
- Seletor de entrada restrito a `.xlsx`; campo de saída é diretório (pasta), não arquivo.
- `slow_mo` condicional: `500` com browser visível, `0` em headless.
- Validações de formulário com mensagens exatas do código.
- `validate_spreadsheet_extension` importada de `PrinterAGHU.py` e usada na validação pré-execução.
- Bloco de bootstrap para executável congelado documentado em §7.
- Regra anti-processo invisível e seletor de ambiente documentados.
- Seções adicionadas seguindo o padrão de RFC-001: "Recuperação de Falhas Técnicas", "API Pública do Módulo", "Contratos entre RFCs" e "Considerações Operacionais".
