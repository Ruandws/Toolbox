# SPEC.md — Especificação de Requisitos: Senna
> Fonte da verdade do projeto. Toda decisão de arquitetura, escopo e implementação deve ser validada contra este documento.

---

## 1. Visão Geral

O **Senna** é uma aplicação desktop em Python que centraliza automações web voltadas à gestão de usuários em sistemas hospitalares.

O técnico de TI, ao receber um chamado, abre o Senna, seleciona o sistema-alvo, escolhe o procedimento desejado, preenche o formulário e dispara a automação. O Senna executa o fluxo via Playwright em segundo plano e exibe o resultado na interface.

**Usuários:** Técnico de TI (executa procedimentos), Coordenador de TI (consulta logs de auditoria), Desenvolvedor (estende o Senna com novos sistemas e procedimentos).

---

## 2. Objetivos

| # | Objetivo | Critério de Sucesso |
|---|----------|---------------------|
| O1 | Automatizar procedimentos repetitivos | Execução de ponta a ponta sem intervenção manual |
| O2 | Permitir processamento em lote via planilha |

---

## 3. Stack de Tecnologias

| Componente | Tecnologia | Versão |
|------------|-----------|--------|
| Linguagem | Python | 3.14 |
| Automação Web | Playwright | 1.58 |
| Interface Gráfica | CustomTkinter | 5.2.2 |
| Processamento de Dados | Pandas | 3.0.1 |
| Manipulação de Planilhas | openpyxl | >=3.1.5 |
| Variáveis de Ambiente | python-dotenv | >=1.0 |
| Linter | Ruff | latest |
| Versionamento | Git | — |

---



### 6.1 Camadas

```
┌──────────────────────────────────────┐
│           Interface (CustomTkinter)   │  ← ui_main.py, forms.py
├──────────────────────────────────────┤
│              Orchestrator             │  ← orquestra sistema + procedimento
├──────────────────────────────────────┤
│  Core (Contratos, Config, Logger)    │  ← ABCs, Settings, Result[T,E]
├──────────────────────────────────────┤
│       Systems (S1…S5)                │  ← client, procedures, pages, locators
├──────────────────────────────────────┤
│           Utils                       │  ← BrowserFactory, DataLoader
└──────────────────────────────────────┘
```

### 6.2 Fluxo de Execução

```
Técnico seleciona sistema + procedimento
        │
        ▼
UI coleta e valida payload via forms.py
        │
        ▼
Orchestrator.get_procedure(sistema, proc)
        │
        ▼
procedure.validate(payload) ──falha──► exibe erro na UI
        │ sucesso
        ▼
BrowserFactory abre BrowserContext isolado
        │
        ▼
system.login(ctx)
        │
        ▼
procedure.execute(payload) → Result[T, E]
        │
        ▼
system.logout(ctx) ──► BrowserContext encerrado
        │
        ▼
audit_logger.write(entrada_json)
        │
        ▼
UI exibe resultado ao técnico
```

### 6.3 Padrão Result

Toda operação retorna `Result[T, E]` — nunca lança exceção para a camada de UI. A UI lê `result.success` para decidir o que exibir.

### 6.4 Padrão Page Object

Cada sistema possui `pages/` com classes que encapsulam ações de tela e `locators/` com seletores isolados. Procedimentos **nunca** contêm seletores diretamente.

---







### Fase 1 — Contratos e Orquestração (Sprint 2)
**Objetivo**: esqueleto de extensão funcionando.

- [x] `1.1` Implementar `core/base_system.py`: ABC com `login`, `logout`, `is_logged_in`.

**Critério de saída**: `Orchestrator` instancia corretamente qualquer procedimento registrado.

---

### Fase 2 — Sistema Piloto: Serviços TI (Sprint 3–4)
**Objetivo**: primeiro sistema completo, do login à execução de procedimento.

- [x] `2.1` Implementar `systems/servicos_ti/config.py`: URL base, seletores, timeouts.


**Critério de saída**: os 2 procedimentos executam com sucesso em staging; logs de auditoria gerados corretamente.

---

### Fase 3 — Interface Gráfica (Sprint 5)
**Objetivo**: UI funcional conectada ao Orchestrator.

- [x] `3.1` Implementar `interface/forms.py`: definição declarativa de campos por procedimento.
- [x] `3.2` Implementar `interface/ui_main.py`: tela inicial, seleção de sistema, formulário dinâmico, área de resultado.
- [x] `3.3` Conectar UI → `Orchestrator` → `Result` → exibição.
- [x] `3.4` Indicador de progresso durante execução (thread separada para não travar a UI).
- [x] `3.5` Exibição inline de erros de validação de formulário.
- [x] `3.6` Testes unitários de lógica de formulários (validação de campos).

**Critério de saída**: técnico consegue executar procedimentos no sistema piloto pela UI sem erros visuais.

---

### Fase 4 — Processamento em Lote (Sprint 6)
**Objetivo**: importar planilha e executar N registros sequencialmente.

- [ ] `4.1` Implementar `utils/data_loader.py`: leitura de CSV/XLSX, validação de colunas obrigatórias.
- [ ] `4.2` Integrar DataLoader à UI: botão "Importar Planilha", tabela de preview.
- [ ] `4.3` Executar linhas sequencialmente, atualizando progresso linha a linha.
- [ ] `4.4` Gerar relatório de execução em `data/output/` (CSV com status por linha).
- [ ] `4.5` Testes unitários de `data_loader.py` com arquivos de `tests/testdata/`.

**Critério de saída**: planilha com 10 registros processada, relatório gerado, falhas individuais não interrompem o lote.

---

### Fase 5 — Sistemas Adicionais (Sprint 7–9)
**Objetivo**: replicar padrão do sistema piloto para os demais 4 sistemas.

- [ ] `5.1` Implementar `systems/aghux/` completo (client, config, locators, pages, procedures).
- [ ] `5.2` Implementar `systems/integra/` completo.
- [ ] `5.3` Implementar sistemas S4 e S5 completos.
- [ ] `5.4` Registrar todos os sistemas em `AVAILABLE_SYSTEMS`.
- [ ] `5.5` Testes de integração para cada sistema.

**Critério de saída**: todos os 5 sistemas operáveis pela UI; testes de integração verdes.

---

### Fase 6 — Testes E2E e Qualidade (Sprint 10)
**Objetivo**: cobertura completa, zero regressões.

- [ ] `6.1` Implementar cenários E2E em `tests/e2e/scenarios/` para os fluxos críticos.
- [ ] `6.2` Cobertura de testes ≥ 100% medida via `pytest --cov`.
- [ ] `6.3` Pipeline CI local: `ruff check . && pytest` como hook de pre-commit.
- [ ] `6.4` Revisão e atualização da documentação em `docs/`.

**Critério de saída**: cobertura ≥ 100%; zero erros Ruff; todos os testes E2E verdes.

---

## 9. Workflow Git

### 9.1 Fluxo Obrigatório

Todo desenvolvimento deve seguir **estritamente** esta ordem:

```
Codificar → Testes unitários → Testes de integração → Ruff → Commit
```

Se qualquer etapa falhar: corrigir e repetir o ciclo. Commit é proibido antes de tudo passar.

### 9.2 Regra de Commit

Um commit só é permitido quando todos os testes unitários e de integração passam e Ruff não retorna erros.

### 9.3 Convenção de Commits

Formato obrigatório: `<tipo>: <descrição curta>`

| Tipo | Uso |
|------|-----|
| `feat` | nova automação ou funcionalidade |
| `fix` | correção de erro |
| `refactor` | reorganização interna sem mudança funcional |
| `test` | novos testes ou melhoria de testes |
| `chore` | ajustes técnicos |
| `docs` | documentação |

Commits vagos (`fix stuff`, `update`, `changes`) são proibidos.

### 9.4 Frequência

Um commit deve representar **uma única mudança lógica**. Pequenos, frequentes e coerentes.

### 9.5 Hook de Verificação

Configurar pre-commit hook executando `ruff check . && pytest`. Commit bloqueado automaticamente em caso de falha.

---

## 10. Riscos e Mitigações

---

## 11. Glossário
