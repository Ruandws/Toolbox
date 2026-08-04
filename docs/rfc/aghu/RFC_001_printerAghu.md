# RFC-001 — Orquestrador de Vínculos Impressora-Computador (PrinterAGHU)

- **Status:** Estável
- **Autor:** Pedro e Ruan
- **Data:** 2026-06
- **Atualizado em:** 2026-08-04
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

Esta revisão atualiza a RFC para refletir o estado atual do código:

| Área | Situação atual |
|---|---|
| Autenticação | Centralizada em `autenticador.py`, não mais descrita como lógica manual local do Maestro |
| URL do AGHUX | Uso de `AGHU_URL` como padrão, com suporte a `url_aghu` recebido do chamador para Produção/Homologação |
| Login local | `fazer_login` agora é wrapper de `autenticar_aghu_page` + `exigir_login_valido` |
| Clean State | Fecha **todas** as abas do contexto antes de abrir aba limpa; tenta autenticação em loop com até `MAX_TENTATIVAS_AUTENTICAR_NOVA_ABA` tentativas; lança `RuntimeError` próprio ao esgotar |
| Navegação | Usa `navegar_menu_aghu` de `menu.py` (RFC-004) com caminho local `CAMINHO_MENU_IMPRESSORA_POR_COMPUTADOR`; mantém retry com Clean State na primeira falha |
| Busca de IP | Usa `_criar_regex_valor_exato` com `re.escape` e lookaround usando `CARACTERES_DE_VALOR` (`A-Za-z0-9_.-`) para evitar correspondência parcial de IP |
| Leitura de planilha | Usa `openpyxl` diretamente via `read_spreadsheet`/`read_xlsx`; extensão suportada apenas `.xlsx`; resolve nomes de colunas com `ALIASES_COLUNAS_PLANILHA` e `normalize_column_name`; retorna `list[Row]` |
| Decisão de ação | `_coletar_linhas_computador` integra a espera de estado e a extração de registros; `_decidir_acao_linhas` decide com quatro casos: `mantido`, `alterar`, `incluir` e `conferir` |
| Relatório | Gera `.xlsx` via `write_xlsx_report` com `freeze_panes`, `auto_filter` e `autofit`; nome `Resultado_{DD_MM_YY_HHhMMmSS}.xlsx`; `report_directory` é parâmetro obrigatório de `processar_computadores`; a UI o fornece explicitamente |

---

## 3. Motivação

Vincular impressoras a computadores no AGHUX é uma rotina repetitiva, sensível a divergências silenciosas e dependente de autocompletes JSF. Um computador pode já possuir vínculo correto, possuir vínculo para outra impressora, não possuir vínculo ou nem existir no cadastro. Além disso, a impressora alvo pode não existir no catálogo do AGHUX, embora exista no CUPS.

O Maestro centraliza esse fluxo em uma rotina auditável com recuperação controlada: tenta operar o vínculo, usa aba limpa quando a interface fica instável, delega o cadastro de impressoras ausentes ao Almoxarifado e registra o resultado por linha em relatório `.xlsx`.

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
        └─► processar_computadores(..., caminho_planilha, report_directory, url_aghu=url_aghu)
                 │
                 ├─ ler_planilha(caminho_planilha) → list[Row] (internamente)
                 │
                 ├─ Para cada linha da planilha:
                 │     ├─ Busca computador por IP no autocomplete
                 │     │    └─ Usa _criar_regex_valor_exato com CARACTERES_DE_VALOR
                 │     ├─ Pesquisa vínculo existente (botão Pesquisar)
                 │     ├─ _coletar_linhas_computador: aguarda estado + coleta registros com IP correspondente
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
                 └─ Gera relatório .xlsx auditável em report_directory
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
| `BASE_DIR` | `Path(__file__).resolve().parent` | Diretório base do arquivo |
| `SUPPORTED_EXTENSIONS` | `(".xlsx",)` | Única extensão aceita por `ler_planilha`/`validate_spreadsheet_extension` |
| `CAMINHO_MENU_IMPRESSORA_POR_COMPUTADOR` | `("Outros Módulos", "Configuração", "Impressão", "Cadastros", "Impressora por Computador")` | Caminho completo usado por `navegar_ate_modulo` para abrir o módulo de vínculo |
| `COLUNAS_OBRIGATORIAS_PLANILHA` | `["IPPC", "HostPrinter", "PrinterClass"]` | Colunas obrigatórias validadas ao ler a planilha e ao verificar campos em branco por linha |
| `COLUNAS_RELATORIO` | `("HostPC", "IPPC", "HostPrinter", "IPPrinter", "PrinterClass", "Status", "Detalhes")` | Ordem e conjunto de colunas do relatório `.xlsx` gerado |
| `ALIASES_COLUNAS_PLANILHA` | `dict[str, tuple[str, ...]]` | Mapa de aliases por coluna canônica; usado por `identify_column_by_alias` para localizar colunas independente do nome exato na planilha (ver §8.1) |
| `CARACTERES_DE_VALOR` | `r"A-Za-z0-9_.-"` | Classe de caracteres usada nos lookarounds de `_criar_regex_valor_exato` para definir limites de "palavra" em IPs e nomes de fila |
| `TABELA_COMPUTADOR_IMPRESSORA_SELECTOR` | `'[id="tabelaComputadorImpressora:resultList_data"]'` | Seletor CSS do `<tbody>` da tabela de resultados do módulo |
| `MENSAGEM_ERRO_PESQUISA_INDEFINIDA` | Texto descritivo | Mensagem de detalhe quando a pesquisa não retorna linhas nem mensagem de "nenhum registro" |
| `MAX_TENTATIVAS_AUTENTICAR_NOVA_ABA` | `3` | Número máximo de tentativas de autenticação dentro de `trocar_aba_aghux` |
| `INTERVALO_RETRY_AUTENTICAR_NOVA_ABA_SEGUNDOS` | `1` | Pausa em segundos entre tentativas de autenticação no Clean State |
| `MAX_TENTATIVAS_PROCESSAMENTO_LINHA` | `3` | Número máximo de tentativas por linha em `_processar_linha_com_retentativas` |
| `MAX_TENTATIVAS_ESTOQUE` | `3` | Número máximo de tentativas de cadastro delegado ao Almoxarifado |
| `XLSX_HEADER_ROW` | `1` | Linha do cabeçalho no relatório `.xlsx` |
| `XLSX_FREEZE_PANES_CELL` | `"A2"` | Célula de referência para `freeze_panes` do relatório |
| `XLSX_MIN_COLUMN_WIDTH` | `12` | Largura mínima de coluna no autofit |
| `XLSX_MAX_COLUMN_WIDTH` | `60` | Largura máxima de coluna no autofit |
| `XLSX_COLUMN_PADDING` | `2` | Padding adicionado ao comprimento máximo de célula no autofit |

---

## 7. Dataclasses e Exceção

### 7.1 `DadosLinhaPlanilha`

```python
@dataclass(frozen=True)
class DadosLinhaPlanilha:
    ip_pc: str
    impressora_alvo: str
    classe_impressao: str
```

Representa os dados extraídos de uma linha da planilha prontos para uso no fluxo de automação.

### 7.2 `ResultadoLinha`

```python
@dataclass(frozen=True)
class ResultadoLinha:
    status: str
    detalhes: str
```

Encapsula o desfecho de uma linha processada. `status` é um dos valores de `COLUNAS_RELATORIO` (`Mantido`, `Alterado`, `Vinculado`, `Criado`, `Inexistente`, `Erro`).

### 7.3 `AcaoVinculo`

```python
@dataclass(frozen=True)
class AcaoVinculo:
    tipo: str
    registro: dict | None = None
```

Transporta a decisão retornada por `_decidir_acao_linhas` (`mantido`, `conferir`, `alterar` ou `incluir`) e o registro da tabela associado, quando houver.

### 7.4 `FalhaTecnicaProcessamento`

```python
class FalhaTecnicaProcessamento(RuntimeError):
    def __init__(self, passo: str, erro: Exception): ...
```

Exceção própria lançada por `_processar_linha_aghu` quando ocorre falha técnica de browser/elemento num passo específico. Carrega `passo` (nome do passo corrente) e `erro` (exceção original), permitindo ao tratador de retentativas identificar onde a falha ocorreu.

---

## 8. Funções Auxiliares Privadas

### 8.1 Normalização e Comparação

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

### 8.2 Validação de IP

| Função | Assinatura | Descrição |
|---|---|---|
| `_regex_ip_celula` | `(ip_pc: str) → re.Pattern` | Cria regex `^\s*<ip>\s*$` para conferência de célula |
| `_ip_celula_confere` | `(valor_celula: object, ip_pc: str) → bool` | Valida se o valor de uma célula da tabela confere com o IP esperado |
| `_extrair_ips` | `(texto: object) → list[str]` | Extrai todos os endereços IPv4 de um texto |
| `_validar_computador_selecionado` | `(campo_computador, ip_pc, texto_item) → (bool, str)` | Verifica se o computador selecionado no autocomplete corresponde ao IP esperado, retornando `(True, "")` em caso de sucesso ou `(False, ip_divergente)` |

### 8.3 Classificação de Impressão

| Função | Assinatura | Descrição |
|---|---|---|
| `_classe_impressao_aghu` | `(tipo_cups: str) → str` | Converte o tipo CUPS para classe de impressão AGHU; `"PDF"` → `"A"`, demais mantém o valor original |
| `_registro_confere_tipo_e_classe` | `(registro: dict, tipo_cups_esperado: str) → bool` | Verifica se o registro da tabela corresponde ao tipo CUPS esperado e à classe de impressão derivada |
| `_registro_eh_pdf` | `(registro: dict) → bool` | Atalho para verificar se um registro é do tipo PDF (classe A) |

### 8.4 Manipulação da Tabela de Resultados

| Função | Assinatura | Descrição |
|---|---|---|
| `_tbody_resultados` | `(janela_sistema) → Locator` | Localiza o `<tbody>` da tabela pelo seletor `TABELA_COMPUTADOR_IMPRESSORA_SELECTOR` |
| `_linhas_resultado` | `(tbody) → Locator` | Localiza linhas de dados (`tr[data-ri]`) dentro do tbody |
| `_linha_vazia_resultado` | `(tbody) → Locator` | Localiza a linha de "Nenhum registro encontrado!" |
| `_texto_celula` | `(linha_tabela, indice: int) → str` | Extrai o texto da célula na posição `indice` de uma linha da tabela |

### 8.5 Espera e Estado da Pesquisa

A função `_aguardar_estado_resultado_pesquisa` **não existe mais como função autônoma**. Ela foi fundida em `_coletar_linhas_computador`, que hoje executa tanto a espera de estado quanto a extração de registros em um único passo:

```python
def _coletar_linhas_computador(
    janela_sistema,
    ip_pc: str,
    timeout_ms: int = 7000,
) -> tuple[str, list[dict]]:
```

A função monitora a tabela `TABELA_COMPUTADOR_IMPRESSORA_SELECTOR` durante `timeout_ms` ms e retorna `(estado, registros)`:

| Estado retornado | Condição | Registros |
|---|---|---|
| `"vazio"` | Linha "Nenhum registro encontrado!" visível | `[]` |
| `"linhas"` | Linhas `tr[data-ri]` com IP correspondente encontradas | Lista de dicts filtrada |
| `"linhas"` | Linhas visíveis, mas nenhuma com o IP esperado (timeout) | `[]` |
| `"indefinido"` | Timeout sem linha vazia nem linha com dados | `[]` |

Mapeamento de colunas da tabela (índices em `_extrair_registro_linha`):

| Índice | Chave no dict | Campo da tabela |
|---|---|---|
| 1 | `ip` | Endereço IP |
| 2 | `computador` | Nome do computador |
| 3 | `descricao` | Descrição |
| 4 | `classe` | Classe de impressão |
| 5 | `fila` | Fila de impressão |
| 6 | `tipo_cups` | Tipo CUPS |

### 8.6 Lógica de Decisão

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

### 8.7 Tratamento de Gravação

| Função | Assinatura | Descrição |
|---|---|---|
| `_mensagem_dialog` | `(janela_sistema, seletor: str) → Locator` | Localiza mensagem dentro do dialog modal de mensagens do AGHU |
| `_aguardar_resultado_gravacao` | `(janela_sistema, page=None, timeout_ms=10000) → (str, str)` | Espera mensagem de sucesso ou erro após clique em Gravar. Retorna `("sucesso", msg)`, `("erro", msg)` ou `("indefinido", "")` |
| `_erro_classe_pdf_duplicada` | `(mensagem: str) → bool` | Detecta erro específico "existe uma impressora cadastrada ... classe a" — caso onde o AGHU bloqueia inclusão de segunda impressora PDF no mesmo computador |

### 8.8 Limpeza de Estado

| Função | Assinatura | Descrição |
|---|---|---|
| `_aguardar_botao_pesquisar_se_possivel` | `(janela_sistema) → None` | Aguarda até 3 s pelo botão Pesquisar ficar visível (pós-gravação) |
| `_limpar_estado_formulario` | `(janela_sistema, page=None) → None` | Sequência de limpeza: fecha dialog modal, clica Cancelar, clica botão limpar (cleaner). Usada após erros de gravação |

---

## 9. Descrição dos Componentes Públicos

### 9.1 `ler_planilha(caminho_arquivo: str) → list[Row]`

Lê um arquivo `.xlsx` e retorna uma lista de dicionários normalizados. A função não assume arquivo fixo no diretório do script; o caminho é fornecido pelo chamador.

**Implementação interna:**

1. `validate_spreadsheet_extension` — rejeita qualquer extensão fora de `SUPPORTED_EXTENSIONS`.
2. `read_xlsx` — lê a planilha com `openpyxl` (`load_workbook(..., data_only=True)`), extrai a aba ativa, converte a primeira linha em cabeçalhos únicos e retorna `(headers, rows)`.
3. `identify_spreadsheet_columns` — para cada coluna canônica, chama `identify_column_by_alias`, que normaliza os nomes com `normalize_column_name` e os compara com as entradas de `ALIASES_COLUNAS_PLANILHA`.
4. `build_spreadsheet_row` — mapeia cada linha da planilha para as chaves canônicas (`HostPC`, `IPPC`, `HostPrinter`, `IPPrinter`, `PrinterClass`).

**Formato aceito:**

| Extensão | Leitor | Observação |
|---|---|---|
| `.xlsx` | `openpyxl` via `load_workbook` | Única extensão suportada |

**Sistema de alias de colunas (`ALIASES_COLUNAS_PLANILHA`):**

A planilha de entrada não precisa usar exatamente os nomes canônicos. O dicionário `ALIASES_COLUNAS_PLANILHA` mapeia cada coluna canônica a uma tupla de variações aceitas:

```python
ALIASES_COLUNAS_PLANILHA = {
    "HostPC":       ("HostPC", "Host PC", "Computador", "Nome Computador", "Nome do Computador"),
    "IPPC":         ("IPPC", "IP PC", "IP do PC", "IP Computador", "IP do Computador",
                     "Endereco IP PC", "Endereco IP do PC"),
    "HostPrinter":  ("HostPrinter", "Host Printer", "Impressora", "Fila",
                     "Fila Impressora", "Fila da Impressora", "Nome Impressora", "Nome da Impressora"),
    "IPPrinter":    ("IPPrinter", "IP Printer", "IP da Impressora", "IP Impressora",
                     "Endereco IP Impressora", "Endereco IP da Impressora"),
    "PrinterClass": ("PrinterClass", "Printer Class", "Classe", "Classe Impressao",
                     "Classe de Impressao", "Tipo", "Tipo CUPS"),
}
```

A função `normalize_column_name` normaliza o nome antes da comparação: remove acentos (NFKD + filtragem de combining chars), aplica `casefold` e colapsa espaços consecutivos.

**Erros previstos:**

| Condição | Exceção |
|---|---|
| Arquivo inexistente | `FileNotFoundError` |
| Extensão inválida (não `.xlsx`) | `ValueError("Formato de planilha nao suportado: ...")` |
| Planilha sem aba ativa | `ValueError("A planilha nao possui aba ativa.")` |
| Planilha vazia | `ValueError("A planilha XLSX esta vazia.")` |
| Planilha sem cabeçalho | `ValueError("A planilha nao possui cabecalho.")` |
| Coluna obrigatória ausente | `ValueError("Coluna obrigatoria nao encontrada para ...")` |

### 9.2 `fazer_login(page, usuario_str, senha_str, *, url_aghu=AGHU_URL)`

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

### 9.3 `trocar_aba_aghux(context, page_atual, usuario_str, senha_str, *, url_aghu=AGHU_URL, max_tentativas_autenticacao=MAX_TENTATIVAS_AUTENTICAR_NOVA_ABA)` — Clean State

Isola a sessão fechando **todas as abas do contexto** (não apenas a aba atual) e abre uma aba limpa com autenticação em loop.

**Fluxo:**

1. Fecha `page_atual` silenciosamente com `_fechar_page_silenciosamente`.
2. Fecha todas as demais abas do contexto com `_fechar_abas_contexto(context)`.
3. Itera até `max_tentativas_autenticacao` vezes:
   - Cria `nova_page = context.new_page()` e navega para `url_aghu`.
   - Chama `autenticar_aghu_page(...)`.
   - Se `resultado.status` for `"sessao_ativa"` ou `"sucesso"`, fecha todas as abas exceto `nova_page` e retorna `nova_page`.
   - Se falhar, fecha `nova_page`, aguarda `INTERVALO_RETRY_AUTENTICAR_NOVA_ABA_SEGUNDOS` s e tenta novamente.
4. Ao esgotar todas as tentativas, fecha quaisquer abas restantes e lança:

```python
RuntimeError(
    f"Falha ao autenticar nova aba apos {total_tentativas} tentativas: {ultima_falha}"
)
```

> A função **não chama `exigir_login_valido`** internamente — ela gerencia o loop de retry diretamente e lança `RuntimeError` próprio ao esgotar tentativas.

O uso do mesmo `BrowserContext` preserva sessão, certificados e configuração do browser criada pelo chamador. O uso de `url_aghu` evita que retries ou clean states retornem para Produção quando a UI iniciou a execução em Homologação.

### 9.4 `navegar_ate_modulo(context, page_atual, usuario_str, senha_str, *, url_aghu=AGHU_URL)`

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

### 9.5 `processar_computadores(...)`

É o laço principal da automação. Assinatura completa:

```python
def processar_computadores(
    context: BrowserContext,
    page_inicial: Page,
    janela_sistema_inicial,
    caminho_planilha: str,
    usuario_str: str,
    senha_str: str,
    report_directory: str | os.PathLike,
    url_aghu: str = AGHU_URL,
) -> str:
```

| Parâmetro | Tipo | Uso |
|---|---|---|
| `context` | `BrowserContext` | Abre novas abas e permite Clean State |
| `page_inicial` | `Page` | Página AGHUX já autenticada |
| `janela_sistema_inicial` | FrameLocator | Último iframe do módulo **Impressora por Computador** |
| `caminho_planilha` | `str` | Caminho do arquivo `.xlsx` lido internamente por `ler_planilha` |
| `usuario_str` | `str` | Reautenticação em Clean State |
| `senha_str` | `str` | Reautenticação em Clean State |
| `report_directory` | `str \| os.PathLike` | **Parâmetro obrigatório** — diretório onde o relatório `.xlsx` será gravado; a UI pergunta ao operador e passa explicitamente |
| `url_aghu` | `str` | URL do ambiente AGHUX usado em reautenticações e Clean States; default `AGHU_URL` |

A função chama `ler_planilha(caminho_planilha)` internamente para obter `list[Row]`. O `report_directory` é validado por `build_report_path`, que exige que o diretório exista (`FileNotFoundError` caso contrário).

Para cada linha, o processamento usa `DadosLinhaPlanilha`:

| Campo | Uso |
|---|---|
| `ip_pc` | Busca e seleção do computador no AGHUX |
| `impressora_alvo` | Impressora alvo a vincular |
| `classe_impressao` | Classe usada na pesquisa e validação do vínculo |

Os campos `HostPC` e `IPPrinter` são copiados diretamente para o relatório sem uso no fluxo de automação.

Cada linha possui até `MAX_TENTATIVAS_PROCESSAMENTO_LINHA` tentativas para falhas técnicas. O estado inicial é `Erro` com detalhe `Falha Desconhecida.` e só é substituído quando a linha alcança um desfecho reconhecido.

Retorna o caminho absoluto (string) do arquivo `.xlsx` gerado.

---

## 10. Regras de Processamento por Linha

### 10.1 Busca do computador

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

Se nenhuma sugestão compatível aparece, a linha recebe `Inexistente` com detalhe `Computador não cadastrado no AGHUX.`

### 10.2 Pesquisa e coleta de vínculos

Após selecionar o computador, o Maestro clica em **Pesquisar**. A função `_coletar_linhas_computador` (que integra a espera de estado) é invocada e:

1. Monitora a tabela `TABELA_COMPUTADOR_IMPRESSORA_SELECTOR` em loop por até `timeout_ms` ms.
2. Retorna `"vazio"` ao detectar a linha "Nenhum registro encontrado!".
3. Se detectar linhas `tr[data-ri]`, filtra somente aquelas cujo IP confere via `_ip_celula_confere` e retorna `"linhas"` com a lista.
4. Se o loop expirar sem resultado claro, retorna `"indefinido"`.

O estado retornado guia o fluxo:

| Estado | Significado | Ação |
|---|---|---|
| `"linhas"` com registros | Registros encontrados para o IP | Passa para `_decidir_acao_linhas` |
| `"linhas"` sem registros | Tabela tem linhas, mas nenhuma com o IP | Erro: conferência manual |
| `"vazio"` | Nenhum registro encontrado | Passa para `_decidir_acao_linhas` (lista vazia → incluir) |
| `"indefinido"` | Timeout sem estado claro | Erro: `MENSAGEM_ERRO_PESQUISA_INDEFINIDA` |

### 10.3 Decisão de ação (`_decidir_acao_linhas`)

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

## 11. Delegação ao Almoxarifado

A delegação é acionada quando a seleção da impressora lança exatamente:

```python
ValueError("Impressora não existe")
```

O Maestro interpreta essa mensagem como ausência da fila no autocomplete de impressoras do AGHUX e chama o Robô Especialista.

Fluxo da delegação:

```text
ValueError("Impressora não existe")
        │
        └─► Até MAX_TENTATIVAS_ESTOQUE (3) tentativas de Almoxarifado:
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

## 12. Recuperação de Falhas Técnicas

Erros do tipo `ValueError` são tratados como eventos de negócio quando contêm mensagens conhecidas:

| Mensagem | Interpretação |
|---|---|
| `Impressora não existe` | Aciona Almoxarifado |
| `Computador não encontrado` | Marca computador como inexistente |
| Outra mensagem | Marca linha como erro funcional |

Demais exceções são capturadas por `_processar_linha_aghu` e relançadas como `FalhaTecnicaProcessamento`, transportando o nome do passo atual. Nesses casos:

| Tentativa | Ação |
|---|---|
| 1ª ou 2ª | Cria aba limpa, renavega ao módulo e tenta novamente |
| 3ª | Marca `Erro` e detalhe `Falha de sistema ou rede no passo '<passo_atual>' após 3 tentativas.` |

Após falhas funcionais, o Maestro tenta cancelar a tela ou limpar o formulário antes de seguir para a próxima linha. A limpeza é feita por `_limpar_estado_formulario`, que:

1. Fecha o dialog modal de mensagens (se aberto).
2. Clica em **Cancelar**.
3. Clica no botão de limpeza (`.aghu-icon-cleaner-aghu`).

---

## 13. Relatório de Auditoria

Ao final, `processar_computadores` chama `_gerar_relatorio_xlsx`, que invoca `write_report` → `write_xlsx_report`.

O arquivo gerado é:

```text
<report_directory>/Resultado_{DD_MM_YY_HHhMMmSS}.xlsx
```

O nome é produzido por `generate_report_filename` usando `datetime.now().strftime("%d_%m_%y_%Hh%Mm%S")`. Se o arquivo já existir (colisão de nome), `get_available_report_path` incrementa um contador (`_2`, `_3`, …) até encontrar nome disponível.

`write_xlsx_report` usa `openpyxl.Workbook` e aplica `apply_xlsx_report_layout`, que:

- Define `worksheet.freeze_panes = "A2"` (linha de cabeçalho congelada).
- Define `worksheet.auto_filter.ref` cobrindo todo o intervalo de dados.
- Chama `autofit_xlsx_columns` para ajustar a largura de cada coluna com base no conteúdo, respeitando `XLSX_MIN_COLUMN_WIDTH` e `XLSX_MAX_COLUMN_WIDTH`.

Não há linha de auditoria `"Atualizado por: <usuario>"` nem uso de `pandas` na geração do relatório.

Colunas do relatório (definidas em `COLUNAS_RELATORIO`):

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

## 14. API Pública do Módulo

| Função | Responsabilidade |
|---|---|
| `ler_planilha(caminho_arquivo: str) → list[Row]` | Lê e valida planilha `.xlsx`; resolve aliases de colunas; retorna lista de dicts normalizados |
| `fazer_login(page, usuario_str, senha_str, *, url_aghu=AGHU_URL)` | Autentica usando o autenticador centralizado na URL do ambiente atual |
| `trocar_aba_aghux(context, page_atual, usuario_str, senha_str, *, url_aghu=AGHU_URL, max_tentativas_autenticacao=MAX_TENTATIVAS_AUTENTICAR_NOVA_ABA) → Page` | Fecha todas as abas do contexto, abre aba limpa e tenta autenticar em loop; lança `RuntimeError` ao esgotar tentativas |
| `navegar_ate_modulo(context, page_atual, usuario_str, senha_str, *, url_aghu=AGHU_URL) → (Page, FrameLocator)` | Abre **Impressora por Computador** e retorna `(page, janela_sistema)`, preservando a URL em retry |
| `processar_computadores(..., caminho_planilha, report_directory, url_aghu=AGHU_URL) → str` | Lê planilha internamente, processa linhas, preserva a URL em Clean States e gera `.xlsx` auditável; retorna caminho do arquivo |

---

## 15. Contratos entre RFCs

### 15.1 Contrato com RFC-002

| Evento | Origem | Interpretação no Maestro |
|---|---|---|
| `ValueError("Impressora não existe")` | Seleção de impressora no vínculo | Aciona Almoxarifado |
| `ValueError("Não existe no CUPS")` | Consulta ao CUPS no Almoxarifado | Marca fila como inexistente |
| Retorno silencioso de `cadastrar_nova_impressora` | Impressora já existia no AGHUX | Retoma tentativa de vínculo |
| Cadastro concluído | Almoxarifado | Abre aba limpa e reprocessa linha |

### 15.2 Contrato com RFC-003

A UI deve fornecer:

| Item | Origem |
|---|---|
| `BrowserContext` | Criado pela UI com `ignore_https_errors=True` |
| `Page` | Criada pela UI e apontada para `url_aghu` |
| `url_aghu` | URL resolvida a partir do seletor de ambiente da UI |
| Credenciais | Campos da interface |
| `caminho_planilha` | Caminho do arquivo `.xlsx` fornecido pelo operador |
| `report_directory` | Diretório de saída perguntado pela UI ao operador e passado explicitamente |

A UI deve passar o mesmo `url_aghu` para `fazer_login`, `navegar_ate_modulo` e `processar_computadores`, garantindo que qualquer Clean State permaneça no ambiente selecionado. `processar_computadores` retorna o caminho absoluto do `.xlsx` gerado, que a UI pode usar para exibir ou abrir o relatório diretamente.

---

## 16. Considerações Operacionais

1. `PrinterAGHU.py` não cria o browser principal; o chamador cria `Browser`, `BrowserContext` e `Page`.
2. O módulo cria novas abas no mesmo contexto apenas para Clean State.
3. A autenticação deve permanecer centralizada em `autenticador.py`.
4. O parâmetro `url_aghu` deve ser propagado por todo retry, retomada e Clean State para evitar troca acidental de ambiente.
5. O fluxo depende de textos visíveis do AGHUX como **Outros Módulos**, **Configuração**, **Impressão**, **Cadastros**, **Impressora por Computador**, **Pesquisar**, **Novo** e **Gravar**.
6. As mensagens de erro usadas como contrato (`Impressora não existe`, `Computador não encontrado`, `Não existe no CUPS`) não devem ser alteradas sem atualizar as RFCs e os tratadores.
7. O uso de `press_sequentially` é intencional para disparar eventos JSF/autocomplete.
8. O seletor `TABELA_COMPUTADOR_IMPRESSORA_SELECTOR` e os índices de coluna usados em `_coletar_linhas_computador` dependem da estrutura HTML atual do AGHUX; mudanças na tabela exigem ajuste coordenado.

---

## 17. Limitações Conhecidas

| Limitação | Impacto |
|---|---|
| Seletores dependem de textos do AGHUX | Mudanças de nomenclatura no sistema podem quebrar navegação |
| Erros de negócio dependem de strings exatas | Alterações nas mensagens exigem atualização coordenada |
| Relatório `.xlsx` é gerado mesmo se todas as linhas falharem | A auditoria fica preservada, mas o operador deve validar os status |
| Pontos cegos restantes a mapear | Existem cenários não cobertos que devem ser mapeados e tratados em revisão futura |

---

## 18. Estado Atual da RFC

Esta RFC reflete o código atual de `PrinterAGHU.py` conforme a release de 2026-08-04, incluindo:

- Dependência explícita de `autenticador.py`, login centralizado e uso de `AGHU_URL` como default com `url_aghu` propagado em runtime.
- Clean State com fechamento de **todas** as abas do contexto, loop de autenticação com até `MAX_TENTATIVAS_AUTENTICAR_NOVA_ABA` tentativas e `RuntimeError` próprio ao esgotar.
- Leitura de planilha via `openpyxl` apenas (`.xlsx`), com resolução de aliases via `ALIASES_COLUNAS_PLANILHA` e `normalize_column_name`; retorna `list[Row]`.
- `_coletar_linhas_computador` integra espera de estado e extração de registros (substituindo `_aguardar_estado_resultado_pesquisa` como função independente); recebe `timeout_ms: int = 7000`.
- Constantes e dataclasses documentadas: `SUPPORTED_EXTENSIONS`, `COLUNAS_OBRIGATORIAS_PLANILHA`, `COLUNAS_RELATORIO`, `ALIASES_COLUNAS_PLANILHA`, `MAX_TENTATIVAS_*`, `XLSX_*`, `DadosLinhaPlanilha`, `ResultadoLinha`, `AcaoVinculo`, `FalhaTecnicaProcessamento`.
- `processar_computadores` recebe `caminho_planilha: str` (lê internamente) e `report_directory` obrigatório.
- Relatório `.xlsx` com `freeze_panes`, `auto_filter` e `autofit`; nome `Resultado_{DD_MM_YY_HHhMMmSS}.xlsx`; sem linha de auditoria `"Atualizado por: <usuario>"` e sem `pandas`.
- Quatro casos de decisão (`mantido`, `conferir`, `alterar`, `incluir`) documentados individualmente.
- Validação de computador selecionado no autocomplete.
- Tratamento diferenciado de resultados de gravação (sucesso, erro, indefinido) com mensagem específica para erro de classe PDF duplicada.
- Tratamento e registro correto de linhas com campos obrigatórios vazios.
- Limitações atualizadas com base no código corrente.
