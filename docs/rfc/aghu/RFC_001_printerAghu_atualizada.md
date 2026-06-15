# RFC-001 — Orquestrador de Vínculos Impressora-Computador (PrinterAGHU)

- **Status:** Estável
- **Autor:** Pedro e Ruan
- **Data:** 2026-06
- **Atualizado em:** 2026-06-15
- **Arquivo:** `PrinterAGHU.py`
- **Depende de:** `autenticador.py`
- **Depende de:** `AddPrinterAGHU.py` (RFC-002)
- **Chamado por:** `ui_alignprinterAGHU.py` (RFC-003)

---

## 1. Resumo

`PrinterAGHU.py` é o **Maestro** da automação de vínculos computador–impressora no AGHUX. Ele concentra a regra operacional do módulo **Impressora por Computador**: lê e valida a planilha de entrada, autentica a sessão por meio do autenticador centralizado, navega até o módulo correto, processa cada computador informado e mantém, altera ou cria vínculos conforme o estado encontrado no sistema.

Quando a impressora informada na planilha não existe no autocomplete do AGHUX, o Maestro delega o cadastro ao Robô Especialista (`AddPrinterAGHU.py`, RFC-002). O especialista consulta o CUPS, cadastra a impressora no catálogo do AGHUX e devolve o fluxo ao Maestro, que reconstrói uma aba limpa e tenta novamente a mesma linha.

A autenticação não é mais implementada manualmente neste arquivo. O arquivo importa `AGHU_URL`, `autenticar_aghu_page` e `exigir_login_valido` de `autenticador.py`, que passa a ser a dependência transversal dos robôs.

---

## 2. Mudanças incorporadas nesta revisão

Esta revisão atualiza a RFC para refletir as implementações atuais dos arquivos de automação:

| Área | Situação atual |
|---|---|
| Autenticação | Centralizada em `autenticador.py`, não mais descrita como lógica manual local do Maestro |
| URL do AGHUX | Uso de `AGHU_URL`, importada do autenticador, com suporte a variáveis de ambiente |
| Login local | `fazer_login` agora é wrapper de `autenticar_aghu_page` + `exigir_login_valido` |
| Clean State | Continua fechando a aba atual, abrindo nova aba no mesmo contexto e autenticando pela rotina central |
| Navegação | Mantém retry de navegação com Clean State na primeira falha |
| Busca de IP | Usa regex com `re.escape` e borda de palavra para evitar correspondência parcial de IP |
| Relatório | Gera CSV em `logs/log_resultado_YYYYMMDD_HHMMSS.csv` com primeira linha de auditoria `Atualizado por: <usuario>` |

---

## 3. Motivação

Vincular impressoras a computadores no AGHUX é uma rotina repetitiva, sensível a divergências silenciosas e dependente de autocompletes JSF. Um computador pode já possuir vínculo correto, possuir vínculo para outra impressora, não possuir vínculo ou nem existir no cadastro. Além disso, a impressora alvo pode não existir no catálogo do AGHUX, embora exista no CUPS.

O Maestro centraliza esse fluxo em uma rotina auditável com recuperação controlada: tenta operar o vínculo, usa aba limpa quando a interface fica instável, delega o cadastro de impressoras ausentes ao Almoxarifado e registra o resultado por linha em relatório CSV.

A separação entre núcleo (`PrinterAGHU.py`), cadastro especializado (`AddPrinterAGHU.py`), autenticação (`autenticador.py`) e interface gráfica (`ui_alignprinterAGHU.py`) reduz acoplamento e permite que a regra de negócio seja reutilizada por outros chamadores.

---

## 4. Arquitetura e Fluxo de Dados

```text
[ui_alignprinterAGHU.py / outro chamador]
        │
        ├─► Cria BrowserContext e Page com Playwright
        │
        ├─► page.goto(AGHU_URL)
        │
        ├─► fazer_login(page, usuario, senha)
        │        └─ autenticar_aghu_page(...) em autenticador.py
        │
        ├─► navegar_ate_modulo(context, page, usuario, senha)
        │        ├─ Outros Módulos → Configuração → Impressão → Cadastros
        │        ├─ Abre "Impressora por Computador"
        │        ├─ Valida tela pelo botão "Pesquisar" no último iframe
        │        └─ Em falha inicial, aciona Clean State
        │
        └─► processar_computadores(...)
                 │
                 ├─ Para cada linha da planilha:
                 │     ├─ Busca computador por IP no autocomplete
                 │     ├─ Pesquisa vínculo existente por IP e classe
                 │     │
                 │     ├─ [Caso A] Vínculo correto      → Status: Mantido
                 │     ├─ [Caso B] Vínculo divergente   → Edita  → Status: Alterado/Criado
                 │     └─ [Caso C] Sem vínculo          → Cria   → Status: Vinculado/Criado
                 │
                 ├─ Se a impressora não existir no AGHUX:
                 │     └─► Delegação ao Almoxarifado (RFC-002)
                 │           ├─ trocar_aba_aghux(...)
                 │           ├─ consultar_dados_site_secundario(...)
                 │           ├─ navegar_ate_cadastro_impressora(...)
                 │           └─ cadastrar_nova_impressora(...)
                 │
                 ├─ Após cadastro delegado:
                 │     ├─ Abre nova aba limpa
                 │     ├─ Retorna ao módulo "Impressora por Computador"
                 │     ├─ Marca impressora_fabricada_agora = True
                 │     └─ Reprocessa a mesma linha
                 │
                 └─ Gera CSV auditável em ./logs
```

---

## 5. Dependências

### 5.1 `autenticador.py`

`PrinterAGHU.py` importa:

```python
from autenticador import AGHU_URL, autenticar_aghu_page, exigir_login_valido
```

Responsabilidades delegadas ao autenticador:

| Item | Responsabilidade |
|---|---|
| `AGHU_URL` | URL padrão do AGHUX, com override por variáveis de ambiente |
| `autenticar_aghu_page` | Autentica usando uma `Page` existente, sem criar ou fechar browser/context/page |
| `exigir_login_valido` | Lança erro se o resultado de login não for `sucesso` ou `sessao_ativa` |

`PrinterAGHU.py` não deve voltar a duplicar seletores de login, mensagens de erro de credencial ou validação de sessão. Essa lógica pertence ao autenticador central.

### 5.2 `AddPrinterAGHU.py`

`PrinterAGHU.py` importa diretamente as três funções públicas usadas para cadastrar uma impressora inexistente:

```python
from AddPrinterAGHU import (
    cadastrar_nova_impressora,
    consultar_dados_site_secundario,
    navegar_ate_cadastro_impressora,
)
```

O Maestro chama essas funções somente quando a seleção da impressora no módulo **Impressora por Computador** falha com `ValueError("Impressora não existe")`.

---

## 6. Descrição dos Componentes

### 6.1 `ler_planilha(caminho_arquivo)`

Recebe um caminho de arquivo e retorna um `DataFrame` normalizado. A função não assume arquivo fixo no diretório do script; o caminho é fornecido pelo chamador.

Formatos aceitos:

| Extensão | Leitor | Observação |
|---|---|---|
| `.xlsx` | `pandas.read_excel(..., engine="openpyxl")` | Entrada Excel padrão |
| `.xlsm` | `pandas.read_excel(..., engine="openpyxl")` | Entrada Excel com macro |
| `.csv` | `pandas.read_csv(..., sep=";")` | Tenta `utf-8-sig`; se falhar, usa `latin1` |

Após leitura, remove espaços dos nomes das colunas com `df.columns.str.strip()`, substitui `NaN` por string vazia e valida as colunas obrigatórias:

```text
IPPC, HostPrinter, PrinterClass
```

Campos opcionais preservados para relatório:

```text
HostPC, IPPrinter
```

Erros previstos:

| Condição | Exceção |
|---|---|
| Arquivo inexistente | `FileNotFoundError` |
| Extensão inválida | `ValueError("Formato inválido. Use .xlsx, .xlsm ou .csv.")` |
| Coluna obrigatória ausente | `ValueError` com lista de colunas faltantes |

### 6.2 `fazer_login(page, usuario_str, senha_str)`

É um wrapper local para autenticação centralizada. O fluxo atual é:

1. Imprime o usuário usado na checagem de autenticação.
2. Chama `autenticar_aghu_page(page=page, usuario=usuario_str, senha=senha_str, timeout_ms=15000)`.
3. Imprime mensagem conforme `resultado.status`:
   - `sessao_ativa`: sessão já estava ativa;
   - `sucesso`: login efetuado com sucesso;
   - demais status: falha de autenticação.
4. Chama `exigir_login_valido(resultado)`.
5. Retorna o `ResultadoLogin`.

A função não contém mais seletores de campo de usuário, senha ou botão **Entrar**. A detecção da tela de login, credenciais inválidas, timeout e sessão já ativa pertence a `autenticador.py`.

### 6.3 `trocar_aba_aghux(context, page_atual, usuario_str, senha_str)` — Clean State

Fecha a aba atual, ignorando erro caso ela já esteja indisponível. Em seguida, abre uma nova `Page` no mesmo `BrowserContext`, acessa `AGHU_URL`, executa `autenticar_aghu_page` e valida o resultado com `exigir_login_valido`.

O Clean State é usado como recuperação quando a interface do AGHUX fica inconsistente, quando o menu falha, quando o fluxo retorna do Almoxarifado ou quando há falhas técnicas durante o processamento de uma linha.

O uso do mesmo `BrowserContext` preserva sessão, certificados e configuração do browser criada pelo chamador.

### 6.4 `navegar_ate_modulo(context, page_atual, usuario_str, senha_str)`

Navega até o módulo **Impressora por Computador**:

```text
Outros Módulos → Configuração → Impressão → Cadastros → Impressora por Computador
```

Antes de clicar em cada item, verifica se o item de destino já está visível. Isso reduz cliques redundantes em menus já expandidos.

Ao abrir o módulo, captura o último iframe com:

```python
janela_sistema = page.frame_locator("iframe").last
```

A tela é considerada carregada quando o botão **Pesquisar** fica visível dentro do iframe.

A função faz até duas tentativas:

| Tentativa | Ação em falha |
|---|---|
| 1ª | Aciona `trocar_aba_aghux` e tenta novamente |
| 2ª | Propaga a exceção |

Se o laço terminar sem retorno, lança `RuntimeError("Falha ao navegar até o módulo de Impressora por Computador.")`.

### 6.5 `processar_computadores(...)`

É o laço principal da automação. Recebe:

| Parâmetro | Uso |
|---|---|
| `context` | Abre novas abas e permite Clean State |
| `page_inicial` | Página AGHUX já autenticada |
| `janela_sistema_inicial` | Último iframe do módulo **Impressora por Computador** |
| `planilha` | `DataFrame` já validado |
| `usuario_str` | Registro de auditoria e reautenticação |
| `senha_str` | Reautenticação em Clean State |
| `diretorio_logs` | Diretório opcional para gravação do CSV |

Para cada linha, extrai:

| Campo | Uso |
|---|---|
| `IPPC` | Busca e seleção do computador no AGHUX |
| `HostPrinter` | Impressora alvo a vincular |
| `PrinterClass` | Classe usada na pesquisa e validação do vínculo |
| `HostPC` | Apenas relatório, quando presente |
| `IPPrinter` | Apenas relatório, quando presente |

Cada linha possui até três tentativas para falhas técnicas. O estado inicial é `Erro` com detalhe `Falha Desconhecida.` e só é substituído quando a linha alcança um desfecho reconhecido.

---

## 7. Regras de Processamento por Linha

### 7.1 Busca do computador

O campo de computador é localizado por:

```text
input[id*='computador' i], input.ui-autocomplete-input
```

O IP é digitado com:

```python
press_sequentially(ip_pc, delay=150)
```

A seleção do autocomplete usa regex com `re.escape` e borda de palavra:

```python
padrao_exato = re.compile(fr"\b{re.escape(ip_pc)}\b")
```

Esse ajuste evita que `10.6.0.22` corresponda indevidamente a `10.6.0.225`.

Se nenhuma sugestão compatível aparece, a linha recebe `Inexistente` com detalhe `Computador não cadastrado no AGHUX.`.

### 7.2 Pesquisa do vínculo

Após selecionar o computador, o Maestro clica em **Pesquisar** e procura uma linha da tabela contendo o IP e a classe:

```text
row com IPPC + PrinterClass
```

Se a linha existir, o conteúdo da linha define o próximo passo.

### 7.3 Vínculo já correto

Condição:

```text
linha encontrada contém HostPrinter
```

Resultado:

| Campo | Valor |
|---|---|
| `Status` | `Mantido` |
| `Detalhes` | `Impressora já estava correta no sistema.` |

A tela é limpa pelo botão com ícone `.aghu-icon-cleaner-aghu`.

### 7.4 Vínculo divergente

Condição:

```text
linha encontrada contém IPPC e PrinterClass, mas não contém HostPrinter
```

Ação:

1. Clica no botão de edição da linha por título `editar`/`alterar` ou ícone `.aghu-icon-edit`.
2. Aguarda botão **Gravar**.
3. Limpa o campo de impressora.
4. Digita `HostPrinter` com `press_sequentially(..., delay=150)`.
5. Seleciona a sugestão.
6. Clica em **Gravar**.
7. Aguarda retorno do botão **Pesquisar**.
8. Limpa a tela.

Se a impressora já precisou ser fabricada pelo Almoxarifado durante esta linha, o status final é `Criado`; caso contrário, é `Alterado`.

| Condição | Status | Detalhes |
|---|---|---|
| Impressora já existia no AGHUX | `Alterado` | `Vínculo atualizado com sucesso.` |
| Impressora foi cadastrada nesta execução | `Criado` | `Impressora cadastrada no CUPS e atualizada.` |

### 7.5 Sem vínculo existente

Condição:

```text
Nenhuma linha encontrada para IPPC + PrinterClass
```

Ação:

1. Clica em **Novo**.
2. Aguarda botão **Gravar**.
3. Seleciona novamente o computador pelo IP exato.
4. Seleciona a impressora alvo.
5. Valida a classe preenchida automaticamente.
6. Se a classe não corresponder, limpa o campo e usa a lupa para selecionar `PrinterClass`.
7. Clica em **Gravar**.
8. Aguarda retorno do botão **Pesquisar**.
9. Limpa a tela.

Resultado:

| Condição | Status | Detalhes |
|---|---|---|
| Impressora já existia no AGHUX | `Vinculado` | `Vínculo criado com sucesso.` |
| Impressora foi cadastrada nesta execução | `Criado` | `Impressora nova identificada no CUPS, criada e vinculada no AGHU.` |

---

## 8. Delegação ao Almoxarifado

A delegação é acionada quando a seleção da impressora lança exatamente:

```python
ValueError("Impressora não existe")
```

O Maestro interpreta essa mensagem como ausência da fila no autocomplete de impressoras do AGHUX e chama o Robô Especialista.

Fluxo da delegação:

```text
ValueError("Impressora não existe")
        │
        └─► Até 3 tentativas de Almoxarifado:
              ├─ trocar_aba_aghux(...)
              ├─ consultar_dados_site_secundario(context, impressora, classe)
              ├─ navegar_ate_cadastro_impressora(page)
              └─ cadastrar_nova_impressora(janela, dados_cups)
```

Se a delegação for bem-sucedida:

1. O Maestro cria nova aba limpa.
2. Retorna ao módulo **Impressora por Computador**.
3. Marca `impressora_fabricada_agora = True`.
4. Usa `continue` para gastar uma nova tentativa da mesma linha.

Se a delegação falhar definitivamente:

| Erro final | Status | Detalhes |
|---|---|---|
| Mensagem contém `Não existe no CUPS` | `Inexistente` | `Fila de impressão não encontrada no Servidor CUPS.` |
| Outro erro do Almoxarifado | `Erro` | `Falha no Almoxarifado após 3 tentativas: <erro>` |

---

## 9. Recuperação de Falhas Técnicas

Erros do tipo `ValueError` são tratados como eventos de negócio quando contêm mensagens conhecidas:

| Mensagem | Interpretação |
|---|---|
| `Impressora não existe` | Aciona Almoxarifado |
| `Computador não encontrado` | Marca computador como inexistente |
| Outra mensagem | Marca linha como erro funcional |

Demais exceções são tratadas como falha técnica ou instabilidade do navegador. Nesses casos:

| Tentativa | Ação |
|---|---|
| 1ª ou 2ª | Cria aba limpa, renavega ao módulo e tenta novamente |
| 3ª | Marca `Erro` e detalhe `Falha de sistema ou rede no passo '<passo_atual>' após 3 tentativas.` |

Após falhas funcionais, o Maestro tenta cancelar a tela ou limpar o formulário antes de seguir para a próxima linha.

---

## 10. Relatório de Auditoria

Ao final, `processar_computadores` cria um `DataFrame` com os logs e grava um CSV em:

```text
logs/log_resultado_YYYYMMDD_HHMMSS.csv
```

Se `diretorio_logs` for informado, o arquivo é gravado nesse diretório. Caso contrário, usa:

```python
BASE_DIR / "logs"
```

O CSV é escrito em duas etapas:

1. Cria o arquivo em modo `w` e grava a linha de auditoria:

```text
Atualizado por: <usuario>
```

2. Acrescenta o `DataFrame` em modo append:

```python
df_logs.to_csv(nome_arquivo_log, index=False, sep=";", encoding="utf-8-sig", mode="a")
```

Colunas do relatório:

| Coluna | Origem |
|---|---|
| `HostPC` | Coluna opcional da planilha |
| `IPPC` | Coluna obrigatória da planilha |
| `HostPrinter` | Coluna obrigatória da planilha |
| `IPPrinter` | Coluna opcional da planilha |
| `PrinterClass` | Coluna obrigatória da planilha |
| `Status` | Resultado da linha |
| `Detalhes` | Explicação textual do resultado |

Status possíveis:

```text
Mantido, Alterado, Vinculado, Criado, Inexistente, Erro
```

---

## 11. API Pública do Módulo

| Função | Responsabilidade |
|---|---|
| `ler_planilha(caminho_arquivo)` | Lê e valida a planilha de entrada |
| `fazer_login(page, usuario_str, senha_str)` | Autentica usando o autenticador centralizado |
| `trocar_aba_aghux(context, page_atual, usuario_str, senha_str)` | Fecha aba atual, abre aba limpa e reautentica |
| `navegar_ate_modulo(context, page_atual, usuario_str, senha_str)` | Abre **Impressora por Computador** e retorna `(page, janela_sistema)` |
| `processar_computadores(...)` | Processa linhas da planilha e gera CSV auditável |

---

## 12. Contratos entre RFCs

### 12.1 Contrato com RFC-002

| Evento | Origem | Interpretação no Maestro |
|---|---|---|
| `ValueError("Impressora não existe")` | Seleção de impressora no vínculo | Aciona Almoxarifado |
| `ValueError("Não existe no CUPS")` | Consulta ao CUPS no Almoxarifado | Marca fila como inexistente |
| Retorno silencioso de `cadastrar_nova_impressora` | Impressora já existia no AGHUX | Retoma tentativa de vínculo |
| Cadastro concluído | Almoxarifado | Abre aba limpa e reprocessa linha |

### 12.2 Contrato com RFC-003

A UI deve fornecer:

| Item | Origem |
|---|---|
| `BrowserContext` | Criado pela UI com `ignore_https_errors=True` |
| `Page` | Criada pela UI e apontada para `AGHU_URL` |
| Credenciais | Campos da interface |
| Planilha | Lida e validada antes da execução |
| Caminho de saída | Usado pela UI após localizar o CSV gerado |

O Maestro retorna o caminho do CSV gerado, mas a UI atual localiza o arquivo por timestamp em `./logs` e converte para XLSX.

---

## 13. Considerações Operacionais

1. `PrinterAGHU.py` não cria o browser principal; o chamador cria `Browser`, `BrowserContext` e `Page`.
2. O módulo cria novas abas no mesmo contexto apenas para Clean State.
3. A autenticação deve permanecer centralizada em `autenticador.py`.
4. O fluxo depende de textos visíveis do AGHUX como **Outros Módulos**, **Configuração**, **Impressão**, **Cadastros**, **Impressora por Computador**, **Pesquisar**, **Novo** e **Gravar**.
5. As mensagens de erro usadas como contrato (`Impressora não existe`, `Computador não encontrado`, `Não existe no CUPS`) não devem ser alteradas sem atualizar as RFCs e os tratadores.
6. O uso de `press_sequentially` é intencional para disparar eventos JSF/autocomplete.

---

## 14. Limitações Conhecidas

| Limitação | Impacto |
|---|---|
| Seletores dependem de textos do AGHUX | Mudanças de nomenclatura no sistema podem quebrar navegação |
| Erros de negócio dependem de strings exatas | Alterações nas mensagens exigem atualização coordenada |
| Relatório CSV é gerado mesmo se todas as linhas falharem | A auditoria fica preservada, mas o operador deve validar os status |
| UI não passa `diretorio_logs` explicitamente | A localização do CSV depende de `BASE_DIR / "logs"` compartilhado entre os arquivos |

---

## 15. Estado Atual da RFC

Esta RFC passa a refletir o código atual de `PrinterAGHU.py`, incluindo a dependência explícita de `autenticador.py`, o login centralizado, o uso de `AGHU_URL`, o Clean State reautenticado, a delegação ao Almoxarifado e o relatório CSV com linha de auditoria.
