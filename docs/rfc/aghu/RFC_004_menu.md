# RFC-004 — Navegação de Menu do AGHUX (menu)

- **Status:** Estável
- **Autor:** Ruan
- **Data:** 2026-06
- **Atualizado em:** 2026-06-19
- **Arquivo:** `menu.py`
- **Depende de:** —
- **Usado por:** `PrinterAGHU.py` (RFC-001), `AddPrinterAGHU.py` (RFC-002)

---

## 1. Resumo

`menu.py` é o módulo utilitário genérico de **navegação de menu** do AGHUX. Ele não conhece caminhos específicos de procedimentos e não mantém constantes de domínio, como caminhos de impressoras.

A função pública `navegar_menu_aghu` recebe do chamador o caminho completo do menu, percorre os níveis informados, clica no último item e retorna o último iframe disponível na página. A validação de que a tela final carregou corretamente pertence ao procedimento chamador, pois cada tela pode ter elementos de confirmação diferentes.

Exemplos de caminhos atualmente declarados fora de `menu.py`:

| Chamador | Constante local | Caminho final |
|---|---|---|
| Maestro (`PrinterAGHU.py`) | `CAMINHO_MENU_IMPRESSORA_POR_COMPUTADOR` | `Outros Módulos → Configuração → Impressão → Cadastros → Impressora por Computador` |
| Almoxarifado (`AddPrinterAGHU.py`) | `CAMINHO_MENU_CADASTRO_IMPRESSORA` | `Outros Módulos → Configuração → Impressão → Cadastros → Impressora` |

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

`menu.py` não declara constantes públicas de caminhos de negócio.

Os caminhos completos pertencem aos procedimentos chamadores. Atualmente:

| Procedimento | Constante |
|---|---|
| `PrinterAGHU.py` | `CAMINHO_MENU_IMPRESSORA_POR_COMPUTADOR` |
| `AddPrinterAGHU.py` | `CAMINHO_MENU_CADASTRO_IMPRESSORA` |

---

## 5. Descrição dos Componentes

### 5.1 `_locator_menu_visivel(page, texto)` (privada)

Retorna o primeiro locator visível cujo texto exato corresponda ao parâmetro `texto`:

```python
page.get_by_text(texto, exact=True).locator("visible=true").first
```

O uso de `exact=True` evita correspondências parciais em itens de menu com nomes semelhantes.

### 5.2 `_item_menu_visivel(page, texto)` (privada)

Retorna `True` se o item de menu com o texto informado estiver visível. Captura exceções e retorna `False` em caso de falha.

Usada por `_garantir_proximo_nivel_visivel` para evitar cliques redundantes em menus já expandidos.

### 5.3 `_clicar_item_menu(page, texto, timeout_ms)` (privada)

Aguarda o item de menu ficar visível e clica nele. Ambas as operações respeitam `timeout_ms`.

### 5.4 `_garantir_proximo_nivel_visivel(page, item_atual, proximo_item, timeout_ms)` (privada)

Verifica se o próximo nível do menu já está visível. Se sim, não faz nada. Se não, clica no item atual e aguarda o próximo nível aparecer.

Esse comportamento garante idempotência: se o menu já estiver parcialmente expandido, a função não tenta reexpandir níveis já abertos.

### 5.5 `navegar_menu_aghu(page, caminho, timeout_menu_ms)`

Função pública e único ponto de entrada do módulo. Percorre o caminho completo de menu e retorna o último iframe.

Assinatura:

```python
def navegar_menu_aghu(
    page: Page,
    caminho: Sequence[str],
    timeout_menu_ms: int = 5000,
):
```

Parâmetros:

| Parâmetro | Uso |
|---|---|
| `page` | Página AGHUX já autenticada |
| `caminho` | Sequência completa de textos do menu, incluindo o item final |
| `timeout_menu_ms` | Timeout para cada nível do menu (padrão: 5000 ms) |

Validações:

| Entrada inválida | Comportamento |
|---|---|
| Sequência vazia | Lança `ValueError` |
| String única em vez de sequência de itens | Lança `ValueError` |

Fluxo:

1. Valida que `caminho` é uma sequência não vazia e não é `str`.
2. Converte `caminho` para tupla.
3. Para cada par `(item_atual, proximo_item)`, chama `_garantir_proximo_nivel_visivel`.
4. Clica no último item do caminho.
5. Retorna `page.frame_locator("iframe").last`.

A função não aguarda elemento específico da tela final. Essa espera deve ser feita pelo chamador.

---

## 6. API Pública do Módulo

| Função | Responsabilidade |
|---|---|
| `navegar_menu_aghu(page, caminho, ...)` | Percorre o caminho completo informado, clica no item final e retorna o último iframe |

Não há constante pública de caminho em `menu.py`.

---

## 7. Contrato com os Chamadores

### 7.1 Contrato com RFC-001 (Maestro)

O Maestro declara `CAMINHO_MENU_IMPRESSORA_POR_COMPUTADOR` em `PrinterAGHU.py` e chama:

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

Em caso de falha, o Maestro aciona Clean State e tenta novamente.

### 7.2 Contrato com RFC-002 (Almoxarifado)

O Almoxarifado declara `CAMINHO_MENU_CADASTRO_IMPRESSORA` em `AddPrinterAGHU.py` e chama:

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

Em caso de falha, o Almoxarifado faz reload da página e tenta novamente.

---

## 8. Considerações Operacionais

1. O módulo depende dos textos visíveis passados pelo chamador.
2. Mudanças na estrutura ou nomenclatura do menu afetam o procedimento que declara o caminho correspondente.
3. A verificação de visibilidade antes de cada clique torna a navegação idempotente em retries.
4. O módulo assume que a `Page` informada já está autenticada.
5. A validação de carregamento da tela final é responsabilidade do procedimento chamador.

---

## 9. Limitações Conhecidas

| Limitação | Impacto |
|---|---|
| Seletores dependem de texto visível exato | Mudanças de nomenclatura no AGHUX exigem ajuste no procedimento que declarou o caminho |
| Sem validação interna da tela final | O chamador precisa aguardar um elemento confiável após a navegação |
| Sem tratamento de retry interno | Retries continuam responsabilidade do chamador |

---

## 10. Estado Atual da RFC

Esta RFC documenta o contrato atual de `menu.py`: navegação genérica por caminho completo, sem constantes de domínio e sem validação de tela final embutida.
