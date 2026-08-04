# RFC-006 — Concessão de Perfis de Acesso a Usuários no AGHUX (concessor_aghu)

- **Status:** Estável
- **Autor:** Ruan
- **Data:** 2026-07
- **Atualizado em:** 2026-08-04
- **Arquivo:** `concessor_aghu.py`
- **Depende de:** `autenticador.py` (RFC-005)
- **Depende de:** `menu.py` (RFC-004)
- **Chamado por:** `ui_concessor.py` (mesma RFC, seção 13)

---

## 1. Resumo

`concessor_aghu.py` automatiza a concessão de perfis de acesso a usuários no módulo **Acesso → Usuario** do AGHUX. Ele lê uma regra de negócio (catálogo de perfis por escopo/categoria, hoje mantido em `docs/regras_perfis_aghu.yaml`), decide quais perfis podem ser concedidos automaticamente, autentica a sessão pelo autenticador central, navega até o cadastro de usuário, pesquisa o usuário alvo, abre a aba de perfis e adiciona cada perfil elegível via autocomplete, gravando o protocolo de autorização em cada item.

O módulo suporta duas formas de execução: **individual** (uma ou poucas concessões informadas diretamente) e **em lote** (planilha `.xlsx` com várias linhas). `ui_concessor.py` é a interface gráfica (CustomTkinter) que expõe as duas formas ao operador, sempre chamando as funções públicas deste módulo — a UI não contém lógica de negócio própria além de validação de formulário e organização de estado de tela.

Diferente do par Maestro/Almoxarifado de impressoras (RFC-001/RFC-002), aqui não há delegação entre dois robôs: existe um único fluxo, com uma camada de regras (catálogo YAML) que decide o que é seguro automatizar e o que exige validação humana.

---

## 2. Mudanças incorporadas nesta revisão

Esta revisão atualiza a RFC para refletir o refatoramento recente do módulo e reestruturar o documento segundo os padrões da arquitetura AGHUX (RFC-001):

| Área | Alteração | Justificativa |
|---|---|---|
| Checagem de Perfis | Remoção de `_checagem_final_perfis` (commit `eefa1b2`) | Eliminar o retry pós-gravação, alinhando com a ausência de reconferência após `_gravar_perfis` |
| Componentes Públicos | Consolidação das seções de preparação, validação, planilha, fluxo, navegação e concessão sob "Descrição dos Componentes Públicos" | Padronização estrutural com a RFC-001 |
| Funções Auxiliares Privadas | Mapeamento completo dos auxiliares (`_normalizar_*`, `_parse_*`, Playwright) posicionado antes do fechamento do documento | Documentar rotinas internas na seção 17, respeitando a convenção de fechamento |
| Dependências | Reorganização da seção de dependências em subseções estruturadas com tabelas Item \| Responsabilidade | Padronizar com RFC-001/RFC-005 |
| Contratos entre RFCs | Inclusão explícita dos contratos com RFC-004 (`menu.py`) e RFC-005 (`autenticador.py`) | Esclarecer delegações de menu e autenticação centralizada |
| Navegabilidade | Reordenação da seção "Estado Atual da RFC" como a seção final (seção 18) | Manter "Estado Atual da RFC" como encerramento definitivo do documento |

---

## 3. Motivação

Conceder perfis de acesso no AGHUX é uma tarefa sensível: perfis existem aos dezenas, alguns são críticos (acesso administrativo, evolução de prontuário) e não devem ser concedidos sem correta alçada, outros dependem de autorização externa (Unidade de Regulação Assistencial / Setor de Contratualização e Regulação). Automatizar a digitação sem uma camada de regra correria o risco de conceder o perfil errado com base apenas na entrada do operador.

`concessor_aghu.py` resolve isso separando duas responsabilidades:

1. **Regra de negócio** (`CatalogoPerfis`, carregado de YAML): decide, para cada par escopo/categoria, quais perfis são concedidos automaticamente, quais são bloqueados globalmente e quais exigem validação externa antes de qualquer ação no navegador.
2. **Execução mecânica** (Playwright): dado um conjunto de perfis já aprovados pela regra, realiza a navegação, pesquisa e gravação no AGHUX.

Essa separação permite que a política de perfis (o que pode ser automatizado) evolua no arquivo YAML sem alterar código, e garante que perfis críticos ou sujeitos a validação externa nunca chegam à etapa de automação no navegador — eles são filtrados antes de qualquer interação com a tela.

Até esta RFC, o módulo estava em produção sem RFC própria, violando o item 6 do `Guia_AGHU.md` ("toda função pública usada por outro módulo deve constar na seção API Pública da RFC correspondente"). Esta RFC fecha essa lacuna.

---

## 4. Arquitetura e Fluxo de Dados

```text
[ui_concessor.py]
        │
        ├─► carregar_catalogo_regras()               (ao abrir a tela)
        │
        ├─► executar_concessoes_perfis(...)           (execução unitária, até 5 linhas)
        │        ou
        ├─► executar_concessao_lote(...)              (execução em lote via planilha)
        │
        └────────────────────────────────────────────────────────────
                             │
                             ▼
        _executar_concessoes_perfis_com_saida_configurada(...)
                             │
                ┌────────────┴─────────────┐
                │                           │
        carregar_catalogo_regras    _preparar_concessoes_lote
                │                           │
                │                 preparar_concessao() por linha
                │                 ├─ valida entrada (login/protocolo/escopo/categoria)
                │                 ├─ obter_regra(escopo, categoria)
                │                 ├─ separa perfis em:
                │                 │    ├─ bloqueados (regra + globais)      → nunca abrem browser
                │                 │    ├─ validação URA/STCOR (regra + globais) → nunca abrem browser
                │                 │    └─ perfis_automatizados              → únicos que geram ação
                │                 └─ linhas sem nenhum perfil automatizável
                │                      são resolvidas SEM abrir Playwright
                │
                ▼ (somente se existir ao menos 1 perfil automatizável em alguma linha)
        sync_playwright() → browser → context → page
                │
                ├─► page.goto(url_aghu)
                ├─► fazer_login(page, usuario_rede, senha, url_aghu=url_aghu)
                │        └─ autenticar_aghu_page(...) em autenticador.py
                │
                ├─► navegar_ate_cadastro_usuario(...)
                │        └─ navegar_menu_aghu(caminho=CAMINHO_MENU_CADASTRO_USUARIO)  (RFC-004)
                │
                └─► processar_concessoes(...) — para cada linha preparada:
                         │
                         ├─ garantir_tela_pesquisa_usuario(...)      (idempotente / Clean State)
                         ├─ _pesquisar_usuario(login)                 → encontrado / nao_encontrado / sem_login_exato / indefinido
                         ├─ _clicar_editar_usuario(linha_usuario)
                         ├─ _abrir_aba_perfis_usuario(...)            → FrameLocator de perfis
                         └─ _conceder_perfis_na_tela(...)              → adiciona cada perfil elegível + Gravar
                             │
                             ▼
                gerar_csv_logs(...) + (lote) salvar_relatorio_resultados(...)
```

---

## 5. Dependências

### 5.1 `autenticador.py` (RFC-005)

`concessor_aghu.py` importa:

```python
from autenticador import AGHU_URL, autenticar_aghu_page, exigir_login_valido
```

Responsabilidades delegadas ao autenticador:

| Item | Responsabilidade |
|---|---|
| `AGHU_URL` | URL padrão do AGHUX, com override por variáveis de ambiente; usada como default quando o chamador não fornece `url_aghu` |
| `autenticar_aghu_page` | Autentica usando uma `Page` existente, sem criar ou fechar browser/context/page |
| `exigir_login_valido` | Lança erro se o resultado de login não for `sucesso` ou `sessao_ativa` |

### 5.2 `menu.py` (RFC-004)

`concessor_aghu.py` importa:

```python
from menu import navegar_menu_aghu
```

Responsabilidades delegadas ao `menu.py`:

| Item | Responsabilidade |
|---|---|
| `navegar_menu_aghu` | Percorre o caminho `CAMINHO_MENU_CADASTRO_USUARIO` (`("Outros Módulos", "Configuração", "Acesso", "Usuario")`) e retorna o `FrameLocator` do último iframe |

### 5.3 Bibliotecas de Terceiros e Módulos Externos

| Dependência | Responsabilidade / Uso |
|---|---|
| `pandas` + `openpyxl` | Leitura da planilha de lote e geração do relatório `.xlsx` |
| `playwright.sync_api` | Automação de navegador (síncrona) |
| `yaml` (opcional) | Leitura do catálogo de regras; se ausente, usa parser de fallback próprio (seção 8.2) |

`concessor_aghu.py` não importa `AddPrinterAGHU.py` nem `PrinterAGHU.py` — não há relação de dependência com o domínio de impressoras. `ui_concessor.py` importa apenas de `autenticador.py` e `concessor_aghu.py`.

---

## 6. Constantes de Módulo

| Constante | Valor / Origem | Uso |
|---|---|---|
| `BASE_DIR` | `Path(__file__).resolve().parent` | Base para `LOGS_DIR` |
| `PROJECT_DIR` | `BASE_DIR.parents[1]` | Raiz do repositório |
| `REGRAS_PADRAO` | `PROJECT_DIR / "docs" / "regras_perfis_aghu.yaml"` | Caminho padrão do catálogo de regras |
| `LOGS_DIR` | `BASE_DIR / "logs"` | Diretório padrão do CSV de auditoria; também importado por `ui_concessor.py` |
| `CAMINHO_MENU_CADASTRO_USUARIO` | `("Outros Módulos", "Configuração", "Acesso", "Usuario")` | Caminho passado a `navegar_menu_aghu` |
| `SELECTOR_PESQUISA_LOGIN` | `'[id="nomeOuLogin:nomeOuLogin:inputId"]'` | Campo de pesquisa por login/nome |
| `SELECTOR_TABELA_USUARIOS` | `'[id="tabelaUsuarios:resultList_data"] > tr'` | Linhas do resultado da pesquisa de usuário |
| `SELECTOR_PERFIL_INPUT` | `'[id="selecionaPerfil:selecionaPerfil:suggestion_input"]'` | Autocomplete de perfil na aba de edição |
| `SELECTOR_PROTOCOLO_INPUT` | `'[id="motivoDelegacao:motivoDelegacao:inputId_input"]'` | Campo de protocolo/motivo de delegação |
| `SELECTOR_TABELA_PERFIS` | `'[id="tabelaItens:resultList_data"] > tr'` | Linhas da tabela de perfis do usuário |
| `SELECTOR_MENSAGENS` | seletor combinado `#messagesInDialog .ui-messages-*-summary` | Mensagens de info/erro/aviso do AGHUX |
| `TEXTO_NENHUM_REGISTRO` | `"Nenhum registro encontrado!"` | Marca linha vazia de tabela |
| `TEMPO_MAXIMO_CONSULTA_MS` | `90000` | Timeout total de espera de pesquisa |
| `TEMPO_DETECCAO_WIDGET_CARREGAMENTO_MS` | `2000` | Janela para detectar o início do widget "Carregando" |
| `TEMPO_ESTABILIDADE_RESULTADO_MS` | `250` | Tempo mínimo que um estado precisa se manter antes de ser confirmado |
| `PADRAO_LOGIN_VALIDO` | `r"^[A-Za-z0-9._-]+$"` | Validação de login |
| `PADRAO_PROTOCOLO_VALIDO` | `r"^\d{1,17}$"` | Validação de protocolo (apenas dígitos, até 17) |
| `ALIASES_COLUNAS_PLANILHA` | dict de tuplas por campo (`login`, `protocolo`, `escopo`, `categoria`) | Reconhecimento tolerante de cabeçalhos na planilha de lote |
| `CAMPOS_CONCESSAO_OBRIGATORIOS` | `("login", "protocolo", "escopo", "categoria")` | Campos exigidos na planilha |
| `STATUS_*` | strings (`concedido`, `ja_existente`, `bloqueado`, `validacao_ura`, `usuario_nao_encontrado`, `conferir_manual`, `erro`, `ignorado`) | Valores de `StatusPerfil`, usados como contrato com `ui_concessor.py` (seção 13) |

---

## 7. Modelo de Dados

Todas as estruturas são `@dataclass(frozen=True)`:

| Classe | Campos | Papel |
|---|---|---|
| `RegraPerfil` | `escopo`, `categoria`, `perfis_conceder`, `perfis_bloqueados`, `perfis_validacao_ura`, `observacoes` | Uma linha do catálogo YAML |
| `CatalogoPerfis` | `regras: tuple[RegraPerfil, ...]` | Coleção de regras + métodos de consulta (`escopos()`, `categorias(escopo)`, `obter_regra(escopo, categoria)`, `perfis_bloqueados_globais()`, `perfis_validacao_ura_globais()`) |
| `ConcessaoPerfisEntrada` | `login`, `protocolo`, `escopo`, `categoria` | Entrada de uma concessão (unitária ou linha de planilha) |
| `ResultadoPerfil` | `login`, `escopo`, `categoria`, `perfil`, `status`, `detalhes` | Resultado por perfil individual |
| `ResultadoConcessao` | `login`, `protocolo`, `escopo`, `categoria`, `status`, `detalhes`, `resultados_perfis` | Resultado agregado de uma entrada (todos os perfis) |
| `ConcessaoPreparada` | `entrada`, `regra`, `perfis_automatizados`, `resultados_previos` | Saída de `preparar_concessao`: já contém os perfis previamente resolvidos (bloqueados/URA) e os que ainda precisam de ação no navegador |

`obter_regra` lança `ValueError("Regra de perfis nao encontrada para o escopo/categoria informados.")` quando a combinação não existe no catálogo — esse erro é capturado por `_preparar_concessoes_lote` e vira `STATUS_IGNORADO` por linha, nunca interrompe o lote inteiro.

---

## 8. Catálogo de Regras (YAML)

`carregar_catalogo_regras(caminho_regras=REGRAS_PADRAO)` lê o arquivo e ignora as chaves `metadata` e `tabelas` do YAML — apenas a lista `regras` é usada. Cada item deve ter `escopo` e `categoria` não vazios; itens sem esses campos são descartados silenciosamente. Se nenhuma regra válida sobrar, lança `ValueError("Nenhuma regra valida foi encontrada no YAML.")`.

### 8.1 Parser com PyYAML (padrão)

Se o pacote `yaml` estiver instalado, `_carregar_yaml_regras` usa `yaml.safe_load` diretamente.

### 8.2 Parser de fallback (`_parse_regras_yaml_fallback`)

Se `yaml` **não** estiver instalado, o módulo interpreta o arquivo com um parser de linha própria, específico para o formato usado em `regras_perfis_aghu.yaml`:

- Reconhece o início de cada regra por `- escopo:`.
- Reconhece listas (`perfis_conceder`, `perfis_bloqueados`, `perfis_validacao_ura`, `observacoes`) por indentação de 2 espaços + `- `.
- Reconhece continuação de valor multilinha (indentação de 4 espaços) e concatena ao último valor de string ou ao último item de lista.
- Remove aspas simples/duplas envolventes e desfaz `''` → `'` (escape YAML de aspa simples).

Este parser é intencionalmente restrito ao formato já usado no arquivo real — não é um parser YAML genérico. Qualquer mudança estrutural no YAML de regras (novos níveis de aninhamento, âncoras, etc.) exige revisão deste fallback junto com a mudança do arquivo.

---

## 9. Descrição dos Componentes Públicos

### 9.1 Preparação da Concessão (`preparar_concessao`)

Função central de regra de negócio. Fluxo:

1. Normaliza a entrada (`normalizar_entrada`: login em maiúsculas, protocolo só dígitos, escopo/categoria com `strip()`).
2. Valida (`validar_entrada`); se houver erro, lança `ValueError("; ".join(erros))`.
3. Busca a regra (`catalogo.obter_regra(escopo, categoria)`).
4. Monta os conjuntos globais `bloqueados` e `validacao_ura` a partir de **todas** as regras do catálogo (`perfis_bloqueados_globais()` / `perfis_validacao_ura_globais()`), não apenas da regra selecionada.
5. Para cada perfil em `regra.perfis_bloqueados` → resultado prévio `STATUS_BLOQUEADO`.
6. Para cada perfil em `regra.perfis_validacao_ura` → resultado prévio `STATUS_VALIDACAO_URA`.
7. Para cada perfil em `regra.perfis_conceder`, na ordem declarada:
   - Se já apareceu em um resultado prévio (passos 5/6), pula (evita duplicidade).
   - Se está na lista global de bloqueados → vira `STATUS_BLOQUEADO`, mesmo que a regra específica não o tivesse marcado como tal.
   - Se está na lista global de validação URA → vira `STATUS_VALIDACAO_URA`, mesma lógica.
   - Caso contrário, entra em `perfis_automatizados`.

**Efeito prático:** um perfil listado como "conceder" em uma regra específica, mas presente na lista global de perfis críticos (regra `PERFIS CRÍTICOS. ATENÇÃO!` → categoria `Ninguém`) ou na lista global de validação URA/STCOR, nunca é automatizado — a lista global sempre prevalece sobre a regra local. Isso é o mecanismo que impede que uma regra de categoria mal configurada libere um perfil crítico.

Somente os perfis em `perfis_automatizados` chegam à camada de Playwright. Se `perfis_automatizados` for vazio, a concessão inteira é resolvida sem abrir navegador (`processar_concessao_sem_browser`).

### 9.2 Validação de Entrada

`validar_entrada` (usada tanto pela UI quanto pelo lote) verifica:

| Campo | Regra | Mensagem |
|---|---|---|
| `login` | não pode estar em branco; deve casar `PADRAO_LOGIN_VALIDO` após normalização | `"Usuario alvo em branco."` / `"Usuario alvo invalido: use apenas letras, numeros, ponto, hifen ou sublinhado."` |
| `protocolo` | não pode estar em branco; deve casar `PADRAO_PROTOCOLO_VALIDO` (1 a 17 dígitos) após extrair apenas dígitos | `"Protocolo em branco."` / `"Protocolo invalido: informe ate 17 digitos."` |
| `escopo` | não pode estar em branco | `"Escopo em branco."` |
| `categoria` | não pode estar em branco | `"Categoria em branco."` |

A validação roda sobre a entrada já normalizada, mas as mensagens usam o valor original bruto para checar "em branco" — isso permite diferenciar campo vazio de campo inválido após normalização.

### 9.3 Leitura da Planilha de Lote (`ler_planilha_concessoes`)

Aceita apenas `.xlsx` (lança `ValueError` para qualquer outra extensão). Lê com `pandas.read_excel(dtype=str, engine="openpyxl")`, remove espaços de nomes de coluna e mapeia colunas por alias tolerante a acento/caixa (`_normalizar_cabecalho_planilha`, que aplica NFKD e remove diacríticos).

`ALIASES_COLUNAS_PLANILHA` aceita, por exemplo, `Login`, `Usuário`, `Usuario`, `User`, `Usuário alvo` para o campo `login`, e `Protocolo`, `Nro Protocolo`, `Despacho`, `Chamado` para `protocolo`. Se qualquer campo obrigatório não tiver coluna correspondente, lança `ValueError` listando os nomes canônicos faltantes (primeiro alias de cada tupla).

Linhas totalmente em branco são ignoradas. Cada linha lida é normalizada com `normalizar_entrada` antes de retornar.

### 9.4 Execução: Preparação em Lote e Fluxo de Navegador

#### 9.4.1 `_preparar_concessoes_lote`

Para cada entrada da lista:

- Normaliza e valida; se inválida, gera `ConcessaoPreparada` vazia + resultado de pré-validação `STATUS_IGNORADO` com o motivo, **sem** chamar `preparar_concessao`.
- Chama `preparar_concessao`; se lançar exceção (ex.: regra inexistente), mesmo tratamento acima com a mensagem da exceção.
- Se `perfis_automatizados` não for vazio, marca a linha para processamento no navegador (`resultados_prevalidacao[i] = None`) e liga `existem_automatizaveis = True`.
- Caso contrário, resolve a linha imediatamente com `processar_concessao_sem_browser` (sem abrir Playwright).

#### 9.4.2 Decisão de abrir o navegador

`executar_concessoes_perfis` só abre `sync_playwright()` se **pelo menos uma linha** do lote tiver `perfis_automatizados` não vazio. Se todas as linhas forem resolvidas por regra (bloqueadas, em validação URA, ou com erro de validação/regra), a função retorna sem nunca criar `Browser`/`Page`. Esse comportamento é coberto por teste (`test_executar_concessoes_sem_perfis_elegiveis_nao_abre_playwright`).

#### 9.4.3 Fluxo com navegador

Quando há automação a fazer:

```python
page.goto(url_aghu)
fazer_login(page, usuario_rede, senha, url_aghu=url_aghu)
page, janela_sistema = navegar_ate_cadastro_usuario(context, page, usuario_rede, senha, url_aghu=url_aghu)
resultados = processar_concessoes(context, page, janela_sistema, preparadas, usuario_rede, senha,
                                   resultados_prevalidacao=resultados_prevalidacao, url_aghu=url_aghu)
```

`processar_concessoes` itera as linhas preparadas; linhas já resolvidas por pré-validação (`pre_resultado is not None`) são apenas repassadas ao relatório final, sem tocar o navegador. Linhas pendentes vão para `processar_concessao`.

### 9.5 Navegação e Pesquisa de Usuário

#### 9.5.1 `navegar_ate_cadastro_usuario`

Chama `navegar_menu_aghu(page, caminho=CAMINHO_MENU_CADASTRO_USUARIO)` e valida a tela final aguardando `SELECTOR_PESQUISA_LOGIN` e o botão **Pesquisar**. Duas tentativas: na primeira falha, aciona Clean State (`trocar_aba_aghux`) e tenta de novo; na segunda falha, propaga a exceção.

#### 9.5.2 `garantir_tela_pesquisa_usuario` — idempotência entre linhas do lote

Antes de processar cada linha, `processar_concessao` chama esta função para confirmar que a tela de pesquisa ainda está acessível, sem sempre pagar o custo de renavegar. Estratégia em camadas:

1. Se `SELECTOR_PESQUISA_LOGIN` já está visível no `janela_atual` (timeout curto de 1500 ms), reaproveita a mesma janela sem navegar.
2. Caso contrário, tenta `navegar_menu_aghu` de novo na mesma `page` (a tela pode ter mudado de aba interna, sem precisar de Clean State completo).
3. Se isso também falhar, aciona Clean State completo (`trocar_aba_aghux`) e chama `navegar_ate_cadastro_usuario` do zero.

#### 9.5.3 `_pesquisar_usuario` e estados de resultado

Preenche `SELECTOR_PESQUISA_LOGIN`, clica **Pesquisar**, aguarda o ciclo de carregamento (`_aguardar_ciclo_carregamento`, que espera o widget "Carregando" aparecer e desaparecer, com timeout de `TEMPO_MAXIMO_CONSULTA_MS`) e então resolve o estado da busca via `_aguardar_resultado_pesquisa_usuario`, que retorna um dos quatro estados:

| Estado | Significado | Tratamento em `processar_concessao` |
|---|---|---|
| `"encontrado"` | Linha da tabela com login exato (coluna de índice 2) | Prossegue para edição |
| `"nao_encontrado"` | Mensagem "Nenhum registro encontrado!" visível | `STATUS_USUARIO_NAO_ENCONTRADO` para todos os perfis automatizados |
| `"sem_login_exato"` | Tabela tem linhas, mas nenhuma bate o login exato | `STATUS_USUARIO_NAO_ENCONTRADO` (mesmo tratamento de `"nao_encontrado"`) |
| `"indefinido"` | Timeout sem estado conclusivo | `STATUS_CONFERIR_MANUAL` para todos os perfis automatizados |

A função só confirma um estado depois que ele se mantém estável por `TEMPO_ESTABILIDADE_RESULTADO_MS` (250 ms) **e** o ciclo de carregamento já foi concluído (`_pode_confirmar_resultado`) — isso evita confirmar `"nao_encontrado"` prematuramente enquanto o AGHUX ainda está renderizando a tabela.

### 9.6 Concessão de Perfis na Tela

#### 9.6.1 Abrir a aba de perfis

1. `_clicar_editar_usuario(linha_usuario)`: tenta uma lista ordenada de candidatos (role `link`/`button` com nome `Editar|Alterar`, atributos `title`/`aria-label` contendo esses termos, classes conhecidas `silk-pencil`/`silk-user_edit`/`ui-commandlink`). É um fallback documentado por posição/classe, não um seletor único garantido.
2. `_abrir_aba_perfis_usuario(page, janela_sistema)`: primeiro verifica se o frame de perfis já está visível via `_frame_perfis_visivel` (candidatos, em ordem: `iframe[name="i_frame_usuario"]` a partir de `page`, o mesmo a partir de `janela_sistema`, o último iframe da página, e a própria `janela_sistema`). Se nenhum candidato mostra `SELECTOR_PERFIL_INPUT`, tenta clicar em um link/texto "Editar perfil" ou "Perfis" e reavalia.

#### 9.6.2 Selecionar um perfil no autocomplete (`_selecionar_perfil_autocomplete`)

Digita o nome do perfil com `press_sequentially(perfil, delay=150)` (necessário para disparar o autocomplete JSF), aguarda os itens (`tr.ui-autocomplete-item, li.ui-autocomplete-item`), percorre até 50 itens visíveis e clica no primeiro cujo texto bate exatamente com o perfil (`_texto_item_autocomplete_confere`: compara a linha inteira normalizada **ou** apenas o primeiro token, para tolerar itens como `"MED01 - Descrição"`). Se nenhum item bater, lança `PlaywrightTimeoutError` com o último texto visto, para facilitar diagnóstico. Após a seleção, valida que o valor final do campo ainda corresponde ao perfil esperado — proteção equivalente à validação de IP da RFC-001.

#### 9.6.3 Preencher o protocolo (`_preencher_protocolo`)

Usa `Control+A` + `Backspace` para limpar (com fallback para `fill("")` se as tecla não funcionarem), digita com `press_sequentially(delay=30)`, dispara eventos `input`/`change` manualmente via `evaluate` (necessário porque JSF depende desses eventos para atualizar o `ViewState`), faz `blur()` e dispara os eventos de novo. Ao final, relê `input_value()` e, se o valor não bater com o esperado, lança `RuntimeError` — nenhuma gravação prossegue com protocolo divergente.

#### 9.6.4 Adicionar um perfil (`_adicionar_perfil`) e gravar em lote (`_conceder_perfis_na_tela`)

Fluxo por perfil dentro de `_conceder_perfis_na_tela`:

1. Lê a tabela atual de perfis do usuário (`_perfis_atuais_na_tabela`). Perfis já presentes recebem `STATUS_JA_EXISTENTE` e não passam por nenhuma ação no navegador.
2. Para os demais, chama `_adicionar_perfil` (seleciona autocomplete → preencher protocolo → clica **Adicionar** → aguarda o perfil aparecer na tabela, `_aguardar_perfil_na_tabela`, até 10 s). Se o perfil não aparecer, lança `RuntimeError` incluindo qualquer mensagem do AGHUX capturada por `_mensagens_sistema`.
3. Perfis adicionados com sucesso na etapa 2 (mas ainda não gravados) são acumulados em `adicionados`.
4. **Um único clique em Gravar** (`_gravar_perfis`) é feito para todos os perfis acumulados da linha — não há um Gravar por perfil.
5. O resultado desse **único** `_gravar_perfis` (`sucesso` / `erro` / `indefinido`, via `_aguardar_mensagem_gravacao`, que procura a mensagem de sucesso `"perfil do usuario atualizado com sucesso"` ou termos de erro) é aplicado a **todos** os perfis do lote de adição — não há distinção por perfil individual nessa etapa. A remoção de `_checagem_final_perfis` (commit `eefa1b2`) eliminou a etapa de retry pós-gravação, fazendo com que o resultado venha diretamente desse único `_gravar_perfis`.

> **Implicação:** se dois perfis forem adicionados à tabela com sucesso mas o clique em **Gravar** falhar (ex.: erro de validação do AGHUX não relacionado a nenhum dos dois), ambos os perfis recebem `STATUS_ERRO`, mesmo que um deles pudesse ter sido gravado isoladamente. Não há reconferência ou retry após esse ponto — o status vem diretamente do resultado desse `_gravar_perfis`.

---

## 10. Recuperação de Falhas Técnicas

`processar_concessao` executa o corpo do processamento de uma linha dentro de um laço de até 2 tentativas:

| Tentativa | Ação em exceção não tratada como resultado de negócio |
|---|---|
| 1ª | Aciona Clean State (`trocar_aba_aghux`) e renavega (`navegar_ate_cadastro_usuario`); repete a linha |
| 2ª | Registra `STATUS_ERRO` para todos os `perfis_automatizados` da linha com detalhe `"Falha tecnica durante a concessao: <exc>"` |

Diferente da RFC-001, aqui não há distinção entre "erro de negócio conhecido por mensagem" e "erro técnico" via `ValueError` com texto específico — qualquer exceção não capturada localmente (por exemplo, timeout do Playwright) cai neste tratamento genérico de 2 tentativas.

---

## 11. Relatórios e Auditoria

| Saída | Função | Formato |
|---|---|---|
| Log de auditoria (sempre, unitário ou lote) | `gerar_csv_logs` | CSV em `logs/log_concessao_perfis_YYYYMMDD_HHMMSS.csv`, primeira linha `Atualizado por: <usuario_rede>`, depois uma linha por perfil processado (`Login`, `Protocolo`, `Escopo`, `Categoria`, `Perfil`, `Status`, `Detalhes`) |
| Relatório de lote | `salvar_relatorio_resultados` | `.xlsx` com aba "Resultado", `freeze_panes="A2"`, `auto_filter` e largura de coluna ajustada (máx. 90) |

`gerar_csv_log` é `True` por padrão em todas as funções de execução pública; pode ser desativado (usado nos testes) para evitar I/O em disco.

---

## 12. API Pública do Módulo

| Função | Responsabilidade |
|---|---|
| `carregar_catalogo_regras(caminho_regras=REGRAS_PADRAO)` | Carrega e valida o catálogo de regras a partir do YAML |
| `normalizar_entrada(entrada)` | Normaliza login/protocolo/escopo/categoria |
| `validar_entrada(entrada)` | Retorna lista de erros de validação (vazia se válida) |
| `preparar_concessao(entrada, catalogo)` | Aplica a regra de negócio e separa perfis automatizáveis dos resolvidos previamente |
| `ler_planilha_concessoes(caminho_planilha)` | Lê e normaliza uma planilha `.xlsx` de lote |
| `salvar_relatorio_resultados(resultados, caminho_saida)` | Gera o relatório `.xlsx` de uma execução em lote |
| `gerar_csv_logs(resultados, usuario_rede, diretorio_logs)` | Gera o CSV de auditoria |
| `resultado_ignorado(entrada, detalhes)` | Constrói um `ResultadoConcessao` com status `ignorado`, usado para linhas inválidas |
| `processar_concessao_sem_browser(preparada)` | Resolve uma concessão sem abrir Playwright, quando não há perfil automatizável |
| `fazer_login(page, usuario_rede, senha, *, url_aghu=AGHU_URL)` | Wrapper de autenticação centralizada |
| `trocar_aba_aghux(context, page_atual, usuario_rede, senha, *, url_aghu=AGHU_URL)` | Clean State: fecha aba, abre nova, reautentica |
| `navegar_ate_cadastro_usuario(context, page_atual, usuario_rede, senha, *, url_aghu=AGHU_URL)` | Abre o módulo Acesso → Usuario, com 1 retry via Clean State |
| `garantir_tela_pesquisa_usuario(context, page_atual, janela_atual, usuario_rede, senha, *, url_aghu=AGHU_URL)` | Garante tela de pesquisa disponível entre linhas, com recuperação em 3 camadas |
| `processar_concessao(context, page_inicial, janela_sistema_inicial, preparada, usuario_rede, senha, *, url_aghu=AGHU_URL)` | Processa uma única concessão já preparada |
| `processar_concessoes(context, page_inicial, janela_sistema_inicial, preparadas, usuario_rede, senha, *, resultados_prevalidacao=None, url_aghu=AGHU_URL)` | Processa uma lista de concessões preparadas |
| `executar_concessao_perfis(entrada, usuario_rede, senha, **kwargs)` | Execução completa (ponta a ponta) de uma única entrada |
| `executar_concessoes_perfis(concessoes, usuario_rede, senha, **kwargs)` | Execução completa de uma lista de entradas (usada pela UI unitária e pelo lote) |
| `executar_concessao_lote(usuario_rede, senha, caminho_planilha, caminho_relatorio, **kwargs)` | Lê planilha, executa e salva relatório `.xlsx` |
| `executar_concessao_individual(usuario_rede, senha, login, protocolo, escopo, categoria, **kwargs)` | Atalho para `executar_concessao_perfis` sem construir `ConcessaoPerfisEntrada` manualmente |
| `esconder_console_windows()` | Esconde o console do processo no Windows (usado quando `mostrar_console=False`) |

Constantes públicas usadas por `ui_concessor.py`: `LOGS_DIR`, todos os `STATUS_*`, `ConcessaoPerfisEntrada`.

Funções privadas (prefixo `_`) documentadas na seção 17 não devem ser importadas por `ui_concessor.py` nem por outro módulo.

---

## 13. `ui_concessor.py` — Interface Gráfica

### 13.1 Papel

`AghuConcessorPerfisApp` (CustomTkinter) é a única forma de operação do módulo em uso real. Ela não implementa regra de negócio: monta `ConcessaoPerfisEntrada` a partir dos campos de tela e chama `executar_concessoes_perfis` / `executar_concessao_lote` em uma `threading.Thread` separada (`daemon=True`), devolvendo o resultado à thread principal do Tkinter via `self.after(0, callback, ...)` — nunca toca widgets diretamente a partir da thread de execução.

### 13.2 Ambiente

```python
AMBIENTE_PRODUCAO = "Produção"
AMBIENTE_HOMOLOGACAO = "Homologação"
URLS_AMBIENTE_AGHU = {AMBIENTE_PRODUCAO: AGHU_URL, AMBIENTE_HOMOLOGACAO: AGHU_URL_HOMOLOGACAO}
```

Homologação é o padrão ao abrir a tela (`var_ambiente = "Homologação"`), conforme a seção 5 do `Guia_AGHU.md`. Ao selecionar Produção, a UI exibe um `messagebox.showwarning` e mantém um banner amarelo fixo ("Atenção: você está executando no Ambiente de Produção...") enquanto essa opção estiver selecionada.

### 13.3 Tipo de execução

| Tipo | Entrada | Limite | Saída |
|---|---|---|---|
| **Unitária** | até `MAX_USUARIOS_UNITARIOS = 5` linhas preenchidas na própria tela (login, protocolo, e opcionalmente "Acesso próprio") | 5 usuários (limite só da UI; o núcleo aceita listas de qualquer tamanho) | Mensagem de status na tela; CSV de auditoria sempre gerado |
| **Lote** | planilha `.xlsx` selecionada por `filedialog` | tamanho da planilha | Relatório `.xlsx` (`caminho_relatorio_padrao`, mesmo diretório da planilha por padrão) + CSV de auditoria |

Na execução unitária, cada linha tem um "Acesso Padrão" compartilhado (escopo/categoria selecionados no topo da seção) que se aplica a todas as linhas por padrão. Marcar "Acesso próprio" em uma linha revela seletores de escopo/categoria específicos **daquela linha**, que passam a prevalecer sobre o acesso padrão para aquele usuário (`_resolver_acesso_efetivo`). O botão de reset (↺) desmarca "Acesso próprio" e volta a linha ao acesso padrão.

Na execução em lote, escopo e categoria vêm de colunas da própria planilha — não existe conceito de "acesso próprio" no lote.

### 13.4 Proteção contra execução invisível

`_validar_opcoes_visibilidade` impede que o operador desmarque simultaneamente "Exibir Navegador" e "Exibir Terminal de processos": se ambos forem desmarcados, a última ação é revertida e uma mensagem de aviso é exibida. Isso evita que o robô rode totalmente oculto (sem navegador visível e sem console), dificultando a auditoria em tempo real de uma execução.

### 13.5 Bloqueio de controles durante execução

`_bloquear_execucao` / `_liberar_execucao` desabilitam todos os campos de entrada, seletor de tipo de execução, seletor de ambiente e botões de arquivo enquanto `em_execucao` é `True`, evitando disparar uma segunda execução concorrente ou alterar ambiente/credenciais em meio ao processamento.

### 13.6 Resumo de resultados

`_resumir_resultados` conta ocorrências de cada `STATUS_*` (via `collections.Counter`) e monta uma frase única com os totais. A cor do texto de status (`verde`/`vermelho`) é decidida por presença de `STATUS_ERRO` (lote e execução unitária múltipla) ou por `STATUS_ERRO`/`STATUS_CONFERIR_MANUAL` (execução unitária de uma única linha).

---

## 14. Contratos entre RFCs

### 14.1 Contrato com RFC-004 (`menu.py`)

| Função / Elemento | Origem | Comportamento no `concessor_aghu.py` |
|---|---|---|
| `navegar_menu_aghu` | `menu.py` (RFC-004) | Chamado com `CAMINHO_MENU_CADASTRO_USUARIO` (`("Outros Módulos", "Configuração", "Acesso", "Usuario")`); percorre os níveis de menu e retorna o `FrameLocator` do iframe de cadastro de usuários |
| Falha de navegação | `menu.py` (RFC-004) | Em falha de localização de menu, o concessor aciona Clean State (`trocar_aba_aghux`) e tenta renavegar |

### 14.2 Contrato com RFC-005 (`autenticador.py`)

| Função / Elemento | Origem | Comportamento no `concessor_aghu.py` |
|---|---|---|
| `AGHU_URL` | `autenticador.py` (RFC-005) | URL padrão de Produção do AGHUX, usada em retries e Clean States |
| `autenticar_aghu_page` | `autenticador.py` (RFC-005) | Autentica a sessão Playwright na `Page` fornecida |
| `exigir_login_valido` | `autenticador.py` (RFC-005) | Assegura que o resultado do login seja válido (`sucesso` ou `sessao_ativa`), lançando exceção caso contrário |

### 14.3 Contrato com `ui_concessor.py` e Internos

| Contrato | Descrição |
|---|---|
| `ValueError("Regra de perfis nao encontrada para o escopo/categoria informados.")` | Lançado por `obter_regra`; tratado por `_preparar_concessoes_lote` como linha ignorada, nunca propaga para fora do módulo em execução de lote/unitária |
| `StatusPerfil` (`Literal`) | Contrato de valores entre `concessor_aghu.py` e `ui_concessor.py`; a UI decide cor e agregação de mensagem com base nesses valores — não devem ser renomeados sem atualizar a UI e esta RFC |
| Prioridade de agregação (`_status_geral`) | `erro` > `conferir_manual` > `concedido` > `usuario_nao_encontrado` > `ja_existente` > (`bloqueado`/`validacao_ura`/`ignorado`) → `ignorado`. Determina o status "geral" de uma `ResultadoConcessao` com múltiplos perfis |
| `LOGS_DIR` | Importado por `ui_concessor.py` como diretório padrão de log para ambas as execuções |
| `MAX_USUARIOS_UNITARIOS` | Limite é responsabilidade exclusiva da UI; `executar_concessoes_perfis` não impõe limite de tamanho de lista |

---

## 15. Considerações Operacionais

1. `concessor_aghu.py` não cria o browser antes de confirmar que há trabalho a fazer — evita custo de Playwright quando toda a entrada é resolvida por regra (bloqueio/validação URA/erro de validação).
2. `url_aghu` é propagado por login, navegação, Clean State e recuperação de tela, seguindo o mesmo padrão da RFC-001/RFC-005 — nenhum retry deve derivar a URL de uma constante fixa.
3. A gravação de perfis é feita em lote por usuário (um único **Gravar** por chamada a `_conceder_perfis_na_tela`), não por perfil — ver implicação na seção 9.6.4.
4. Perfis bloqueados e de validação URA/STCOR nunca chegam à camada de Playwright; são resolvidos inteiramente pela regra de negócio antes de qualquer navegação.
5. O parser de fallback do YAML (seção 8.2) é específico ao formato atual de `regras_perfis_aghu.yaml` e não deve ser tratado como parser YAML genérico.
6. A UI impede execução totalmente invisível (seção 13.4) e mantém Homologação como padrão operacional seguro.
7. O fluxo depende de textos/seletores visíveis do AGHUX: **Outros Módulos**, **Configuração**, **Acesso**, **Usuario**, **Pesquisar**, **Editar**/**Alterar**, **Adicionar**, **Gravar**, além dos IDs de campo listados na seção 6.

---

## 16. Limitações Conhecidas

| Limitação | Impacto |
|---|---|
| Resultado de gravação é por lote de perfis, não por perfil individual | Uma falha de gravação não relacionada a um perfil específico pode marcar `erro` para perfis que seriam gravados corretamente isoladamente; não há reconferência ou retry após esse ponto |
| `_clicar_editar_usuario` e `_abrir_aba_perfis_usuario` usam cadeias de seletores fallback (texto, `title`, `aria-label`, classes CSS) | Mudança de layout/nomenclatura no AGHUX pode exigir ajuste de vários candidatos de uma vez |
| Estado `"sem_login_exato"` trata pesquisa com resultados parciais como usuário não encontrado | Um AGHUX que retorne múltiplos usuários semelhantes ao login pesquisado não é diferenciado de "usuário inexistente"; ambos exigem conferência manual pelo operador |
| Parser de fallback do YAML é restrito ao formato atual | Mudanças estruturais no arquivo de regras podem quebrar o fallback sem quebrar o caminho com PyYAML instalado |
| `MAX_USUARIOS_UNITARIOS` é validado apenas na UI | Uma chamada direta a `executar_concessoes_perfis` fora da UI não tem esse limite — comportamento intencional, mas não deve ser assumido como validação de negócio |

---

## 17. Funções Auxiliares Privadas (`concessor_aghu.py`)

Catálogo das rotinas internas (prefixo `_`) que dão suporte a sanitização, parsing do catálogo YAML e automação Playwright. Não fazem parte da API pública (seção 12) e não devem ser importadas por `ui_concessor.py` nem por outro módulo.

### 17.1 Sanitização e Normalização

| Função | Assinatura | Descrição |
|---|---|---|
| `_normalizar_texto` | `(valor: object) -> str` | Colapsa espaços, remove bordas e aplica `casefold()`. Usada para comparações tolerantes a acento/caixa (escopo, categoria, mensagens do AGHUX). |
| `_normalizar_login` | `(valor: object) -> str` | `strip()` + `upper()`. Usada para padronizar o login antes de validação/pesquisa. |
| `_normalizar_perfil` | `(valor: object) -> str` | Colapsa espaços e aplica `upper()`. Usada para comparar nomes de perfil (catálogo vs. tabela de perfis do usuário). |
| `_apenas_digitos` | `(valor: object) -> str` | Remove tudo que não for dígito (`\D+`). Usada em protocolo e CPF. |
| `_valor_em_branco` | `(valor: object) -> bool` | Trata `NaN` do pandas e string vazia/whitespace como "em branco". |
| `_texto_planilha` | `(valor: object) -> str` | Envolve `_valor_em_branco`; devolve `""` para célula vazia/NaN, senão o texto com `strip()`. |
| `_normalizar_cabecalho_planilha` | `(valor: object) -> str` | Remove diacríticos via NFKD, colapsa espaços e aplica `casefold()`. Base do reconhecimento tolerante de cabeçalhos (seção 9.3). |
| `_unicos_preservando_ordem` | `(valores) -> tuple[str, ...]` | Deduplica por `_normalizar_texto`, preservando a ordem de primeira aparição. Usada por `CatalogoPerfis.escopos()`/`categorias()` e pelos parsers YAML. |

### 17.2 Parsing do Catálogo YAML (fallback)

| Função | Assinatura | Descrição |
|---|---|---|
| `_limpar_valor_yaml` | `(valor: str) -> str` | Remove aspas simples/duplas envolventes, trata `[]` como vazio e desfaz o escape `''` → `'`. |
| `_lista_yaml` | `(valor: object) -> tuple[str, ...]` | Normaliza um valor de YAML (já uma lista, string única ou vazio) para tupla de strings únicas via `_unicos_preservando_ordem`. |
| `_parse_regras_yaml_fallback` | `(texto: str) -> dict` | Parser de linha própria descrito na seção 8.2; usado somente quando o pacote `yaml` não está instalado. |

### 17.3 Automação e Resiliência de Tela (Playwright)

| Função | Assinatura | Descrição |
|---|---|---|
| `_primeiro_visivel` | `(janela_sistema: FrameLocator, seletores: tuple[str, ...], timeout_ms: int = 5000) -> Locator` | Tenta cada seletor da tupla em ordem e retorna o primeiro que ficar visível; lança `PlaywrightTimeoutError` se nenhum ficar. Base dos fallbacks de seletor (ex.: `_frame_perfis_visivel`). |
| `_clicar_botao` | `(janela_sistema: FrameLocator, nome: str, timeout_ms: int = 10000) -> None` | Localiza um botão por role/nome acessível (`get_by_role("button", name=nome)`), espera ficar visível e clica. |
| `_preencher_input` | `(locator: Locator, valor: str, timeout_ms: int = 5000) -> None` | Clica no campo, limpa com `fill("")` e preenche com `fill(valor)`. |
| `_disparar_eventos_input_jsf` | `(locator: Locator) -> None` | Dispara `input`/`change` via `evaluate`, necessário porque o JSF do AGHUX depende desses eventos para atualizar o `ViewState`. |
| `_preencher_protocolo` | `(locator: Locator, protocolo: str, timeout_ms: int = 5000) -> None` | Implementação de `_preencher_protocolo` descrita na seção 9.6.3 (limpa com `Control+A`+`Backspace`, digita com `press_sequentially`, dispara eventos, valida `input_value()` ao final). |
| `_mensagens_sistema` | `(janela_sistema: FrameLocator) -> list[str]` | Varre `SELECTOR_MENSAGENS` e retorna o texto de cada mensagem de info/erro/aviso atualmente visível no AGHUX. Usada para compor `detalhes` em falhas de gravação/adição de perfil. |

Não existem, neste módulo, funções chamadas `_aplicar_bloqueio_global`, `_validar_regras_locais`, `_parse_simplificado_yaml`, `_extrair_mensagem_erro` ou `_garantir_elemento_visivel` — a lógica equivalente já é coberta, respectivamente, pelos passos 4–7 de `preparar_concessao` (seção 9.1), por `CatalogoPerfis.obter_regra` (seção 7), por `_parse_regras_yaml_fallback` (17.2) e por `_mensagens_sistema` (17.3).

---

## 18. Estado Atual da RFC

Esta RFC documenta o estado de `concessor_aghu.py` e `ui_concessor.py` conforme o código em produção nesta data, cobrindo:

- Separação entre regra de negócio (catálogo YAML, perfis bloqueados/validação URA globais e por regra) e execução mecânica no AGHUX.
- Preparação em lote com resolução antecipada de linhas sem perfil automatizável, sem custo de Playwright.
- Navegação, pesquisa de usuário e abertura da aba de perfis com fallbacks documentados.
- Gravação em lote por usuário, com status definido diretamente pelo retorno de `_gravar_perfis` após a remoção de `_checagem_final_perfis` (commit `eefa1b2`), sem reconferência ou retry pós-gravação.
- Relatórios `.xlsx` (lote) e CSV de auditoria (sempre).
- Interface gráfica com execução unitária (com "acesso próprio" por linha) e em lote, proteção contra execução invisível e ambiente padrão de Homologação.
- Contratos de status (`StatusPerfil`) entre núcleo e UI, além dos contratos formais com RFC-004 (`menu.py`) e RFC-005 (`autenticador.py`).
- Limitações conhecidas de seletor, agregação de resultado e do parser de fallback do YAML.

Esta RFC fecha a lacuna apontada no checklist do `Guia_AGHU.md`: até então, `concessor_aghu.py` estava em produção sem RFC correspondente.
