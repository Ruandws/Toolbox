## Checklist - Nova Automação AGHUx

> Nota: este checklist complementa `docs/guias/Guia_AGHU.md`. Em caso de conflito, prevalecem o guia e as RFCs AGHU aplicáveis.
> Práticas genéricas de estrutura de projeto, UI/execução, planilhas, resiliência e relatórios foram extraídas para `docs/guias/Checklist_Backend_Gn.md`; consulte-o em conjunto com este documento.

Resumo prático para preparar uma nova automação AGHUx alinhada aos padrões atuais do projeto. Itens específicos do AGHU/JSF ficam aqui; práticas de backend independentes de sistema estão em `Checklist_Backend_Gn.md`.

### Antes de codar
- [ ] Mapear a árvore de menu completa até o módulo alvo em uma constante `CAMINHO_MENU_*`
- [ ] Confirmar se o módulo abre no iframe padrão retornado por `navegar_menu_aghu`; documentar exceções se não for `page.frame_locator("iframe").last`
- [ ] Identificar quais campos são autocomplete JSF e quais são inputs normais
- [ ] Identificar quais dropdowns são `selectOneMenu` JSF e quais são `<select>` nativo
- [ ] Mapear mensagens de sucesso, erro, duplicidade, "nenhum registro encontrado" e estados inconclusivos
- [ ] Definir previamente quando o robô deve alterar, manter, incluir, ignorar ou marcar como "conferir manualmente"

### Estrutura do projeto (específico AGHU)
- [ ] Reusar `autenticador.py` para login; não duplicar fluxo de autenticação dentro do robô
- [ ] Reusar `menu.py` para navegação; não reimplementar cliques de menu em cada automação
- [ ] URLs do AGHU devem vir de `autenticador.py`, constantes de ambiente ou variáveis de ambiente; evitar URL solta no meio do código
- [ ] Para separação UI/núcleo, posse dos recursos Playwright e demais itens de estrutura, ver `Checklist_Backend_Gn.md`

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
- [ ] Práticas gerais de leitura/validação de planilha estão em `Checklist_Backend_Gn.md`
- [ ] Validar regras de negócio da entrada antes de acionar o AGHU sempre que possível

### Autocompletes
- [ ] Para autocomplete JSF, usar `press_sequentially(valor, delay=150)`; evitar `fill()` quando a lista depende de eventos de teclado
- [ ] Usar timeout de pelo menos 5-6s para a lista flutuante
- [ ] Para IPs, logins ou valores com números/sufixos, usar regex com limites customizados de valor, não apenas `\b`
- [ ] Após selecionar item crítico, validar que o valor selecionado corresponde ao esperado
- [ ] Registrar como "conferir manualmente" quando a seleção retornar valor divergente

### Resiliência (específico AGHU)
- [ ] Implementar Clean State no formato AGHU: fechar aba atual, abrir nova aba, relogar via `autenticador.py` e renavegar ao módulo com `navegar_menu_aghu`
- [ ] Demais práticas de retry, `try/finally`, `except Exception:` e diferenciação erro de negócio/técnico estão em `Checklist_Backend_Gn.md`

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
- [ ] Práticas de geração de relatório/CSV/XLSX estão em `Checklist_Backend_Gn.md`
- [ ] Tratar duplicidade e demais mensagens de negócio do AGHU nos detalhes do relatório, conforme mapeado em "Antes de codar"
