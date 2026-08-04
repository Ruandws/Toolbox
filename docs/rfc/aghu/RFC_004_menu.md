# RFC-004 — Navegação de Menu do AGHUX (menu)

- **Status:** Estável
- **Autor:** Ruan
- **Data:** 2026-06
- **Atualizado em:** 2026-08-04
- **Arquivo:** `menu.py`
- **Depende de:** —
- **Chamado por:** `PrinterAGHU.py` (RFC-001), `AddPrinterAGHU.py` (RFC-002), `concessor_aghu.py` (RFC-006), `criar_pessoa_aghu.py` (RFC-007), `criar_usuario_aghu.py` (RFC-008), `profissionais_unidade_cirurgica_aghu.py` (RFC-009)

---

## 1. Resumo

`menu.py` é o módulo utilitário genérico de **navegação de menu** do AGHUX. Ele não conhece caminhos específicos de procedimentos e não mantém constantes de domínio, como caminhos de impressoras ou de cadastros.

A função pública `navegar_menu_aghu` recebe do chamador o caminho completo do menu, percorre os níveis informados, clica no último item e retorna o último iframe disponível na página. A validação de que a tela final carregou corretamente pertence ao procedimento chamador, pois cada tela pode ter elementos de confirmação diferentes.

Exemplos de caminhos atualmente declarados fora de `menu.py`:

| Chamador | Constante local | Caminho final |
|---|---|---|
| `PrinterAGHU.py` | `CAMINHO_MENU_IMPRESSORA_POR_COMPUTADOR` | `Outros Módulos → Configuração → Impressão → Cadastros → Impressora por Computador` |
| `AddPrinterAGHU.py` | `CAMINHO_MENU_CADASTRO_IMPRESSORA` | `Outros Módulos → Configuração → Impressão → Cadastros → Impressora` |
| `concessor_aghu.py` | `CAMINHO_MENU_CADASTRO_USUARIO` | `Outros Módulos → Configuração → Acesso → Usuario` |
| `criar_pessoa_aghu.py` | `CAMINHO_MENU_CADASTRO_PESSOA` | `Outros Módulos → Colaborador → Administrar Servidores → Pessoas` |
| `criar_usuario_aghu.py` | `CAMINHO_MENU_CADASTRO_USUARIO` | `Outros Módulos → Configuração → Acesso → Usuario` |
| `profissionais_unidade_cirurgica_aghu.py` | `CAMINHO_MENU_CADASTRO_UNI_CIRURGICA` | `Cirurgias / PDT → Cadastros → Profissionais da Unidade Cirúrgica` |

---

## 2. Motivação

A navegação pelo menu do AGHUX usa a mesma mecânica em diferentes procedimentos: localizar itens visíveis por texto exato, expandir níveis quando necessário e clicar no destino final. Antes da generalização, `menu.py` carregava uma constante específica de impressoras e a função pública recebia apenas o item final.

A abordagem atual separa responsabilidades:

1. `menu.py` sabe **como navegar** por uma sequência de itens.
2. Cada procedimento sabe **qual caminho** precisa abrir.
3. Cada procedimento sabe **como validar** que a tela final carregou.

Isso evita transformar `menu.py` em um catálogo central de todos os módulos do AGHUX e permite reutilizar a navegação em procedimentos que não pertençam ao domínio de impressoras.

---

## 3. Dependências

O módulo depende apenas da biblioteca padrão e do Playwright:

```python
from collections.abc import Sequence

from playwright.sync_api import Page
```

Não há dependência de `autenticador.py`, `PrinterAGHU.py`, `AddPrinterAGHU.py` ou qualquer procedimento específico. O módulo permanece uma folha no grafo de dependências.

---

## 4. Constantes

`menu.py` **não declara constantes** — nem públicas de caminhos de negócio, nem privadas de configuração interna. O módulo é stateless e recebe tudo via parâmetros.

Os caminhos completos pertencem exclusivamente aos procedimentos chamadores. Consulte a seção "Chamado por" no cabeçalho e a seção 7 para a lista completa dos chamadores e suas constantes locais.

---

## 5. Arquitetura e Fluxo de Dados

### 5.1 Diagrama do Módulo

```
  Chamador (ex: criar_usuario_aghu.py)
  ┌───────────────────────────────────────┐
  │  CAMINHO_MENU_CADASTRO_USUARIO = (    │
  │      "Outros Módulos",                │
  │      "Configuração",                  │
  │      "Acesso",                        │
  │      "Usuario",                       │
  │  )                                    │
  │                                       │
  │  janela = navegar_menu_aghu(          │
  │      page=page,                       │
  │      caminho=CAMINHO_MENU_...,        │
  │  )    │                               │
  └───────┼───────────────────────────────┘
          │  page + caminho (Sequence[str])
          ▼
  ┌───────────────────────────────────────────────────────────────┐
  │                        menu.py                                │
  │                                                               │
  │  navegar_menu_aghu(page, caminho, timeout_menu_ms)            │
  │  ├─ valida caminho (não vazio, não é str)                     │
  │  ├─ para cada par (item_atual, proximo_item):                 │
  │  │   └─ _garantir_proximo_nivel_visivel()                     │
  │  │       ├─ _item_menu_visivel()  ──► já aberto? não faz nada │
  │  │       └─ _clicar_item_menu()  ──► aguarda + clica          │
  │  │           └─ _locator_menu_visivel()  ──► locator visível  │
  │  └─ _clicar_item_menu(último item)                            │
  │  └─ retorna page.frame_locator("iframe").last                 │
  └───────────────────────────────────────────────────────────────┘
          │  FrameLocator (último iframe)
          ▼
  Chamador: aguarda elemento de confirmação da tela final
  ex: janela.get_by_role("button", name="Pesquisar").first.wait_for(...)
```

### 5.2 Sequência de Chamada Interna

```
navegar_menu_aghu
    └── para cada par (item_atual[i], caminho[i+1]):
            _garantir_proximo_nivel_visivel(page, item_atual, proximo_item)
                ├── _item_menu_visivel(page, proximo_item)
                │       └── _locator_menu_visivel(page, proximo_item).is_visible()
                └── (se não visível) _clicar_item_menu(page, item_atual)
                        └── _locator_menu_visivel(page, item_atual).wait_for() + .click()
    └── _clicar_item_menu(page, último item)
    └── return page.frame_locator("iframe").last
```

---

## 6. Descrição dos Componentes

### 6.1 Funções Privadas

Todas as funções privadas operam sobre `page` e texto de item de menu. Não são parte do contrato público e podem mudar sem aviso.

| Função | Assinatura | Descrição |
|---|---|---|
| `_locator_menu_visivel` | `(page: Page, texto: str) -> Locator` | Retorna o primeiro locator visível cujo texto exato corresponde ao parâmetro. Usa `exact=True` para evitar correspondências parciais em itens com nomes semelhantes. |
| `_item_menu_visivel` | `(page: Page, texto: str) -> bool` | Retorna `True` se o item de menu estiver visível. Captura exceções e retorna `False` em caso de falha. Usada para evitar cliques redundantes em níveis já expandidos. |
| `_clicar_item_menu` | `(page: Page, texto: str, timeout_ms: int) -> None` | Aguarda o item ficar visível e clica nele. Ambas as operações respeitam `timeout_ms`. |
| `_garantir_proximo_nivel_visivel` | `(page: Page, item_atual: str, proximo_item: str, timeout_ms: int) -> None` | Verifica se o próximo nível já está visível. Se sim, não faz nada (idempotência). Se não, clica no item atual e aguarda o próximo aparecer. |

### 6.2 Função Pública

| Função | Assinatura | Descrição |
|---|---|---|
| `navegar_menu_aghu` | `(page: Page, caminho: Sequence[str], timeout_menu_ms: int = 5000) -> FrameLocator` | Único ponto de entrada do módulo. Percorre o caminho completo, clica no item final e retorna o último iframe disponível na página. |

**Parâmetros de `navegar_menu_aghu`:**

| Parâmetro | Tipo | Padrão | Descrição |
|---|---|---|---|
| `page` | `Page` | — | Página AGHUX já autenticada |
| `caminho` | `Sequence[str]` | — | Sequência completa de textos do menu, incluindo o item final |
| `timeout_menu_ms` | `int` | `5000` | Timeout em ms para cada nível do menu |

**Validações e comportamento de erro:**

| Entrada inválida | Comportamento |
|---|---|
| Sequência vazia | Lança `ValueError` |
| String única em vez de sequência de itens | Lança `ValueError` |

**Fluxo interno:**

1. Valida que `caminho` é uma sequência não vazia e não é `str`.
2. Converte `caminho` para tupla.
3. Para cada par `(item_atual, proximo_item)`, chama `_garantir_proximo_nivel_visivel`.
4. Clica no último item do caminho.
5. Retorna `page.frame_locator("iframe").last`.

A função não aguarda elemento específico da tela final. Essa espera deve ser feita pelo chamador.

---

## 7. Contrato com os Chamadores

Padrão comum a todos os chamadores:

| Etapa | Responsabilidade |
|---|---|
| Declarar constante de caminho | Do chamador (em seu próprio módulo) |
| Chamar `navegar_menu_aghu(page=..., caminho=...)` | Do chamador |
| Aguardar elemento de confirmação com `wait_for` | Do chamador |
| Retry em caso de falha (Clean State ou reload) | Do chamador |

---

### 7.1 Contrato com RFC-001 (`PrinterAGHU.py` — Maestro)

| Campo | Valor |
|---|---|
| Constante local | `CAMINHO_MENU_IMPRESSORA_POR_COMPUTADOR` |
| Caminho | `Outros Módulos → Configuração → Impressão → Cadastros → Impressora por Computador` |
| Elemento de confirmação | `button[name="Pesquisar"]` (primeiro visível, timeout 15 s) |
| Estratégia de retry | Clean State: abre nova aba e refaz login |

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

---

### 7.2 Contrato com RFC-002 (`AddPrinterAGHU.py` — Almoxarifado)

| Campo | Valor |
|---|---|
| Constante local | `CAMINHO_MENU_CADASTRO_IMPRESSORA` |
| Caminho | `Outros Módulos → Configuração → Impressão → Cadastros → Impressora` |
| Elemento de confirmação | `button[name="Pesquisar"]` (primeiro visível, timeout 15 s) |
| Estratégia de retry | Reload da página e nova tentativa |

```python
janela_sistema = navegar_menu_aghu(
    page=page_aghu,
    caminho=CAMINHO_MENU_CADASTRO_IMPRESSORA,
)
janela_sistema.get_by_role("button", name="Pesquisar").first.wait_for(
    state="visible",
    timeout=15000,
)
```

---

### 7.3 Contrato com RFC-006 (`concessor_aghu.py` — Concessor)

| Campo | Valor |
|---|---|
| Constante local | `CAMINHO_MENU_CADASTRO_USUARIO` |
| Caminho | `Outros Módulos → Configuração → Acesso → Usuario` |
| Elemento de confirmação | `input[id="nomeOuLogin:..."]` via `_primeiro_visivel` + `button[name="Pesquisar"]` (timeout 15 s) |
| Estratégia de retry | Clean State: fecha aba, abre nova aba e refaz login |

```python
janela_sistema = navegar_menu_aghu(
    page=page,
    caminho=CAMINHO_MENU_CADASTRO_USUARIO,
)
_primeiro_visivel(janela_sistema, (SELECTOR_PESQUISA_LOGIN,))
janela_sistema.get_by_role("button", name="Pesquisar").first.wait_for(
    state="visible",
    timeout=15000,
)
```

---

### 7.4 Contrato com RFC-007 (`criar_pessoa_aghu.py` — Criar Pessoa)

| Campo | Valor |
|---|---|
| Constante local | `CAMINHO_MENU_CADASTRO_PESSOA` |
| Caminho | `Outros Módulos → Colaborador → Administrar Servidores → Pessoas` |
| Elemento de confirmação | `input[id="cpf:cpf:inputId"]` via `primeiro_visivel` (timeout 15 s) + `button[name="Pesquisar"]` |
| Estratégia de retry | Clean State: fecha aba, abre nova aba e refaz login |

```python
janela_sistema = navegar_menu_aghu(
    page=page,
    caminho=CAMINHO_MENU_CADASTRO_PESSOA,
)
primeiro_visivel(janela_sistema, (SELECTOR_PESQUISA_CPF,), timeout_ms=15000)
janela_sistema.get_by_role("button", name="Pesquisar").first.wait_for(
    state="visible",
    timeout=15000,
)
```

---

### 7.5 Contrato com RFC-008 (`criar_usuario_aghu.py` — Criar Usuário)

| Campo | Valor |
|---|---|
| Constante local | `CAMINHO_MENU_CADASTRO_USUARIO` |
| Caminho | `Outros Módulos → Configuração → Acesso → Usuario` |
| Elemento de confirmação | `input[id="nomeOuLogin:..."]` via `_primeiro_visivel` + `button[name="Pesquisar"]` (timeout 15 s) |
| Estratégia de retry | Clean State: fecha aba, abre nova aba e refaz login |

```python
janela_sistema = navegar_menu_aghu(
    page=page,
    caminho=CAMINHO_MENU_CADASTRO_USUARIO,
)
_primeiro_visivel(janela_sistema, (SELECTOR_PESQUISA_LOGIN,))
janela_sistema.get_by_role("button", name="Pesquisar").first.wait_for(
    state="visible",
    timeout=15000,
)
```

> **Nota:** `concessor_aghu.py` (RFC-006) e `criar_usuario_aghu.py` (RFC-008) compartilham o mesmo caminho de menu (`Outros Módulos → Configuração → Acesso → Usuario`) mas são módulos independentes com fluxos de negócio diferentes.

---

### 7.6 Contrato com RFC-009 (`profissionais_unidade_cirurgica_aghu.py`)

| Campo | Valor |
|---|---|
| Constante local | `CAMINHO_MENU_CADASTRO_UNI_CIRURGICA` |
| Caminho | `Cirurgias / PDT → Cadastros → Profissionais da Unidade Cirúrgica` |
| Elemento de confirmação | `input[name="Pesquisa Nome"]` via `ProfissionalUnidadeCirurgicaFlow.validar_tela_pesquisa()` (timeout 15 s) |
| Estratégia de retry | Clean State: fecha aba, abre nova aba e refaz login |

```python
janela_sistema = navegar_menu_aghu(
    page=page,
    caminho=CAMINHO_MENU_CADASTRO_UNI_CIRURGICA,
)
ProfissionalUnidadeCirurgicaFlow(janela_sistema).validar_tela_pesquisa()
```

---

## 8. API Pública do Módulo

| Função | Assinatura resumida | Responsabilidade |
|---|---|---|
| `navegar_menu_aghu` | `(page, caminho, timeout_menu_ms=5000)` | Percorre o caminho completo informado, clica no item final e retorna o último iframe |

Não há constante pública de caminho em `menu.py`.

---

## 9. Considerações Operacionais

1. O módulo depende dos textos visíveis passados pelo chamador.
2. Mudanças na estrutura ou nomenclatura do menu do AGHUX afetam **todos os 6 módulos chamadores** listados na seção 7 — qualquer alteração em `navegar_menu_aghu` deve considerar o impacto nos 6.
3. A verificação de visibilidade antes de cada clique torna a navegação idempotente em retries.
4. O módulo assume que a `Page` informada já está autenticada.
5. A validação de carregamento da tela final é responsabilidade do procedimento chamador.

---

## 10. Limitações Conhecidas

| Limitação | Impacto |
|---|---|
| Seletores dependem de texto visível exato | Mudanças de nomenclatura no AGHUX exigem ajuste no procedimento que declarou o caminho |
| Sem validação interna da tela final | O chamador precisa aguardar um elemento confiável após a navegação |
| Sem tratamento de retry interno | Retries continuam responsabilidade do chamador |

---

## 11. Estado Atual da RFC

Esta RFC documenta o contrato atual de `menu.py`: navegação genérica por caminho completo, sem constantes de domínio e sem validação de tela final embutida. O módulo é compartilhado por 6 módulos chamadores (RFC-001, RFC-002, RFC-006, RFC-007, RFC-008, RFC-009).

---

## 12. Mudanças Incorporadas nesta Revisão

| # | Mudança | Motivo |
|---|---|---|
| 1 | Campo `"Usado por"` renomeado para `"Chamado por"` no cabeçalho | Padronização com demais RFCs do projeto |
| 2 | Adicionados 4 chamadores reais ausentes na versão anterior: RFC-006, RFC-007, RFC-008, RFC-009 | `menu.py` é usado por 6 módulos; a RFC anterior reconhecia apenas 2, criando risco de mudanças sem análise de impacto completa |
| 3 | Seção "Contrato com os Chamadores" expandida com tabelas e subseções individuais para cada chamador | Rastreabilidade de dependentes: qualquer mudança futura em `navegar_menu_aghu` deve considerar os 6 robôs |
| 4 | Seção "Arquitetura e Fluxo de Dados" adicionada com diagrama ASCII do módulo e sequência de chamada interna | Ausência dificultava compreensão do fluxo sem ler o código |
| 5 | Funções privadas separadas da função pública em tabelas distintas na seção 6 | A prosa corrida anterior não diferenciava contrato público de implementação interna |
| 6 | Seção "Constantes" corrigida: versão anterior listava constantes de outros módulos como se fossem de `menu.py` | `menu.py` não declara constante alguma; as constantes pertencem aos chamadores |
