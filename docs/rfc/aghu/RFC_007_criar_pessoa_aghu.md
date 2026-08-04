# RFC-007 — Cadastro de Pessoa no AGHUX (criar_pessoa_aghu / ui_criar_pessoa_aghu)

- **Status:** Estável
- **Autor:** Ruan
- **Data:** 2026-07
- **Atualizado em:** 2026-08-04
- **Arquivos:** `criar_pessoa_aghu.py` (núcleo), `ui_criar_pessoa_aghu.py` (interface)
- **Depende de:** `autenticador.py` (RFC-005)
- **Depende de:** `menu.py` (RFC-004)
- **Chamado por:** operador via `ui_criar_pessoa_aghu.py`

---

## Mudanças incorporadas nesta revisão

| Data | Mudança | Justificativa |
|---|---|---|
| 2026-08-04 | Expansão de `__all__` em `criar_pessoa_aghu.py` para incluir todas as constantes de status publicadas. | Conformidade com §11.1 e regra de exportação da API pública do módulo. |
| 2026-08-04 | Correção do default do atributo `orgao_emissor` em `CadastroPessoaEntrada` (§5.2). | O valor padrão real é `ORGAO_EMISSOR_PADRAO` ("SSP - Secretaria de Segurança Pública"), e não `""`. |
| 2026-08-04 | Documentação de `_atualizar_visual_sexo` na seção "Limitações Conhecidas". | Identificação de método morto na UI `ui_criar_pessoa_aghu.py`. |
| 2026-08-04 | Inclusão da coluna "Assinatura" em todas as tabelas de mapeamento de funções. | Padronização dos tipos e assinaturas dos métodos expostos e utilitários. |
| 2026-08-04 | Adição da seção "Contratos entre RFCs" com subseções para RFC-004 e RFC-005. | Formalização do contrato de dependências transversais do módulo. |
| 2026-08-04 | Adição da seção "Considerações Operacionais". | Orientação operacional sobre execução de lotes, timeouts e tolerância a falhas. |
| 2026-08-04 | Remoção das seções duplicadas 14 e 15 e reorganização do encerramento do documento. | Eliminação de redundâncias após o fechamento da RFC ("Estado Atual da RFC"). |

---

## 1. Resumo

`criar_pessoa_aghu.py` automatiza o cadastro de **Pessoa Física** no módulo **Colaborador → Administrar Servidores → Pessoas** do AGHUX. Diferente da família de impressoras (RFC-001/002/003), não existe um Robô Especialista separado: o mesmo módulo pesquisa a pessoa pelo CPF, decide se cria ou mantém o cadastro, preenche o formulário e grava, tudo dentro de uma única classe `PessoaFlow`.

O módulo aceita dois modos de entrada equivalentes:

| Modo | Entrada | Função pública | Assinatura |
|---|---|---|---|
| Lote | Planilha `.xlsx` | `executar_cadastro_lote` | `(usuario_rede: str, senha: str, caminho_planilha: str \| Path, caminho_relatorio: str \| Path, ...) -> tuple[list[ResultadoCadastroPessoa], Path]` |
| Unitário/Manual | Lista de `CadastroPessoaEntrada` em memória | `executar_cadastro_pessoas` / `executar_cadastro_individual` | `(cadastros: list[CadastroPessoaEntrada], usuario_rede: str, senha: str, ...) -> list[ResultadoCadastroPessoa]` / `(usuario_rede: str, senha: str, cadastro: CadastroPessoaEntrada, ...) -> ResultadoCadastroPessoa` |

`ui_criar_pessoa_aghu.py` é a camada `customtkinter` que coleta credenciais, ambiente, até 5 pessoas digitadas manualmente ou uma planilha de lote, executa o núcleo em uma thread e devolve um resumo por severidade.

Este documento fecha o débito apontado no `Guia_AGHU.md` (seção 7, "Toda função pública usada por outro módulo deve constar na seção API Pública da RFC correspondente"): o módulo está em produção desde 2026-06 sem RFC própria.

---

## 2. Motivação

O cadastro de pessoa é pré-requisito para outras automações do AGHUX que dependem de a pessoa já existir no sistema (ex.: `criar_usuario_aghu.py`). Diferente do fluxo de impressoras, aqui não há uma tela "catálogo" separada da tela "vínculo" — pesquisar, criar e gravar acontecem na mesma tela do AGHUX, então não há necessidade de um segundo robô especialista nem de um contrato de exceções entre módulos como `ValueError("Impressora não existe")`.

A principal complexidade do módulo não é de navegação, e sim de **dados**: mapear colunas de planilha com nomes variáveis para os campos do formulário, normalizar CPF/data/nacionalidade/naturalidade, e decidir entre 5 status de resultado (não apenas sucesso/erro) para permitir que o operador saiba quando precisa conferir manualmente no AGHUX.

---

## 3. Arquitetura e Fluxo de Dados

```text
[ui_criar_pessoa_aghu.py / Operador]
        │
        ├─► Modo Unitário: até 5 linhas de CadastroPessoaEntrada (formulário)
        └─► Modo Lote: planilha .xlsx
                │
                └─► executar_cadastro_lote / executar_cadastro_pessoas
                        │
                        ├─ Pré-validação de TODAS as linhas (sem abrir Playwright)
                        │     └─ Linha inválida → status "ignorado" direto
                        │
                        ├─ Se nenhuma linha for válida → retorna sem abrir browser
                        │
                        └─ Abre Chromium, login, navega até Cadastro de Pessoa
                                │
                                └─► processar_cadastros (loop por linha)
                                        │
                                        ├─ garantir_tela_pesquisa_pessoa(...)
                                        │
                                        └─► processar_cadastro → PessoaFlow.processar(entrada)
                                                ├─ pesquisar_por_cpf
                                                │     ├─ "encontrado"     → status MANTIDO
                                                │     ├─ "nao_encontrado" → clica Novo, preenche, grava
                                                │     └─ "indefinido"     → status CONFERIR_MANUAL
                                                │
                                                └─ Gravação
                                                      ├─ mensagem de sucesso → status CRIADO
                                                      ├─ mensagem de erro    → status ERRO
                                                      └─ sem mensagem a tempo→ status CONFERIR_MANUAL
                                │
                                ├─ Falha técnica na 1ª tentativa → Clean State + renavega + repete a linha
                                └─ Falha técnica na 2ª tentativa → status ERRO, segue para a próxima linha
                        │
                        └─ Gera relatório .xlsx (lote) e log .csv (todas as execuções)
```

---

## 4. Dependências

### 4.1 `autenticador.py`

```python
from autenticador import AGHU_URL, autenticar_aghu_page, exigir_login_valido
```

`fazer_login` (núcleo) é um wrapper fino sobre `autenticar_aghu_page` + `exigir_login_valido`, no mesmo padrão de RFC-001/002. O módulo não mantém seletores próprios de tela de login.

### 4.2 `menu.py`

```python
from menu import navegar_menu_aghu
```

Caminho declarado localmente, seguindo o contrato da RFC-004:

```python
CAMINHO_MENU_CADASTRO_PESSOA = (
    "Outros Módulos",
    "Colaborador",
    "Administrar Servidores",
    "Pessoas",
)
```

A validação da tela final é responsabilidade deste módulo, feita por `PessoaFlow.validar_tela_pesquisa` (aguarda o campo de CPF e o botão **Pesquisar**).

### 4.3 `ui_criar_pessoa_aghu.py` → núcleo

A UI importa apenas funções e constantes públicas do núcleo — não reimplementa seletores nem regras de negócio:

```python
from criar_pessoa_aghu import (
    CadastroPessoaEntrada,
    CAMPOS_PESSOA_UI,
    STATUS_CONFERIR_MANUAL,
    STATUS_CRIADO,
    STATUS_ERRO,
    STATUS_IGNORADO,
    STATUS_MANTIDO,
    executar_cadastro_individual,
    executar_cadastro_pessoas,
    executar_cadastro_lote,
)
from autenticador import AGHU_URL, AGHU_URL_HOMOLOGACAO
```

`CAMPOS_PESSOA_UI` é o contrato explícito entre núcleo e UI: o núcleo declara `(nome, label, placeholder, tipo_ui)` para cada campo e a UI gera os widgets dinamicamente a partir dessa tupla, em vez de hardcodar campos duas vezes.

---

## 5. Modelo de Dados

### 5.1 `CampoPessoaSpec` e `CAMPOS_PESSOA_SCHEMA`

Cada campo do formulário é declarado uma única vez como `CampoPessoaSpec(nome, label_ui, placeholder_ui, aliases_planilha, obrigatorio, tipo_ui)`. Dessa declaração derivam três estruturas usadas em pontos diferentes do sistema:

| Derivado | Uso |
|---|---|
| `ALIASES_COLUNAS` | Mapeia `nome` → aliases aceitos na planilha (leitura tolerante a variações de coluna) |
| `CAMPOS_PESSOA_OBRIGATORIOS` | Lista de campos que `validar_entrada` cobra |
| `CAMPOS_PESSOA_UI` | Tupla `(nome, label, placeholder, tipo_ui)` consumida pela UI para montar os campos |

Campos obrigatórios atuais: `nome_pessoa`, `nome_mae`, `data_nascimento`, `naturalidade`, `rg`, `uf_rg`, `cpf`. `sexo`, `nacionalidade`, `ddd`, `telefone_celular` e os campos de endereço são opcionais.

`orgao_emissor` **não é um campo de planilha/UI**: é sempre sobrescrito por `ORGAO_EMISSOR_PADRAO = "SSP - Secretaria de Segurança Pública"` dentro de `normalizar_entrada`, independentemente do que vier na entrada.

### 5.2 `CadastroPessoaEntrada` / `ResultadoCadastroPessoa`

`CadastroPessoaEntrada` é o dataclass de entrada (todos os campos como `str`, com default `""`, exceto `orgao_emissor` que possui default `ORGAO_EMISSOR_PADRAO` = `"SSP - Secretaria de Segurança Pública"`). `ResultadoCadastroPessoa` é a saída por linha: `cpf`, `nome_pessoa`, `status`, `detalhes`, `pessoa` (resumo textual do `FluxoResultado` interno).

### 5.3 `StatusCadastro`

| Status | Quando ocorre |
|---|---|
| `criado` | CPF não encontrado, formulário preenchido e gravado com mensagem de sucesso |
| `mantido` | CPF já encontrado na pesquisa; nenhuma alteração é feita |
| `erro` | Mensagem de erro na gravação, ou falha técnica que sobreviveu às 2 tentativas |
| `ignorado` | Falhou na pré-validação (campo obrigatório vazio, CPF com menos de 11 dígitos, data inválida) — a linha nunca chega a abrir o navegador |
| `conferir_manual` | Pesquisa ou gravação não retornou um estado conclusivo dentro do timeout |

Este é o contrato mais importante do módulo: ao contrário da família de impressoras, aqui não há exceções cruzando módulos — o estado inconclusivo vira dado (`conferir_manual`), não exceção, permitindo que o lote inteiro continue mesmo quando uma linha específica fica ambígua.

---

## 6. Normalização e Validação

Todas as funções abaixo são independentes de Playwright e cobertas por `test_unit_criar_pessoa_aghu.py`.

| Função | Assinatura | Regra |
|---|---|---|
| `apenas_digitos` | `(valor: object) -> str` | Remove tudo que não é dígito (usado em CPF, CEP, DDD) |
| `normalizar_data_nascimento` | `(valor: object) -> str` | Aceita `datetime`/`date`, ou texto em 6 formatos (`%d/%m/%Y`, `%d-%m-%Y`, `%Y-%m-%d`, `%Y/%m/%d`, `%d/%m/%y`, `%d-%m-%y`); como último recurso, tenta interpretar dígitos puros (`ddmmaaaa`, completando com `0` à esquerda se vier com 7 dígitos) |
| `_data_nascimento_valida` | `(valor: str) -> bool` | Confirma que a data existe de fato (protege contra `31/02/2020`, por exemplo) comparando o round-trip `strptime`→`strftime` |
| `normalizar_nacionalidade` | `(valor: object) -> str` | Qualquer variação começando com "bra" (sem acento, case-insensitive) vira `"Brasileiro"` |
| `normalizar_naturalidade` | `(valor: object) -> str` | Aplica um dicionário de aliases (`ALIASES_NATURALIDADE_AGHU`) — hoje cobre apenas variações de "Brasília/DF"; outros textos passam sem alteração |
| `cpf_confere` | `(valor_atual: object, cpf_esperado: str) -> bool` | Compara dois CPFs por sufixo de dígitos (`endswith`), não por igualdade exata — tolera diferenças de máscara |
| `validar_entrada` | `(entrada: CadastroPessoaEntrada) -> list[str]` | Verifica campos obrigatórios em branco, CPF com 11 dígitos e data válida; retorna lista de mensagens (não lança exceção) |

`normalizar_entrada` é chamada em todo ponto de entrada de dados (leitura de planilha, coleta da UI, resultado de erro) e é **idempotente** — pode ser chamada mais de uma vez sobre o mesmo dado sem efeito colateral.

---

## 7. Leitura de Planilha e Pré-validação

`ler_planilha_cadastros(caminho)`:

1. Exige `.xlsx` existente (`FileNotFoundError` / `ValueError` caso contrário).
2. Lê com `pandas.read_excel(dtype=str, engine="openpyxl")`, todas as colunas como texto.
3. Confere que ao menos um alias de cada campo obrigatório está presente nas colunas; se faltar, lança `ValueError` listando as colunas ausentes pelo **primeiro alias** de cada campo.
4. Cada linha vira um `CadastroPessoaEntrada` já normalizado.

A pré-validação acontece **antes** de abrir o Playwright, tanto em `executar_cadastro_pessoas` quanto em `processar_cadastros` (que aceita `resultados_prevalidacao` pré-computado para não validar duas vezes). Se **nenhuma** linha passar na validação, o navegador nunca é aberto — comportamento coberto por `test_lote_totalmente_invalido_retorna_ignorados_sem_playwright`.

---

## 8. Componentes de Interação com o AGHUX

### 8.1 Utilitários genéricos (reaproveitáveis fora de Pessoa)

| Função | Assinatura | Papel |
|---|---|---|
| `primeiro_visivel` | `(janela_sistema: FrameLocator, seletores: tuple[str, ...], timeout_ms: int = 5000) -> Locator` | Tenta uma lista de seletores em ordem e retorna o primeiro visível |
| `clicar_botao` | `(janela_sistema: FrameLocator, nome: str, timeout_ms: int = 10000) -> None` | Clica em botão por `role`/`name`, com espera de visibilidade |
| `widget_carregamento` / `existe_carregamento_visivel` | `(janela_sistema: FrameLocator) -> Locator / bool` | Detecta o overlay `Carregando... Aguarde...` do AGHUX |
| `aguardar_ciclo_carregamento` | `(janela_sistema: FrameLocator, *, timeout_ms: int = TEMPO_MAXIMO_CONSULTA_MS, deteccao_ms: int = TEMPO_DETECCAO_WIDGET_CARREGAMENTO_MS) -> bool` | Espera o overlay aparecer (até `deteccao_ms`) e depois sumir (até `timeout_ms`); se o overlay nunca aparecer, assume que o ciclo já terminou |
| `preencher_input` | `(locator: Locator, valor: str, timeout_ms: int = 5000) -> None` | Clica, limpa (`fill("")`) e preenche um campo de texto simples |
| `selecionar_autocomplete` | `(janela_sistema: FrameLocator, seletor_input: str, valor: str, *, texto_esperado: str \| None = None, timeout_ms: int = 7000) -> None` | Digita com `press_sequentially(delay=150)` e clica na primeira opção visível dentre 4 candidatos de seletor, com fallback para `Enter` |
| `selecionar_selectonemenu` | `(janela_sistema: FrameLocator, texto: str, *, indice_trigger: int = 0, panel_selector: str \| None = None, timeout_ms: int = 7000) -> None` | Abre um `div.ui-selectonemenu-trigger` pelo índice e seleciona o item por texto exato |
| `mensagens_sistema` | `(janela_sistema: FrameLocator) -> list[str]` | Lê os textos visíveis de `#messagesInDialog` (info/erro/warning) |
| `aguardar_mensagem_gravacao` | `(janela_sistema: FrameLocator, *, sucessos: tuple[str, ...], erros_negocio: tuple[str, ...] = (), timeout_ms: int = 15000) -> tuple[str, str]` | Faz polling de `mensagens_sistema` até casar com uma mensagem de sucesso, de erro de negócio, ou com os textos genéricos `"campo obrigatorio"` / `"invalido"` / `"erro"` |

### 8.2 Máquina de estados de pesquisa: `_aguardar_resultado_pesquisa`

Esta é a parte mais delicada do módulo. Depois de clicar **Pesquisar**, o AGHUX pode demorar para trocar o conteúdo da tabela, e um estado "vazio" pode aparecer momentaneamente antes do resultado real. Para evitar falso-negativo (concluir "não encontrado" enquanto a tabela ainda está trocando), a função:

1. Monitora o overlay de carregamento; enquanto ele está visível, nenhum estado é confirmado.
2. Quando encontra a linha do CPF pesquisado (`_linha_por_cpf`, que compara a 5ª coluna via `cpf_confere`), retorna `"encontrado"` **imediatamente** — sem esperar estabilidade.
3. Para os estados `"nao_encontrado"` (mensagem `Nenhum registro encontrado!` ou classe `ui-datatable-empty-message`) e `"sem_cpf_exato"` (tabela com linhas, mas nenhuma bate o CPF), exige que o mesmo estado se repita por `TEMPO_ESTABILIDADE_RESULTADO_MS` (250 ms) **e** que a consulta já tenha passado por um ciclo de carregamento observado (`pode_confirmar_resultado`), antes de aceitar o estado como definitivo.
4. Se o timeout (`TEMPO_MAXIMO_CONSULTA_MS`, 90s) estourar sem confirmação, retorna `"indefinido"`.

Essa janela de estabilidade é o motivo do status `conferir_manual` existir: em vez de arriscar um falso "não encontrado" (que criaria uma pessoa duplicada) ou travar indefinidamente, o módulo prefere devolver a linha para conferência humana.

### 8.3 Classe `PessoaFlow`

Encapsula toda a interação da tela de Pessoa, recebendo o `FrameLocator` no construtor (mesmo padrão de "janela do sistema" usado nos módulos de impressora).

| Método | Assinatura | Responsabilidade |
|---|---|---|
| `validar_tela_pesquisa` | `() -> None` | Confirms campo de CPF e botão **Pesquisar** visíveis — é o critério de "tela carregada" usado por todo o resto do fluxo |
| `pesquisar_por_cpf` | `(cpf: str) -> tuple[str, Locator \| None]` | Preenche CPF, clica Pesquisar, aguarda ciclo de carregamento e delega à máquina de estados |
| `processar` | `(entrada: CadastroPessoaEntrada) -> FluxoResultado` | Orquestra pesquisa → decisão (mantido/criar/conferir) → preenchimento → gravação → retorno à pesquisa |
| `_preencher_formulario` | `(entrada: CadastroPessoaEntrada) -> None` | Preenche/seleciona todos os campos do schema; campos opcionais só são tocados se vierem preenchidos na entrada |
| `_gravar_pessoa` | `() -> tuple[str, str]` | Clica **Gravar** e aguarda mensagem de sucesso ou erro |
| `_retornar_para_pesquisa` | `() -> None` | Até 3 tentativas de clicar **Voltar** até a tela de pesquisa reaparecer |
| `_normalizar_sexo` | `(valor: str) -> str` | Mapeia `m*`/`f*` (case-insensitive) para `Masculino`/`Feminino`; qualquer outro valor vira `Ignorado` |
| `fechar_painel_sucesso_se_visivel` | `() -> None` | Fecha o diálogo de confirmação pós-gravação, se existir; usado só pelo Maestro após `STATUS_CRIADO` |

#### 8.3.1 Seletores de campo (`SELECTOR_*`)

Todos os campos usam seletores por atributo (`id`/`name` exatos), sem depender de texto visível — mais estáveis que os fallbacks JSF genéricos usados pela família de impressoras:

```text
input[name="cpf:cpf:inputId"]                 → CPF de pesquisa e de cadastro (mesmo seletor)
[id="nomePessoa:nomePessoa:inputId"]           → Nome da Pessoa
input[name="nomeMae:nomeMae:inputId"]          → Nome da Mãe
[id="dataNascimento:dataNascimento:inputId_input"] → Data de Nascimento
[id="suggestionNacionalidade:...suggestion_input"] → Nacionalidade (autocomplete)
[id="naturalidade:naturalidade:suggestion_input"]  → Naturalidade (autocomplete)
input[name="rg:rg:inputId"]                    → RG
[id="orgao:orgao:suggestion_input"]            → Órgão emissor (autocomplete, sempre ORGAO_EMISSOR_PADRAO)
[id="ufRgPessoa:ufRgPessoa:suggestion_input"]  → UF do RG (autocomplete)
[id="dddCelular:dddCelular:inputId_input"]     → DDD
[id="telefoneCelular:telefoneCelular:inputId_input"] → Telefone celular
[id="suggestionCepCadastrado:...suggestion_input"]   → CEP já cadastrado (autocomplete)
[id="logradouroNaoCadastrado:...inputId"]      → Logradouro (endereço não cadastrado)
[id="bairroNaoCadastrado:...inputId"]          → Bairro (endereço não cadastrado)
[id="cepNaoCadastrado:...inputId_input"]       → CEP (endereço não cadastrado)
[id="suggestionCidadeNaoCadastrada:...suggestion_input"] → Município (endereço não cadastrado)
```

A tabela de resultado da pesquisa usa `[id="tabelaPessoaFisica:resultList_data"] > tr`, e o CPF de cada linha é lido da 5ª célula (`td[4]`).

#### 8.3.2 Contrato de mensagens de gravação

```text
Sucesso: "Pessoa incluída com sucesso." | "Pessoa alterada com sucesso." | "Pessoa atualizada com sucesso."
```

Não há lista de `erros_negocio` própria — qualquer mensagem contendo `"campo obrigatorio"`, `"invalido"` ou `"erro"` (comparação sem remoção de acento, ver seção 12) já cai no ramo `"erro"` genérico de `aguardar_mensagem_gravacao`.

---

## 9. Orquestração (Maestro do módulo)

Não existe Robô Especialista separado; as funções abaixo cumprem o mesmo papel que o Maestro de impressoras, mas operando sozinhas.

| Função | Assinatura | Responsabilidade |
|---|---|---|
| `fazer_login` | `(page: Page, usuario_str: str, senha_str: str, *, timeout_ms: int = 15000) -> ResultadoLogin` | Wrapper de `autenticar_aghu_page` + `exigir_login_valido` |
| `trocar_aba_aghux` | `(context: BrowserContext, url_aghu: str, usuario_rede: str, senha: str, ...) -> tuple[Page, FrameLocator]` | Clean State: fecha a aba atual, abre nova aba no mesmo `BrowserContext`, acessa `url_aghu` e refaz login |
| `navegar_ate_cadastro_pessoa` | `(page: Page, context: BrowserContext, url_aghu: str, usuario_rede: str, senha: str) -> tuple[Page, FrameLocator]` | Navega via `navegar_menu_aghu`; 1 retry com Clean State completo em caso de falha |
| `garantir_tela_pesquisa_pessoa` | `(page: Page, context: BrowserContext, url_aghu: str, usuario_rede: str, senha: str, ...) -> tuple[Page, FrameLocator]` | Antes de processar uma linha, confirma que a tela atual já é a de pesquisa; se não for, tenta renavegar pelo menu e, falhando, aciona Clean State completo |
| `processar_cadastro` | `(janela_sistema: FrameLocator, entrada: CadastroPessoaEntrada) -> ResultadoCadastroPessoa` | Roda `PessoaFlow.processar` para uma entrada e converte `FluxoResultado` em `ResultadoCadastroPessoa` |
| `processar_cadastros` | `(page: Page, context: BrowserContext, cadastros: list[CadastroPessoaEntrada], ...) -> list[ResultadoCadastroPessoa]` | Loop principal: pula linhas pré-invalidadas, chama `garantir_tela_pesquisa_pessoa` + `processar_cadastro` por linha, com até 2 tentativas e Clean State entre elas |
| `executar_cadastro_pessoas` | `(cadastros: list[CadastroPessoaEntrada], usuario_rede: str, senha: str, ...) -> list[ResultadoCadastroPessoa]` | Ponto de entrada em memória: valida credenciais/URL, abre Playwright, delega a `processar_cadastros`, grava CSV de auditoria |
| `executar_cadastro_lote` | `(usuario_rede: str, senha: str, caminho_planilha: str \| Path, ...) -> tuple[list[ResultadoCadastroPessoa], Path]` | Lê planilha → `executar_cadastro_pessoas` → salva relatório `.xlsx` |
| `executar_cadastro_individual` | `(usuario_rede: str, senha: str, cadastro: CadastroPessoaEntrada, ...) -> ResultadoCadastroPessoa` | Atalho de `executar_cadastro_pessoas` para uma única entrada, retornando o primeiro resultado |

### 9.1 Recuperação de estado (Clean State)

```text
Falha técnica na linha N (tentativa 1/2)
        │
        ├─► trocar_aba_aghux(url_aghu preservado)
        ├─► navegar_ate_cadastro_pessoa(url_aghu preservado)
        └─► repete a MESMA linha (tentativa 2/2)
                │
                └─► Falha de novo → STATUS_ERRO com a mensagem da exceção; segue para a linha N+1
```

`url_aghu` é propagado em toda a cadeia (login, Clean State, navegação, retry), no mesmo padrão do Guia (`docs/guias/Guia_AGHU.md`, seção 1) — confirmado por `test_processar_cadastros_preserva_url_aghu_no_retry`.

Diferença relevante em relação a RFC-001: aqui o retry é **por linha dentro do próprio processar_cadastros**, não delegado a um módulo externo, porque não há um segundo sistema (CUPS) a consultar.

### 9.2 Saída e Auditoria

| Saída | Gerada por | Assinatura | Conteúdo |
|---|---|---|---|
| Relatório `.xlsx` | `salvar_relatorio_resultados` (só no modo lote) | `(resultados: list[ResultadoCadastroPessoa], caminho_saida: str \| Path) -> Path` | Colunas CPF/Nome/Status/Detalhes/Pessoa, cabeçalho congelado e autofiltro |
| Log `.csv` | `gerar_csv_logs` (toda execução, unitária ou lote) | `(resultados: list[ResultadoCadastroPessoa], usuario_rede: str, diretorio_logs: str \| Path \| None) -> str` | Primeira linha `Atualizado por: <usuario_rede>`, depois os mesmos dados do relatório, em `logs/log_cadastro_pessoas_<timestamp>.csv` |

---

## 10. Interface Gráfica (`ui_criar_pessoa_aghu.py`)

### 10.1 Estrutura da janela

| Elemento | Detalhe |
|---|---|
| Título | `AGHUX Bot - Cadastro de Pessoa` |
| Tamanho | `900x820`, redimensionável, `minsize(760, 650)` |
| Seções | Acesso (usuário/senha/ambiente), Tipo de Execução (`Unitária`/`Lote`), painel de execução correspondente, botão único **Executar cadastro** |

### 10.2 Modo Unitário

Até `MAX_PESSOAS_MANUAIS = 5` pessoas digitadas na mesma execução. `adicionar_linha_pessoa` gera dinamicamente os campos a partir de `CAMPOS_PESSOA_UI`, divididos em duas colunas (`CAMPOS_PESSOA_ESQUERDA` = 9 primeiros campos, `CAMPOS_PESSOA_DIREITA` = restantes). O campo `sexo` é o único que não vira `CTkEntry`: é renderizado como `CTkSegmentedButton` (`tipo_ui == "sexo"`).

`coletar_pessoas_individuais` ignora linhas totalmente em branco, exige que `sexo` esteja preenchido quando qualquer outro campo da linha estiver preenchido, e lança `ValueError` se nenhuma pessoa válida sobrar.

### 10.3 Modo Lote

Campos de planilha de entrada (`.xlsx`) e relatório de saída (`.xlsx`), cada um com `filedialog`. Se o relatório não for informado, é gerado automaticamente com `caminho_relatorio_padrao` (mesmo diretório da planilha de entrada, nome `relatorio_cadastro_pessoas_<timestamp>.xlsx`).

### 10.4 Ambiente e alerta de Produção

Mesma UX de RFC-003: `CTkOptionMenu` com `URLS_AMBIENTE_AGHU = {Produção: AGHU_URL, Homologação: AGHU_URL_HOMOLOGACAO}`. Diferença em relação à RFC-003: **aqui o padrão é `AMBIENTE_HOMOLOGACAO`**, não Produção — alinhado ao Guia (seção 5, "Homologação é o padrão operacional seguro"). Ao trocar para Produção, exibe `messagebox.showwarning` e mantém um painel de alerta persistente enquanto Produção estiver selecionado.

### 10.5 Regra anti-processo invisível

Idêntica à RFC-003: `_validar_opcoes_visibilidade` impede desmarcar **Exibir Navegador** e **Exibir Terminal** simultaneamente, reativando a opção alterada por último e emitindo aviso.

### 10.6 Execução e feedback

`iniciar_execucao` despacha para `iniciar_execucao_individual` ou `iniciar_execucao_lote`, cada uma validando o formulário na thread principal e delegando o trabalho pesado a uma `threading.Thread(daemon=True)` que chama as funções do núcleo (`executar_cadastro_individual`, `executar_cadastro_pessoas` ou `executar_cadastro_lote`) e agenda a atualização de UI via `self.after(0, ...)`.

`_resumir_resultados` conta ocorrências de cada `StatusCadastro` com `collections.Counter` e monta uma frase única com todos os totais. `_cor_resultado` decide a cor do texto de status por severidade:

| Condição | Cor |
|---|---|
| Há ao menos 1 `STATUS_ERRO` | vermelho |
| Sem erro, mas há `STATUS_IGNORADO` ou `STATUS_CONFERIR_MANUAL` | laranja |
| Só `criado`/`mantido` | verde |

Essa regra vale tanto para lote quanto para execução unitária com múltiplas pessoas **e** para uma única pessoa (unificado em `_cor_resultado` desde a release de 2026-07-09 — ver `docs/releases/sistemas/aghu/criar_pessoa/release_09_07_26_1729.md`).

---

## 11. Contratos entre RFCs

### 11.1 Contrato com RFC-004 (`menu.py`)

- **Caminho consumido:**
  ```python
  CAMINHO_MENU_CADASTRO_PESSOA = (
      "Outros Módulos",
      "Colaborador",
      "Administrar Servidores",
      "Pessoas",
  )
  ```
- **Assinatura da função externa:** `navegar_menu_aghu(page: Page, caminho: Sequence[str], timeout_menu_ms: int = 5000) -> FrameLocator`
- **Validação pós-navegação:** Responsabilidade de `criar_pessoa_aghu.py` via `PessoaFlow.validar_tela_pesquisa()`, que aguarda o seletor `SELECTOR_PESQUISA_CPF` (`input[name="cpf:cpf:inputId"]`) e o botão **Pesquisar**.

### 11.2 Contrato com RFC-005 (`autenticador.py`)

- **Funções importadas:** `AGHU_URL`, `autenticar_aghu_page`, `exigir_login_valido` (núcleo) e `AGHU_URL_HOMOLOGACAO` (UI).
- **Assinatura da função externa:** `autenticar_aghu_page(page: Page, usuario: str, senha: str, url_login: str = AGHU_URL, ...) -> ResultadoLogin`
- **Garantia de Sessão:** `fazer_login` em `criar_pessoa_aghu.py` autentica a página e executa `exigir_login_valido` para garantir que exceções de credenciais inválidas ou timeout de login sejam propagadas antes de tentar navegar.

---

## 12. Considerações Operacionais

1. **Pré-validação offline de planilhas:** Antes de inicializar a instância do Playwright, todas as linhas são validadas quanto à integridade de CPF (11 dígitos) e data de nascimento. Caso o lote inteiro seja inválido, o processo é abortado sem consumo de recursos do navegador.
2. **Ambiente padrão:** O ambiente padrão configurado na interface gráfica é **Homologação**. A alternância para **Produção** exige confirmação explícita no diálogo de aviso.
3. **Resiliência a latência (Máquina de Estados):** O polling de pesquisa de CPF aguarda o ciclo completo do overlay PrimeFaces e exige estabilidade de 250 ms no DOM antes de declarar "Não Encontrado", prevenindo duplo cadastro em AGHUX sob carga.
4. **Log de Auditoria:** Toda execução gera um arquivo CSV append-only no diretório `logs/` identificado com o usuário de rede e timestamp, garantindo rastreabilidade das operações realizadas.

---

## 13. API Pública do Módulo

### 13.1 `criar_pessoa_aghu.py`

| Função/Classe/Constante | Assinatura | Responsabilidade |
|---|---|---|
| `CadastroPessoaEntrada` | Dataclass `(nome_pessoa, nome_mae, sexo, data_nascimento, nacionalidade, naturalidade, rg, orgao_emissor, uf_rg, cpf, ddd, telefone_celular, cep_cadastrado, logradouro_nao_cadastrado, bairro_nao_cadastrado, cep_nao_cadastrado, municipio_nao_cadastrado)` | Dataclass de entrada de uma pessoa |
| `ResultadoCadastroPessoa` | Dataclass `(cpf, nome_pessoa, status, detalhes, pessoa)` | Dataclass de resultado por linha |
| `CAMPOS_PESSOA_UI` | `tuple[tuple[str, str, str, str], ...]` | Contrato de campos consumido pela UI |
| `ORGAO_EMISSOR_PADRAO` | `str` = `"SSP - Secretaria de Segurança Pública"` | Constante do órgão emissor fixo usado no cadastro |
| `STATUS_CRIADO`, `STATUS_MANTIDO`, `STATUS_ERRO`, `STATUS_IGNORADO`, `STATUS_CONFERIR_MANUAL` | `str` (`"criado"`, `"mantido"`, `"erro"`, `"ignorado"`, `"conferir_manual"`) | Constantes de status consumidas pela UI e em `__all__` |
| `ler_planilha_cadastros` | `(caminho_planilha: str \| Path) -> list[CadastroPessoaEntrada]` | Lê e valida planilha de lote |
| `salvar_relatorio_resultados` | `(resultados: list[ResultadoCadastroPessoa], caminho_saida: str \| Path) -> Path` | Gera relatório `.xlsx` formatado |
| `executar_cadastro_pessoas` | `(cadastros: list[CadastroPessoaEntrada], usuario_rede: str, senha: str, ...) -> list[ResultadoCadastroPessoa]` | Executa cadastro para uma lista de entradas em memória |
| `executar_cadastro_lote` | `(usuario_rede: str, senha: str, caminho_planilha: str \| Path, caminho_relatorio: str \| Path, ...) -> tuple[list[ResultadoCadastroPessoa], Path]` | Lê planilha, executa e salva relatório |
| `executar_cadastro_individual` | `(usuario_rede: str, senha: str, cadastro: CadastroPessoaEntrada, ...) -> ResultadoCadastroPessoa` | Executa uma única entrada e retorna o resultado direto |

Todas as 11 entidades acima estão exportadas no `__all__` do módulo `criar_pessoa_aghu.py`.

Funções internas de navegação/gravação (`fazer_login`, `trocar_aba_aghux`, `navegar_ate_cadastro_pessoa`, `garantir_tela_pesquisa_pessoa`, `processar_cadastro`, `processar_cadastros`, `PessoaFlow`) não estão em `__all__`, mas são importadas diretamente pela suíte de testes (`test_unit_criar_pessoa_aghu.py`, `test_regression_criar_pessoa_aghu.py`) via `import criar_pessoa_aghu as aghu`. Não possuem prefixo `_` porque são reaproveitáveis em teste/depuração isolada, mas não fazem parte do contrato estável para outros módulos de produção — apenas as entidades em `__all__` devem ser importadas por outros robôs.

### 13.2 `ui_criar_pessoa_aghu.py`

| Item | Assinatura | Responsabilidade |
|---|---|---|
| `AghuCadastroPessoaApp` | `ctk.CTk` class | Classe principal da janela `customtkinter` |
| `obter_url_ambiente_aghu` | `(ambiente: str) -> str` | Resolve o rótulo de ambiente para a URL efetiva |
| `caminho_relatorio_padrao` | `(base: str = "") -> str` | Gera nome de relatório padrão com timestamp |

A UI não expõe API para outros módulos; é ponto de entrada de execução (`if __name__ == "__main__"`).

---

## 14. Limitações Conhecidas

| Limitação | Impacto |
|---|---|
| `aguardar_mensagem_gravacao` compara `"campo obrigatorio"` / `"invalido"` sem remoção de acento, mas só faz `casefold()` | Se o AGHUX exibir a mensagem acentuada (`"Campo obrigatório"`, `"CEP inválido"`), o texto normalizado (`"campo obrigatório"`) não contém a substring sem acento (`"campo obrigatorio"`) e a checagem genérica de erro pode não disparar, deixando o status cair em `conferir_manual` por timeout em vez de `erro` imediato |
| Janela de estabilidade de 250 ms (`TEMPO_ESTABILIDADE_RESULTADO_MS`) na pesquisa por CPF | Em AGHUX sob alta latência, um resultado intermediário pode, em teoria, permanecer estável por 250 ms sem ser o resultado final; não há relato de ocorrência em produção até o momento |
| Código morto na UI (`_usar_formulario_individual_legado` e `_atualizar_visual_sexo`) | Em `ui_criar_pessoa_aghu.py`, o ramo legado `_usar_formulario_individual_legado` checa atributos nunca definidos em `__init__`, e o método `_atualizar_visual_sexo(self, sexo: str)` faz referência a `self.__dict__.get("segment_sexo")` que não é populado na versão atual — ambos representam código morto vestigial mantido por compatibilidade histórica |
| `normalizar_naturalidade` só resolve variações de "Brasília/DF" | Outras cidades com grafia divergente da esperada pelo autocomplete do AGHUX passam sem correção e podem falhar na seleção do autocomplete |
| `_data_nascimento_valida` aceita apenas datas de 8 dígitos após limpeza | Entradas ambíguas de 6 dígitos (ex.: `010190`) não são interpretadas; apenas o caso de 7 dígitos recebe `0` à esquerda |
| Cadastro depende de `id`/`name` gerados pelo JSF do AGHUX (`cpf:cpf:inputId`, `nomePessoa:nomePessoa:inputId`, etc.) | Mudança de versão do AGHUX que renomeie esses componentes quebra os seletores sem fallback textual |
| Retry de linha é local a `processar_cadastros`, não há retry entre linhas diferentes do lote | Uma falha técnica definitiva (`erro` após 2 tentativas) não impede o processamento das linhas seguintes, mas também não é re-enfileirada automaticamente |

---

## 15. Estado Atual da RFC

Esta RFC documenta o contrato atual de `criar_pessoa_aghu.py` e `ui_criar_pessoa_aghu.py`: cadastro de pessoa sem robô especialista separado, cinco status de resultado (`criado`, `mantido`, `erro`, `ignorado`, `conferir_manual`), pré-validação antes de abrir o Playwright, máquina de estados de pesquisa com janela de estabilidade, Clean State por linha preservando `url_aghu`, e UI com modos Unitário (até 5 pessoas) e Lote, ambos com resumo e cor de status por severidade. Fecha o débito de conformidade com `Guia_AGHU.md` (seção 7) para este módulo.
