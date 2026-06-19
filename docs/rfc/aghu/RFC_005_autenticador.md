# RFC-005 — Módulo Transversal de Autenticação do AGHUX (autenticador)

- **Status:** Estável
- **Autor:** Ruan
- **Data:** 2026-06
- **Atualizado em:** 2026-06-19
- **Arquivo:** `autenticador.py`
- **Depende de:** `playwright.sync_api`
- **Usado por:** `PrinterAGHU.py` (RFC-001), `AddPrinterAGHU.py` (RFC-002), `ui_alignprinterAGHU.py` (RFC-003), `test_ui_autenticador.py`

---

## 1. Resumo

`autenticador.py` centraliza a autenticação no AGHUX. O módulo concentra URLs, seletores da tela de login, detecção de sessão ativa, detecção de credenciais inválidas e wrappers usados pelos robôs.

O uso principal é `autenticar_aghu_page`, que autentica uma `Page` já existente sem criar ou fechar browser/context/page. Para teste manual ou execução isolada, existe `autenticar_aghu`, que cria e fecha seus próprios recursos do Playwright.

---

## 2. Motivação e Escopo

A autenticação é uma dependência transversal dos fluxos AGHUX. Mantê-la em um único arquivo evita duplicação de seletores, mensagens de erro e critérios de sessão ativa em `PrinterAGHU.py`, `AddPrinterAGHU.py` e telas auxiliares.

O autenticador sabe:

| Responsabilidade | Descrição |
|---|---|
| URLs | Resolve Produção e expõe Homologação |
| Login | Localiza campos, preenche credenciais e clica em **Entrar** |
| Estado | Diferencia sessão ativa, sucesso, credencial inválida, timeout e erro técnico |
| Compatibilidade | Mantém wrappers para chamadas antigas |

O módulo não conhece regras de negócio de impressoras, menu ou planilhas.

---

## 3. Fluxo

```text
[Chamador com Page existente]
        │
        └─► autenticar_aghu_page(page, usuario, senha, url_login, ...)
              ├─ Valida usuário/senha
              ├─ Acessa url_login, quando informado
              ├─ Detecta sessão já ativa
              ├─ Aguarda tela de login
              ├─ Preenche credenciais
              ├─ Clica em Entrar
              └─ Retorna ResultadoLogin
```

Para teste isolado:

```text
autenticar_aghu(...)
    ├─ Cria Playwright, browser, context e page
    ├─ Chama autenticar_aghu_page(...)
    └─ Fecha context e browser em finally
```

---

## 4. Dependências e Constantes

Dependências diretas:

```python
import os
import time
from dataclasses import dataclass
from typing import Literal, Optional, Sequence

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright
```

URLs públicas:

| Constante | Uso |
|---|---|
| `DEFAULT_AGHU_URL` | URL padrão de Produção |
| `AGHU_URL_HOMOLOGACAO` | URL do ambiente de Homologação |
| `AGHU_URL` | URL efetiva, com override por `AGHU_URL` ou `URL_LOGIN_AGHU` |
| `URL_LOGIN_AGHU` | Alias legado de `AGHU_URL` |

Seletores e textos principais:

| Item | Uso |
|---|---|
| `SELECTOR_USUARIO`, `SELECTOR_SENHA`, `SELECTOR_ENTRAR` | Seletores preferenciais da tela de login |
| `SELETORES_*_FALLBACK` | Alternativas quando os seletores preferenciais não aparecem |
| `MENSAGEM_ERRO_AUTENTICACAO` | Texto usado para identificar credencial inválida |
| `TEXTO_TELA_PRINCIPAL_AGHU` | Saudação esperada: `Olá,` |
| `TEXTO_MENU_PRINCIPAL_AGHU` | Fallback de sessão ativa: `Outros Módulos` |

---

## 5. Resultado e API Pública

### 5.1 `ResultadoLogin`

```python
StatusLogin = Literal[
    "sucesso",
    "sessao_ativa",
    "credenciais_invalidas",
    "timeout",
    "erro",
]

@dataclass(frozen=True)
class ResultadoLogin:
    status: StatusLogin
    mensagem: str
    url_final: Optional[str] = None
```

Status esperados:

| Status | Significado |
|---|---|
| `sucesso` | Login feito e confirmado |
| `sessao_ativa` | A `Page` já estava autenticada |
| `credenciais_invalidas` | O AGHUX exibiu erro de usuário/senha |
| `timeout` | Login, erro ou tela esperada não foram confirmados no prazo |
| `erro` | Falha técnica do Playwright ou exceção inesperada |

### 5.2 Funções públicas

| Função | Responsabilidade |
|---|---|
| `autenticar_aghu_page(page, usuario, senha, ...)` | Autentica usando uma `Page` existente |
| `autenticar_aghu(usuario, senha, ...)` | Cria browser/context/page para teste isolado |
| `exigir_login_valido(resultado)` | Lança `RuntimeError` se o status não for `sucesso` ou `sessao_ativa` |
| `fazer_login(page, usuario_str, senha_str, ...)` | Wrapper legado sobre `autenticar_aghu_page` |

Contrato de `autenticar_aghu_page`:

| Item | Comportamento |
|---|---|
| Recursos Playwright | Não cria nem fecha browser, context ou page |
| URL | Faz `page.goto(url_login)` quando `url_login` é informado |
| Falhas esperadas | Retorna `ResultadoLogin`, não lança exceção |
| Usuário | Aplica `strip()` antes de autenticar |
| Senha | Não normaliza nem registra em log |

---

## 6. Componentes Internos

As funções iniciadas por `_` são privadas e não devem ser importadas por outros módulos.

| Função | Papel |
|---|---|
| `_url_atual` | Lê `page.url` com fallback para `None` |
| `_primeiro_visivel` | Retorna o primeiro locator visível dentre seletores candidatos |
| `_erro_autenticacao_visivel` | Detecta mensagem de credencial inválida |
| `_menu_principal_visivel` | Confirma presença de `Outros Módulos` |
| `_login_efetuado` | Confirma sessão ativa pela saudação ou pelo menu principal |
| `_tela_login_visivel` | Usa campo de senha como marcador de tela de login |
| `_preencher_credenciais` | Preenche usuário e senha |
| `_clicar_entrar` | Clica no botão **Entrar** por role ou fallback |

---

## 7. Contratos com Chamadores

| Chamador | Uso do autenticador |
|---|---|
| `PrinterAGHU.py` | Importa `AGHU_URL`, `autenticar_aghu_page` e `exigir_login_valido`; repassa `url_aghu` nos fluxos de login e Clean State |
| `AddPrinterAGHU.py` | Importa `autenticar_aghu_page` e `exigir_login_valido`; mantém login local apenas como compatibilidade |
| `ui_alignprinterAGHU.py` | Importa `AGHU_URL` e `AGHU_URL_HOMOLOGACAO` para montar o seletor de ambiente |
| `test_ui_autenticador.py` | Usa `URL_LOGIN_AGHU` e `autenticar_aghu` para teste manual de credenciais |

Nenhum chamador deve duplicar seletores de login, mensagem de erro ou regra de validação de sessão ativa.

---

## 8. Erros, Execução Direta e Operação

Saídas relevantes:

| Situação | Resultado |
|---|---|
| Usuário ou senha vazios | `status="erro"` |
| Página já autenticada | `status="sessao_ativa"` |
| Login confirmado | `status="sucesso"` |
| Credencial inválida | `status="credenciais_invalidas"` |
| Tela esperada não confirmada | `status="timeout"` |
| Erro do Playwright ou exceção inesperada | `status="erro"` |

Quando executado diretamente, o módulo lê `AGHU_USUARIO` e `AGHU_SENHA`, chama `autenticar_aghu(...)` com `headless=False` e imprime status, mensagem e URL final quando disponível.

Considerações operacionais:

1. `autenticar_aghu_page` não é dona dos recursos Playwright recebidos.
2. `autenticar_aghu` fecha os recursos que cria.
3. `url_login` pode ser vazio; nesse caso a função valida/autentica a página atual.
4. Senhas não são registradas em mensagens de retorno.

---

## 9. Limitações e Estado Atual

| Limitação | Impacto |
|---|---|
| Login depende de textos como `Olá,` e `Outros Módulos` | Mudanças no AGHUX podem causar timeout falso |
| Erro de credencial usa texto exato | Alteração da mensagem exige ajuste centralizado |
| Fallbacks de seletores são genéricos | Mudanças grandes no HTML podem exigir revisão dos seletores |
| `fazer_login` legado não recebe URL | Fluxos com ambiente selecionável devem preferir `autenticar_aghu_page` |

Esta RFC documenta o contrato atual de `autenticador.py`: autenticação centralizada, URLs compartilhadas, retorno padronizado por `ResultadoLogin` e integração com os robôs AGHUX sem acoplar regra de negócio ao login.
