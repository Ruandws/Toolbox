# RFC-009 — Cadastro de Profissionais da Unidade Cirúrgica (profissionais_unidade_cirurgica_aghu)

- **Status:** Estável
- **Autor:** Ruan
- **Data:** 2026-07 (primeira versão funcional em 02/07/2026)
- **Atualizado em:** 2026-07-23
- **Arquivo:** `profissionais_unidade_cirurgica_aghu.py` (núcleo)
- **Arquivo:** `ui_profissionais_unidade_cirurgica.py` (interface gráfica)
- **Depende de:** `autenticador.py` (RFC-005)
- **Depende de:** `menu.py` (RFC-004)
- **Chamado por:** — (ponto de entrada próprio, sem chamador externo mapeado)

---

## 1. Resumo

`profissionais_unidade_cirurgica_aghu.py` automatiza a inclusão de profissionais (atualmente apenas a função **Médico residente**) nas Unidades Funcionais do módulo **Profissionais da Unidade Cirúrgica** do AGHUX (menu `Cirurgias / PDT`). Para cada par profissional/unidade, o robô pesquisa se já existe vínculo ativo, evita duplicidade e cria o vínculo quando necessário.

`ui_profissionais_unidade_cirurgica.py` é a interface gráfica (customtkinter) que coleta credenciais, ambiente, e os dados de entrada em dois modos — **Unitária** (até 5 profissionais × Unidades Funcionais marcadas em checkbox) e **Lote** (planilha `.xlsx`) — cria o Playwright/browser/context/page e delega o processamento ao núcleo.

Diferente de `PrinterAGHU.py` (RFC-001), este módulo não tem um "Robô Especialista" satélite: núcleo e UI cobrem toda a funcionalidade, e por isso são documentados juntos nesta RFC.

---

## 2. Mudanças incorporadas nesta revisão

Esta revisão documenta a escrita retroativa e as revisões funcionais da RFC para refletir o estado atual do código:

| Área | Situação atual |
|---|---|
| Autenticação | Centralizada em `autenticador.py` (RFC-005), usando `autenticar_aghu_page` e `exigir_login_valido` |
| Navegação | Uso de `navegar_menu_aghu` de `menu.py` (RFC-004) com o caminho `CAMINHO_MENU_CADASTRO_UNI_CIRURGICA` |
| Resiliência | Recuperação em 3 níveis antes de cada linha (`garantir_tela_pesquisa_profissional_unidade`) |
| Desempenho | Cache por execução de profissional ausente (`profissionais_nao_encontrados`), evitando reconsultar o mesmo nome inválido nas demais unidades |
| Pré-validação | Validação local (`validar_entrada`) de todos os registros antes de interagir com o AGHUX (registros inválidos viram `ignorado` sem tocar a rede) |
| Relatórios | Modo lote gera relatório `.xlsx` formatado e CSV de auditoria em `./logs` |

---

## 3. Motivação

O cadastro manual de profissional por unidade é repetitivo e sujeito a erro humano (unidade errada, duplicidade de vínculo, nome de profissional digitado de forma diferente do cadastro no AGHUX). O robô centraliza essa rotina, com:

- Normalização de nomes de unidade e texto (case/acentuação) para evitar falsos negativos na comparação com o AGHUX.
- Detecção de vínculo já existente e ativo, evitando duplicar cadastro.
- Detecção de profissional inexistente no AGHUX (autocomplete sem sugestão), tratado como resultado de negócio (`funcionario_nao_encontrado`) e não como erro técnico.
- Execução em lote via planilha, com relatório XLSX e log CSV auditável, no mesmo padrão dos demais robôs AGHUX.

---

## 4. Arquitetura e Fluxo de Dados

### 4.1 Núcleo

```text
[ui_profissionais_unidade_cirurgica.py]
        │
        ├─► Cria Playwright, Chromium, BrowserContext(ignore_https_errors=True), Page
        │
        └─► executar_cadastros_profissionais(cadastros, usuario, senha, context, page, url_aghu, ...)
               │  (ou executar_cadastro_lote, que le a planilha e chama a função acima)
               │
               ├─ Valida usuario/senha e url_aghu
               ├─ controle_saida_terminal(mostrar_console) — oculta console/stdout se solicitado
               ├─ Pré-valida TODOS os cadastros (validar_entrada) antes de tocar o AGHUX
               │
               ├─ Se nenhum cadastro for válido:
               │     └─► Gera apenas o CSV de auditoria (todos "ignorado") e retorna,
               │          sem login nem navegação
               │
               └─ Se houver ao menos um cadastro válido:
                     ├─ page.goto(url_aghu)
                     ├─ fazer_login(page, usuario, senha, url_aghu=url_aghu)
                     ├─ navegar_ate_cadastro_profissional_unidade(...)
                     │     └─ navegar_menu_aghu(caminho=CAMINHO_MENU_CADASTRO_UNI_CIRURGICA)
                     │
                     └─ processar_cadastros(...)
                            │
                            ├─ Para cada cadastro (já pré-validado):
                            │     ├─ [Se pré-validação falhou] → Status: Ignorado (nunca chega no AGHUX)
                            │     ├─ [Se profissional já confirmado ausente nesta execução]
                            │     │      → Status: Funcionario_nao_encontrado (sem nova tentativa)
                            │     └─ [Caso contrário]
                            │            ├─ garantir_tela_pesquisa_profissional_unidade(...)
                            │            │      (auto-recuperação em 3 níveis, ver §12)
                            │            └─ ProfissionalUnidadeCirurgicaFlow.processar(entrada)
                            │                   ├─ pesquisar() → estado do vínculo
                            │                   ├─ [vínculo ativo]    → Mantido
                            │                   ├─ [vínculo inativo]  → Conferir manual
                            │                   ├─ [indefinido]       → Conferir manual
                            │                   └─ [sem vínculo]      → Novo → preencher → Gravar
                            │                          ├─ [sucesso]   → Criado
                            │                          ├─ [indefinido]→ Conferir manual
                            │                          └─ [erro]      → Erro
                            │
                            └─ Gera CSV auditável em ./logs (ou diretorio_logs)
```

### 4.2 UI (adaptador)

```text
[Operador]
    │
    └─► AghuProfissionaisUnidadeCirurgicaApp (customtkinter)
          │
          ├─► Coleta: usuário, senha, ambiente, exibir navegador, exibir terminal
          ├─► Modo "Unitária": até 5 profissionais × Unidades Funcionais marcadas (checkbox)
          ├─► Modo "Lote": planilha .xlsx de entrada + caminho de relatório .xlsx
          │
          └─► Thread daemon → _executar_com_playwright(mostrar_browser, acao)
                  ├─ Cria Playwright, Chromium (headless=not mostrar_browser,
                  │    slow_mo=500 apenas se mostrar_browser=True)
                  ├─ Cria BrowserContext(ignore_https_errors=True) e Page
                  ├─ acao(context, page):
                  │     ├─ Unitária → executar_cadastros_profissionais(...)
                  │     └─ Lote     → executar_cadastro_lote(...) (gera XLSX + CSV)
                  ├─ Fecha browser em finally
                  └─ self.after(0, ...) devolve resultado para a thread principal do Tk
```

---

## 5. Dependências

### 5.1 `autenticador.py`

O núcleo importa:

```python
from autenticador import AGHU_URL, autenticar_aghu_page, exigir_login_valido
```

A UI importa:

```python
from autenticador import AGHU_URL, AGHU_URL_HOMOLOGACAO
```

Mesmo contrato das demais RFCs: nenhum seletor de login, mensagem de credencial inválida ou regra de sessão ativa é duplicado aqui.

### 5.2 `menu.py`

O núcleo importa:

```python
from menu import navegar_menu_aghu
```

Caminho declarado localmente:

```python
CAMINHO_MENU_CADASTRO_UNI_CIRURGICA = (
    "Cirurgias / PDT",
    "Cadastros",
    "Profissionais da Unidade Cirúrgica",
)
```

### 5.3 UI → Núcleo

A UI importa diretamente do núcleo:

```python
from profissionais_unidade_cirurgica_aghu import (
    CadastroProfissionalUnidadeEntrada,
    FUNCAO_MEDICO_RESIDENTE,
    LOGS_DIR,
    STATUS_CONFERIR_MANUAL,
    STATUS_CRIADO,
    STATUS_ERRO,
    STATUS_FUNCIONARIO_NAO_ENCONTRADO,
    STATUS_IGNORADO,
    STATUS_MANTIDO,
    UNIDADES_FUNCIONAIS,
    executar_cadastros_profissionais,
    executar_cadastro_lote,
    validar_entrada,
)
```

A UI não cria browser/context antes do núcleo estar pronto para recebê-los; ela é a única dona do ciclo de vida do Playwright, entregando `context` e `page` já autenticáveis (não autenticados) para as funções públicas do núcleo, no mesmo padrão do par RFC-001/RFC-003.

### 5.4 Importação tardia (evita ciclo)

`profissionais_unidade_cirurgica_aghu.py` é executável diretamente (`python profissionais_unidade_cirurgica_aghu.py`). Como a UI importa do núcleo, `main()` importa a UI **dentro da função**, e não no topo do arquivo, para evitar import circular:

```python
def main() -> None:
    from ui_profissionais_unidade_cirurgica import executar_interface
    executar_interface()
```

---

## 6. Constantes de Módulo (Núcleo)

| Constante | Valor / Descrição |
|---|---|
| `BASE_DIR` | `Path(__file__).resolve().parent` |
| `LOGS_DIR` | `BASE_DIR / "logs"` |
| `CAMINHO_MENU_CADASTRO_UNI_CIRURGICA` | Caminho de menu, ver §5.2 |
| `UNIDADES_FUNCIONAIS` | 5 unidades válidas: `CENTRO OBSTETRICO - PRE-PARTO`, `CENTRO CIRURGICO AMBULATORIAL`, `CENTRO DE ENDOSCOPIA`, `CENTRO DE HEMODINAMICA`, `CENTRO CIRURGICO CENTRAL` |
| `FUNCAO_MEDICO_RESIDENTE` | `"Médico residente"` |
| `FUNCOES_PROFISSIONAL` | `(FUNCAO_MEDICO_RESIDENTE,)` — **única função suportada atualmente** |
| `ALIASES_COLUNAS` | Mapa de nomes aceitos por coluna da planilha (ver §8) |
| `CAMPOS_OBRIGATORIOS_PLANILHA` | `("profissional", "unidade_funcional")` — `funcao` é opcional |
| `TEMPO_MAXIMO_CONSULTA_MS` | `90000` — timeout de espera do resultado da pesquisa |
| `TEMPO_DETECCAO_WIDGET_CARREGAMENTO_MS` | `2000` — tempo para detectar início do ciclo de loading JSF |
| `TEMPO_ESTABILIDADE_RESULTADO_MS` | `250` — debounce antes de confirmar um estado de resultado |

Principais seletores (todos por atributo, sem depender de texto de tela):

| Seletor | Uso |
|---|---|
| `SELECTOR_PESQUISA_NOME` | `input[name="nome:nome:inputId"]` — campo de busca por nome |
| `SELECTOR_BOTAO_LIMPAR_PESQUISA` | `[id="bt_limpar:button"]` |
| `SELECTOR_TABELA_PROFISSIONAIS` | `[id="tabelaProfissionaisAtuantes:resultList_data"] > tr` |
| `SELECTOR_UNIDADE_FUNCIONAL_CONTAINER` / `_INPUT` | Dropdown/autocomplete de Unidade Funcional |
| `SELECTOR_PROFISSIONAL_INPUT` / `_SUGGESTION_PANEL` | Autocomplete de Profissional |
| `SELECTOR_FUNCAO_PANEL` | Painel do `selectonemenu` de Função |
| `SELECTOR_MENSAGENS` | Mensagens de sucesso/erro/aviso do dialog modal |
| `SELECTOR_FECHAR_DIALOG_MENSAGEM` | Ícone de fechar do dialog de mensagens |

---

## 7. Modelo de Dados

```python
@dataclass(frozen=True)
class CadastroProfissionalUnidadeEntrada:
    profissional: str = ""
    unidade_funcional: str = ""
    funcao: str = FUNCAO_MEDICO_RESIDENTE

@dataclass(frozen=True)
class ResultadoCadastroProfissional:
    profissional: str
    unidade_funcional: str
    funcao: str
    status: StatusCadastro
    detalhes: str
```

`StatusCadastro` é um `Literal` com os seis status descritos no §11.

---

## 8. Normalização e Leitura de Planilha (Lote)

### 8.1 Normalização

| Função | Assinatura | Descrição |
|---|---|---|
| `_remover_acentos` / `normalizar_texto` | `(texto: str) → str` | `NFKD` + remoção de combining chars + `casefold()` + colapso de espaços — usada em toda comparação texto-a-texto |
| `_sem_codigo_unidade` | `(texto: str) → str` | Remove prefixo `"NN - "` de código de unidade, se presente |
| `unidade_confere` | `(u1: str, u2: str) → bool` | Compara duas unidades funcionais ignorando acentos, caixa e código numérico |
| `funcao_confere` | `(f1: str, f2: str) → bool` | Compara duas funções de profissional ignorando acentos e caixa |
| `profissional_confere` | `(p1: str, p2: str) → bool` | Compara dois nomes de profissional ignorando acentos e caixa |
| `normalizar_unidade_funcional` | `(unidade: str) → str` | Casa o valor recebido contra `UNIDADES_FUNCIONAIS` e devolve a forma canônica; se não casar com nenhuma, devolve o texto original (a validação subsequente rejeita) |
| `normalizar_funcao` | `(funcao: str) → str` | Idem para `FUNCOES_PROFISSIONAL`; texto vazio vira `FUNCAO_MEDICO_RESIDENTE` |
| `normalizar_entrada` | `(entrada: CadastroProfissionalUnidadeEntrada) → CadastroProfissionalUnidadeEntrada` | Aplica as normalizações acima em um `CadastroProfissionalUnidadeEntrada` completo |
| `validar_entrada` | `(entrada: CadastroProfissionalUnidadeEntrada) → list[str]` | Retorna lista de erros: profissional em branco, unidade em branco/inválida, função em branco/inválida |

### 8.2 `ler_planilha_cadastros(caminho_planilha)`

Aceita **somente `.xlsx`** (diferente de `PrinterAGHU.ler_planilha`, que também aceita `.xlsm` e `.csv`). Lê com `dtype=str` e `fillna("")`, remove espaços dos nomes de coluna, e resolve colunas por alias:

| Campo | Aliases aceitos |
|---|---|
| `profissional` | `Profissional`, `Nome`, `Nome Profissional`, `Nome do Profissional` |
| `unidade_funcional` | `Unidade Funcional`, `Unidade`, `Unidade Cirurgica`, `Unidade Cirúrgica` |
| `funcao` | `Função`, `Funcao` (opcional; ausência não é erro) |

Linhas totalmente em branco são ignoradas silenciosamente. Coluna `funcao` ausente ou vazia por linha usa `FUNCAO_MEDICO_RESIDENTE` como padrão. Falta de coluna obrigatória lança `ValueError` listando os aliases faltantes.

---

## 9. Helpers Genéricos de Interação com AGHUX

Funções de nível de módulo, reutilizáveis por qualquer fluxo dentro deste arquivo (não são específicas de "profissional"):

| Função | Assinatura | Papel |
|---|---|---|
| `primeiro_visivel` | `(janela, seletores, timeout_ms=3000)` | Tenta cada seletor da tupla em ordem, retorna o primeiro visível |
| `clicar_botao` | `(janela, nome, timeout_ms=5000)` | Clique por `get_by_role("button", name=nome)` |
| `widget_carregamento` / `existe_carregamento_visivel` | `(janela) → Locator / bool` | Localizam o indicador JSF `"Carregando" + "Aguarde..."` |
| `aguardar_ciclo_carregamento` | `(janela, timeout_ms=15000, deteccao_ms=2000) → bool` | Espera o indicador aparecer (até `deteccao_ms`) e depois sumir (até `timeout_ms`); se nunca aparecer, assume que não houve ciclo de AJAX e retorna imediatamente |
| `pode_confirmar_resultado` | `(estado_desde, consulta_concluida, estabilidade_resultado_ms=250) → bool` | Debounce: só confirma um estado de tela se ele persistiu por `estabilidade_resultado_ms` **e** o ciclo de carregamento já concluiu — evita ler DOM em atualização parcial |
| `linha_vazia_visivel` | `(linhas) → bool` | Detecta linha `"Nenhum registro encontrado!"` / classe `ui-datatable-empty-message` |
| `preencher_input` | `(locator, valor, timeout_ms=5000)` | Clica, limpa (`fill("")`) e preenche — padrão robusto para inputs JSF |
| `selecionar_autocomplete` | `(janela, seletor_input, valor, texto_esperado, seletor_painel_sem_registro=None, timeout_ms=10000)` | Autocomplete genérico com cadeia de candidatos (linha destacada → célula por texto → primeira linha → `Enter` como último recurso). Se `seletor_painel_sem_registro` for informado, monitora ativamente o painel `"Nenhum Registro"` e lança `AutocompleteSemRegistroError` antes de esgotar o timeout |
| `selecionar_unidade_funcional` | `(janela, unidade, timeout_ms=10000)` | Tenta abrir dropdown de container (`SELECTOR_UNIDADE_FUNCIONAL_CONTAINER`) e selecionar por texto exato; se o dropdown não abrir ou não achar candidato, cai para `selecionar_autocomplete` (digitação) como fallback |
| `selecionar_selectonemenu` | `(janela, texto, panel_selector=None, timeout_ms=5000)` | Clica no `.ui-selectonemenu-trigger` **(primeiro da tela — não escopado a um campo específico)** e seleciona item por texto exato, opcionalmente restrito a `panel_selector` |
| `clicar_voltar_se_visivel` | `(janela, timeout_ms=3000) → bool` | Clica em **Voltar** se visível, aguarda ciclo de loading; retorna `bool` de sucesso |
| `fechar_dialog_mensagem_se_visivel` | `(janela, timeout_ms=2000) → bool` | Fecha todos os dialogs de mensagem abertos |
| `mensagens_sistema` | `(janela) → list[str]` | Extrai textos visíveis de `SELECTOR_MENSAGENS` |
| `aguardar_mensagem_gravacao` | `(janela, timeout_ms=15000) → tuple[str, str]` | Ver contrato no §14 |

> `selecionar_selectonemenu` usa `.first` sem escopo — assume que só há um `selectonemenu` ativo na tela no momento da chamada (verdadeiro para o formulário atual, que só tem o campo Função). Uma segunda tela com múltiplos `selectonemenu` simultâneos quebraria essa função; ver Limitações (§18).

---

## 10. Regras de Processamento

### 10.1 `ProfissionalUnidadeCirurgicaFlow` — Núcleo do Fluxo

Classe que encapsula pesquisa, decisão e gravação para um `FrameLocator` (`janela_sistema`) já posicionado na tela **Profissionais da Unidade Cirúrgica**.

#### 10.1.1 `validar_tela_pesquisa()`

Aguarda `SELECTOR_PESQUISA_NOME` e o botão **Pesquisar** ficarem visíveis. É a validação de tela final exigida pelo guia (item 2), usada tanto após navegação quanto para checar se a tela ainda está íntegra antes de processar a próxima linha.

#### 10.1.2 `pesquisar(entrada) → (estado, linha)`

1. `validar_tela_pesquisa()`.
2. `_limpar_pesquisa()`: clica no botão limpar, aguarda ciclo de loading, reconfirma o campo de nome visível.
3. Preenche o campo de nome com `entrada.profissional` e clica **Pesquisar**.
4. `aguardar_ciclo_carregamento`.
5. `_aguardar_resultado_pesquisa(entrada, consulta_concluida=...)`.

#### 10.1.3 `_aguardar_resultado_pesquisa` — máquina de estados da pesquisa

Faz polling até `TEMPO_MAXIMO_CONSULTA_MS` (90s):

1. Em cada iteração, verifica `_estado_vinculo` — se encontrar uma linha cujo (unidade, função, profissional) confere exatamente com a entrada, retorna **imediatamente** (`"vinculo_existente"` ou `"vinculo_inativo"`, conforme a coluna Situação seja `"Ativo"` ou não), sem esperar debounce.
2. Caso não haja correspondência exata, classifica o estado corrente como `"nao_encontrado"` (linha vazia visível) ou `"sem_vinculo_exato"` (há linhas na tabela, mas nenhuma bate exatamente — nomes parecidos, por exemplo).
3. Esse estado só é confirmado (retornado) depois de `pode_confirmar_resultado` indicar estabilidade — evita decidir com base em uma tabela ainda em atualização pelo AJAX.
4. Sem confirmação dentro do timeout, retorna `("indefinido", None)`.

#### 10.1.4 `_estado_vinculo` — mapeamento de colunas da tabela

| Índice da célula | Campo |
|---|---|
| 1 | Unidade Funcional |
| 2 | Função |
| 5 | Profissional |
| 7 (se existir) | Situação |

Comparação usa `unidade_confere` / `funcao_confere` / `profissional_confere` (normalizados). Situação `"Ativo"` (normalizado) decide `vinculo_existente` vs. `vinculo_inativo`.

#### 10.1.5 `processar(entrada) → ResultadoCadastroProfissional`

```text
pesquisar(entrada) → estado
  "vinculo_existente"                 → Mantido
  "vinculo_inativo"                   → Conferir manual ("situação não ativa")
  "indefinido"                        → Conferir manual ("pesquisa sem estado conclusivo")
  outro estado inesperado (defensivo) → Conferir manual
  "nao_encontrado" / "sem_vinculo_exato":
      clicar "Novo" → aguardar ciclo
      _preencher_formulario(entrada)
        [AutocompleteSemRegistroError] → cancelar formulário → Funcionário não encontrado
      _gravar() → (status_gravacao, mensagem)
      _retornar_para_pesquisa()  (sempre executado, mesmo em erro)
        "sucesso"    → Criado
        "indefinido" → Conferir manual
        "erro"       → Erro
```

#### 10.1.6 `_preencher_formulario`

1. `selecionar_autocomplete` no campo Profissional, com `seletor_painel_sem_registro=SELECTOR_PROFISSIONAL_SUGGESTION_PANEL` — é aqui que `AutocompleteSemRegistroError` pode ser lançada.
2. `selecionar_unidade_funcional`.
3. `selecionar_selectonemenu` para Função, restrito a `SELECTOR_FUNCAO_PANEL`.

#### 10.1.7 `_gravar` e `aguardar_mensagem_gravacao`

Clica **Gravar**, aguarda ciclo de loading, e então `aguardar_mensagem_gravacao` faz polling (até 15s) das mensagens do dialog:

| Condição (texto normalizado) | Resultado |
|---|---|
| contém `"profissional na unidade cirurgica incluido com sucesso"` | `("sucesso", mensagem)` |
| contém `"campo obrigatorio"`, `"invalido"`, `"erro"` ou `"ja existe"` | `("erro", mensagem)` |
| nenhuma mensagem reconhecida dentro do timeout | `("indefinido", "A gravacao nao retornou mensagem dentro do tempo limite.")` |

#### 10.1.8 `_cancelar_formulario` e `_retornar_para_pesquisa`

- `_cancelar_formulario`: tenta clicar **Cancelar**; se falhar por qualquer motivo, cai para `clicar_voltar_se_visivel`.
- `_retornar_para_pesquisa`: fecha dialog de mensagem se aberto e tenta até 3 vezes `validar_tela_pesquisa()`; se falhar, tenta `clicar_voltar_se_visivel()` e repete. Se não houver botão **Voltar** disponível, desiste silenciosamente — a linha seguinte do lote é quem detecta e corrige o estado via `garantir_tela_pesquisa_profissional_unidade` (§12.3).

---

## 11. Estados de Resultado (`StatusCadastro`)

| Status | Quando ocorre |
|---|---|
| `criado` | Vínculo novo gravado com sucesso |
| `mantido` | Vínculo ativo já existia para profissional + unidade + função |
| `funcionario_nao_encontrado` | Autocomplete de Profissional retornou "Nenhum Registro"; ou o profissional já foi confirmado ausente nesta mesma execução (ver §12.4) |
| `conferir_manual` | Vínculo existe mas está inativo; pesquisa/gravação retornou estado indefinido (timeout); estado de pesquisa inesperado |
| `erro` | AGHUX retornou mensagem de erro na gravação (campo obrigatório/inválido/erro/já existe); ou falha técnica esgotou as 2 tentativas |
| `ignorado` | Linha reprovada na pré-validação local (`validar_entrada`) — **nunca chega a tocar o AGHUX** |

---

## 12. Login, Navegação e Recuperação de Estado

### 12.1 `fazer_login` / `trocar_aba_aghux` (Clean State)

Mesmo padrão de RFC-001/002: `fazer_login` é wrapper de `autenticar_aghu_page` + `exigir_login_valido`. `trocar_aba_aghux` fecha a aba atual (ignorando erro), abre nova `Page` no mesmo `BrowserContext`, acessa `url_aghu` e reautentica.

### 12.2 `navegar_ate_cadastro_profissional_unidade` — navegação inicial

Até 2 tentativas: `navegar_menu_aghu(caminho=CAMINHO_MENU_CADASTRO_UNI_CIRURGICA)` seguido de `validar_tela_pesquisa()`. Na 1ª falha, aciona `trocar_aba_aghux` e tenta de novo; na 2ª falha, propaga a exceção.

### 12.3 `garantir_tela_pesquisa_profissional_unidade` — auto-recuperação em 3 níveis (por linha)

Diferença chave em relação ao padrão do Maestro de impressoras: aqui a recuperação é chamada **antes de cada linha do lote**, não só na navegação inicial, com escalonamento de custo:

```text
1. Tenta validar a janela atual como está (barato, sem navegação)
      → se OK, retorna imediatamente (idempotente)
2. Tenta renavegar pelo menu na MESMA página (mais barato que Clean State)
      → se validar, retorna
3. Aciona Clean State completo (nova aba + login) e chama
   navegar_ate_cadastro_profissional_unidade novamente
```

Esse escalonamento evita pagar o custo de um Clean State completo quando o problema é apenas a tela ter voltado ao estado de pesquisa "desalinhado" (por exemplo, após um `_retornar_para_pesquisa` que não conseguiu confirmar 100%).

### 12.4 `processar_cadastros` — laço principal e otimização de profissional ausente

Recebe `resultados_prevalidacao` opcional (se `None`, calcula pré-validação de todas as linhas via `validar_entrada`). O tamanho da lista de pré-validação deve bater com o total de cadastros, senão `ValueError`.

Para cada linha:

1. Se a pré-validação reprovou a linha → status `ignorado`, sem tocar o AGHUX.
2. Se o profissional (nome normalizado) já foi confirmado como `funcionario_nao_encontrado` **nesta mesma execução** → resultado imediato `funcionario_nao_encontrado` com detalhe `"já confirmado anteriormente nesta execução"`, **sem** nova consulta ao AGHUX.
3. Caso contrário, até 2 tentativas: `garantir_tela_pesquisa_profissional_unidade` + `Flow.processar`. Na 1ª falha técnica, Clean State + renavegação e repete a linha; na 2ª falha, marca `erro` com o texto da exceção.

O item 2 é a otimização introduzida em 23/07/2026 (commit `fad690b`): no modo Unitário da UI, um mesmo profissional pode gerar várias linhas (profissional × Unidades Funcionais marcadas). Sem esse cache, um nome digitado errado geraria uma tentativa de autocomplete falha por unidade selecionada.

---

## 13. Pontos de Entrada Públicos de Execução

### 13.1 `executar_cadastros_profissionais(cadastros, usuario_rede, senha, *, context, page, url_aghu, mostrar_console, diretorio_logs, gerar_csv_log)`

Valida usuário/senha e `url_aghu`, normaliza todas as entradas e executa dentro de `controle_saida_terminal(mostrar_console)`. Internamente:

- Pré-valida **todas** as linhas antes de decidir se vale a pena logar no AGHUX.
- Se **nenhuma** linha for válida, gera apenas o CSV de auditoria (todas `ignorado`) e retorna **sem login nem navegação** — economiza um ciclo completo de Playwright para um lote inteiramente inválido.
- Caso contrário, faz `goto` + `fazer_login` + `navegar_ate_cadastro_profissional_unidade` + `processar_cadastros` e gera o CSV ao final.

`context` e `page` são obrigatórios (sem valor padrão) — o chamador (a UI) é sempre o dono do ciclo de vida do Playwright; a função nunca cria nem fecha browser/context/page.

### 13.2 `executar_cadastro_lote(usuario_rede, senha, caminho_planilha, caminho_relatorio, *, context, page, url_aghu, mostrar_console, diretorio_logs) → (resultados, relatorio: Path)`

Lê a planilha (`ler_planilha_cadastros`), delega a `executar_cadastros_profissionais` e grava o relatório XLSX via `salvar_relatorio_resultados`. **Gera dois artefatos**: o XLSX pedido pelo operador (produzido diretamente pelo núcleo, via `openpyxl`) e o CSV de auditoria em `./logs` (sempre, pois `gerar_csv_log` não é repassado como `False`). Isso é uma divergência intencional do padrão RFC-001, onde o CSV é o único artefato do núcleo e a UI é quem converte para XLSX depois.

### 13.3 `executar_cadastro_individual(usuario_rede, senha, cadastro, *, context, page, url_aghu, ...) → ResultadoCadastroProfissional`

Wrapper de `executar_cadastros_profissionais` para uma única entrada. **Não é usado pela UI atual** — o modo "Unitária" da UI chama `executar_cadastros_profissionais` diretamente com a lista já expandida (profissional × unidade). Função pública mantida sem chamador interno no momento; ver Limitações (§18).

---

## 14. Relatórios

### 14.1 `salvar_relatorio_resultados(resultados, caminho_saida) → Path`

Gera XLSX (`openpyxl`), aba `"Resultado"`, colunas `Profissional, Unidade Funcional, Funcao, Status, Detalhes`. Acrescenta `.xlsx` se a extensão faltar; `ValueError` se houver outra extensão. `freeze_panes="A2"`, autofiltro no range dos dados, largura de coluna = maior conteúdo + 2 (limite 90).

### 14.2 `gerar_csv_logs(resultados, usuario_rede, diretorio_logs) → str`

CSV em `logs/log_profissionais_unidade_cirurgica_<AAAAMMDD_HHMMSS>.csv`, primeira linha `Atualizado por: <usuario>`, dados em modo append (`sep=";"`, `utf-8-sig`) — mesmo padrão de auditoria de RFC-001.

---

## 15. Contratos entre RFCs

### 15.1 Contrato com RFC-004 (`menu.py`)

| Item | Origem | Papel |
|---|---|---|
| `navegar_menu_aghu` | `menu.py` | Executa a travessia de menus do AGHUX recebendo o caminho `CAMINHO_MENU_CADASTRO_UNI_CIRURGICA` |
| `CAMINHO_MENU_CADASTRO_UNI_CIRURGICA` | Núcleo | Tuple `("Cirurgias / PDT", "Cadastros", "Profissionais da Unidade Cirúrgica")` repassada ao `menu.py` |

### 15.2 Contrato com RFC-005 (`autenticador.py`)

| Função / Constante | Origem | Interpretação no Núcleo / UI |
|---|---|---|
| `AGHU_URL` / `AGHU_URL_HOMOLOGACAO` | `autenticador.py` | URLs padrão dos ambientes de Produção e Homologação |
| `autenticar_aghu_page` | `autenticador.py` | Autentica a página Playwright sem criar/fechar browser ou context |
| `exigir_login_valido` | `autenticador.py` | Valida se o resultado da autenticação foi `sucesso` ou `sessao_ativa`, lançando exceção caso contrário |

---

## 16. Contratos Internos (Sinais Núcleo ↔ UI)

| Sinal | Origem | Interpretação |
|---|---|---|
| `AutocompleteSemRegistroError("Autocomplete sem registro para: <nome>")` | `selecionar_autocomplete`, ao detectar painel `"Nenhum Registro"` no autocomplete de Profissional | `Flow.processar` traduz para status `funcionario_nao_encontrado` |
| Mensagem AGHUX contendo `"profissional na unidade cirurgica incluido com sucesso"` | Dialog de mensagens após Gravar | `status_gravacao = "sucesso"` → `criado` |
| Mensagem AGHUX contendo `"campo obrigatorio"` / `"invalido"` / `"erro"` / `"ja existe"` | Dialog de mensagens após Gravar | `status_gravacao = "erro"` → `erro` |

Diferente de RFC-001/002, este módulo **não expõe exceções de negócio entre arquivos** (não há especialista satélite): todo o tratamento de "profissional inexistente" acontece dentro do próprio núcleo, e a UI só recebe o `ResultadoCadastroProfissional` já classificado.

---

## 17. Interface Gráfica (`ui_profissionais_unidade_cirurgica.py`)

### 17.1 Constantes e Ambiente

| Constante | Valor |
|---|---|
| `TIPO_INDIVIDUAL` / `TIPO_LOTE` | `"Unitária"` / `"Lote"` |
| `MAX_USUARIOS_UNITARIOS` | `5` |
| `URLS_AMBIENTE_AGHU` | `{Produção: AGHU_URL, Homologação: AGHU_URL_HOMOLOGACAO}` |

O ambiente padrão da UI é **Homologação** (`self.var_ambiente = tk.StringVar(value=AMBIENTE_HOMOLOGACAO)`), diferente de `ui_alignprinterAGHU.py` (RFC-003), cujo padrão é Produção com alerta. Este módulo já nasce alinhado à recomendação do guia (item 5: *"Homologação é o padrão operacional seguro das UIs AGHU, salvo exceção documentada"*) — não é necessário exceção aqui. O alerta de Produção (`frame_alerta_producao` + `messagebox.showwarning` ao trocar para Produção) segue o mesmo padrão visual de RFC-003.

### 17.2 Modo Unitária

- Até 5 linhas dinâmicas de nome de profissional (`+ Adicionar usuário` / remover, mínimo 1).
- Checkboxes de Unidade Funcional (uma ou mais), aplicadas a **todos** os profissionais informados.
- `_cadastros_individuais()` monta o produto cartesiano profissionais × unidades, sempre com `funcao=FUNCAO_MEDICO_RESIDENTE` (a UI não expõe seleção de função — hoje só há uma função suportada no núcleo).
- Cada cadastro gerado passa por `validar_entrada` **na thread principal, antes de iniciar a automação** — erro de validação aparece como mensagem vermelha sem sequer abrir o navegador.
- Mensagem especial: se apenas um profissional foi informado e **todos** os resultados vierem `funcionario_nao_encontrado`, a UI substitui o resumo genérico por uma mensagem direta: `Execução encerrada: profissional "<nome>" não encontrado no AGHUX. Verifique o nome informado.`

### 17.3 Modo Lote

Seleciona planilha `.xlsx` de entrada e sugere automaticamente um caminho de relatório (`relatorio_profissionais_unidade_cirurgica_<timestamp>.xlsx` no mesmo diretório da entrada). Chama `executar_cadastro_lote`.

### 17.4 Execução Playwright pela UI

`_executar_com_playwright(mostrar_browser, acao)` cria Playwright/Chromium/Context/Page e os fecha em `finally`:

```python
headless = not mostrar_browser
slow_mo = 500 if mostrar_browser else 0
```

O `slow_mo` é condicional (só aplicado com navegador visível) — diferença deliberada de RFC-003, cujo `slow_mo=500` é incondicional. Reduz o tempo de execução em modo headless. `ignore_https_errors=True`, igual às demais UIs AGHUX.

A execução roda em thread daemon; o retorno para a UI usa `self.after(0, ...)`, respeitando a exigência do Tkinter de só atualizar widgets a partir da thread principal.

### 17.5 Regra Anti-Zombie

Idêntica à de RFC-003: não permite desmarcar **Exibir Navegador** e **Exibir Terminal** simultaneamente; reativa a última opção alterada e mostra aviso.

### 17.6 Resumo de Resultados

`_resumir_resultados` usa `Counter` sobre os status e monta uma linha com total, criados, mantidos, funcionários não encontrados, conferir manualmente, ignorados e erros. Cor do status final:

| Modo | Vermelho | Amarelo | Verde |
|---|---|---|---|
| Unitária | `erro`, `conferir_manual`, `ignorado` ou `funcionario_nao_encontrado` presentes | — | caso contrário |
| Lote | `erro` ou `conferir_manual` presentes | `funcionario_nao_encontrado` ou `ignorado` presentes (sem erro/conferir) | caso contrário |

---

## 18. API Pública do Módulo

### 18.1 Núcleo (`profissionais_unidade_cirurgica_aghu.py`)

| Função/Classe | Responsabilidade |
|---|---|
| `ler_planilha_cadastros(caminho_planilha)` | Lê e valida planilha `.xlsx` de lote |
| `validar_entrada(entrada)` | Retorna lista de erros de uma entrada (usado pela UI antes de iniciar automação) |
| `normalizar_entrada(entrada)` | Normaliza profissional/unidade/função |
| `fazer_login(page, usuario_rede, senha, *, url_aghu=AGHU_URL)` | Autenticação centralizada |
| `trocar_aba_aghux(context, page_atual, usuario_rede, senha, *, url_aghu=AGHU_URL)` | Clean State |
| `navegar_ate_cadastro_profissional_unidade(context, page_atual, usuario_rede, senha, *, url_aghu=AGHU_URL)` | Navegação inicial até a tela de cadastro |
| `garantir_tela_pesquisa_profissional_unidade(context, page_atual, janela_atual, usuario_rede, senha, *, url_aghu=AGHU_URL)` | Recuperação em 3 níveis antes de cada linha |
| `processar_cadastro(janela_sistema, entrada)` | Processa uma única entrada já com a tela posicionada |
| `processar_cadastros(context, page_inicial, janela_sistema_inicial, cadastros, usuario_rede, senha, *, resultados_prevalidacao=None, url_aghu=AGHU_URL)` | Laço principal do lote |
| `executar_cadastros_profissionais(cadastros, usuario_rede, senha, *, context, page, url_aghu=AGHU_URL, mostrar_console=True, diretorio_logs=None, gerar_csv_log=True)` | Ponto de entrada completo (login → navegação → processamento → CSV) |
| `executar_cadastro_lote(usuario_rede, senha, caminho_planilha, caminho_relatorio, *, context, page, url_aghu=AGHU_URL, mostrar_console=True, diretorio_logs=None)` | Lote via planilha, gera XLSX + CSV |
| `executar_cadastro_individual(usuario_rede, senha, cadastro, *, context, page, url_aghu=AGHU_URL, mostrar_console=True, diretorio_logs=None)` | Wrapper de entrada única (sem chamador interno atual) |
| `salvar_relatorio_resultados(resultados, caminho_saida)` | Gera XLSX de relatório |
| `gerar_csv_logs(resultados, usuario_rede, diretorio_logs)` | Gera CSV de auditoria |
| `CadastroProfissionalUnidadeEntrada`, `ResultadoCadastroProfissional` | Dataclasses de entrada/saída |
| `STATUS_*`, `UNIDADES_FUNCIONAIS`, `FUNCAO_MEDICO_RESIDENTE`, `LOGS_DIR` | Constantes públicas consumidas pela UI |

Funções com prefixo `_` (`_limpar_pesquisa`, `_aguardar_resultado_pesquisa`, `_estado_vinculo`, `_preencher_formulario`, `_gravar`, `_cancelar_formulario`, `_retornar_para_pesquisa`, `_valor_em_branco`, `_remover_acentos`, `_sem_codigo_unidade`, `_normalizar_cabecalho`, `_mapear_colunas_planilha`, `_coluna_por_alias`, `_valor_coluna`, `_linha_relatorio`, `_executar_cadastros_profissionais_com_saida_configurada`) são privadas e não devem ser importadas por outros módulos.

### 18.2 UI (`ui_profissionais_unidade_cirurgica.py`)

| Função/Classe | Responsabilidade |
|---|---|
| `obter_url_ambiente_aghu(ambiente)` | Resolve rótulo de ambiente para URL, com fallback `AGHU_URL` |
| `caminho_relatorio_padrao(base)` | Sugere nome de relatório de lote |
| `AghuProfissionaisUnidadeCirurgicaApp` | Classe principal `ctk.CTk` |
| `executar_interface()` | Ponto de entrada da UI (`ctk.set_appearance_mode`, instancia app, `mainloop`) |

---

## 19. Considerações Operacionais

1. O núcleo não cria o browser principal; a UI cria `Browser`, `BrowserContext` e `Page`, no mesmo padrão de RFC-001/003.
2. O parâmetro `url_aghu` deve ser propagado por todo retry, Clean State e renavegação, para não trocar de ambiente durante a execução.
3. `selecionar_selectonemenu` assume um único `.ui-selectonemenu-trigger` visível por chamada — válido para o formulário atual (só o campo Função o usa), mas frágil se uma tela futura tiver mais de um componente desse tipo simultaneamente.
4. A leitura de planilha de lote aceita **apenas `.xlsx`**, diferente de `PrinterAGHU.py`, que também aceita `.xlsm`/`.csv`.
5. `executar_cadastro_lote` gera dois artefatos por execução: o relatório XLSX pedido pelo operador **e** um CSV de auditoria em `./logs`.
6. O cache de "profissional não encontrado" (`profissionais_nao_encontrados`) vive apenas durante uma execução (`processar_cadastros`); não é persistido entre execuções.
7. `garantir_tela_pesquisa_profissional_unidade` é chamada a cada linha do lote, não só na navegação inicial — a recuperação em 3 níveis (validar → renavegar → Clean State) é o principal mecanismo de resiliência deste módulo.
8. `FUNCOES_PROFISSIONAL` hoje contém apenas `"Médico residente"`; qualquer outro valor na coluna Função da planilha de lote é rejeitado pela pré-validação (`ignorado`).

---

## 20. Limitações Conhecidas

| Limitação | Impacto |
|---|---|
| `executar_cadastro_individual` não tem chamador interno atual | API pública "morta" — a UI monta a lista expandida e chama `executar_cadastros_profissionais` diretamente |
| `selecionar_selectonemenu` não escopa o trigger a um campo específico | Uma tela com múltiplos `selectonemenu` simultâneos quebraria a seleção |
| `_retornar_para_pesquisa` pode desistir silenciosamente após 3 tentativas sem botão Voltar | A tela pode ficar em estado intermediário até a próxima linha acionar `garantir_tela_pesquisa_profissional_unidade` |
| Apenas uma função (`Médico residente`) é suportada | Extensão para outras funções exige atualizar `FUNCOES_PROFISSIONAL` e a UI (hoje sem seletor de função) |
| Leitura de planilha de lote não aceita `.xlsm`/`.csv` | Inconsistente com `PrinterAGHU.py`; pode confundir operadores acostumados ao outro robô |
| Seletores de tabela dependem de índice de célula fixo (`unidade`=1, `funcao`=2, `profissional`=5, `situacao`=7) | Mudança de colunas na tela do AGHUX exige atualização coordenada de `_estado_vinculo` |
| Cache de "profissional não encontrado" é por execução, não persistente | Reexecuções repetem a consulta ao AGHUX para o mesmo nome inválido |

---

## 21. Estado Atual da RFC

Esta RFC documenta, de forma retroativa, o código em produção de `profissionais_unidade_cirurgica_aghu.py` e `ui_profissionais_unidade_cirurgica.py` conforme a release de 23/07/2026 (commit `fad690b`), incluindo:

- Fluxo completo de pesquisa/decisão/gravação via `ProfissionalUnidadeCirurgicaFlow`.
- Recuperação de estado em 3 níveis por linha (`garantir_tela_pesquisa_profissional_unidade`).
- Otimização de profissional não encontrado (cache por execução).
- Seis estados de resultado (`criado`, `mantido`, `funcionario_nao_encontrado`, `conferir_manual`, `erro`, `ignorado`).
- Geração dupla de relatório no modo lote (XLSX + CSV de auditoria).
- Interface gráfica com modos Unitária/Lote, ambiente padrão Homologação e execução Playwright com `slow_mo` condicional.
- Limitações conhecidas listadas no §20, para revisão futura.
