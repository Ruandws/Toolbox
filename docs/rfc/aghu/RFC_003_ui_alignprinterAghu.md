# RFC-003 — Interface Gráfica e Empacotador de Execução (ui_alignprinterAGHU)

- **Status:** Estável
- **Autor:** Pedro e Ruan
- **Data:** 2026-06
- **Atualizado em:** 2026-06-19
- **Arquivo:** `ui_alignprinterAGHU.py`
- **Depende de:** `PrinterAGHU.py` (RFC-001)
- **Depende de:** `autenticador.py`
- **Depende indiretamente de:** `AddPrinterAGHU.py` (RFC-002)
- **Depende indiretamente de:** `menu.py` (RFC-004)

---

## 1. Resumo

`ui_alignprinterAGHU.py` é a **camada de interface gráfica e empacotamento operacional** da automação de impressoras do AGHUX. Ele não implementa a regra principal de vínculo nem o cadastro mestre de impressoras. Em vez disso, coleta credenciais e caminhos de planilha, configura opções de execução, inicia o Playwright, chama o Maestro (`PrinterAGHU.py`, RFC-001) e converte o relatório CSV gerado pelo núcleo para uma planilha XLSX formatada.

A UI também importa `AGHU_URL` e `AGHU_URL_HOMOLOGACAO` de `autenticador.py`, refletindo a centralização das URLs e da autenticação. O operador escolhe o ambiente na interface, e a URL resolvida é enviada ao Maestro para login, navegação, processamento e retries em Clean State.

---

## 2. Mudanças incorporadas nesta revisão

| Área | Situação atual |
|---|---|
| URL do AGHUX | Importada de `autenticador.py` como `AGHU_URL` e `AGHU_URL_HOMOLOGACAO` |
| Seletor de ambiente | `CTkOptionMenu` permite escolher `Produção` ou `Homologação`; Produção é o padrão |
| Alerta de Produção | Painel visível quando `Produção` está selecionado, avisando que alterações serão feitas no AGHUX produtivo |
| Constante antiga | Não há `AGHU_URL_PRODUCAO` na UI atual |
| Execução | `executar_automacao_aghu` cria Playwright, browser, context e page, e recebe `url_aghu` |
| Browser | `headless=not mostrar_browser` e `slow_mo=500` |
| Contexto | `browser.new_context(ignore_https_errors=True)` |
| Entrada | Aceita `.xlsx`, `.xlsm` e `.csv` separado por `;` |
| Saída | Obriga `.xlsx` e cria diretório pai se necessário |
| Relatório | Localiza CSV recente em `LOGS_DIR` e converte para XLSX formatado |
| Antiprocesso invisível | Impede navegador e terminal desativados simultaneamente |

---

## 3. Motivação

A automação precisa ser operada por usuário técnico, com credenciais de rede, seleção de arquivo de entrada e escolha do local de saída do relatório. Essas tarefas são de interface e não pertencem ao núcleo de processamento.

Esta camada separa o uso humano do processamento automatizado. O Maestro continua responsável por navegar e corrigir vínculos, enquanto a UI cuida de experiência operacional: campos de login, seleção de ambiente, seleção de planilhas, opção de exibir navegador, opção de exibir terminal, prevenção de processo invisível, execução em thread e entrega do relatório XLSX.

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
          │     ├─ Planilha de entrada (.xlsx, .xlsm ou .csv)
          │     └─ Planilha de saída (.xlsx)
          │
          ├─► start_automation()
          │     ├─ Valida campos obrigatórios
          │     ├─ Valida caminho XLSX de saída
          │     ├─ Desabilita botão de execução
          │     └─ Inicia thread daemon
          │
          └─► run_playwright_task()
                │
                └─► executar_automacao_aghu(...)
                      ├─ Opcionalmente oculta console no Windows
                      ├─ Lê e valida planilha de entrada
                      ├─ Normaliza caminho de saída XLSX
                      ├─ Cria ./logs
                      ├─ Abre Chromium com Playwright
                      ├─ Cria BrowserContext com ignore_https_errors=True
                      ├─ Acessa url_aghu
                      ├─ Chama fazer_login(..., url_aghu=url_aghu) do Maestro
                      ├─ Chama navegar_ate_modulo(..., url_aghu=url_aghu) do Maestro
                      ├─ Chama processar_computadores(..., url_aghu=url_aghu) do Maestro
                      ├─ Fecha browser em finally
                      ├─ Localiza CSV gerado em ./logs
                      ├─ Converte CSV para XLSX formatado
                      └─ Retorna mensagem de conclusão
```

---

## 5. Dependências

### 5.1 `PrinterAGHU.py`

A UI importa:

```python
from PrinterAGHU import fazer_login, navegar_ate_modulo, processar_computadores
```

Essas funções executam o núcleo da automação. A UI não acessa diretamente funções do Almoxarifado.

### 5.2 `autenticador.py`

A UI importa:

```python
from autenticador import AGHU_URL, AGHU_URL_HOMOLOGACAO
```

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
| `LOGS_DIR` | `BASE_DIR / "logs"`, usado para localizar o CSV gerado pelo Maestro |
| `AGHU_URL` | Importada de `autenticador.py`; URL padrão de Produção |
| `AGHU_URL_HOMOLOGACAO` | Importada de `autenticador.py`; URL de Homologação |
| `AMBIENTE_PRODUCAO` | Rótulo `Produção` usado no seletor da UI |
| `AMBIENTE_HOMOLOGACAO` | Rótulo `Homologação` usado no seletor da UI |
| `URLS_AMBIENTE_AGHU` | Mapa entre rótulo de ambiente e URL efetiva |

Não existe mais `AGHU_URL_PRODUCAO` nesta UI. Qualquer referência a esse nome deve ser substituída por `AGHU_URL` ou pelo mapa `URLS_AMBIENTE_AGHU`, conforme o caso.

O helper `obter_url_ambiente_aghu(ambiente)` retorna a URL correspondente ao rótulo selecionado, com fallback para `AGHU_URL` se o valor recebido não estiver no mapa.

---

## 7. Descrição dos Componentes

### 7.1 `esconder_console_windows()`

Oculta a janela do console apenas em Windows (`os.name == "nt"`) usando:

```python
ctypes.windll.kernel32.GetConsoleWindow()
ctypes.windll.user32.ShowWindow(hwnd, 0)
```

Em outros sistemas operacionais, retorna sem ação.

É chamada quando o operador desmarca **Exibir Terminal de processos (logs)**.

### 7.2 `ler_planilha_entrada(caminho_planilha)`

Lê e valida a planilha informada na UI. A lógica é equivalente ao helper `ler_planilha` do Maestro, mas permanece duplicada para validar a entrada antes da execução.

Formatos aceitos:

| Extensão | Leitor | Observação |
|---|---|---|
| `.xlsx` | `pandas.read_excel(..., engine="openpyxl")` | Excel padrão |
| `.xlsm` | `pandas.read_excel(..., engine="openpyxl")` | Excel com macro |
| `.csv` | `pandas.read_csv(..., sep=";")` | UTF-8-sig com fallback Latin-1 |

Colunas obrigatórias:

```text
IPPC, HostPrinter, PrinterClass
```

Se o arquivo não existir, lança `FileNotFoundError`. Se a extensão for inválida ou se faltarem colunas obrigatórias, lança `ValueError`.

### 7.3 `normalizar_saida_xlsx(caminho_saida)`

Recebe o caminho de saída escolhido pelo operador.

Regras:

| Condição | Ação |
|---|---|
| Caminho sem extensão | Acrescenta `.xlsx` |
| Extensão diferente de `.xlsx` | Lança `ValueError("A planilha de saída deve ser um arquivo .xlsx.")` |
| Diretório pai inexistente | Cria com `mkdir(parents=True, exist_ok=True)` |

Retorna o caminho normalizado como `Path`.

### 7.4 `localizar_csv_relatorio_gerado(inicio_execucao)`

Busca arquivos com padrão:

```text
log_resultado_*.csv
```

Dentro de:

```python
LOGS_DIR
```

Critério de seleção:

1. Prioriza arquivos com `mtime >= inicio_execucao - 2`.
2. Se houver múltiplos recentes, usa o mais novo.
3. Se não houver recentes, usa o CSV mais novo da pasta.
4. Se nenhum CSV existir, lança `FileNotFoundError("Nenhum relatório CSV foi gerado na pasta logs.")`.

Essa função existe porque o Maestro gera o CSV com nome baseado em data/hora. Embora `processar_computadores` retorne o caminho do CSV, a UI atual localiza o relatório pelo diretório de logs após a execução.

### 7.5 `converter_csv_relatorio_para_xlsx(caminho_csv, caminho_xlsx)`

Converte o CSV auditável gerado pelo Maestro para XLSX formatado.

A primeira linha do CSV é tratada como metadado de auditoria:

```text
Atualizado por: <usuario>
```

Os dados tabulares são lidos com:

```python
pd.read_csv(..., sep=";", encoding="utf-8-sig", skiprows=1)
```

Formatação aplicada:

| Elemento | Regra |
|---|---|
| Aba | `Relatório` |
| Linha 1 | Auditoria do CSV ou fallback `Atualizado por:` |
| Linha 2 | `Gerado em: dd/mm/aaaa HH:MM:SS` |
| Linha 4 | Cabeçalho da tabela |
| Linha 5 em diante | Dados |
| Congelamento | `A5` |
| Autofiltro | Do cabeçalho até a última linha/coluna |
| Cabeçalho | Negrito, alinhado ao centro, preenchimento `D9EAF7` |
| Largura de colunas | Tamanho máximo do conteúdo + 2, limitado a 60 |

O XLSX é gerado com:

```python
pd.ExcelWriter(caminho_xlsx, engine="openpyxl")
```

### 7.6 `executar_automacao_aghu(...)`

É o adaptador entre UI e núcleo de automação.

Assinatura:

```python
executar_automacao_aghu(
    usuario: str,
    senha: str,
    mostrar_console: bool,
    mostrar_browser: bool,
    caminho_planilha_entrada: str,
    caminho_planilha_saida: str,
    url_aghu: str = AGHU_URL,
) -> str
```

Fluxo interno:

1. Valida usuário e senha.
2. Valida se `url_aghu` foi informado.
3. Oculta console se `mostrar_console` for falso.
4. Executa `os.chdir(BASE_DIR)`.
5. Lê a planilha com `ler_planilha_entrada`.
6. Normaliza o caminho XLSX de saída.
7. Cria `LOGS_DIR`.
8. Registra timestamp de início.
9. Abre Playwright.
10. Abre Chromium com:

```python
headless=not mostrar_browser
slow_mo=500
```

11. Cria contexto com:

```python
ignore_https_errors=True
```

12. Cria nova página.
13. Acessa `url_aghu`.
14. Chama `fazer_login(page, usuario, senha, url_aghu=url_aghu)` do Maestro.
15. Chama `navegar_ate_modulo(context, page, usuario, senha, url_aghu=url_aghu)`.
16. Chama `processar_computadores(context, page, janela_sistema, planilha, usuario, senha, url_aghu=url_aghu)`.
17. Fecha o browser em `finally`.
18. Localiza o CSV gerado.
19. Converte CSV para XLSX.
20. Retorna mensagem de sucesso com o caminho final.

---

## 8. Classe `AghuPrinterApp`

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
| Planilhas | Entrada e saída com botões de seleção |
| Controle | Botão `Iniciar Robô` e label de status |

### 8.1 Métodos de montagem

| Método | Responsabilidade |
|---|---|
| `create_login_fields` | Monta campos de usuário e senha |
| `create_environment_fields` | Monta seletor de ambiente e painel de alerta de Produção |
| `create_execution_options` | Monta checkboxes de navegador/terminal |
| `create_spreadsheet_fields` | Monta campos de planilha de entrada e saída |
| `on_environment_changed` | Atualiza o alerta quando o operador troca o ambiente |
| `update_environment_alert` | Exibe o painel quando o ambiente é Produção e oculta em Homologação |

### 8.2 Métodos de seleção de arquivo

| Método | Responsabilidade |
|---|---|
| `select_input_spreadsheet` | Abre seletor para `.xlsx`, `.xlsm` ou `.csv`; se saída estiver vazia, sugere `relatorio_aghu_YYYYMMDD_HHMMSS.xlsx` no mesmo diretório da entrada |
| `select_output_spreadsheet` | Abre seletor de salvamento XLSX com nome padrão `relatorio_aghu_YYYYMMDD_HHMMSS.xlsx` |

### 8.3 Métodos de execução

| Método | Responsabilidade |
|---|---|
| `start_automation` | Valida formulário, desabilita botão e cria thread daemon |
| `run_playwright_task` | Executa `executar_automacao_aghu` fora da thread principal da UI |
| `finish_automation` | Atualiza status final e reabilita botão |
| `show_status` | Atualiza texto e cor do label de status |

### 8.4 Seletor de ambiente

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

## 9. Regra Anti-Zombie

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

## 10. Validações de Formulário

Antes de iniciar a thread, `start_automation` valida:

| Campo | Mensagem em erro |
|---|---|
| Usuário ou senha vazios | `Erro: preencha usuário de rede e senha.` |
| Planilha de entrada vazia | `Erro: informe a planilha de entrada.` |
| Planilha de saída vazia | `Erro: informe a planilha de saída do relatório.` |
| Saída inválida | `Erro: <mensagem de normalizar_saida_xlsx>` |

Durante a execução, exceções de qualquer etapa são capturadas em `run_playwright_task` e enviadas para `finish_automation` com status vermelho.

---

## 11. Contrato com o Maestro (RFC-001)

A UI entrega ao Maestro:

| Item | Origem |
|---|---|
| `context` | `browser.new_context(ignore_https_errors=True)` |
| `page` | `context.new_page()` já aberta em `url_aghu` |
| `url_aghu` | URL resolvida pelo seletor `Produção`/`Homologação` |
| `usuario` | Campo de usuário da interface |
| `senha` | Campo de senha da interface |
| `planilha` | `DataFrame` validado por `ler_planilha_entrada` |

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
processar_computadores(
    context,
    page,
    janela_sistema,
    planilha,
    usuario,
    senha,
    url_aghu=url_aghu,
)
```

A UI não chama o Almoxarifado diretamente. O repasse de `url_aghu` garante que retries e Clean States no Maestro permaneçam no ambiente escolhido pelo operador.

---

## 12. Relatório Final

O núcleo gera CSV auditável. A UI converte esse CSV para XLSX final escolhido pelo operador.

Fluxo:

```text
processar_computadores(...)
        │
        └─► ./logs/log_resultado_YYYYMMDD_HHMMSS.csv
                  │
                  └─► localizar_csv_relatorio_gerado(inicio_execucao)
                            │
                            └─► converter_csv_relatorio_para_xlsx(csv, saida.xlsx)
```

O XLSX final contém:

| Linha | Conteúdo |
|---|---|
| 1 | Auditoria `Atualizado por: <usuario>` |
| 2 | Data/hora de geração do XLSX |
| 4 | Cabeçalho dos dados |
| 5+ | Linhas de resultado |

---

## 13. Execução como Script

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

## 14. Limitações Conhecidas

| Limitação | Impacto |
|---|---|
| Execução usa thread daemon sem botão de cancelamento | Interrupção controlada pela UI ainda não existe |
| Ocultação de console só funciona em Windows | Em outros sistemas, `esconder_console_windows` não tem efeito |
| Leitura de planilha está duplicada entre UI e Maestro | Mudanças de colunas/formatos precisam ser mantidas em ambos ou refatoradas |
| UI localiza CSV por timestamp em vez de usar retorno direto do Maestro | Pode escolher o CSV mais novo se houver execução concorrente na mesma pasta |
| Caminho de logs depende de `BASE_DIR / "logs"` | A UI pressupõe que o Maestro grave no mesmo diretório padrão |

---

## 15. Estado Atual da RFC

Esta RFC passa a refletir o código atual de `ui_alignprinterAGHU.py`, incluindo o uso de `AGHU_URL` e `AGHU_URL_HOMOLOGACAO` vindos de `autenticador.py`, o seletor Produção/Homologação com alerta de Produção, a criação do Playwright na camada de UI, a execução em thread, a validação de planilhas, a regra anti-processo invisível e a conversão do CSV auditável para XLSX formatado.
