# RFC-003 — Interface Gráfica e Empacotador de Execução (ui_alignprinterAGHU)

- **Status:** Estável
- **Autor:** Pedro e Ruan
- **Data:** 2026-06
- **Arquivo:** `ui_alignprinterAGHU.py`
- **Depende de:** `PrinterAGHU.py` (RFC-001)
- **Depende indiretamente de:** `AddPrinterAGHU.py` (RFC-002)

---

## 1. Resumo

`ui_alignprinterAGHU.py` é a **camada de interface gráfica e empacotamento operacional** da automação de impressoras do AGHUX. Ele não implementa a regra principal de vínculo nem o cadastro de impressoras no catálogo. Em vez disso, coleta credenciais e caminhos de planilha, configura opções de execução, inicia o Playwright, chama o Maestro (`PrinterAGHU.py`, RFC-001) e converte o relatório CSV gerado pelo núcleo para uma planilha XLSX formatada.

O arquivo usa `customtkinter` para fornecer uma janela local, `threading` para executar a automação sem congelar a interface, `Playwright` para abrir o AGHUX e `openpyxl` para formatar o relatório final.

---

## 2. Motivação

A automação original precisa ser operada por usuário técnico, com credenciais de rede, seleção de arquivo de entrada e escolha do local de saída do relatório. Essas tarefas são de interface e não pertencem ao núcleo de processamento.

Esta camada existe para separar o uso humano do processamento automatizado. O Maestro continua responsável por navegar e corrigir vínculos, enquanto a UI cuida de experiência operacional: campos de login, seleção de planilhas, opção de exibir navegador, opção de exibir terminal, prevenção de processo invisível, execução em thread e entrega do relatório XLSX.

---

## 3. Arquitetura e Fluxo de Dados

```text
[Operador]
    │
    └─► AghuPrinterApp (customtkinter)
          │
          ├─► Coleta:
          │     ├─ Usuário de rede
          │     ├─ Senha
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
                      ├─ Abre Chromium com Playwright
                      ├─ Acessa AGHU_URL_PRODUCAO
                      ├─ Chama fazer_login() do Maestro
                      ├─ Chama navegar_ate_modulo() do Maestro
                      ├─ Chama processar_computadores() do Maestro
                      ├─ Fecha browser em finally
                      ├─ Localiza CSV gerado em ./logs
                      ├─ Converte CSV para XLSX formatado
                      └─ Retorna mensagem de conclusão
```

---

## 4. Descrição dos Componentes

### 4.1 Constantes Globais

| Constante | Valor / Função |
|---|---|
| `AGHU_URL_PRODUCAO` | URL de produção do AGHUX usada pela UI para abrir a primeira página |
| `BASE_DIR` | Diretório do arquivo `ui_alignprinterAGHU.py` |
| `LOGS_DIR` | `BASE_DIR / "logs"`, usado para localizar o CSV gerado pelo Maestro |

A URL de produção também existe no Maestro. Essa duplicidade é funcional, mas deve ser tratada como ponto de manutenção.

### 4.2 `esconder_console_windows`

Oculta a janela do console apenas em Windows (`os.name == "nt"`) usando `ctypes.windll.kernel32.GetConsoleWindow()` e `ctypes.windll.user32.ShowWindow(hwnd, 0)`. Em outros sistemas operacionais, retorna sem ação.

A função é chamada quando o operador desmarca **Exibir Terminal de processos (logs)**.

### 4.3 `ler_planilha_entrada`

Lê e valida a planilha informada na UI. A lógica é equivalente ao helper `ler_planilha` do Maestro, mas está duplicada neste arquivo para validar a entrada antes da execução.

Formatos aceitos:

| Extensão | Leitor | Observação |
|---|---|---|
| `.xlsx` | `pandas.read_excel(..., engine="openpyxl")` | Excel padrão |
| `.xlsm` | `pandas.read_excel(..., engine="openpyxl")` | Excel com macro |
| `.csv` | `pandas.read_csv(..., sep=";")` | UTF-8-sig com fallback Latin-1 |

Colunas obrigatórias: `IPPC`, `HostPrinter`, `PrinterClass`.

Se o arquivo não existir, lança `FileNotFoundError`. Se a extensão for inválida ou se faltarem colunas obrigatórias, lança `ValueError`.

### 4.4 `normalizar_saida_xlsx`

Recebe o caminho de saída escolhido pelo operador. Se o caminho não tiver extensão, acrescenta `.xlsx`. Se a extensão existir e não for `.xlsx`, lança `ValueError("A planilha de saída deve ser um arquivo .xlsx.")`.

Também garante a existência do diretório pai com `mkdir(parents=True, exist_ok=True)` e retorna o caminho normalizado como `Path`.

### 4.5 `localizar_csv_relatorio_gerado`

Busca arquivos `log_resultado_*.csv` dentro de `LOGS_DIR`. Prioriza arquivos com `mtime` maior ou igual ao timestamp de início da execução menos 2 segundos. Se houver mais de um candidato recente, seleciona o mais novo. Se não houver candidato recente, usa o CSV mais novo da pasta. Se nenhum CSV existir, lança `FileNotFoundError`.

Essa função existe porque o Maestro gera o CSV com nome baseado em data/hora e retorna o caminho, mas a UI atual localiza o relatório pelo diretório de logs após a execução.

### 4.6 `converter_csv_relatorio_para_xlsx`

Converte o CSV auditável gerado pelo Maestro para XLSX formatado. A primeira linha do CSV é tratada como metadado de auditoria (`Atualizado por: ...`) e os dados tabulares são lidos com `skiprows=1`.

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

O XLSX é gerado com `pandas.ExcelWriter(..., engine="openpyxl")`.

### 4.7 `executar_automacao_aghu`

É o adaptador entre UI e núcleo de automação. Recebe credenciais, flags de visualização e caminhos de entrada/saída.

Fluxo interno:

1. Valida usuário e senha.
2. Oculta console se `mostrar_console` for falso.
3. Executa `os.chdir(BASE_DIR)`.
4. Lê a planilha com `ler_planilha_entrada`.
5. Normaliza o caminho XLSX de saída.
6. Cria `LOGS_DIR`.
7. Registra timestamp de início.
8. Abre Playwright e Chromium com `headless=not mostrar_browser` e `slow_mo=500`.
9. Cria contexto com `ignore_https_errors=True`.
10. Acessa `AGHU_URL_PRODUCAO`.
11. Chama `fazer_login`, `navegar_ate_modulo` e `processar_computadores` do Maestro.
12. Fecha o browser em bloco `finally`.
13. Localiza o CSV gerado.
14. Converte CSV para XLSX.
15. Retorna mensagem de sucesso com o caminho final.

### 4.8 `AghuPrinterApp`

Classe principal da interface gráfica, derivada de `ctk.CTk`.

Características da janela:

| Propriedade | Valor |
|---|---|
| Título | `AGHUX Bot - Impressoras` |
| Tamanho | `760x520` |
| Redimensionável | Não |
| Tema | Sistema |
| Cor padrão | Azul |

Campos criados:

| Grupo | Elementos |
|---|---|
| Login | Usuário de rede, senha mascarada |
| Execução | Checkboxes de navegador e terminal |
| Planilhas | Entrada e saída com botões de seleção |
| Controle | Botão `Iniciar Robô` e label de status |

Métodos principais:

| Método | Responsabilidade |
|---|---|
| `create_login_fields` | Monta campos de usuário e senha |
| `create_execution_options` | Monta checkboxes de navegador/terminal |
| `create_spreadsheet_fields` | Monta campos de planilha de entrada e saída |
| `validate_visibility_options_from_browser` | Impede navegador e terminal desativados simultaneamente |
| `validate_visibility_options_from_console` | Mesma regra anti-invisibilidade pela outra checkbox |
| `select_input_spreadsheet` | Abre seletor de entrada e sugere saída padrão |
| `select_output_spreadsheet` | Abre seletor de salvamento XLSX |
| `start_automation` | Valida formulário e inicia thread |
| `run_playwright_task` | Executa automação fora da thread da UI |
| `finish_automation` | Reabilita botão e exibe status final |
| `show_status` | Atualiza mensagem e cor do status |

### 4.9 Regra Anti-Zombie

A UI impede que o operador desmarque simultaneamente **Exibir Navegador** e **Exibir Terminal**. Se isso ocorrer, a última opção alterada é reativada e uma mensagem de aviso é exibida.

Essa regra evita execução invisível: Chromium em headless sem console aparente, o que dificultaria supervisão ou interrupção manual.

---

## 5. Relação com o Maestro e o Almoxarifado

A UI importa do Maestro:

```python
from PrinterAGHU import fazer_login, navegar_ate_modulo, processar_computadores
```

A UI não importa diretamente `AddPrinterAGHU.py`. A dependência com o Almoxarifado é indireta: quando `processar_computadores` encontra uma impressora ausente no AGHUX, o próprio Maestro aciona o fluxo da RFC-002.

Responsabilidades por camada:

| Camada | Arquivo | Responsabilidade |
|---|---|---|
| UI | `ui_alignprinterAGHU.py` | Coleta parâmetros, executa em thread, gera XLSX |
| Maestro | `PrinterAGHU.py` | Processa vínculos e gera CSV |
| Almoxarifado | `AddPrinterAGHU.py` | Cadastra impressora ausente a partir do CUPS |

---

## 6. Decisões Técnicas

### 6.1 Por que converter o relatório para XLSX na UI?

O Maestro gera CSV auditável e simples. A UI entrega ao operador um XLSX formatado, com filtros, congelamento de cabeçalho e largura ajustada. Isso preserva o núcleo leve e deixa a formatação de apresentação na camada de interface.

### 6.2 Por que executar a automação em thread?

Playwright e o processamento de planilha são operações bloqueantes. Se executados na thread principal do Tkinter, a janela ficaria congelada. O uso de `threading.Thread(..., daemon=True)` mantém a interface responsiva e permite atualizar status ao final por `self.after(...)`.

### 6.3 Por que usar `self.after` para finalizar?

Atualizações de widgets Tkinter devem ocorrer na thread da interface. `run_playwright_task` executa em thread secundária e agenda `finish_automation` com `self.after(0, ...)`, evitando atualização direta de widgets fora da thread principal.

### 6.4 Por que impedir navegador e console ocultos ao mesmo tempo?

A execução completamente invisível dificulta diagnóstico, cancelamento e acompanhamento. A regra anti-zombie garante que o operador tenha ao menos um canal de observabilidade: navegador visível ou console de logs.

### 6.5 Por que `ignore_https_errors=True`?

O AGHUX e o CUPS são ambientes internos e podem usar certificados não reconhecidos pelo Chromium. O contexto Playwright é criado com `ignore_https_errors=True` para evitar bloqueio por certificado.

### 6.6 Por que localizar o CSV por timestamp?

O nome do CSV é gerado pelo Maestro com data/hora. A UI registra o início da execução e busca arquivos modificados depois desse ponto, com margem de 2 segundos. Isso permite converter o relatório recém-gerado sem precisar alterar o contrato público do Maestro.

---

## 7. Tratamento de Erros

| Situação | Comportamento |
|---|---|
| Usuário ou senha vazios na UI | Status vermelho e execução não inicia |
| Planilha de entrada não informada | Status vermelho e execução não inicia |
| Planilha de saída não informada | Status vermelho e execução não inicia |
| Saída com extensão diferente de `.xlsx` | Status vermelho e execução não inicia |
| Arquivo de entrada inexistente | Exceção capturada na thread; status vermelho |
| Extensão de entrada inválida | Exceção capturada; status vermelho |
| Colunas obrigatórias ausentes | Exceção capturada; status vermelho |
| Falha durante Playwright/Maestro | Browser é fechado no `finally`; status vermelho |
| Nenhum CSV encontrado em `logs` | `FileNotFoundError`; status vermelho |
| Tentativa de ocultar navegador e console | Bloqueada por aviso e reversão da checkbox |
| Execução bem-sucedida | Botão reabilitado e status verde com caminho do relatório |

---

## 8. Limitações Conhecidas

- `AGHU_URL_PRODUCAO` está duplicada na UI e no Maestro.
- A função `ler_planilha_entrada` duplica lógica de `ler_planilha` do Maestro.
- `os.chdir(BASE_DIR)` altera o diretório de trabalho global do processo.
- `slow_mo=500` é fixo e não configurável pela interface.
- A UI não passa `diretorio_logs` para `processar_computadores`; presume que o CSV será gerado em `BASE_DIR / "logs"` compatível com `LOGS_DIR`.
- A busca do CSV por timestamp tem fallback para o CSV mais recente, o que pode selecionar relatório antigo se a execução falhar depois de apagar/impedir a geração do novo.
- `esconder_console_windows` só funciona em Windows e não possui fluxo de restauração da janela após ocultar.
- A thread é daemon; se a janela for encerrada abruptamente, a execução pode ser interrompida pelo término do processo.
- A interface não valida conectividade com AGHUX antes de iniciar o browser.
- Credenciais são mantidas em memória enquanto a execução está ativa; não há persistência, mas também não há cofre/integração de segredo.

---

## 9. Alterações Futuras Consideradas

- Centralizar `AGHU_URL_PRODUCAO` em configuração única compartilhada.
- Reutilizar `ler_planilha` do Maestro ou extrair a validação de planilha para módulo comum.
- Fazer `processar_computadores` retornar diretamente o caminho do CSV e usar esse retorno na UI.
- Passar `diretorio_logs=LOGS_DIR` explicitamente ao Maestro.
- Tornar `slow_mo`, headless e ambiente configuráveis por arquivo ou opções avançadas.
- Adicionar botão de cancelamento controlado da execução.
- Adicionar campo para diretório de logs ou retenção de histórico.
- Implementar barra de progresso por quantidade de linhas processadas.
- Registrar logs estruturados em arquivo além do console.
- Validar conectividade com AGHUX e CUPS antes de iniciar o processamento completo.
