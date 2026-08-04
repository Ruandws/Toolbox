# RFC-008 — Cadastro/Importação de Usuário no AGHUX (criar_usuario_aghu + ui_criar_usuario_aghu)

- **Status:** Estável
- **Autor:** Ruan
- **Data:** 2026-07-27
- **Atualizado em:** 2026-07-27 (reflete o código como está desde a release de 2026-07-23)
- **Arquivo (núcleo):** `criar_usuario_aghu.py`
- **Arquivo (UI):** `ui_criar_usuario_aghu.py`
- **Depende de:** `autenticador.py` (RFC-005), `menu.py` (RFC-004)
- **Chamado por:** ninguém além da própria UI; não é chamado por outros robôs AGHU

---

## 0. Por que esta RFC existe

`criar_usuario_aghu.py` está em produção sem RFC própria, o que contraria o item 6 do `Guia_AGHU.md`: "toda função pública usada por outro módulo deve constar na seção API Pública da RFC correspondente". Esta RFC cobre o núcleo e a UI juntos, em um único documento, porque os dois arquivos formam um par fechado (motor + operador) sem terceiro módulo envolvido — diferente do par Maestro/Almoxarifado do RFC-001/002, aqui não há delegação entre robôs.

---

## 1. Resumo

O par `criar_usuario_aghu.py` (núcleo) + `ui_criar_usuario_aghu.py` (interface) automatiza a **importação de usuários já existentes no Identity Manager corporativo para dentro do cadastro do AGHUX**. Ele não cria usuários do zero: pesquisa o login no AGHUX, e caso não exista, abre a tela "Importar Usuário", pesquisa o mesmo login no Identity Manager, adiciona o resultado encontrado, preenche Nome Completo e E-mail, marca o usuário como ativo e grava.

Suporta duas formas de execução: unitária (até 5 usuários digitados na UI) e em lote (planilha `.xlsx`). Ambas passam pela mesma função de orquestração, `executar_importacao_usuarios`.

---

## 2. Motivação e Escopo

Cadastrar usuários manualmente no AGHUX é repetitivo e o funcionário já existe, quase sempre, no Identity Manager (diretório corporativo). O trabalho manual é: pesquisar o login no AGHUX, conferir que não está cadastrado, abrir a importação, localizar a mesma pessoa no Identity Manager, clicar em adicionar, digitar nome e e-mail, marcar ativo e gravar — para cada linha de uma lista que pode ter dezenas de nomes.

O núcleo sabe:

| Responsabilidade | Descrição |
|---|---|
| Validação de entrada | Login, Nome Completo e E-mail, antes de abrir o browser |
| Pesquisa dupla | Confere se o login já está no AGHUX; se não, pesquisa no Identity Manager |
| Preenchimento e gravação | Nome, e-mail, ativo, e leitura da mensagem de resultado |
| Relatório | CSV auditável em `logs/` e XLSX final para o operador |

O núcleo não conhece regra de perfis/permissões do usuário (isso é outro módulo, `concessor_aghu.py`, fora do escopo desta RFC) nem cadastra usuários que não existam no Identity Manager.

---

## 3. Fluxo

```text
[ui_criar_usuario_aghu.py]
        │
        ├─► executar_importacao_usuarios(usuarios, usuario_rede, senha, url_aghu, ...)
        │        │
        │        ├─ _validar_lote_usuarios(usuarios)         (síncrono, sem browser)
        │        │      ├─ usuários inválidos → status "ignorado", nunca chegam ao browser
        │        │      └─ usuários válidos → seguem para a automação
        │        │
        │        ├─ Se nenhum usuário for válido: retorna direto, SEM abrir Playwright
        │        │
        │        └─ Abre Playwright/Chromium
        │               ├─ page.goto(url_aghu)
        │               ├─ fazer_login(page, ..., url_aghu=url_aghu)
        │               ├─ navegar_ate_cadastro_usuario(...)  → Outros Módulos → Configuração → Acesso → Usuario
        │               └─ processar_usuarios(...)
        │                       │
        │                       └─ Para cada usuário válido:
        │                             ├─ garantir_tela_pesquisa_usuario(...)
        │                             └─ importar_usuario(janela_sistema, usuario)
        │                                   │
        │                                   ├─ Pesquisa login na tabela de usuários do AGHUX
        │                                   │     ├─ "encontrado"   → ja_importado
        │                                   │     ├─ "indefinido"   → conferir_manualmente
        │                                   │     └─ não encontrado → segue
        │                                   │
        │                                   ├─ Abre "Importar Usuário"
        │                                   ├─ Pesquisa login no Identity Manager
        │                                   │     ├─ "indefinido"       → conferir_manualmente
        │                                   │     └─ não encontrado     → nao_encontrado
        │                                   │
        │                                   └─ Encontrado no Identity Manager:
        │                                         ├─ Clica "Adicionar"
        │                                         ├─ Preenche Nome Completo e E-mail
        │                                         ├─ Marca usuário ativo
        │                                         ├─ Clica "Gravar"
        │                                         └─ Lê mensagem de gravação
        │                                               ├─ sucesso    → importado
        │                                               ├─ duplicado  → ja_importado
        │                                               ├─ indefinido → conferir_manualmente
        │                                               └─ erro       → erro
        │
        └─► CSV auditável em ./logs (sempre) + XLSX de relatório escolhido pelo operador (lote)
```

Não há delegação a outro robô: se o login não existir no Identity Manager, a linha é marcada `nao_encontrado` e o fluxo segue para a próxima, sem intervenção externa (diferente do par Maestro/Almoxarifado do RFC-001/002).

---

## 4. Dependências

### 4.1 `autenticador.py`

```python
from autenticador import AGHU_URL, autenticar_aghu_page, exigir_login_valido
```

Mesmo contrato documentado no RFC-005: `fazer_login` e `trocar_aba_aghux` (Clean State) são wrappers finos sobre `autenticar_aghu_page` + `exigir_login_valido`. Nenhum seletor de login é duplicado aqui.

### 4.2 `menu.py`

```python
from menu import navegar_menu_aghu
```

Caminho declarado localmente:

```python
CAMINHO_MENU_CADASTRO_USUARIO = (
    "Outros Módulos",
    "Configuração",
    "Acesso",
    "Usuario",
)
```

A validação da tela final (`SELECTOR_PESQUISA_LOGIN` visível + botão **Pesquisar** visível) é feita pelo próprio módulo, como manda o Guia AGHU.

---

## 5. Constantes e Seletores

| Constante | Valor / Uso |
|---|---|
| `CAMINHO_MENU_CADASTRO_USUARIO` | Caminho de menu até a tela de cadastro de usuário |
| `COLUNAS_OBRIGATORIAS_PLANILHA` | `("Login", "Nome Completo", "E-mail")` |
| `ALIASES_COLUNAS_PLANILHA` | Aceita variações de cabeçalho por campo (`Usuário`, `User`, `Nome`, `Email`, etc.) |
| `PADRAO_EMAIL_MINIMO` | `^[^@\s]+@[^@\s]+\.[^@\s]+$` |
| `PADRAO_LOGIN_VALIDO` | `^[A-Za-z0-9._-]+$` |
| `SELECTOR_PESQUISA_LOGIN` | Campo de pesquisa por login na tela principal de usuários |
| `SELECTOR_IMPORTACAO_LOGIN` | Campo de pesquisa por login dentro do diálogo "Importar Usuário" |
| `SELECTOR_CADASTRO_NOME` / `SELECTOR_CADASTRO_EMAIL` | Campos de Nome Completo e E-mail no formulário de importação |
| `SELECTOR_TABELA_USUARIOS` | Linhas da tabela de resultado da pesquisa principal |
| `SELECTOR_TABELA_IDENTITY` | Linhas da tabela de resultado da pesquisa no Identity Manager |
| `TEMPO_MAXIMO_CONSULTA_USUARIO_MS` | `130000` — consulta ao AGHUX pode ser bem lenta |
| `TEMPO_MAXIMO_GRAVACAO_USUARIO_MS` | `10000` |

Status possíveis (`StatusImportacao`):

```text
importado, ja_importado, nao_encontrado, erro, ignorado, conferir_manualmente
```

---

## 6. Validação de Entrada (antes do browser)

### 6.1 `_validar_usuario`

Verifica, por usuário:

| Campo | Regra |
|---|---|
| Login | Não pode estar em branco; sem espaços; deve casar com `PADRAO_LOGIN_VALIDO` |
| Nome Completo | Não pode estar em branco; sem espaços laterais ou duplos (`_nome_tem_espacos_indevidos`) |
| E-mail | Não pode estar em branco; sem espaços; deve casar com `PADRAO_EMAIL_MINIMO` |

### 6.2 Assimetria intencional entre login/e-mail e nome completo — **ponto de atenção**

`_preparar_usuario_importacao` monta o objeto que vai para `_validar_usuario` assim:

```python
usuario_normalizado = _normalizar_usuario_importacao(usuario)
usuario_para_validacao = UsuarioImportacao(
    login=usuario.login,                          # bruto, sem normalizar
    nome_completo=usuario_normalizado.nome_completo,  # já normalizado
    email=usuario.email,                           # bruto, sem normalizar
)
erros = _validar_usuario(usuario_para_validacao)
```

Login e e-mail são validados com o valor **bruto** (como veio da planilha/UI), de propósito: `_normalizar_login`/`_texto_para_validacao` só fazem `strip()`, então se o valor bruto tiver espaço nas pontas, a validação ainda os vê e acusa "contem espacos indevidos".

Nome Completo, porém, é validado já **normalizado** por `_normalizar_nome_completo` (que colapsa espaços duplos e tira espaços das pontas antes da checagem). Na prática, isso significa que a regra `"Nome Completo contem espacos indevidos"` — testada e funcional quando `_validar_usuario` é chamada diretamente (ver `test_unit_criar_usuario_aghu.py::TestValidarUsuario::test_nome_com_espaco_indevido`) — **nunca dispara no fluxo real de produção** (via `_preparar_usuario_importacao` → `_validar_lote_usuarios` → `executar_importacao_usuarios`), porque o valor já chega limpo à validação. Um nome como `"Joao  Silva"` (espaço duplo) ou `"  Joao Silva  "` é silenciosamente normalizado e aceito, em vez de gerar um item `ignorado`. Se o comportamento esperado for realmente barrar nomes malformatados, `_preparar_usuario_importacao` precisa passar `usuario.nome_completo` bruto para a validação, não o normalizado.

### 6.3 Validação síncrona em lote, antes do Playwright

Desde a release de 23/07/2026, a validação inteira do lote acontece de uma vez em `_validar_lote_usuarios`, dentro de `executar_importacao_usuarios`, **antes** de abrir o Playwright:

```python
validacao = _validar_lote_usuarios(usuarios)
...
if not validacao.usuarios_validos:
    return _finalizar_resultados_importacao(...)  # sem nunca ter chamado sync_playwright
```

Isso é coberto por teste (`test_executar_importacao_invalida_nao_abre_playwright`, que faz o `sync_playwright` monkeypatched levantar `AssertionError` se for chamado). Usuários inválidos recebem status `ignorado` e nunca contam como tentativa de gravação no AGHUX. Resultados válidos e ignorados são recombinados na ordem original da planilha por `_combinar_resultados_na_ordem_original`.

---

## 7. Componentes Públicos do Núcleo

### 7.1 `ler_planilha_usuarios(caminho_planilha)`

Só aceita `.xlsx`. Colunas obrigatórias: `Login`, `Nome Completo`, `E-mail` (por alias). Levanta `FileNotFoundError` se o arquivo não existir e `ValueError` se faltar coluna obrigatória.

### 7.2 `fazer_login` / `trocar_aba_aghux` / `navegar_ate_cadastro_usuario` / `garantir_tela_pesquisa_usuario`

Mesmo padrão do RFC-001: login delegado ao autenticador, Clean State reabre aba no mesmo `BrowserContext` e reautentica preservando `url_aghu`, navegação delegada a `navegar_menu_aghu` com validação local pelo botão **Pesquisar**.

`garantir_tela_pesquisa_usuario` tenta, nesta ordem: (1) reaproveitar a janela atual se o campo de pesquisa ainda estiver visível (1500ms); (2) renavegar pelo menu; (3) Clean State completo + renavegação. Usado antes de cada usuário do lote, não só no início.

### 7.3 `importar_usuario(janela_sistema, usuario) → ResultadoImportacao`

Implementa a árvore de decisão descrita na Seção 3. É a função central do módulo.

### 7.4 `processar_usuarios(...)`

Laço principal. Cada usuário tem até 2 tentativas: na primeira falha técnica, aciona `trocar_aba_aghux` + `navegar_ate_cadastro_usuario` e tenta de novo; na segunda falha, marca `erro` com a exceção na mensagem.

### 7.5 `executar_importacao_usuarios(usuarios, usuario_rede, senha, *, url_aghu, mostrar_browser, mostrar_console, diretorio_logs, gerar_csv_log) → list[ResultadoImportacao]`

Função de orquestração central, chamada tanto pela execução unitária quanto pela de lote na UI. Valida credenciais/URL, roda a validação síncrona do lote, abre Playwright/Chromium (`headless=not mostrar_browser`, `slow_mo=500` quando visível), autentica, navega, processa e sempre gera o CSV auditável em `logs/` (a menos que `gerar_csv_log=False`).

### 7.6 `executar_importacao_lote(usuario_rede, senha, caminho_planilha, caminho_relatorio, ...) → (resultados, caminho_relatorio)`

Lê a planilha com `ler_planilha_usuarios`, chama `executar_importacao_usuarios` e depois `salvar_relatorio_resultados` para gravar o XLSX final escolhido pelo operador.

### 7.7 `executar_importacao_individual(usuario_rede, senha, login, nome_completo, email, ...) → ResultadoImportacao` — **função pública não usada pela UI atual**

Existe no núcleo e é coberta pelos testes unitários, mas **não é mais chamada pela UI** desde a release de 03/07/2026: `_executar_individual_thread` passou a montar a lista de `UsuarioImportacao` (até 5 linhas dinâmicas) e chamar `executar_importacao_usuarios` diretamente, para poder reaproveitar a mesma lógica de resumo de múltiplos resultados usada no lote. `executar_importacao_individual` continua pública e funcional (é um atalho de conveniência para um único usuário), mas hoje só é exercitada pelos testes, não por nenhum chamador em produção.

### 7.8 `salvar_relatorio_resultados(resultados, caminho_saida) → Path`

Só aceita `.xlsx` (adiciona a extensão se faltar). Formata a planilha com cabeçalho fixo, congelamento de painel e autofiltro, larguras de coluna proporcionais ao conteúdo (limite 70 caracteres).

---

## 8. Contratos com Chamadores

| Chamador | Uso do núcleo |
|---|---|
| `ui_criar_usuario_aghu.py` | Importa `UsuarioImportacao`, todos os `STATUS_*`, `executar_importacao_usuarios` e `executar_importacao_lote`. Não importa `executar_importacao_individual` nem `ler_planilha_usuarios`/`salvar_relatorio_resultados` diretamente (usa a versão empacotada em `executar_importacao_lote`) |
| `test_unit_criar_usuario_aghu.py` | Testa funções puras (`_validar_usuario`, `_normalizar_*`, `_valor_em_branco`, `_resultado`) e `ler_planilha_usuarios`/`salvar_relatorio_resultados` isoladamente |
| `test_regression_criar_usuario_aghu.py` | Cobertura de regressão do fluxo completo |

Não há mensagens de exceção contratuais entre núcleo e UI (diferente do RFC-001, que tem `ValueError("Impressora não existe")` como contrato com o Almoxarifado). A UI trata qualquer exceção do núcleo de forma genérica, exibindo `f"Erro: {exc}"` em vermelho.

---

## 9. `ui_criar_usuario_aghu.py` — Interface Gráfica

### 9.1 Estrutura geral

Classe `AghuImportUserApp(ctk.CTk)`, com duas seções principais controladas por um `CTkSegmentedButton`:

| Tipo | Rótulo | Campos |
|---|---|---|
| Unitária | `TIPO_INDIVIDUAL` | Lista dinâmica de 1 a `MAX_USUARIOS_MANUAIS` (5) linhas de Login/Nome/E-mail, com botão "+ Adicionar usuário" e botão de remover por linha |
| Lote | `TIPO_LOTE` | Planilha `.xlsx` de entrada + planilha `.xlsx` de relatório de saída, ambas com seletor de arquivo |

### 9.2 Ambiente

```python
URLS_AMBIENTE_AGHU = {
    AMBIENTE_PRODUCAO: AGHU_URL,
    AMBIENTE_HOMOLOGACAO: AGHU_URL_HOMOLOGACAO,
}
```

`AMBIENTE_HOMOLOGACAO` é o valor padrão do seletor (`self.var_ambiente = tk.StringVar(value=AMBIENTE_HOMOLOGACAO)`), em linha com o item 5 do Guia AGHU ("Homologação é o padrão operacional seguro das UIs AGHU"). Ao trocar para Produção, `_on_ambiente_changed` exibe um `messagebox.showwarning` modal e mantém um painel de alerta fixo visível enquanto Produção estiver selecionado.

### 9.3 Regra anti-processo invisível

Igual ao padrão do RFC-003: `_validar_opcoes_visibilidade` impede que **Exibir Navegador** e **Exibir Terminal** fiquem desligados ao mesmo tempo, reativando a última opção alterada e avisando com `messagebox.showwarning`.

### 9.4 Lista dinâmica de usuários (execução unitária)

`adicionar_linha_usuario`/`remover_linha_usuario` mantêm `self.linhas_usuarios_individual` como lista de dicts (`frame`, `login`, `nome_completo`, `email`, `remover`). Ao remover uma linha do meio, as linhas restantes são reindexadas via `grid_configure(row=...)`. O limite de 5 é reforçado tanto ao adicionar (`adicionar_linha_usuario` ignora silenciosamente além do limite, apenas atualizando o texto de aviso) quanto na UI (botão desabilitado).

### 9.5 Execução em thread

Tanto `iniciar_execucao_individual` quanto `iniciar_execucao_lote` validam o formulário na thread principal e disparam uma `threading.Thread(daemon=True)` que chama, respectivamente, `executar_importacao_usuarios` ou `executar_importacao_lote`. O retorno é levado de volta à thread principal via `self.after(0, self._finalizar_execucao, mensagem, cor)`.

### 9.6 Resumo e cor do resultado

`_resumir_resultados` conta cada `StatusImportacao` com `Counter` e monta uma frase única; `_cor_resultado` decide a cor do label de status:

| Condição | Cor |
|---|---|
| Algum `erro` | Vermelho |
| Nenhum erro, mas algum `ignorado` ou `conferir_manualmente` | Laranja |
| Só `importado`/`ja_importado`/`nao_encontrado` | Verde |

Note que `nao_encontrado` (usuário que não existe nem no Identity Manager) conta como "verde" — não é tratado como erro operacional, só como um resultado esperado de negócio.

### 9.7 Relatório

A UI sempre grava o CSV auditável do núcleo em `LOGS_DIR` (`BASE_DIR / "logs"`, dentro de `sistemas/aghu/`) e, no caso de lote, também grava o XLSX final escolhido pelo operador via `executar_importacao_lote`. Na execução unitária não há XLSX de saída — só o CSV interno e a mensagem de status na tela.

---

## 10. Limitações Conhecidas

| Limitação | Impacto |
|---|---|
| `_validar_usuario` não pega nome com espaço indevido no fluxo real (Seção 6.2) | Nomes com espaço duplo ou lateral passam normalizados silenciosamente, mesmo a regra existindo e sendo testada isoladamente |
| Pesquisa no Identity Manager (`_linha_tabela_por_texto`) não ancora o login à célula, apenas usa `has_text` sobre a linha inteira | Diferente da pesquisa na tabela principal do AGHUX (`_linha_tabela_por_login`, que ancora `^\s*login\s*$` numa coluna específica), a pesquisa no Identity Manager pode casar com uma linha cujo texto contenha o login como substring, não como valor exato de coluna |
| `_marcar_usuario_ativo` localiza o checkbox de "ativo" pelo primeiro `.ui-chkbox-icon` visível na janela do sistema (`.first`), sem escopo restrito ao campo | Se o formulário de importação ganhar outro checkbox antes do de "ativo", a automação marcaria o elemento errado |
| `executar_importacao_individual` não é mais chamada pela UI (Seção 7.7) | Função pública mantida e testada, mas órfã de uso em produção; qualquer mudança nela não é validada pelo fluxo real da UI |
| `TEMPO_MAXIMO_CONSULTA_USUARIO_MS = 130000` (130s) | Timeout alto sem justificativa documentada no código; útil se o AGHUX ficar lento, mas mascara problemas de rede por até 2min e meio por linha |
| Sem delegação a outro módulo quando usuário não existe no Identity Manager | Ao contrário do par Maestro/Almoxarifado (RFC-001/002), aqui `nao_encontrado` é terminal — não há tentativa de busca alternativa |
| Leitura de planilha duplica lógica de aliases de coluna presente em `concessor_aghu.py` (módulo de concessão de perfis) | Mudança nos nomes de coluna aceitos precisa ser replicada manualmente nos dois arquivos, se a intenção for manter consistência entre os dois fluxos de usuário |

---

## 11. Estado Atual da RFC

Esta RFC documenta `criar_usuario_aghu.py` e `ui_criar_usuario_aghu.py` como estão na release de 23/07/2026 (validação de lote centralizada e síncrona antes do Playwright) e 03/07/2026 (lista dinâmica de usuários na execução unitária da UI), fechando a lacuna apontada no checklist do `Guia_AGHU.md`: toda função pública do par núcleo/UI está listada nas Seções 7 e 9, e as inconsistências reais encontradas durante o levantamento (Seções 6.2, 7.7 e 10) ficam registradas para decisão futura, em vez de silenciosamente mantidas.
