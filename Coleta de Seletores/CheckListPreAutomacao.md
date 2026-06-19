## Checklist — Nova Automação AGHUx

Resumo prático para quem vai começar uma nova automação:

```markdown
### Antes de codar
- [ ] Mapear a árvore de menu completa até o módulo alvo
- [ ] Inspecionar se o iframe do módulo tem `name` ou `id` estável
- [ ] Identificar quais campos são autocomplete JSF vs inputs normais
- [ ] Identificar quais dropdowns são `selectOneMenu` JSF vs `<select>` nativo

### Estrutura do projeto
- [ ] Separar UI (customtkinter) do núcleo (Playwright)
- [ ] Se houver tarefa auxiliar delegável → criar Especialista separado
- [ ] URLs e IPs em constantes ou `.env`, nunca hardcoded no meio do código

### Autenticação
- [ ] `BrowserContext` com `ignore_https_errors=True`
- [ ] `fazer_login` idempotente (não falha se já logado)

### Autocompletes
- [ ] Usar `press_sequentially(valor, delay=150)` — nunca `fill()`
- [ ] Usar regex com `\b` para seleção quando o valor contém números
- [ ] Timeout de pelo menos 5-6s para a lista flutuante

### Resiliência
- [ ] Implementar Clean State (nova aba + relogin + renavegar)
- [ ] Retry por item (2-3 tentativas por linha/registro)
- [ ] `try/finally` para fechar abas auxiliares
- [ ] `except Exception:` em vez de `except:` genérico

### Relatórios
- [ ] Gerar CSV com auditoria (quem executou, quando)
- [ ] Conversão para XLSX na camada de UI
- [ ] Status descritivo por linha processada

### Seletores
- [ ] Preferir seletores por atributo (`input[id*='campo' i]`) sobre texto visível
- [ ] Usar `exact=True` em `get_by_text` para itens de menu
- [ ] Documentar fallbacks posicionais com comentário explicando qual campo representam
```