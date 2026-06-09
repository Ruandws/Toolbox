# RFC-001 — Orquestrador de Vínculos Impressora-Computador (PrinterAGHU)

- **Status:** Estável
- **Autor:** Pedro e Ruan
- **Data:** 2026-06
- **Arquivo:** `PrinterAGHU.py`
- **Depende de:** `AddPrinterAGHU.py` (RFC-002)
- **Chamado por:** `ui_alignprinterAGHU.py` (RFC-003)

---

## 1. Resumo

`PrinterAGHU.py` é o **Maestro** da automação de vínculos computador–impressora no AGHUX. Ele concentra a regra operacional do módulo **Impressora por Computador**: valida a planilha de entrada, autentica a sessão quando necessário, navega até o módulo correto, processa cada computador informado e mantém, altera ou cria vínculos conforme o estado encontrado no sistema.

Quando a impressora informada na planilha não existe no catálogo do AGHUX, o Maestro delega o cadastro ao Robô Especialista (`AddPrinterAGHU.py`, RFC-002), que consulta o CUPS e cria a impressora. Após a delegação, o Maestro reconstrói uma aba limpa, retorna ao módulo de vínculo e tenta novamente a linha corrente.

O arquivo atual não contém interface gráfica própria. A execução assistida por tela, seleção de arquivos e conversão do relatório para XLSX ficam em `ui_alignprinterAGHU.py` (RFC-003). Este módulo permanece como núcleo reutilizável de automação.

---

## 2. Motivação

Vincular impressoras a computadores no AGHUX é uma rotina repetitiva, sensível a divergências silenciosas e dependente de autocompletes JSF. Um computador pode já possuir vínculo correto, possuir vínculo para outra impressora, não possuir vínculo ou nem existir no cadastro. Além disso, a impressora alvo pode não existir no AGHUX, embora exista no CUPS.

O Maestro centraliza esse fluxo em uma rotina auditável com recuperação controlada: tenta operar o vínculo, usa aba limpa quando a interface fica instável, delega o cadastro de impressoras ausentes ao Almoxarifado e registra o resultado por linha em relatório CSV. A separação entre núcleo (`PrinterAGHU.py`) e UI (`ui_alignprinterAGHU.py`) reduz acoplamento e permite que a regra de negócio seja chamada por interface gráfica ou por outro orquestrador.

---

## 3. Arquitetura e Fluxo de Dados

```text
[ui_alignprinterAGHU.py / outro chamador]
        │
        ├─► ler_planilha(caminho_arquivo)        ← Helper reutilizável do Maestro
        │        ├─ Aceita .xlsx, .xlsm e .csv
        │        ├─ Normaliza nomes de colunas
        │        └─ Valida: IPPC, HostPrinter, PrinterClass
        │
        ├─► [Playwright] Browser/context/page criados pelo chamador
        │
        ├─► fazer_login(page, usuario, senha)
        │        └─ Idempotente: se sessão já estiver ativa, segue
        │
        ├─► navegar_ate_modulo(context, page, usuario, senha)
        │        ├─ Outros Módulos → Configuração → Impressão → Cadastros
        │        ├─ Abre "Impressora por Computador"
        │        ├─ Em falha inicial, aciona Clean State
        │        └─ Retorna (page, janela_sistema)
        │
        └─► processar_computadores(...)
                 │
                 ├─ Para cada linha da planilha:
                 │     ├─ Busca computador por IP no autocomplete
                 │     ├─ Pesquisa vínculo existente por IP e classe
                 │     │
                 │     ├─ [Caso A] Vínculo correto      → Status: "Mantido"
                 │     ├─ [Caso B] Vínculo divergente   → Edita  → Status: "Alterado"
                 │     └─ [Caso C] Sem vínculo          → Cria   → Status: "Vinculado"
                 │
                 ├─ Se a impressora não existir no AGHUX:
                 │     └─► Delegação ao Almoxarifado (RFC-002)
                 │           ├─ consultar_dados_site_secundario()
                 │           ├─ navegar_ate_cadastro_impressora()
                 │           └─ cadastrar_nova_impressora()
                 │
                 ├─ Após cadastro delegado:
                 │     ├─ Abre aba limpa
                 │     ├─ Renavega até "Impressora por Computador"
                 │     └─ Reprocessa a mesma linha
                 │
                 └─ Gera CSV auditável:
                       logs/log_resultado_YYYYMMDD_HHMMSS.csv
```

---

## 4. Descrição dos Componentes

### 4.1 `ler_planilha` — Leitura e Validação de Entrada

Recebe um caminho de arquivo e retorna um `DataFrame` normalizado. A função não assume mais um arquivo fixo no diretório do script; o caminho é fornecido pelo chamador.

Formatos aceitos:

| Extensão | Leitor | Observação |
|---|---|---|
| `.xlsx` | `pandas.read_excel(..., engine="openpyxl")` | Entrada Excel padrão |
| `.xlsm` | `pandas.read_excel(..., engine="openpyxl")` | Entrada Excel com macro |
| `.csv` | `pandas.read_csv(..., sep=";")` | Tenta `utf-8-sig`; se falhar, usa `latin1` |

Após leitura, remove espaços dos nomes das colunas com `df.columns.str.strip()`, substitui `NaN` por string vazia e valida as colunas obrigatórias: `IPPC`, `HostPrinter`, `PrinterClass`.

Se o arquivo não existir, lança `FileNotFoundError`. Se a extensão não for aceita ou se colunas obrigatórias estiverem ausentes, lança `ValueError` com mensagem descritiva.

### 4.2 `fazer_login`

Detecta a tela de login procurando primeiro o campo de senha (`input[type='password']`). Quando a tela está presente, localiza o usuário por seletores tolerantes (`input[id*='usuario' i]`, `input[id*='login' i]` ou `input[type='text']`), preenche as credenciais, clica em **Entrar** e aguarda **Outros Módulos** como evidência de autenticação.

A função é idempotente para sessões já autenticadas: se o campo de senha não aparecer em até 3 segundos, captura a exceção e segue para o fluxo de navegação.

### 4.3 `trocar_aba_aghux` — Clean State

Fecha a aba atual, ignorando erro caso ela já esteja indisponível, abre uma nova aba no mesmo `BrowserContext`, navega para `AGHU_URL_PRODUCAO`, executa `fazer_login` e retorna a nova `Page`.

É usada como estratégia de recuperação quando a interface do AGHUX fica em estado inconsistente, quando o menu falha ou quando o fluxo retorna do Almoxarifado. O reaproveitamento do mesmo contexto preserva a configuração de certificado e isolamento do browser criada pelo chamador.

### 4.4 `navegar_ate_modulo` — Navegação com Auto-Recuperação

Navega até **Configuração → Impressão → Cadastros → Impressora por Computador**. Antes de clicar em cada item, verifica se o item de destino já está visível, evitando cliques redundantes em menus já expandidos.

Ao abrir o módulo, captura o último `iframe` da página por `page.frame_locator("iframe").last` e considera a tela carregada quando o botão **Pesquisar** fica visível. Na primeira falha de navegação, chama `trocar_aba_aghux` e tenta novamente. Na segunda falha, propaga a exceção.

### 4.5 `processar_computadores` — Cérebro Maestro

É o laço principal da automação. Recebe `context`, `page`, `janela_sistema`, `planilha`, credenciais e opcionalmente `diretorio_logs`. Para cada linha, extrai:

| Campo | Uso |
|---|---|
| `IPPC` | Busca e seleção do computador no AGHUX |
| `HostPrinter` | Impressora alvo a vincular |
| `PrinterClass` | Classe usada na pesquisa e no vínculo |
| `HostPC` | Apenas log, quando presente |
| `IPPrinter` | Apenas log, quando presente |

O processamento por linha possui até três tentativas para falhas técnicas. O estado inicial é `Erro`/`Falha Desconhecida.` e só é substituído quando a linha alcança um desfecho reconhecido.

Estados finais possíveis:

| Estado | Condição | Ação |
|---|---|---|
| `Mantido` | Já existe vínculo para o IP, classe e impressora correta | Limpa formulário e segue |
| `Alterado` | Existe vínculo para o IP/classe, mas com impressora divergente | Edita o vínculo, troca a impressora e grava |
| `Vinculado` | Não existe vínculo para o IP/classe | Cria novo vínculo |
| `Criado` | A impressora precisou ser cadastrada pelo Almoxarifado nesta execução | Cria ou atualiza vínculo após o cadastro delegado |
| `Inexistente` | Computador não existe no AGHUX ou fila não existe no CUPS | Registra motivo e segue |
| `Erro` | Falha técnica ou erro não recuperável | Registra detalhe e segue |

Na busca do computador, a função usa `press_sequentially(ip_pc, delay=150)` para disparar eventos reais de teclado nos autocompletes JSF. A seleção do IP usa regex com borda e `re.escape`, evitando que `10.6.0.22` corresponda indevidamente a `10.6.0.225`.

Ao editar vínculo divergente, localiza o botão de edição por título (`editar`/`alterar`) ou ícone `.aghu-icon-edit`, limpa o campo de impressora, digita a impressora alvo, seleciona a sugestão e grava.

Ao criar novo vínculo, clica em **Novo**, seleciona o computador, seleciona a impressora e valida a classe. Se a classe preenchida automaticamente pelo AGHUX não corresponder à `PrinterClass`, limpa o campo e usa a lupa para selecionar a classe correta.

### 4.6 Delegação ao Almoxarifado (AddPrinterAGHU)

A delegação é acionada quando a seleção da impressora lança `ValueError("Impressora não existe")`. O Maestro interpreta essa string como indicação de que a fila não está cadastrada no AGHUX.

Fluxo de delegação:

```text
ValueError("Impressora não existe")
        │
        └─► Até 3 tentativas de Almoxarifado:
              ├─ trocar_aba_aghux(...)
              ├─ consultar_dados_site_secundario(context, impressora, classe)
              ├─ navegar_ate_cadastro_impressora(page)
              └─ cadastrar_nova_impressora(janela, dados_cups)
```

Se a delegação for bem-sucedida, o Maestro abre nova aba limpa, renavega até **Impressora por Computador**, marca `impressora_fabricada_agora = True` e usa `continue` para gastar uma nova tentativa da mesma linha. O status final passa a ser `Criado` quando o vínculo é concluído após essa fabricação.

Se o Almoxarifado falhar definitivamente com mensagem contendo `"Não existe no CUPS"`, a linha é marcada como `Inexistente` e recebe o detalhe `Fila de impressão não encontrada no Servidor CUPS.`. Outras falhas do Almoxarifado viram `Erro` com detalhe da exceção capturada.

### 4.7 Relatório de Auditoria

Ao final, `processar_computadores` cria um `DataFrame` de logs e grava um CSV em:

```text
logs/log_resultado_YYYYMMDD_HHMMSS.csv
```

Quando `diretorio_logs` é informado, grava nesse diretório; caso contrário, usa `BASE_DIR / "logs"`.

O CSV é escrito em duas etapas:

1. Abre o arquivo em modo `w` e escreve `Atualizado por: <usuario>` na primeira linha.
2. Faz `df_logs.to_csv(..., mode='a', sep=';', encoding='utf-8-sig')` abaixo da linha de auditoria.

Colunas geradas:

| Coluna | Origem |
|---|---|
| `HostPC` | Planilha, opcional |
| `IPPC` | Planilha, obrigatório |
| `HostPrinter` | Planilha, obrigatório |
| `IPPrinter` | Planilha, opcional |
| `PrinterClass` | Planilha, obrigatório |
| `Status` | Resultado da linha |
| `Detalhes` | Justificativa operacional |

A função retorna `str(nome_arquivo_log)`, permitindo que a UI ou outro chamador localize o CSV gerado. A UI atual não usa diretamente esse retorno; ela localiza o CSV por timestamp e o converte para XLSX.

---

## 5. Decisões Técnicas

### 5.1 Por que a interface gráfica saiu do Maestro?

A versão atual separa responsabilidades. `PrinterAGHU.py` contém regra de negócio, navegação e processamento. `ui_alignprinterAGHU.py` contém seleção de arquivos, execução em thread, opções visuais e conversão do relatório para XLSX. Isso evita que a automação central dependa de um modo único de uso.

### 5.2 Por que o Maestro não usa `fazer_login` do AddPrinterAGHU?

Os dois módulos possuem funções `fazer_login` próprias. A do Maestro detecta o campo de senha primeiro; a do Almoxarifado detecta o campo de usuário primeiro. Ambas são idempotentes, mas a duplicação aumenta custo de manutenção. A unificação permanece recomendada.

### 5.3 Por que `press_sequentially` em vez de `fill` para autocompletes?

O AGHUX usa autocompletes JSF que dependem de eventos de teclado. `fill()` injeta o texto diretamente no DOM e pode não abrir a lista de sugestões. `press_sequentially(..., delay=150)` simula digitação humana e melhora a confiabilidade da seleção.

### 5.4 Por que regex na seleção do IP?

A regex `re.compile(fr"\b{re.escape(ip_pc)}\b")` impede correspondência parcial. Sem isso, um IP curto poderia selecionar uma sugestão com sufixo adicional, como `10.6.0.22` dentro de `10.6.0.225`.

### 5.5 Por que o relatório usa escrita em duas etapas?

`pandas.to_csv` não oferece uma linha de metadados livre acima do cabeçalho tabular. A escrita manual da linha `Atualizado por:` seguida de append do DataFrame preserva autoria sem alterar as colunas do relatório.

### 5.6 Por que `impressora_fabricada_agora` é uma flag?

A flag distingue linhas em que a impressora já existia daquelas em que a impressora foi criada pelo Almoxarifado durante a execução. Isso permite registrar `Criado` em vez de apenas `Alterado` ou `Vinculado`, sem acoplar o retorno do Almoxarifado ao formato do log.

---

## 6. Formato da Planilha de Entrada

A planilha é recebida como `DataFrame` por `processar_computadores`, mas o helper `ler_planilha` aceita os seguintes arquivos:

| Formato | Suporte | Observação |
|---|---|---|
| `.xlsx` | Sim | Leitura via `openpyxl` |
| `.xlsm` | Sim | Leitura via `openpyxl` |
| `.csv` | Sim | Separador `;`, UTF-8-sig com fallback Latin-1 |

Colunas esperadas:

| Coluna | Obrigatória | Descrição |
|---|---:|---|
| `IPPC` | Sim | IP do computador a ser pesquisado/vinculado |
| `HostPrinter` | Sim | Nome da fila de impressora alvo |
| `PrinterClass` | Sim | Classe de impressão esperada, como `PDF` ou `RAW` |
| `HostPC` | Não | Nome do host do computador, usado apenas no log |
| `IPPrinter` | Não | IP da impressora, usado apenas no log |

A automação não valida semanticamente o conteúdo de `PrinterClass`; ela usa a string recebida para comparar classe e selecionar opções no AGHUX.

---

## 7. Tratamento de Erros

| Situação | Origem | Comportamento |
|---|---|---|
| Arquivo de entrada inexistente | `ler_planilha` | `FileNotFoundError` imediato |
| Extensão inválida | `ler_planilha` | `ValueError("Formato inválido. Use .xlsx, .xlsm ou .csv.")` |
| Colunas obrigatórias ausentes | `ler_planilha` | `ValueError` com lista de colunas faltantes |
| Tela de login ausente | `fazer_login` | Assume sessão ativa e segue |
| Falha ao navegar no menu | `navegar_ate_modulo` | 1 retry com `trocar_aba_aghux`; depois propaga erro |
| Computador não encontrado | Autocomplete do computador | Status `Inexistente`; detalhe `Computador não cadastrado no AGHUX.` |
| Impressora não existe no AGHUX | Autocomplete da impressora | Delegação ao Almoxarifado em até 3 tentativas |
| Fila não existe no CUPS | Almoxarifado | Status `Inexistente`; detalhe específico no log |
| Falha técnica genérica | Qualquer passo de linha | Até 3 tentativas com Clean State; depois status `Erro` |
| Erro sem recuperação imediata | `ValueError` diferente dos contratos esperados | Cancela/limpa quando possível e registra `Erro` |

---

## 8. Limitações Conhecidas

- `AGHU_URL_PRODUCAO` está hardcoded em `PrinterAGHU.py` e também em `ui_alignprinterAGHU.py`, criando risco de divergência entre módulos.
- O arquivo importa `AddPrinterAGHU`, portanto o módulo precisa estar disponível com esse nome no ambiente de execução. Cópias renomeadas, como arquivos com sufixo de download, exigem ajuste antes de execução direta.
- `fazer_login` está duplicado em relação ao Almoxarifado.
- O contrato entre Maestro e Almoxarifado depende de strings de erro específicas: `"Impressora não existe"` e `"Não existe no CUPS"`.
- A busca por iframe usa o último iframe da página. Se o AGHUX inserir iframes auxiliares após o módulo principal, a referência pode quebrar.
- Seletores baseados em texto visível do menu dependem da interface em português.
- Há uso amplo de `except:` e `except Exception`, o que simplifica recuperação, mas reduz precisão diagnóstica.
- `processar_computadores` gera CSV, mas não XLSX; a conversão para XLSX é responsabilidade da UI.
- A UI atual não passa `diretorio_logs`; presume que `PrinterAGHU.py` e `ui_alignprinterAGHU.py` compartilham o mesmo `BASE_DIR`.

---

## 9. Alterações Futuras Consideradas

- Extrair URLs de AGHUX e CUPS para configuração única externa.
- Unificar autenticação em um módulo compartilhado, como `aghux_utils.py`.
- Substituir contratos por string por exceções tipadas (`ComputadorNaoEncontrado`, `ImpressoraNaoExiste`, `FilaNaoExisteNoCUPS`).
- Receber `diretorio_logs` explicitamente a partir da UI, eliminando dependência implícita de diretório.
- Substituir `print()` por `logging` estruturado com níveis e arquivo de diagnóstico.
- Melhorar seletores de iframe e formulário com IDs estáveis quando disponíveis.
- Adicionar modo `dry-run` para simular alterações sem gravar no AGHUX.
- Retornar objeto estruturado de execução, além do caminho do CSV.
