# RFC-001 — Orquestrador de Vínculos Impressora-Computador (PrinterAGHU)

- **Status:** Estável
- **Autor:** Pedro e Ruan
- **Data:** 2026-06
- **Atualizado em:** 2026-06-19
- **Arquivo:** `PrinterAGHU.py`
- **Depende de:** `autenticador.py`
- **Depende de:** `AddPrinterAGHU.py` (RFC-002)
- **Depende de:** `menu.py` (RFC-004)
- **Chamado por:** `ui_alignprinterAGHU.py` (RFC-003)

---

## 1. Resumo

`PrinterAGHU.py` é o **Maestro** da automação de vínculos computador–impressora no AGHUX. Ele concentra a regra operacional do módulo **Impressora por Computador**: lê e valida a planilha de entrada, autentica a sessão por meio do autenticador centralizado, navega até o módulo correto, processa cada computador informado e mantém, altera ou cria vínculos conforme o estado encontrado no sistema.

Quando a impressora informada na planilha não existe no autocomplete do AGHUX, o Maestro delega o cadastro ao Robô Especialista (`AddPrinterAGHU.py`, RFC-002). O especialista consulta o CUPS, cadastra a impressora no catálogo do AGHUX e devolve o fluxo ao Maestro, que reconstrói uma aba limpa e tenta novamente a mesma linha.

A autenticação não é mais implementada manualmente neste arquivo. O arquivo importa `AGHU_URL`, `autenticar_aghu_page` e `exigir_login_valido` de `autenticador.py`, que passa a ser a dependência transversal dos robôs. O Maestro também aceita `url_aghu` como parâmetro opcional nos pontos de login, navegação, processamento e Clean State, para preservar o ambiente escolhido pela UI.

---

## 2. Mudanças incorporadas nesta revisão

Esta revisão atualiza a RFC para refletir as implementações da release de 19/06/2026:

| Área | Situação atual |
|---|---|
| Autenticação | Centralizada em `autenticador.py`, não mais descrita como lógica manual local do Maestro |
| URL do AGHUX | Uso de `AGHU_URL` como padrão, com suporte a `url_aghu` recebido do chamador para Produção/Homologação |
| Login local | `fazer_login` agora é wrapper de `autenticar_aghu_page` + `exigir_login_valido` |
| Clean State | Continua fechando a aba atual, abrindo nova aba no mesmo contexto e autenticando pela rotina central; reaproveita sempre o `url_aghu` do fluxo atual |
| Navegação | Usa `navegar_menu_aghu` de `menu.py` (RFC-004) com caminho local `CAMINHO_MENU_IMPRESSORA_POR_COMPUTADOR`; mantém retry com Clean State na primeira falha e preserva a URL selecionada |
| Busca de IP | Usa `_criar_regex_valor_exato` com `re.escape` e lookaround usando `CARACTERES_DE_VALOR` (`A-Za-z0-9_.-`) para evitar correspondência parcial de IP |
| Decisão de ação | Funções `_coletar_linhas_computador` e `_decidir_acao_linhas` separam coleta de registros da decisão, com quatro casos: `mantido`, `alterar`, `incluir` e `conferir` |
| Validação de computador | `_validar_computador_selecionado` confirma que o IP selecionado no autocomplete corresponde ao esperado, prevenindo vínculo errado |
| Tratamento de gravação | `_aguardar_resultado_gravacao` diferencia `sucesso`, `erro` e `indefinido`; erros de classe PDF duplicada recebem mensagem específica |
| Normalização | Ecossistema de funções `_normalizar_busca`, `_valor_exato`, `_contem_valor_exato` para comparação case-insensitive e tolerante a espaços |
| Relatório | Gera CSV em `logs/log_resultado_YYYYMMDD_HHMMSS.csv` com primeira linha de auditoria `Atualizado por: <usuario>` |
| Campos Vazios | Validação proativa de campos obrigatórios em branco via `_campos_obrigatorios_planilha_em_branco`, ignorando e registrando erro nas linhas divergentes |

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
        ├─► page.goto(url_aghu)
        │
        ├─► fazer_login(page, usuario, senha, url_aghu=url_aghu)
        │        └─ autenticar_aghu_page(..., url_login=url_aghu) em autenticador.py
        │
        ├─► navegar_ate_modulo(context, page, usuario, senha, url_aghu=url_aghu)
        │        ├─ Outros Módulos → Configuração → Impressão → Cadastros
        │        ├─ Abre "Impressora por Computador"
        │        ├─ Valida tela pelo botão "Pesquisar" no último iframe
        │        └─ Em falha inicial, aciona Clean State
        │
        └─► processar_computadores(..., url_aghu=url_aghu)
                 │
                 ├─ Para cada linha da planilha:
                 │     ├─ Busca computador por IP no autocomplete
                 │     │    └─ Usa _criar_regex_valor_exato com CARACTERES_DE_VALOR
                 │     ├─ Pesquisa vínculo existente (botão Pesquisar)
                 │     ├─ _coletar_linhas_computador: coleta registros com IP correspondente
                 │     ├─ _decidir_acao_linhas: decide caso com base nos registros
                 │     │
                 │     ├─ [Caso A] "mantido"    → Vínculo correto      → Status: Mantido
                 │     ├─ [Caso B] "conferir"   → Tipo Cups diverge    → Status: Erro (conferência manual)
                 │     ├─ [Caso C] "alterar"    → Linha PDF existente  → Edita  → Status: Alterado/Criado
                 │     └─ [Caso D] "incluir"    → Sem vínculo útil     → Cria   → Status: Vinculado/Criado
                 │
                 ├─ Se a impressora não existir no AGHUX:
                 │     └─► Delegação ao Almoxarifado (RFC-002)
                 │           ├─ trocar_aba_aghux(..., url_aghu=url_aghu)
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
| `AGHU_URL` | URL padrão do AGHUX, com override por variáveis de ambiente; usada como default quando o chamador não fornece `url_aghu` |
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

### 5.3 `menu.py`

`PrinterAGHU.py` importa:

```python
from menu import navegar_menu_aghu
```

Responsabilidades delegadas ao `menu.py`:

| Item | Responsabilidade |
|---|---|
| `navegar_menu_aghu` | Percorre o caminho completo informado, clica no item final e retorna o último iframe |

A navegação pelo menu do AGHUX não é mais implementada manualmente neste arquivo. O Maestro declara seu caminho em `CAMINHO_MENU_IMPRESSORA_POR_COMPUTADOR`, chama `navegar_menu_aghu` e valida localmente a tela final pelo botão **Pesquisar**.

---

## 6. Constantes de Módulo

| Constante | Valor | Uso |
|---|---|---|
| `BASE_DIR` | `Path(__file__).resolve().parent` | Diretório base para localização de logs |
| `CAMINHO_MENU_IMPRESSORA_POR_COMPUTADOR` | `("Outros Módulos", "Configuração", "Impressão", "Cadastros", "Impressora por Computador")` | Caminho completo usado por `navegar_ate_modulo` para abrir o módulo de vínculo |
| `CARACTERES_DE_VALOR` | `r"A-Za-z0-9_.-"` | Classe de caracteres usada nos lookarounds de `_criar_regex_valor_exato` para definir limites de "palavra" em IPs e nomes de fila |
| `TABELA_COMPUTADOR_IMPRESSORA_SELECTOR` | `'[id="tabelaComputadorImpressora:resultList_data"]'` | Seletor CSS do `<tbody>` da tabela de resultados do módulo |
| `MENSAGEM_ERRO_PESQUISA_INDEFINIDA` | Texto descritivo | Mensagem de detalhe quando a pesquisa não retorna linhas nem mensagem de "nenhum registro" |

---

## 7. Funções Auxiliares Privadas

### 7.1 Normalização e Comparação

| Função | Assinatura | Descrição |
|---|---|---|
| `_normalizar_busca` | `(valor: object) → str` | Remove espaços extras, aplica `strip()` e `casefold()` |
| `_normalizar_texto_simples` | `(valor: object) → str` | Alias de `_normalizar_busca` |
| `_criar_regex_valor_exato` | `(valor: object, flags=re.IGNORECASE) → re.Pattern` | Cria regex com `re.escape` e lookaround negativo usando `CARACTERES_DE_VALOR` para evitar correspondência parcial |
| `_contem_valor_exato` | `(texto: object, valor: object) → bool` | Verifica se `texto` contém `valor` como token isolado usando `_criar_regex_valor_exato` (flags=0) |
| `_valor_exato` | `(valor_atual: object, valor_esperado: object) → bool` | Igualdade exata após normalização |

O regex gerado por `_criar_regex_valor_exato` tem a forma:

```python
re.compile(
    rf"(?<![A-Za-z0-9_.-]){re.escape(valor_normalizado)}(?![A-Za-z0-9_.-])",
    flags,
)
```

Isso impede que `10.6.0.22` corresponda a `10.6.0.225`, por exemplo.

### 7.2 Validação de IP

| Função | Assinatura | Descrição |
|---|---|---|
| `_regex_ip_celula` | `(ip_pc: str) → re.Pattern` | Cria regex `^\s*<ip>\s*$` para conferência de célula |
| `_ip_celula_confere` | `(valor_celula: object, ip_pc: str) → bool` | Valida se o valor de uma célula da tabela confere com o IP esperado |
| `_extrair_ips` | `(texto: object) → list[str]` | Extrai todos os endereços IPv4 de um texto |
| `_validar_computador_selecionado` | `(campo_computador, ip_pc, texto_item) → (bool, str)` | Verifica se o computador selecionado no autocomplete corresponde ao IP esperado, retornando `(True, "")` em caso de sucesso ou `(False, ip_divergente)` |

### 7.3 Classificação de Impressão

| Função | Assinatura | Descrição |
|---|---|---|
| `_classe_impressao_aghu` | `(tipo_cups: str) → str` | Converte o tipo CUPS para classe de impressão AGHU; `"PDF"` → `"A"`, demais mantém o valor original |
| `_registro_confere_tipo_e_classe` | `(registro: dict, tipo_cups_esperado: str) → bool` | Verifica se o registro da tabela corresponde ao tipo CUPS esperado e à classe de impressão derivada |
| `_registro_eh_pdf` | `(registro: dict) → bool` | Atalho para verificar se um registro é do tipo PDF (classe A) |

### 7.4 Manipulação da Tabela de Resultados

| Função | Assinatura | Descrição |
|---|---|---|
| `_tbody_resultados` | `(janela_sistema) → Locator` | Localiza o `<tbody>` da tabela pelo seletor `TABELA_COMPUTADOR_IMPRESSORA_SELECTOR` |
| `_linhas_resultado` | `(tbody) → Locator` | Localiza linhas de dados (`tr[data-ri]`) dentro do tbody |
| `_linha_vazia_resultado` | `(tbody) → Locator` | Localiza a linha de "Nenhum registro encontrado!" |
| `_texto_celula` | `(linha_tabela, indice: int) → str` | Extrai o texto da célula na posição `indice` de uma linha da tabela |

### 7.5 Espera e Estado da Pesquisa

| Função | Assinatura | Descrição |
|---|---|---|
| `_aguardar_estado_resultado_pesquisa` | `(janela_sistema, timeout_ms=7000) → (str, Locator)` | Aguarda resultado da pesquisa e retorna estado: `"linhas"` (registros encontrados), `"vazio"` (nenhum registro), ou `"indefinido"` (timeout) |
| `_coletar_linhas_computador` | `(janela_sistema, ip_pc: str) → (str, list[dict])` | Combina `_aguardar_estado_resultado_pesquisa` com extração de registros. Filtra somente linhas cujo IP confere e retorna lista de dicts com chaves: `linha`, `texto`, `ip`, `computador`, `descricao`, `classe`, `fila`, `tipo_cups` |

Mapeamento de colunas da tabela:

| Índice | Chave no dict | Campo da tabela |
|---|---|---|
| 1 | `ip` | Endereço IP |
| 2 | `computador` | Nome do computador |
| 3 | `descricao` | Descrição |
| 4 | `classe` | Classe de impressão |
| 5 | `fila` | Fila de impressão |
| 6 | `tipo_cups` | Tipo CUPS |

### 7.6 Lógica de Decisão

```python
_decidir_acao_linhas(registros_linhas, impressora_alvo, classe_impressao) → (str, dict | None)
```

Percorre os registros coletados e decide a ação:

| Retorno | Condição | Significado |
|---|---|---|
| `"mantido"`, registro | Registro com `fila == impressora_alvo` e tipo+classe conferem | Vínculo já está correto |
| `"conferir"`, registro | Registro com `fila == impressora_alvo` mas tipo+classe divergem | Divergência de tipo; requer conferência manual |
| `"alterar"`, registro_pdf | Nenhum registro com a fila alvo, mas existe registro PDF (classe A) | Reutilizar linha PDF existente editando a impressora |
| `"incluir"`, None | Nenhum registro com fila alvo e nenhum PDF | Necessário criar novo vínculo |

### 7.7 Tratamento de Gravação

| Função | Assinatura | Descrição |
|---|---|---|
| `_mensagem_dialog` | `(janela_sistema, seletor: str) → Locator` | Localiza mensagem dentro do dialog modal de mensagens do AGHU |
| `_aguardar_resultado_gravacao` | `(janela_sistema, page=None, timeout_ms=10000) → (str, str)` | Espera mensagem de sucesso ou erro após clique em Gravar. Retorna `("sucesso", msg)`, `("erro", msg)` ou `("indefinido", "")` |
| `_erro_classe_pdf_duplicada` | `(mensagem: str) → bool` | Detecta erro específico "existe uma impressora cadastrada ... classe A" — caso onde o AGHU bloqueia inclusão de segunda impressora PDF no mesmo computador |

### 7.8 Limpeza de Estado

| Função | Assinatura | Descrição |
|---|---|---|
| `_aguardar_botao_pesquisar_se_possivel` | `(janela_sistema) → None` | Aguarda até 3s pelo botão Pesquisar ficar visível (pós-gravação) |
| `_limpar_estado_formulario` | `(janela_sistema, page=None) → None` | Sequência de limpeza: fecha dialog modal, clica Cancelar, clica botão limpar (cleaner). Usada após erros de gravação |

---

## 8. Descrição dos Componentes Públicos

### 8.1 `ler_planilha(caminho_arquivo)`

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

### 8.2 `fazer_login(page, usuario_str, senha_str, *, url_aghu=AGHU_URL)`

É um wrapper local para autenticação centralizada. O fluxo atual é:

1. Imprime o usuário usado na checagem de autenticação.
2. Chama `autenticar_aghu_page(page=page, usuario=usuario_str, senha=senha_str, url_login=url_aghu, timeout_ms=15000)`.
3. Imprime mensagem conforme `resultado.status`:
   - `sessao_ativa`: sessão já estava ativa;
   - `sucesso`: login efetuado com sucesso;
   - demais status: falha de autenticação.
4. Chama `exigir_login_valido(resultado)`.
5. Retorna o `ResultadoLogin`.

A função não contém mais seletores de campo de usuário, senha ou botão **Entrar**. A detecção da tela de login, credenciais inválidas, timeout e sessão já ativa pertence a `autenticador.py`.

### 8.3 `trocar_aba_aghux(context, page_atual, usuario_str, senha_str, *, url_aghu=AGHU_URL)` — Clean State

Fecha a aba atual, ignorando erro caso ela já esteja indisponível. Em seguida, abre uma nova `Page` no mesmo `BrowserContext`, acessa `url_aghu`, executa `autenticar_aghu_page(..., url_login=url_aghu)` e valida o resultado com `exigir_login_valido`.

O Clean State é usado como recuperação quando a interface do AGHUX fica inconsistente, quando o menu falha, quando o fluxo retorna do Almoxarifado ou quando há falhas técnicas durante o processamento de uma linha.

O uso do mesmo `BrowserContext` preserva sessão, certificados e configuração do browser criada pelo chamador. O uso de `url_aghu` evita que retries ou clean states retornem para Produção quando a UI iniciou a execução em Homologação.

### 8.4 `navegar_ate_modulo(context, page_atual, usuario_str, senha_str, *, url_aghu=AGHU_URL)`

Navega até o módulo **Impressora por Computador** usando o caminho completo declarado no próprio procedimento:

```python
CAMINHO_MENU_IMPRESSORA_POR_COMPUTADOR = (
    "Outros Módulos",
    "Configuração",
    "Impressão",
    "Cadastros",
    "Impressora por Computador",
)
```

A travessia do menu é delegada a `navegar_menu_aghu` de `menu.py` (RFC-004):

```python
janela_sistema = navegar_menu_aghu(
    page=page,
    caminho=CAMINHO_MENU_IMPRESSORA_POR_COMPUTADOR,
)
janela_sistema.get_by_role("button", name="Pesquisar").first.wait_for(
    state="visible",
    timeout=15000,
)
```

`navegar_menu_aghu` percorre o caminho informado, verifica visibilidade de cada nível antes de clicar, abre o módulo e retorna o `FrameLocator` do último iframe. A validação de carregamento da tela pelo botão **Pesquisar** pertence ao Maestro.

A função faz até duas tentativas:

| Tentativa | Ação em falha |
|---|---|
| 1ª | Aciona `trocar_aba_aghux(..., url_aghu=url_aghu)` e tenta novamente |
| 2ª | Propaga a exceção |

Se o laço terminar sem retorno, lança `RuntimeError("Falha ao navegar até o módulo de Impressora por Computador.")`.

### 8.5 `processar_computadores(...)`

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
| `url_aghu` | URL do ambiente AGHUX usado em reautenticações e clean states; default `AGHU_URL` |

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

## 9. Regras de Processamento por Linha

### 9.1 Busca do computador

O campo de computador é localizado por:

```text
input[id*='computador' i], input.ui-autocomplete-input
```

O IP é digitado com:

```python
press_sequentially(ip_pc, delay=150)
```

A seleção do autocomplete usa a função `_criar_regex_valor_exato`, que aplica `re.escape` e lookaround negativo com `CARACTERES_DE_VALOR` para evitar correspondência parcial:

```python
re.compile(
    rf"(?<![A-Za-z0-9_.-]){re.escape(valor_normalizado)}(?![A-Za-z0-9_.-])",
    re.IGNORECASE,
)
```

Esse ajuste evita que `10.6.0.22` corresponda indevidamente a `10.6.0.225`.

Se nenhuma sugestão compatível aparece, a linha recebe `Inexistente` com detalhe `Computador não cadastrado no AGHUX.`.

### 9.2 Pesquisa e coleta de vínculos

Após selecionar o computador, o Maestro clica em **Pesquisar**. A função `_coletar_linhas_computador` é invocada e:

1. Chama `_aguardar_estado_resultado_pesquisa` que monitora a tabela `TABELA_COMPUTADOR_IMPRESSORA_SELECTOR` até detectar linhas visíveis, mensagem de "nenhum registro", ou timeout.
2. Se o estado for `"linhas"`, percorre cada `tr[data-ri]` visível e filtra somente aquelas cujo IP da célula (índice 1) confere com `ip_pc` via `_ip_celula_confere`.
3. Monta registros com as colunas: `ip`, `computador`, `descricao`, `classe`, `fila`, `tipo_cups`.

O estado retornado guia o fluxo:

| Estado | Significado | Ação |
|---|---|---|
| `"linhas"` com registros | Registros encontrados para o IP | Passa para `_decidir_acao_linhas` |
| `"linhas"` sem registros | Tabela tem linhas, mas nenhuma com o IP | Erro: conferência manual |
| `"vazio"` | Nenhum registro encontrado | Passa para `_decidir_acao_linhas` (lista vazia → incluir) |
| `"indefinido"` | Timeout sem estado claro | Erro: `MENSAGEM_ERRO_PESQUISA_INDEFINIDA` |

### 9.3 Decisão de ação (`_decidir_acao_linhas`)

A função percorre os registros e retorna uma das quatro ações:

#### Caso A: Vínculo já correto (`"mantido"`)

Condição: existe registro com `fila == impressora_alvo` e `_registro_confere_tipo_e_classe` retorna `True`.

| Campo | Valor |
|---|---|
| `Status` | `Mantido` |
| `Detalhes` | `Impressora já estava correta no sistema.` |

A tela é limpa pelo botão com ícone `.aghu-icon-cleaner-aghu`.

#### Caso B: Tipo CUPS divergente (`"conferir"`)

Condição: existe registro com `fila == impressora_alvo`, mas `_registro_confere_tipo_e_classe` retorna `False` — ou seja, a impressora está vinculada ao computador mas com tipo de CUPS diferente do informado na planilha.

| Campo | Valor |
|---|---|
| `Status` | `Erro` |
| `Detalhes` | `Conferir manualmente: impressora ja vinculada ao computador com Tipo do Cups [<atual>], diferente da planilha [<esperado>].` |

Neste caso o Maestro não tenta alterar automaticamente, pois a divergência de tipo pode indicar configuração intencional.

#### Caso C: Linha PDF existente para reutilizar (`"alterar"`)

Condição: nenhum registro com `fila == impressora_alvo`, mas existe registro com tipo `PDF` / classe `A`.

Ação:

1. Clica no botão de edição da linha PDF por título `editar`/`alterar` ou ícone `.aghu-icon-edit`.
2. Aguarda botão **Gravar**.
3. Limpa o campo de impressora (botão cleaner).
4. Digita `HostPrinter` com `press_sequentially(..., delay=150)`.
5. Seleciona a sugestão do autocomplete.
6. Clica em **Gravar**.
7. Aguarda resultado da gravação via `_aguardar_resultado_gravacao`:
   - `"sucesso"`: prossegue.
   - `"erro"`: registra erro com mensagem do AGHU e aciona `_limpar_estado_formulario`.
   - `"indefinido"`: registra erro de conferência manual e aciona `_limpar_estado_formulario`.
8. Aguarda botão **Pesquisar** (`_aguardar_botao_pesquisar_se_possivel`).
9. Limpa a tela.

| Condição | Status | Detalhes |
|---|---|---|
| Impressora já existia no AGHUX | `Alterado` | `Vínculo atualizado com sucesso.` |
| Impressora foi cadastrada nesta execução | `Criado` | `Impressora cadastrada no CUPS e atualizada.` |

#### Caso D: Sem vínculo utilizável (`"incluir"`)

Condição: nenhum registro com `fila == impressora_alvo` e nenhum registro PDF.

Ação:

1. Clica em **Novo**.
2. Aguarda botão **Gravar**.
3. Seleciona novamente o computador pelo IP exato.
4. Valida o computador selecionado com `_validar_computador_selecionado` — se o IP selecionado diverge do esperado, lança `ValueError` para conferência manual.
5. Seleciona a impressora alvo.
6. Verifica a classe preenchida automaticamente via `_classe_impressao_aghu`.
7. Se a classe não corresponder, limpa o campo e usa a lupa (botão `.ui-icon-triangle-1-s`) para selecionar a classe correta.
8. Clica em **Gravar**.
9. Aguarda resultado da gravação via `_aguardar_resultado_gravacao`:
   - `"sucesso"`: prossegue.
   - `"erro"`: verifica se é `_erro_classe_pdf_duplicada` para mensagem específica; caso contrário, registra erro genérico. Aciona `_limpar_estado_formulario`.
   - `"indefinido"`: registra erro de conferência manual e aciona `_limpar_estado_formulario`.
10. Aguarda botão **Pesquisar** (`_aguardar_botao_pesquisar_se_possivel`).
11. Limpa a tela.

| Condição | Status | Detalhes |
|---|---|---|
| Impressora já existia no AGHUX | `Vinculado` | `Vínculo criado com sucesso.` |
| Impressora foi cadastrada nesta execução | `Criado` | `Impressora nova identificada no CUPS, criada e vinculada no AGHU.` |

---

## 10. Delegação ao Almoxarifado

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
              ├─ trocar_aba_aghux(..., url_aghu=url_aghu)
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

## 11. Recuperação de Falhas Técnicas

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

Após falhas funcionais, o Maestro tenta cancelar a tela ou limpar o formulário antes de seguir para a próxima linha. A limpeza é feita por `_limpar_estado_formulario`, que:

1. Fecha o dialog modal de mensagens (se aberto).
2. Clica em **Cancelar**.
3. Clica no botão de limpeza (`.aghu-icon-cleaner-aghu`).

---

## 12. Relatório de Auditoria

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

## 13. API Pública do Módulo

| Função | Responsabilidade |
|---|---|
| `ler_planilha(caminho_arquivo)` | Lê e valida a planilha de entrada |
| `fazer_login(page, usuario_str, senha_str, *, url_aghu=AGHU_URL)` | Autentica usando o autenticador centralizado na URL do ambiente atual |
| `trocar_aba_aghux(context, page_atual, usuario_str, senha_str, *, url_aghu=AGHU_URL)` | Fecha aba atual, abre aba limpa na URL informada e reautentica |
| `navegar_ate_modulo(context, page_atual, usuario_str, senha_str, *, url_aghu=AGHU_URL)` | Abre **Impressora por Computador** e retorna `(page, janela_sistema)`, preservando a URL em retry |
| `processar_computadores(..., url_aghu=AGHU_URL)` | Processa linhas da planilha, preserva a URL em clean states e gera CSV auditável |

---

## 14. Contratos entre RFCs

### 14.1 Contrato com RFC-002

| Evento | Origem | Interpretação no Maestro |
|---|---|---|
| `ValueError("Impressora não existe")` | Seleção de impressora no vínculo | Aciona Almoxarifado |
| `ValueError("Não existe no CUPS")` | Consulta ao CUPS no Almoxarifado | Marca fila como inexistente |
| Retorno silencioso de `cadastrar_nova_impressora` | Impressora já existia no AGHUX | Retoma tentativa de vínculo |
| Cadastro concluído | Almoxarifado | Abre aba limpa e reprocessa linha |

### 14.2 Contrato com RFC-003

A UI deve fornecer:

| Item | Origem |
|---|---|
| `BrowserContext` | Criado pela UI com `ignore_https_errors=True` |
| `Page` | Criada pela UI e apontada para `url_aghu` |
| `url_aghu` | URL resolvida a partir do seletor de ambiente da UI |
| Credenciais | Campos da interface |
| Planilha | Lida e validada antes da execução |
| Caminho de saída | Usado pela UI após localizar o CSV gerado |

O Maestro retorna o caminho do CSV gerado, mas a UI atual localiza o arquivo por timestamp em `./logs` e converte para XLSX. A UI deve passar o mesmo `url_aghu` para `fazer_login`, `navegar_ate_modulo` e `processar_computadores`, garantindo que qualquer Clean State permaneça no ambiente selecionado.

---

## 15. Considerações Operacionais

1. `PrinterAGHU.py` não cria o browser principal; o chamador cria `Browser`, `BrowserContext` e `Page`.
2. O módulo cria novas abas no mesmo contexto apenas para Clean State.
3. A autenticação deve permanecer centralizada em `autenticador.py`.
4. O parâmetro `url_aghu` deve ser propagado por todo retry, retomada e Clean State para evitar troca acidental de ambiente.
5. O fluxo depende de textos visíveis do AGHUX como **Outros Módulos**, **Configuração**, **Impressão**, **Cadastros**, **Impressora por Computador**, **Pesquisar**, **Novo** e **Gravar**.
6. As mensagens de erro usadas como contrato (`Impressora não existe`, `Computador não encontrado`, `Não existe no CUPS`) não devem ser alteradas sem atualizar as RFCs e os tratadores.
7. O uso de `press_sequentially` é intencional para disparar eventos JSF/autocomplete.
8. O seletor `TABELA_COMPUTADOR_IMPRESSORA_SELECTOR` e os índices de coluna usados em `_coletar_linhas_computador` dependem da estrutura HTML atual do AGHUX; mudanças na tabela exigem ajuste coordenado.

---

## 16. Limitações Conhecidas

| Limitação | Impacto |
|---|---|
| Seletores dependem de textos do AGHUX | Mudanças de nomenclatura no sistema podem quebrar navegação |
| Erros de negócio dependem de strings exatas | Alterações nas mensagens exigem atualização coordenada |
| Relatório CSV é gerado mesmo se todas as linhas falharem | A auditoria fica preservada, mas o operador deve validar os status |
| UI não passa `diretorio_logs` explicitamente | A localização do CSV depende de `BASE_DIR / "logs"` compartilhado entre os arquivos |
| Pontos cegos restantes a mapear | Existem cenários não cobertos que devem ser mapeados e tratados em revisão futura |

---

## 17. Estado Atual da RFC

Esta RFC passa a refletir o código atual de `PrinterAGHU.py` conforme a release de 19/06/2026, incluindo:
- Dependência explícita de `autenticador.py`, login centralizado e uso de `AGHU_URL` como default com `url_aghu` propagado em runtime.
- Clean State reautenticado e delegação ao Almoxarifado.
- Ecossistema completo de funções auxiliares privadas: normalização, comparação, validação de IP, classificação de impressão, manipulação de tabela, lógica de decisão e tratamento de gravação.
- Quatro casos de decisão (`mantido`, `conferir`, `alterar`, `incluir`) documentados individualmente.
- Validação de computador selecionado no autocomplete.
- Tratamento diferenciado de resultados de gravação (sucesso, erro, indefinido) com mensagem específica para erro de classe PDF duplicada.
- Relatório CSV com linha de auditoria.
- Tratamento e registro correto de linhas com campos obrigatórios vazios.
- Limitações atualizadas com base nas observações da release.
