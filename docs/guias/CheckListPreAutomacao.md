## Checklist - Nova Automação AGHUx

> Nota: este checklist complementa `docs/guias/Guia_AGHU.md`. Em caso de conflito, prevalecem o guia e as RFCs AGHU aplicáveis.

Resumo prático para preparar uma nova automação AGHUx alinhada aos padrões atuais do projeto.

### Antes de codar
- [ ] Mapear a árvore de menu completa até o módulo alvo em uma constante `CAMINHO_MENU_*`
- [ ] Confirmar se o módulo abre no iframe padrão retornado por `navegar_menu_aghu`; documentar exceções se não for `page.frame_locator("iframe").last`
- [ ] Identificar quais campos são autocomplete JSF e quais são inputs normais
- [ ] Identificar quais dropdowns são `selectOneMenu` JSF e quais são `<select>` nativo
- [ ] Mapear mensagens de sucesso, erro, duplicidade, "nenhum registro encontrado" e estados inconclusivos
- [ ] Definir previamente quando o robô deve alterar, manter, incluir, ignorar ou marcar como "conferir manualmente"

### Estrutura do projeto
- [ ] Reusar `autenticador.py` para login; não duplicar fluxo de autenticação dentro do robô
- [ ] Reusar `menu.py` para navegação; não reimplementar cliques de menu em cada automação
- [ ] Separar UI (`customtkinter`) do núcleo Playwright
- [ ] Definir posse dos recursos Playwright: UI/chamador cria e fecha `Browser`, `BrowserContext` e `Page` principal; núcleo recebe `context/page` e só cria abas auxiliares para Clean State ou consultas
- [ ] Se houver tarefa auxiliar delegável, criar especialista separado e deixar o maestro controlar retry/retomada
- [ ] URLs do AGHU devem vir de `autenticador.py`, constantes de ambiente ou variáveis de ambiente; evitar URL solta no meio do código
- [ ] IPs/URLs externas inevitáveis devem ficar em constantes nomeadas e ter proteção contra ambiente errado quando aplicável

### UI e execução
- [ ] Quando houver UI, executar tarefas longas fora da thread principal para manter a interface responsiva
- [ ] Durante a execução, desabilitar o botão de início e restaurar o estado da UI ao finalizar com sucesso ou erro
- [ ] Atualizações de status vindas da thread de automação devem voltar para a thread da UI por callback seguro (`after`, fila ou equivalente)

### Ambiente
- [ ] Oferecer seleção clara entre Produção e Homologação quando a automação tiver UI
- [ ] Exibir alerta quando o ambiente selecionado for Produção
- [ ] Passar `url_aghu` por parâmetro até login, clean state e navegação; não fixar produção em chamadas internas
- [ ] Validar que automações auxiliares não selecionem recursos de homologação quando estiverem criando dados em produção

### Autenticação
- [ ] Criar `BrowserContext` com `ignore_https_errors=True` nas execuções AGHUx
- [ ] Usar `autenticar_aghu_page(page, usuario, senha, url_login=url_aghu, timeout_ms=15000)`
- [ ] Chamar `exigir_login_valido(resultado)` após autenticar
- [ ] Login deve ser idempotente: sessão ativa deve ser aceita como sucesso
- [ ] Wrappers locais `fazer_login` devem apenas delegar para o autenticador centralizado

### Navegação
- [ ] Declarar caminho de menu completo em tupla, por exemplo `("Outros Módulos", "Configuração", "...")`
- [ ] Usar `navegar_menu_aghu(page, caminho=CAMINHO_MENU_*)`
- [ ] Após navegar, validar um elemento específico da tela alvo antes de iniciar processamento
- [ ] Em falha de navegação, aplicar Clean State e tentar novamente antes de abortar

### Planilhas e entradas
- [ ] Definir `COLUNAS_OBRIGATORIAS_PLANILHA` no núcleo da automação
- [ ] Validar existência do arquivo, extensão permitida e colunas obrigatórias antes de abrir o navegador
- [ ] Ler Excel com `dtype=str` e `engine="openpyxl"`
- [ ] Para CSV, usar `sep=";"`, `encoding="utf-8-sig"` e fallback para `latin1`
- [ ] Normalizar nomes de colunas com `df.columns.str.strip()`
- [ ] Tratar campos obrigatórios em branco como linha ignorada ou erro descritivo, sem quebrar o lote inteiro
- [ ] Validar regras de negócio da entrada antes de acionar o AGHU sempre que possível

### Autocompletes
- [ ] Para autocomplete JSF, usar `press_sequentially(valor, delay=150)`; evitar `fill()` quando a lista depende de eventos de teclado
- [ ] Usar timeout de pelo menos 5-6s para a lista flutuante
- [ ] Para IPs, logins ou valores com números/sufixos, usar regex com limites customizados de valor, não apenas `\b`
- [ ] Após selecionar item crítico, validar que o valor selecionado corresponde ao esperado
- [ ] Registrar como "conferir manualmente" quando a seleção retornar valor divergente

### Resiliência
- [ ] Implementar Clean State: fechar aba atual, abrir nova aba, relogar e renavegar ao módulo
- [ ] Retry por item/registro: normalmente 2 tentativas para navegação e 2-3 para processamento
- [ ] Usar `try/finally` para fechar browser e abas auxiliares
- [ ] Abas auxiliares, como consultas externas, devem ser fechadas também nos caminhos de erro
- [ ] Usar `except Exception:` quando for necessário capturar falha técnica geral; evitar `except:` nu
- [ ] Diferenciar erro de negócio previsível de falha técnica/rede/navegador
- [ ] Quando o AGHU não retornar sucesso nem erro conhecido, marcar estado indefinido para conferência manual

### Seletores
- [ ] Preferir seletores por atributo estável (`input[id*='campo' i]`, `name`, tabela por `id`) sobre texto visível
- [ ] Para itens de menu, usar `get_by_text(..., exact=True)` via helper centralizado
- [ ] Para tabelas JSF, validar linhas reais e ignorar linha `ui-datatable-empty-message`
- [ ] Ao depender de posição (`nth`, `first`, `last`), documentar qual campo ou botão aquele fallback representa
- [ ] Para botões/ações em tabela, buscar por `title`, `aria-label`, role ou classe sem depender de uma única variante
- [ ] Evitar selecionar por texto amplo quando houver risco de falso positivo em outra coluna

### Regras de decisão
- [ ] Definir status finais padronizados antes da execução (`Criado`, `Alterado`, `Mantido`, `Vinculado`, `Inexistente`, `Erro`, `Ignorado`, etc.)
- [ ] Registrar divergências de dados como "conferir manualmente" quando a automação não puder decidir com segurança
- [ ] Tratar duplicidade retornada pelo AGHU como caso de negócio, não como falha técnica genérica
- [ ] Para automações com especialista auxiliar, registrar se a linha foi criada pelo especialista antes de retomar o fluxo principal

### Relatórios
- [ ] Gerar relatório por linha processada com status e detalhes descritivos
- [ ] Incluir auditoria quando o formato comportar: usuário executor e data/hora de geração
- [ ] Se o núcleo gerar CSV, manter separador `;` e `utf-8-sig`
- [ ] Quando houver UI, entregar XLSX final na camada de UI
- [ ] Automações sem CSV intermediário podem gerar XLSX direto, desde que preservem status, detalhes, filtros e colunas legíveis
- [ ] Relatórios devem ser gerados mesmo quando parte das linhas falhar
