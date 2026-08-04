## Checklist - UI Padronizada para Automacoes

> Nota: este checklist define o padrao minimo para novas UIs e para refatoracoes de UIs existentes. Quando uma regra nao se aplicar ao sistema, registre a excecao sempre na RFC correspondente (nunca apenas no release).

Resumo pratico para manter as UIs de automacao consistentes, seguras e testaveis nos sistemas AGHUX, Servicos TI e demais frentes do projeto.

### 1. Estrutura geral da janela
- [ ] Usar `customtkinter` como toolkit padrao.
- [ ] Nomear a classe principal de forma especifica ao fluxo, evitando nomes genericos.
- [ ] Definir titulo da janela com sistema e acao principal, por exemplo `AGHUX - Cadastro de Pessoa`.
- [ ] Configurar `geometry`, `minsize`, `resizable(True, True)`, `grid_columnconfigure(0, weight=1)` e `grid_rowconfigure` quando houver conteudo expansivel.
- [ ] Usar `CTkScrollableFrame` para telas com muitos campos ou que possam exceder a altura de monitores menores.
- [ ] Separar a montagem da tela em metodos pequenos de builder, como `_criar_campos_acesso`, `_criar_seletor_tipo_execucao`, `_criar_campos_individual` e `_criar_campos_lote`.
- [ ] Manter layout em secoes previsiveis: `Acesso`, `Tipo de Execucao`, `Execucao Unitaria`, `Execucao em Lote`, `Status`.
- [ ] Evitar textos informativos longos dentro da UI; quando forem necessarios, manter uma unica mensagem objetiva e sem duplicidade.

### 2. Acesso, credenciais e ambiente
- [ ] Separar coleta de credenciais em metodo dedicado, como `_credenciais_e_url`.
- [ ] Aplicar `.strip()` no usuario/login, mas preservar a senha original com `entry_senha.get()`.
- [ ] Validar senha vazia sem normalizar o valor repassado para a automacao.
- [ ] Quando houver ambiente, usar seletor explicito entre `Homologacao` e `Producao`.
- [ ] Usar `Homologacao` como padrao operacional seguro quando o sistema permitir.
- [ ] Resolver URL por funcao centralizada, como `obter_url_ambiente_*`.
- [ ] Exibir alerta visual persistente quando `Producao` estiver selecionada.
- [ ] Exibir modal de aviso ao trocar para `Producao`, com `parent=self`.
- [ ] Bloquear o seletor de ambiente durante a execucao.
- [ ] Repassar a URL resolvida para login, navegacao, retries, Clean State e processamento.

### 3. Tipo de execucao
> Aplicavel apenas quando o fluxo suporta mais de um modo de execucao (unitaria e lote). Quando a automacao so existe em um modo por natureza do negocio (ex.: fluxo exclusivamente em lote), nao criar um seletor artificial para cumprir a forma do checklist; registrar a nao aplicabilidade na RFC do modulo, como no item 2.
- [ ] Quando houver mais de um modo de execucao, usar `CTkSegmentedButton` para escolher explicitamente entre `Unitaria` e `Lote`.
- [ ] Nao inferir modo lote apenas pela presenca de planilha ou pasta preenchida.
- [ ] Mostrar apenas os campos do modo selecionado, usando `grid` e `grid_remove`.
- [ ] Destacar visualmente a opcao selecionada no segmented button.
- [ ] Bloquear a troca de modo enquanto a automacao estiver em execucao.
- [ ] Centralizar o despacho em um metodo como `iniciar_execucao`, chamando `iniciar_execucao_individual` ou `iniciar_execucao_lote`.

### 4. Entradas individuais
- [ ] Validar campos obrigatorios antes de criar a thread da automacao.
- [ ] Normalizar entradas de usuario antes de passar ao nucleo, sem esconder erros de validacao.
- [ ] Usar controles adequados ao tipo de dado: `CTkEntry` para texto, `CTkSegmentedButton` para opcoes pequenas, `CTkOptionMenu` para listas e `CTkCheckBox` ou `CTkSwitch` para booleanos.
- [ ] Quando houver multiplos itens manuais, permitir adicionar/remover linhas com limite maximo definido em constante.
- [ ] Nao permitir remover a ultima linha quando ao menos um registro manual for obrigatorio.
- [ ] Reindexar titulos e linhas depois de remocao.
- [ ] Desabilitar todos os campos individuais durante a execucao.
- [ ] Preservar ordem e valores coletados da tela ao montar os objetos de entrada.

### 5. Execucao em lote
- [ ] Usar `filedialog.askopenfilename` para selecionar planilha de entrada.
- [ ] Restringir planilha de entrada a `.xlsx`, salvo excecao documentada.
- [ ] Validar extensao da planilha antes de abrir navegador ou iniciar Playwright.
- [ ] Preferir campo de relatorio como arquivo `.xlsx` de saida, selecionado por `filedialog.asksaveasfilename`.
- [ ] Gerar caminho de relatorio padrao com timestamp quando o usuario ainda nao tiver informado saida.
- [ ] Ao selecionar a planilha, preencher o relatorio padrao automaticamente sem sobrescrever escolha manual existente.
- [ ] Validar extensao `.xlsx` do relatorio de saida.
- [ ] Retornar no status final o caminho do relatorio gerado.
- [ ] Garantir que o nucleo gere resultado por linha, mesmo quando parte do lote falhar.

### 6. Opcoes de visibilidade e logs
- [ ] Oferecer opcao clara para exibir navegador em modo visual quando a automacao suportar headless.
- [ ] Oferecer opcao clara para exibir terminal/logs de execucao.
- [ ] Impedir que navegador e console/log fiquem ocultos ao mesmo tempo. Isso cria processo invisivel.
- [ ] No Windows, quando necessario, centralizar a alocacao de console em funcao propria e tolerante a erro.
- [ ] Repassar flags de visibilidade para a camada de automacao, em vez de acoplar essa decisao ao nucleo.
- [ ] Definir diretorio de logs por constante quando o fluxo gerar arquivos de log.

### 7. Controle de execucao e threading
- [ ] Usar flag `em_execucao` para impedir duplo clique e execucoes concorrentes pela mesma janela.
- [ ] Rodar tarefas longas em `threading.Thread(..., daemon=True)`.
- [ ] Nunca atualizar widgets diretamente a partir da thread de automacao.
- [ ] Usar `self.after(0, self._finalizar_execucao, mensagem, cor)` ou equivalente para retornar a thread da UI.
- [ ] Centralizar bloqueio de tela em `_bloquear_execucao`.
- [ ] Centralizar liberacao de tela em `_liberar_execucao`.
- [ ] Bloquear botao executar, seletor de modo, seletor de ambiente, campos, botoes de planilha/relatorio e opcoes de visibilidade durante a execucao.
- [ ] Liberar todos os controles no caminho de sucesso e no caminho de erro.
- [ ] Alterar texto do botao principal para `Executando...` durante o processamento e restaurar ao final.

### 8. Status, retorno e resumo
- [ ] Usar label de status unico e sempre visivel.
- [ ] Inicializar status com `Pronto para execucao.`.
- [ ] Usar mensagens de erro iniciadas por `Erro:` para validacoes e excecoes.
- [ ] Usar cores de status consistentes: cinza para pronto, azul para executando, verde para sucesso, vermelho para erro e laranja/amarelo para alerta quando aplicavel.
- [ ] Criar metodo unico de atualizacao, como `_mostrar_status` ou `show_status`.
- [ ] Criar metodo unico de finalizacao, como `_finalizar_execucao`, que atualiza status e libera a UI.
- [ ] Para lote, resumir resultado por status conhecido: total, sucesso, mantidos/ja existentes, nao encontrados, ignorados, conferir manualmente e erros, conforme o fluxo.
- [ ] Para execucao unitaria com multiplos itens manuais, usar o mesmo padrao de resumo do lote quando houver mais de um item.
- [ ] Evitar retornar somente mensagem livre quando houver status estruturado disponivel no nucleo.

> Nota: este item depende do nucleo devolver resultado estruturado por item processado. Quando o nucleo ainda so retorna uma string agregada (sem status por linha), o gap e do nucleo, nao da UI. Nao simular estrutura na camada de UI; registrar a pendencia na RFC do nucleo correspondente.

### 9. Separacao entre UI e nucleo
- [ ] UI deve apenas coletar dados, validar formulario, iniciar thread, exibir status e repassar parametros.
- [ ] Validacoes de negocio reutilizaveis devem ficar no nucleo da automacao.
- [ ] A UI deve importar funcoes publicas do nucleo, nao funcoes privadas com prefixo `_`.
- [ ] Objetos de entrada e constantes de status devem ser definidos no nucleo quando usados por mais de uma camada.
- [ ] Nao duplicar regras de planilha, normalizacao ou relatorio na UI quando ja existirem no nucleo.
- [ ] A UI deve traduzir `ValueError` em status de erro claro, sem stack trace para o usuario final.
- [ ] Excecoes tecnicas inesperadas devem ser capturadas na thread e retornadas como status vermelho.

### 10. Padrao visual e ergonomia
- [ ] Usar labels alinhados a direita e campos expansivos com `sticky="ew"` em formularios.
- [ ] Configurar pesos de coluna para manter campos responsivos.
- [ ] Usar alturas consistentes para botoes principais e linhas compactas.
- [ ] Manter botoes de selecao de arquivo com largura fixa.
- [ ] Usar placeholders objetivos, indicando formato esperado quando necessario.
- [ ] Usar mascara de digitacao apenas quando ela reduzir erro do usuario, como datas `dd/mm/aaaa`.
- [ ] Nao esconder validacao importante apenas em placeholder; validar antes de executar.
- [ ] Manter o botao principal em posicao previsivel, preferencialmente ao fim do conteudo.
- [ ] Usar `wraplength` e `justify="left"` em mensagens que possam ser longas.

### 11. Testes obrigatorios de UI
- [ ] Criar testes unitarios da UI com widgets fake quando a janela real nao precisar abrir.
- [ ] Testar selecao de modo `Unitaria/Lote`.
- [ ] Testar alerta de `Producao`, quando houver ambiente.
- [ ] Testar validacao que impede processo totalmente invisivel.
- [ ] Testar coleta de credenciais preservando senha sem `.strip()`.
- [ ] Testar selecao de planilha cancelada sem alterar campos.
- [ ] Testar preenchimento automatico do relatorio padrao.
- [ ] Testar nao sobrescrever relatorio ja informado.
- [ ] Testar validacao de extensao da planilha e do relatorio.
- [ ] Testar bloqueio e liberacao da UI durante execucao.
- [ ] Testar que `threading.Thread` recebe os argumentos corretos e `daemon=True`.
- [ ] Testar que a thread agenda finalizacao via `after`.
- [ ] Testar resumo final por status conhecido.

### 12. Documentacao e release
- [ ] Registrar alteracoes relevantes de UI em release do sistema.
- [ ] Documentar excecoes ao padrao sempre na RFC correspondente, quando a automacao tiver restricao tecnica real.
- [ ] Atualizar RFC ou guia especifico quando a UI introduzir novo contrato com o nucleo.
- [ ] Citar arquivos alterados no release.
- [ ] Citar testes executados no release.
- [ ] Quando uma melhoria for globalizavel, avaliar se este checklist tambem deve ser atualizado.

### 13. Checklist rapido antes de liberar
- [ ] Tela abre com tamanho adequado e sem campos cortados.
- [ ] Homologacao é o padrao quando existir ambiente.
- [ ] Producao tem alerta persistente e modal.
- [ ] Modo `Unitária/Lote` e explicito.
- [ ] Campos do modo não selecionado ficam ocultos.
- [ ] Senha nao é normalizada antes de ser repassada.
- [ ] Planilha e relatorio validam `.xlsx`.
- [ ] Relatorio padrao e gerado automaticamente.
- [ ] Botao executar nao permite duplo clique.
- [ ] Todos os controles relevantes bloqueiam durante execucao.
- [ ] A UI volta ao estado normal depois de sucesso ou erro.
- [ ] Status final e claro e inclui resumo ou caminho do relatorio.
- [ ] Testes unitarios cobrem os comportamentos principais da UI.
