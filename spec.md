# SPEC.md — Especificação de Requisitos: Extrator
> Fonte da verdade do projeto. Toda decisão de arquitetura, escopo e implementação deve ser validada contra este documento.

---

## 1. Visão Geral

O **Extrator** é um sistema em Python que realiza automações web.

O técnico de TI, ao receber um chamado, abre o Extrator, insere os dados necessários e dispara a automação. O Extrator executa o fluxo via Playwright em segundo plano e exibe o resultado na interface.

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

## 4. Workflow Git

### 4.1 Fluxo Obrigatório

Todo desenvolvimento deve seguir **estritamente** esta ordem:

```
Codificar → Testes unitários → Testes de integração → Ruff → Commit
```

Se qualquer etapa falhar: corrigir e repetir o ciclo. Commit é proibido antes de tudo passar.

### 4.2 Regra de Commit

Um commit só é permitido quando todos os testes unitários e de integração passam e Ruff não retorna erros.

### 4.3 Convenção de Commits

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

Exemplos reais de uso : 
- `"fix (consultor_sti) : Correção do bug de autenticação"`
- `"feat (consultor_sti) : Implementada nova funcionalidade de automação em lote"`

### 4.4 Frequência

Um commit deve representar **uma única mudança lógica**. Pequenos, frequentes e coerentes.

### 4.5 Hook de Verificação

Configurar pre-commit hook executando `ruff check . && pytest`. Commit bloqueado automaticamente em caso de falha.

---

## 5. Distribuição e Launchers

Automações com UI (`ui_*.py`) voltadas ao técnico de TI final são distribuídas como instalador Windows via GitHub Releases — não exigem Python, git ou pip na máquina do técnico. Detalhes operacionais em [Guia_Build_Launchers.md](docs/guias/Guia_Build_Launchers.md).

| Componente | Tecnologia | Motivo |
|------------|-----------|--------|
| Empacotamento | PyInstaller (onedir), spec único (`launcher/launchers.spec`) para todos os launchers | Executáveis compartilham um só `_internal` (runtime, Playwright, Chromium) — evita duplicar dependências por app |
| Navegador Playwright | Chromium embutido em `ms-playwright/` ao lado dos `.exe`, compartilhado entre launchers | Ambiente do técnico tem proxy/firewall restritivo; não pode depender de download em runtime |
| Versão do executável | `version_info` gerado por `_spec_common.py` a partir de `LAUNCHER_VERSION` | Windows mostra versão/editor nas Propriedades do arquivo (não substitui assinatura de código) |
| Instalador | Inno Setup único, instalação por usuário (`PrivilegesRequired=lowest`) | Técnico pode não ter privilégio de administrador; um instalador cobre todas as automações |
| Integridade | Checksum SHA256 publicado junto ao instalador | Técnico pode validar que o download não foi corrompido/alterado |
| CI/Release | GitHub Actions (`windows-latest`), gatilho em tag `vX.Y.Z`, cache do Chromium por versão do Playwright | Build + instalador publicados como assets do Release, sem passo manual |

Toda nova automação com launcher deve seguir o checklist de "Ao adicionar uma nova automação com launcher" no guia citado acima.
