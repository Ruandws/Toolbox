# RFC-002 — Robô Especialista de Cadastro de Impressoras (AddPrinterAGHU)

- **Status:** Estável
- **Autor:** Pedro e Ruan
- **Data:** 2026-06
- **Arquivo:** `AddPrinterAGHU.py`
- **Chamado por:** `PrinterAGHU.py` (RFC-001)

---

## 1. Resumo

`AddPrinterAGHU.py` é o **Robô Especialista (Almoxarifado)** responsável por cadastrar uma impressora no catálogo do AGHUX quando o Maestro (`PrinterAGHU.py`, RFC-001) detecta que a fila alvo não existe no autocomplete de impressoras do módulo **Impressora por Computador**.

O módulo consulta o servidor CUPS, extrai dados da fila encontrada, transforma descrição/localização para o formato esperado pelo AGHUX, navega até o cadastro de **Impressora** e grava o registro. Ele não é o orquestrador principal e não processa planilhas; sua função é exclusivamente abastecer o catálogo de impressoras para que o Maestro consiga concluir o vínculo.

A versão atual contém apenas funções reutilizáveis. Não há rotina `main`, função de teste independente ou `page.pause()` ativo no arquivo analisado.

---

## 2. Motivação

O Maestro opera sobre vínculos computador–impressora e pressupõe que a impressora alvo exista no AGHUX. Quando essa premissa falha, abortar a linha exigiria intervenção manual e quebraria a continuidade da automação. O Almoxarifado isola a responsabilidade de criar a impressora, mantendo o Maestro focado no vínculo.

Essa separação reduz o risco de misturar duas telas distintas do AGHUX: **Impressora por Computador**, usada para vínculos, e **Impressora**, usada para o cadastro mestre da fila.

---

## 3. Arquitetura e Fluxo de Dados

```text
[PrinterAGHU.py / Maestro]
        │
        └─► Captura ValueError("Impressora não existe")
              │
              └─► [Até 3 tentativas no Maestro]
                    │
                    ├─► consultar_dados_site_secundario(context, impressora, classe)
                    │        ├─ Abre nova aba no mesmo BrowserContext
                    │        ├─ Acessa https://10.6.0.121:631/printers/
                    │        ├─ Busca a fila em input[name='QUERY']
                    │        ├─ Se não encontrar → ValueError("Não existe no CUPS")
                    │        ├─ Extrai fila, descrição e localização da tabela
                    │        ├─ Extrai IP da descrição via regex
                    │        └─ Retorna dict com dados do AGHUX
                    │
                    ├─► navegar_ate_cadastro_impressora(page_aghu)
                    │        ├─ Outros Módulos → Configuração → Impressão → Cadastros
                    │        ├─ Abre o módulo "Impressora"
                    │        ├─ Usa retry com reload em falha inicial
                    │        └─ Retorna janela_sistema do iframe
                    │
                    └─► cadastrar_nova_impressora(janela_sistema, dados)
                             ├─ Pesquisa fila no AGHUX
                             ├─ Se já existir → retorna sem duplicar
                             ├─ Se não existir → clica "Novo"
                             ├─ Preenche fila, tipo, tipo CUPS, servidor, descrição, localização
                             └─ Grava e aguarda retorno à tela de pesquisa
```

---

## 4. Descrição dos Componentes

### 4.1 `fazer_login`

Função idempotente de autenticação para uso quando o Almoxarifado for chamado em uma página que ainda exige login. Detecta a tela procurando primeiro um campo de usuário (`input[type='text']`, `input[id*='usuario']`, `input[id*='login']`). Se o campo aparecer, preenche usuário e senha, clica em **Entrar** e aguarda **Outros Módulos**.

Se a tela de login não aparecer no timeout de 3 segundos, captura a exceção e segue, assumindo sessão ativa. No fluxo normal do Maestro, essa função não é chamada diretamente; o Maestro gerencia login e entrega ao Almoxarifado uma página já autenticada ou recém-recriada por Clean State.

### 4.2 `consultar_dados_site_secundario` — Pipeline ETL

Abre uma nova aba dentro do mesmo `BrowserContext` e acessa o CUPS em:

```text
https://10.6.0.121:631/printers/
```

A busca usa seletores de atributo, não texto visível:

| Elemento | Seletor | Motivo |
|---|---|---|
| Campo de busca | `input[name='QUERY']` | Independente de idioma |
| Botão de busca | `input[type='submit' i], input[type='SUBMIT']` | Aceita variação de caixa e idioma |

Após a busca, localiza a primeira linha de tabela contendo `impressora_alvo`. Se não houver linha visível em até 5 segundos, fecha a aba do CUPS e lança `ValueError("Não existe no CUPS")`.

Quando a linha é encontrada, extrai três colunas:

| Coluna CUPS | Variável | Uso |
|---|---|---|
| `td[0]` | `cups_queue` | Fila da impressora |
| `td[1]` | `cups_desc` | Descrição, normalmente contendo IP |
| `td[2]` | `cups_loc` | Localização |

Transformação aplicada:

```text
match_ip = re.search(r'\b\d{1,3}(?:\.\d{1,3}){3}\b', cups_desc)
```

Se houver IP, remove o IP da descrição e limpa resíduos de hífen/espaço. Se não houver, usa `IP NÃO REGISTRADO` como fallback. Em seguida monta:

| Campo gerado | Regra |
|---|---|
| `fila` | `cups_queue` |
| `classe` | Parâmetro `classe_impressora` recebido do Maestro |
| `descricao_aghux` | `cups_loc + " - " + cups_desc_sem_ip`, com limpeza de hífens |
| `localizacao_aghux` | `descricao_aghux + "\n" + ip_encontrado` |

A aba do CUPS é fechada antes do retorno em caso de sucesso.

### 4.3 `navegar_ate_cadastro_impressora`

Navega no AGHUX até o cadastro mestre de impressoras:

```text
Outros Módulos → Configuração → Impressão → Cadastros → Impressora
```

O destino final é **Impressora**, não **Impressora por Computador**. Essa distinção é crítica: o Almoxarifado cadastra a fila no catálogo; o Maestro cadastra ou altera vínculos.

A função verifica a visibilidade dos níveis de menu antes de clicar. Ao abrir o módulo, usa `page_aghu.frame_locator("iframe").last` e valida o carregamento pelo botão **Pesquisar**. Se falhar na primeira tentativa, executa `page_aghu.reload()`, aguarda 3 segundos e tenta novamente. Na segunda falha, propaga a exceção.

### 4.4 `cadastrar_nova_impressora`

Recebe `janela_sistema` e o dicionário produzido por `consultar_dados_site_secundario`. O cadastro segue nove etapas:

1. Pesquisa a fila no campo `input[id*='fila' i]`.
2. Aguarda `Nenhum registro encontrado!` para confirmar ausência no AGHUX.
3. Se a impressora já aparecer na tabela, retorna sem criar duplicata.
4. Clica **Novo** e aguarda **Gravar**.
5. Preenche a fila.
6. Seleciona **Tipo da Impressora**.
7. Seleciona **Tipo do Cups**.
8. Seleciona o servidor CUPS e preenche descrição/localização.
9. Clica **Gravar** e aguarda retorno à tela de pesquisa.

Regra de negócio para tipo da impressora:

| `PrinterClass` recebido | Tipo da Impressora no AGHUX |
|---|---|
| `PDF` | `Laser PCL` |
| Qualquer outro valor | `Cod. Barras` |

Regra para **Tipo do Cups**: seleciona exatamente a classe recebida no parâmetro `classe_impressora`.

Seleção do servidor CUPS:

```text
tr, li
  has_text("10.6.0.121")
  has_text("CUPS")
  has_not_text("HOMOLOGAÇÃO")
```

Esse filtro evita selecionar o servidor de homologação quando houver múltiplas opções semelhantes.

---

## 5. Relação com o Maestro (RFC-001)

O Maestro importa diretamente três funções públicas deste módulo:

```python
from AddPrinterAGHU import (
    cadastrar_nova_impressora,
    consultar_dados_site_secundario,
    navegar_ate_cadastro_impressora,
)
```

No fluxo atual, `PrinterAGHU.py` não importa nem chama `fazer_login` deste arquivo. O login é feito pelo próprio Maestro por meio de `fazer_login` local e `trocar_aba_aghux`.

Contrato operacional entre RFC-001 e RFC-002:

| Evento | Origem | Quem interpreta |
|---|---|---|
| `ValueError("Impressora não existe")` | Maestro, ao não achar a impressora no AGHUX | Maestro inicia Almoxarifado |
| `ValueError("Não existe no CUPS")` | Almoxarifado, ao não achar fila no CUPS | Maestro registra `Inexistente` |
| Retorno silencioso de `cadastrar_nova_impressora` | Impressora já existia no AGHUX | Maestro continua tentativa de vínculo |
| Cadastro bem-sucedido | Almoxarifado | Maestro abre aba limpa e reprocessa linha |

Fluxo resumido no Maestro:

```text
Impressora não existe no autocomplete AGHUX
        │
        └─► page = trocar_aba_aghux(...)
            dados_cups = consultar_dados_site_secundario(...)
            janela = navegar_ate_cadastro_impressora(page)
            cadastrar_nova_impressora(janela, dados_cups)
            page = trocar_aba_aghux(...)
            navegar_ate_modulo(...)
            reprocessar linha
```

---

## 6. Decisões Técnicas

### 6.1 Por que abrir o CUPS em nova aba e não novo contexto?

`context.new_page()` reaproveita o `BrowserContext` criado pelo chamador. Isso mantém configurações como `ignore_https_errors=True`, necessária para acessar ambientes internos com certificado não confiável pelo navegador.

### 6.2 Por que seletores de atributo no CUPS em vez de texto visível?

A interface do CUPS pode variar entre português e inglês. Seletores como `input[name='QUERY']` e `input[type='submit']` são mais estáveis do que `get_by_text("Pesquisar")` ou `get_by_text("Search")`.

### 6.3 Por que extrair o IP por regex?

A descrição do CUPS pode conter o IP embutido junto a informações livres. A regex localiza o primeiro IPv4, separa o IP do texto descritivo e permite preencher a localização do AGHUX em duas linhas: descrição humana e IP.

### 6.4 Por que pesquisar antes de clicar em "Novo"?

A pesquisa prévia cumpre duas funções: habilita o fluxo de criação no AGHUX e evita duplicidade. Se a fila já existir, a função retorna e não executa nova gravação.

### 6.5 Por que filtros encadeados no servidor CUPS?

O filtro por IP, nome `CUPS` e exclusão de `HOMOLOGAÇÃO` reduz o risco de selecionar servidor errado em uma lista JSF com linhas ou itens visualmente semelhantes.

---

## 7. Tratamento de Erros

| Situação | Comportamento |
|---|---|
| Tela de login ausente | Captura exceção e segue, assumindo sessão ativa |
| Campo de busca do CUPS indisponível | Propaga exceção ao Maestro |
| Impressora não encontrada no CUPS | Fecha aba do CUPS e lança `ValueError("Não existe no CUPS")` |
| Linha encontrada no CUPS | Extrai dados e fecha aba ao final |
| Menu do AGHUX travado | `page.reload()` + uma nova tentativa |
| Impressora já cadastrada no AGHUX | Retorno silencioso, sem duplicar cadastro |
| Dropdown semântico falha | Fallback posicional (`nth(0)` ou `nth(1)`) |
| Servidor de homologação aparece na lista | Excluído por `has_not_text="HOMOLOGAÇÃO"` |
| Falha no preenchimento ou gravação | Propaga exceção para o Maestro, que decide retry/status |

---

## 8. Limitações Conhecidas

- URL e IP do CUPS (`10.6.0.121`) estão hardcoded na navegação e na seleção do servidor.
- A função `fazer_login` está duplicada em relação ao Maestro, com estratégia de detecção diferente.
- O contrato de inexistência no CUPS depende da string exata `"Não existe no CUPS"`.
- Se ocorrer exceção depois da abertura da aba do CUPS e antes do fechamento explícito, a aba pode permanecer aberta até o contexto ser encerrado pelo chamador.
- O seletor da linha de resultado usa `has_text=impressora_alvo`, o que pode aceitar correspondência parcial se houver filas com nomes muito semelhantes.
- Os dropdowns JSF ainda possuem fallback posicional, sensível à alteração de ordem dos campos no formulário.
- A regra de tipo da impressora trata tudo que não for `PDF` como `Cod. Barras`; não há validação explícita para classes inesperadas.
- O módulo não tem execução independente controlada por `if __name__ == "__main__"`; depende de chamada externa.
- Há `except:` genéricos, o que reduz granularidade diagnóstica.

---

## 9. Alterações Futuras Consideradas

- Centralizar URL/IP do CUPS em arquivo de configuração ou variável de ambiente.
- Unificar `fazer_login` com o Maestro em módulo compartilhado.
- Criar exceções tipadas para `FilaNaoExisteNoCUPS`, `CadastroDuplicado` e falhas de navegação.
- Garantir fechamento da aba do CUPS com `try/finally`.
- Trocar busca textual da fila por comparação exata da primeira coluna quando possível.
- Substituir fallbacks posicionais por seletores estáveis do HTML do AGHUX.
- Validar explicitamente `PrinterClass` antes de selecionar tipo da impressora.
- Substituir `print()` por `logging` estruturado.
