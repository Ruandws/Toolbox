# RFC-004 — Navegação de Menu do AGHUX (menu)

- **Status:** Estável
- **Autor:** Ruan
- **Data:** 2026-06
- **Atualizado em:** 2026-06-16
- **Arquivo:** `menu.py`
- **Depende de:** —
- **Usado por:** `PrinterAGHU.py` (RFC-001), `AddPrinterAGHU.py` (RFC-002)

---

## 1. Resumo

`menu.py` é o módulo utilitário de **navegação de menu** do AGHUX. Ele encapsula o caminho fixo do menu lateral até o nível **Cadastros** da área de Impressão e expõe a função `navegar_menu_impressora`, que percorre esse caminho, clica no item final informado pelo chamador e aguarda o carregamento do iframe de destino.

O módulo foi criado para eliminar a duplicação de lógica de navegação que antes existia em `PrinterAGHU.py` e `AddPrinterAGHU.py`. Ambos os robôs compartilham o mesmo caminho de menu mas diferem no item final:

| Chamador | Item Final |
|---|---|
| Maestro (`PrinterAGHU.py`) | `Impressora por Computador` |
| Almoxarifado (`AddPrinterAGHU.py`) | `Impressora` |

---

## 2. Motivação

A navegação pelo menu do AGHUX segue sempre o mesmo caminho hierárquico:

```text
Outros Módulos → Configuração → Impressão → Cadastros → <item final>
```

Antes da extração para `menu.py`, cada robô implementava essa sequência manualmente, com seletores e verificações de visibilidade duplicados. A centralização em um módulo dedicado garante que:

1. Mudanças na estrutura do menu sejam corrigidas em um único ponto.
2. O comportamento de verificação de visibilidade antes de clicar seja uniforme.
3. A espera pelo iframe de destino siga o mesmo contrato em todos os chamadores.

---

## 3. Dependências

O módulo depende apenas do Playwright:

```python
from playwright.sync_api import Page
```

Não há dependência de `autenticador.py`, `PrinterAGHU.py` ou `AddPrinterAGHU.py`. O módulo é uma folha no grafo de dependências.

---

## 4. Constantes

### 4.1 `CAMINHO_MENU_IMPRESSORA`

Tupla com os textos visíveis dos itens de menu que formam o caminho até o nível **Cadastros**:

```python
CAMINHO_MENU_IMPRESSORA = (
    "Outros Módulos",
    "Configuração",
    "Impressão",
    "Cadastros",
)
```

O item final não faz parte da tupla. Ele é informado pelo chamador como parâmetro de `navegar_menu_impressora`.

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

Esse comportamento garante idempotência: se o menu já estiver parcialmente expandido (por exemplo, após um retry), a função não tenta reexpandir níveis já abertos.

### 5.5 `navegar_menu_impressora(page, item_final, timeout_menu_ms, timeout_tela_ms)`

Função pública e único ponto de entrada do módulo. Percorre o caminho completo de menu e abre o módulo de destino.

Assinatura:

```python
def navegar_menu_impressora(
    page: Page,
    item_final: str,
    timeout_menu_ms: int = 5000,
    timeout_tela_ms: int = 15000,
) -> FrameLocator:
```

Parâmetros:

| Parâmetro | Uso |
|---|---|
| `page` | Página AGHUX já autenticada |
| `item_final` | Texto exato do último item de menu a clicar |
| `timeout_menu_ms` | Timeout para cada nível do menu (padrão: 5000 ms) |
| `timeout_tela_ms` | Timeout para aguardar o iframe de destino (padrão: 15000 ms) |

Fluxo:

1. Monta o caminho completo: `(*CAMINHO_MENU_IMPRESSORA, item_final)`.
2. Para cada par `(item_atual, proximo_item)`, chama `_garantir_proximo_nivel_visivel`.
3. Clica no item final.
4. Captura o último iframe: `page.frame_locator("iframe").last`.
5. Aguarda o botão **Pesquisar** ficar visível dentro do iframe.
6. Retorna o `FrameLocator` do iframe.

Valores de `item_final` usados atualmente:

| Chamador | `item_final` |
|---|---|
| `PrinterAGHU.navegar_ate_modulo` | `"Impressora por Computador"` |
| `AddPrinterAGHU.navegar_ate_cadastro_impressora` | `"Impressora"` |

---

## 6. API Pública do Módulo

| Função | Responsabilidade |
|---|---|
| `navegar_menu_impressora(page, item_final, ...)` | Percorre o menu, clica no item final e retorna o iframe carregado |

| Constante | Responsabilidade |
|---|---|
| `CAMINHO_MENU_IMPRESSORA` | Caminho fixo de menu até o nível **Cadastros** |

---

## 7. Contrato com os Chamadores

### 7.1 Contrato com RFC-001 (Maestro)

O Maestro chama `navegar_menu_impressora(page, "Impressora por Computador")` dentro de `navegar_ate_modulo`. Em caso de falha, o Maestro aciona Clean State e tenta novamente.

### 7.2 Contrato com RFC-002 (Almoxarifado)

O Almoxarifado chama `navegar_menu_impressora(page, "Impressora")` dentro de `navegar_ate_cadastro_impressora`. Em caso de falha, faz reload da página e tenta novamente.

---

## 8. Considerações Operacionais

1. O módulo depende dos textos visíveis do AGHUX: **Outros Módulos**, **Configuração**, **Impressão**, **Cadastros** e o item final passado pelo chamador.
2. Mudanças na estrutura ou nomenclatura do menu do AGHUX afetam todos os robôs que usam este módulo.
3. A verificação de visibilidade antes de cada clique torna a navegação idempotente em retries.
4. O módulo assume que a `Page` informada já está autenticada.
5. A validação de carregamento do módulo depende da presença do botão **Pesquisar** no iframe final.

---

## 9. Limitações Conhecidas

| Limitação | Impacto |
|---|---|
| Caminho de menu hard-coded na constante | Mudanças na árvore de menu exigem alteração da tupla |
| Validação de tela depende do botão **Pesquisar** | Se o módulo de destino não possuir botão **Pesquisar**, a espera falhará por timeout |
| Sem tratamento de retry interno | Retries são responsabilidade do chamador |

---

## 10. Estado Atual da RFC

Esta RFC documenta o código atual de `menu.py`, incluindo o caminho fixo de menu, a verificação de visibilidade por nível, a delegação do item final ao chamador e o contrato de retorno do iframe carregado.
