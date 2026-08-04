# RFC-002 — Robô Especialista de Cadastro de Impressoras (AddPrinterAGHU)

- **Status:** Estável
- **Autor:** Pedro e Ruan
- **Data:** 2026-06
- **Atualizado em:** 2026-06-19
- **Arquivo:** `AddPrinterAGHU.py`
- **Depende de:** `autenticador.py`
- **Depende de:** `menu.py` (RFC-004)
- **Chamado por:** `PrinterAGHU.py` (RFC-001)

---

## 1. Resumo

`AddPrinterAGHU.py` é o **Robô Especialista** responsável por cadastrar uma impressora no catálogo do AGHUX quando o Maestro (`PrinterAGHU.py`, RFC-001) detecta que a fila alvo não existe no autocomplete de impressoras do módulo **Impressora por Computador**.

O módulo consulta o servidor CUPS, extrai dados da fila encontrada, transforma descrição/localização para o formato esperado pelo AGHUX, navega até o cadastro mestre de **Impressora** e grava o registro. Ele não processa planilhas e não decide vínculos computador–impressora; sua função é abastecer o catálogo para que o Maestro consiga concluir o vínculo.

A autenticação foi centralizada em `autenticador.py`. Portanto, o `fazer_login` local deste módulo é apenas um wrapper de compatibilidade e não contém mais lógica própria de seleção de campos de login.

---

## 2. Mudanças incorporadas nesta revisão

| Área | Situação atual |
|---|---|
| Autenticação | `fazer_login` usa `autenticar_aghu_page` e `exigir_login_valido` de `autenticador.py` |
| Uso pelo Maestro | `PrinterAGHU.py` importa somente `consultar_dados_site_secundario`, `navegar_ate_cadastro_impressora` e `cadastrar_nova_impressora` |
| CUPS | Consulta `https://10.6.0.121:631/printers/` em nova aba do mesmo contexto |
| Busca CUPS | Usa `input[name='QUERY']` e submit por atributo, independentes de idioma visível |
| Transformação | Extrai IP da descrição via regex e monta `descricao_aghux` e `localizacao_aghux` |
| Navegação | Usa `navegar_menu_aghu` de `menu.py` (RFC-004) com caminho local `CAMINHO_MENU_CADASTRO_IMPRESSORA` |
| Cadastro AGHUX | Seleciona tipo da impressora, tipo do CUPS, servidor CUPS, descrição e localização |
| Anti-homologação | Seleção do servidor exclui item que contenha `HOMOLOGAÇÃO` |

---

## 3. Motivação

O Maestro opera sobre vínculos computador–impressora e pressupõe que a impressora alvo exista no catálogo do AGHUX. Quando essa premissa falha, abortar a linha exigiria intervenção manual e quebraria a continuidade da automação.

O Robô Especialista isola a responsabilidade de criar a impressora no cadastro mestre. Isso evita misturar duas telas distintas do AGHUX:

| Tela | Responsabilidade |
|---|---|
| **Impressora por Computador** | Criar, manter ou alterar vínculos entre computador e impressora |
| **Impressora** | Cadastrar a fila da impressora no catálogo do AGHUX |

---

## 4. Arquitetura e Fluxo de Dados

```text
[PrinterAGHU.py / Maestro]
        │
        └─► Captura ValueError("Impressora não existe")
              │
              └─► [Até 3 tentativas no Maestro]
                    │
                    ├─► trocar_aba_aghux(...)
                    │
                    ├─► consultar_dados_site_secundario(context, impressora, classe)
                    │        ├─ Abre nova aba no mesmo BrowserContext
                    │        ├─ Acessa servidor CUPS
                    │        ├─ Busca a fila em input[name='QUERY']
                    │        ├─ Se não encontrar → ValueError("Não existe no CUPS")
                    │        ├─ Extrai fila, descrição e localização da tabela
                    │        ├─ Extrai IP da descrição via regex
                    │        └─ Retorna dict com dados formatados para AGHUX
                    │
                    ├─► navegar_ate_cadastro_impressora(page_aghu)
                    │        ├─ Outros Módulos → Configuração → Impressão → Cadastros
                    │        ├─ Abre o módulo "Impressora"
                    │        ├─ Valida tela pelo botão "Pesquisar" no último iframe
                    │        ├─ Usa retry com reload em falha inicial
                    │        └─ Retorna janela_sistema do último iframe
                    │
                    └─► cadastrar_nova_impressora(janela_sistema, dados)
                             ├─ Pesquisa fila no AGHUX
                             ├─ Se já existir → retorna sem duplicar
                             ├─ Se não existir → clica "Novo"
                             ├─ Preenche fila, tipo, tipo CUPS, servidor, descrição e localização
                             └─ Grava e aguarda retorno à tela de pesquisa
```

---

## 5. Dependências

### 5.1 `autenticador.py`

O módulo importa:

```python
from autenticador import autenticar_aghu_page, exigir_login_valido
```

A função `fazer_login` local existe para compatibilidade e execução isolada eventual, mas o fluxo atual do Maestro não a importa. O Maestro já entrega uma página autenticada ou recriada por Clean State.

Contrato de autenticação:

| Item | Responsabilidade |
|---|---|
| `autenticar_aghu_page` | Tenta autenticar usando uma `Page` existente |
| `exigir_login_valido` | Interrompe o fluxo se o login não for `sucesso` ou `sessao_ativa` |

O módulo não deve manter seletores próprios para usuário, senha, botão **Entrar**, mensagem de credencial inválida ou confirmação de sessão ativa.

### 5.2 `menu.py`

O módulo importa:

```python
from menu import navegar_menu_aghu
```

| Item | Responsabilidade |
|---|---|
| `navegar_menu_aghu` | Percorre o caminho completo informado, clica no item final e retorna o último iframe |

A navegação até o cadastro mestre de impressoras é delegada a `navegar_menu_aghu` (RFC-004), que percorre o caminho completo informado pelo chamador e retorna o último iframe. O Almoxarifado declara localmente `CAMINHO_MENU_CADASTRO_IMPRESSORA` e valida a tela final aguardando o botão **Pesquisar**.

---

## 6. Constantes de Módulo

| Constante | Valor | Uso |
|---|---|---|
| `CAMINHO_MENU_CADASTRO_IMPRESSORA` | `("Outros Módulos", "Configuração", "Impressão", "Cadastros", "Impressora")` | Caminho completo usado por `navegar_ate_cadastro_impressora` para abrir o módulo de cadastro mestre de impressoras |

---

## 7. Funções Auxiliares Privadas

Não aplicável: módulo não define funções privadas com prefixo `_`.

---

## 8. Descrição dos Componentes Públicos

### 8.1 `fazer_login(page_aghu, usuario_str, senha_str)`

Wrapper de autenticação centralizada.

Fluxo:

1. Imprime `Checando autenticação no AGHUX.`.
2. Chama `autenticar_aghu_page(page=page_aghu, usuario=usuario_str, senha=senha_str, timeout_ms=15000)`.
3. Imprime mensagem conforme status:
   - `sessao_ativa`: sessão já estava ativa;
   - `sucesso`: login efetuado com sucesso;
   - demais status: falha de autenticação.
4. Chama `exigir_login_valido(resultado)`.
5. Retorna o resultado.

Essa função não é o mecanismo principal no fluxo Maestro → Almoxarifado, mas permanece disponível para reaproveitamento.

### 8.2 `consultar_dados_site_secundario(context, impressora_alvo, classe_impressora)`

Abre uma nova aba dentro do mesmo `BrowserContext` e acessa:

```text
https://10.6.0.121:631/printers/
```

A busca no CUPS usa seletores por atributo:

| Elemento | Seletor | Motivo |
|---|---|---|
| Campo de busca | `input[name='QUERY']` | Independente de idioma da interface |
| Botão de busca | `input[type='submit' i], input[type='SUBMIT']` | Aceita variação de caixa e texto visível |

Após o submit, localiza a primeira linha de tabela contendo `impressora_alvo`:

```python
linha_resultado = page_cups.get_by_role("row").filter(has_text=impressora_alvo).first
```

Se não houver linha visível em até 5 segundos:

1. Fecha a aba do CUPS.
2. Lança `ValueError("Não existe no CUPS")`.

Quando a linha é encontrada, extrai:

| Coluna CUPS | Variável | Uso |
|---|---|---|
| `td[0]` | `cups_queue` | Fila da impressora |
| `td[1]` | `cups_desc` | Descrição, normalmente contendo IP |
| `td[2]` | `cups_loc` | Localização |

A aba do CUPS é fechada antes do retorno em caso de sucesso.

### 8.3 `navegar_ate_cadastro_impressora(page_aghu)`

Navega no AGHUX até o cadastro mestre de impressoras usando `CAMINHO_MENU_CADASTRO_IMPRESSORA` (ver §6):

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

`navegar_menu_aghu` percorre o caminho informado, verifica visibilidade de cada nível e retorna o último iframe. A validação de carregamento da tela pelo botão **Pesquisar** pertence ao Almoxarifado.

A função faz até duas tentativas:

| Tentativa | Ação em falha |
|---|---|
| 1ª | `page_aghu.reload()` + espera de 3 segundos |
| 2ª | Propaga a exceção |

### 8.4 `cadastrar_nova_impressora(janela_sistema, dados)`

Recebe o iframe do cadastro de impressoras e o dicionário gerado pelo CUPS.

Etapas:

1. Pesquisa a fila no campo `input[id*='fila' i]`.
2. Clica em **Pesquisar**.
3. Aguarda `Nenhum registro encontrado!` para confirmar ausência no AGHUX.
4. Se a fila já aparecer na tabela, retorna sem criar duplicata.
5. Clica em **Novo**.
6. Aguarda botão **Gravar**.
7. Preenche a fila.
8. Seleciona **Tipo da Impressora**.
9. Seleciona **Tipo do CUPS**.
10. Seleciona servidor CUPS.
11. Preenche descrição.
12. Preenche localização multilinha.
13. Clica em **Gravar**.
14. Aguarda retorno à tela com botão **Pesquisar**.

---

## 9. Regras de Processamento

### 9.1 Tipo da Impressora

| `dados['classe']` | Tipo da Impressora |
|---|---|
| `PDF` | `Laser PCL` |
| Qualquer outro valor | `Cod. Barras` |

A seleção tenta primeiro usar seletor associado ao label `Tipo da Impressora`. Se falhar, usa fallback para o primeiro `div.ui-selectonemenu-trigger`.

### 9.2 Tipo do CUPS

```text
Tipo do Cups = dados['classe']
```

A seleção tenta primeiro usar seletor associado ao label `Tipo do Cups`. Se falhar, usa fallback para o segundo `div.ui-selectonemenu-trigger` e busca por `li, td` contendo a classe.

### 9.3 Seleção do Servidor CUPS

O servidor é selecionado pela lupa/autocomplete:

```python
button.ui-autocomplete-dropdown:has(.ui-icon-triangle-1-s)
```

O item selecionado precisa conter:

```text
10.6.0.121
CUPS
```

E não pode conter:

```text
HOMOLOGAÇÃO
```

### 9.4 Transformação de dados CUPS → AGHUX

O IP é extraído da descrição com:

```python
match_ip = re.search(r'\b\d{1,3}(?:\.\d{1,3}){3}\b', cups_desc)
```

Se houver IP:

| Campo | Regra |
|---|---|
| `ip_encontrado` | IP capturado pela regex |
| `extra_info` | `cups_desc` sem o IP, limpo de hífens e espaços residuais |

Se não houver IP:

| Campo | Regra |
|---|---|
| `ip_encontrado` | `IP NÃO REGISTRADO` |
| `extra_info` | Descrição original do CUPS |

Campos finais montados para o AGHUX:

| Campo | Regra |
|---|---|
| `fila` | `cups_queue` |
| `classe` | `classe_impressora` recebido do Maestro |
| `descricao_aghux` | `<cups_loc> - <extra_info>`, com limpeza de hífens |
| `localizacao_aghux` | `<descricao_aghux>\n<ip_encontrado>` |

### 9.5 Descrição e localização no AGHUX

| Campo AGHUX | Seletor | Valor |
|---|---|---|
| Descrição | `input[id*='descricao' i]` | `dados['descricao_aghux']` |
| Localização | `textarea[id*='localizacao' i]` | `dados['localizacao_aghux']` |

A localização pode conter múltiplas linhas, pois inclui a descrição formatada e o IP em linha separada.

---

## 10. API Pública do Módulo

| Função | Responsabilidade |
|---|---|
| `fazer_login(page_aghu, usuario_str, senha_str)` | Wrapper de login centralizado; uso compatível/isolado |
| `consultar_dados_site_secundario(context, impressora_alvo, classe_impressora)` | Consulta CUPS e transforma dados para o AGHUX |
| `navegar_ate_cadastro_impressora(page_aghu)` | Abre o módulo mestre **Impressora** |
| `cadastrar_nova_impressora(janela_sistema, dados)` | Cria a impressora no AGHUX se ela ainda não existir |

---

## 11. Recuperação de Falhas Técnicas

| Situação | Saída |
|---|---|
| Fila não encontrada no CUPS | `ValueError("Não existe no CUPS")` |
| Impressora já existe no AGHUX | Retorno silencioso, sem duplicar cadastro |
| Falha de navegação no cadastro na primeira tentativa | Reload e nova tentativa |
| Falha de navegação no cadastro na segunda tentativa | Exceção propagada ao Maestro |
| Falha ao selecionar servidor/tipo/campos | Exceção propagada ao Maestro |

#### Lógica de retry em `navegar_ate_cadastro_impressora`

A função implementa um ciclo de até duas tentativas para lidar com instabilidades de carregamento do menu do AGHUX:

| Tentativa | Ação em caso de falha |
|---|---|
| 1ª | Executa `page_aghu.reload()`, aguarda 3 segundos e repete a navegação via `navegar_menu_aghu` |
| 2ª | Propaga a exceção para o Maestro, que contabiliza como falha técnica e aciona seu próprio ciclo de retry (Clean State + nova tentativa) |

O reload é usado em vez de Clean State porque o Almoxarifado não possui acesso ao `BrowserContext` neste ponto — ele recebe apenas a `Page` do AGHUX já preparada pelo Maestro. A exceção propagada na 2ª tentativa é, portanto, o mecanismo de escalada para que o Maestro decida abrir aba limpa.

---

## 12. Contratos entre RFCs

### 12.1 Contrato com RFC-001

O Maestro importa diretamente:

```python
from AddPrinterAGHU import (
    cadastrar_nova_impressora,
    consultar_dados_site_secundario,
    navegar_ate_cadastro_impressora,
)
```

No fluxo atual, o Maestro não importa `fazer_login` deste arquivo. A reautenticação é feita pelo próprio Maestro via `trocar_aba_aghux`, que usa `autenticador.py`.

Eventos de contrato:

| Evento | Origem | Quem interpreta |
|---|---|---|
| `ValueError("Impressora não existe")` | Maestro, ao não achar a impressora no AGHUX | Maestro inicia Almoxarifado |
| `ValueError("Não existe no CUPS")` | Almoxarifado, ao não achar fila no CUPS | Maestro registra `Inexistente` |
| Retorno silencioso de `cadastrar_nova_impressora` | Impressora já existia no AGHUX | Maestro continua tentativa de vínculo |
| Cadastro bem-sucedido | Almoxarifado | Maestro abre aba limpa e reprocessa a linha |

---

## 13. Considerações Operacionais

1. O módulo abre uma aba nova para o CUPS e fecha essa aba ao final da consulta.
2. O módulo assume que o `BrowserContext` já foi criado com as permissões e opções necessárias pelo chamador.
3. O módulo assume que a `Page` do AGHUX já está autenticada quando o Maestro chama `navegar_ate_cadastro_impressora`.
4. `fazer_login` existe, mas não é usado no caminho principal Maestro → Almoxarifado.
5. A seleção do servidor CUPS contém filtro anti-homologação e não deve ser relaxada sem validação operacional.
6. A string `Não existe no CUPS` faz parte do contrato com RFC-001.

---

## 14. Limitações Conhecidas

| Limitação | Impacto |
|---|---|
| Busca no CUPS filtra por texto da fila na linha | Nomes ambíguos podem exigir refinamento futuro |
| Regex de IP não valida faixa 0–255 | Captura padrão IPv4 textual, não valida semanticamente cada octeto |
| Cadastro depende de labels e componentes JSF do AGHUX | Mudanças de tela podem quebrar seletores |
| `cadastrar_nova_impressora` retorna sem indicar explicitamente se criou ou já existia | O Maestro trata ambos como sucesso operacional e tenta vincular novamente |

---

## 15. Estado Atual da RFC

Esta RFC passa a refletir o código atual de `AddPrinterAGHU.py`, incluindo o login centralizado por `autenticador.py`, o contrato real usado pelo Maestro, a consulta CUPS por seletores de atributo, a transformação de dados para o AGHUX e o cadastro com proteção anti-homologação.
