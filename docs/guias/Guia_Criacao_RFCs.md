# Guia para Criação de RFCs — Extrator

- **Tipo:** guia sobre a mecânica do documento RFC (estrutura, formatação, ciclo de vida). Regras de engenharia de domínio ficam em guias próprios (ex.: `docs/guias/Guia_AGHU.md`).
- **Modelo estrutural de referência:** `docs/rfc/aghu/RFC_001_printerAghu.md`. Compare qualquer RFC nova/revisada contra ela seção a seção.
- **Regra de ouro:** nenhuma informação técnica entra na RFC sem ter sido conferida no `.py` real na hora de escrever. Não documentar por memória, por suposição, nem copiando de revisão anterior sem checar.

---

## 1. Quando criar/revisar

- **Criar:** módulo novo de automação, ou utilitário transversal usado por 2+ módulos.
- **Revisar:** qualquer mudança de comportamento (função renomeada/removida/assinatura alterada, formato de saída trocado, nova validação/dependência); ou quando outro módulo passa a depender deste (atualizar "Chamado por" aqui).
- RFC descreve o código **como ele é hoje**, nunca design especulativo.

---

## 2. Nomenclatura e local

```
docs/rfc/<sistema>/RFC_0NN_nome_do_modulo.md
```

- Underscore (`RFC_009`), nunca hífen (`RFC-009`).
- Numeração sequencial por sistema, sem reordenar depois (quebra referências cruzadas em outras RFCs).

---

## 3. Cabeçalho (7 campos, nesta ordem, sempre)

```markdown
# RFC-0NN — <Nome do procedimento> (<nome_do_modulo>)

- **Status:** Rascunho | Em revisão | Estável
- **Autor:** <nome(s)>
- **Data:** <AAAA-MM>
- **Atualizado em:** <AAAA-MM-DD — data real da última edição de conteúdo>
- **Arquivo:** `<nucleo>.py`  (ou **Arquivos:** núcleo + UI, se escopo unificado — seção 5)
- **Depende de:** `<modulo>.py` (RFC-0NN) — uma linha por dependência direta
- **Chamado por:** `<modulo>.py` (RFC-0NN) — ou "— (ponto de entrada próprio)"
```

Antes de preencher "Chamado por": rode `grep`/`ripgrep` por `from <modulo> import` e `import <modulo>` em todo o repo. Não copiar de revisão anterior — listas de dependentes incompletas foram o erro mais comum encontrado em auditoria.

---

## 4. Estrutura de seções

| # | Seção | Conteúdo | Obrigatória |
|---|---|---|---|
| 1 | Resumo | O que o módulo faz, em 1 parágrafo | Sempre |
| 2 | Mudanças incorporadas nesta revisão | Tabela `Área\|Situação atual` | Sempre, mesmo em RFC nova |
| 3 | Motivação | Por que o procedimento existe | Sempre |
| 4 | Arquitetura e Fluxo de Dados | Diagrama (ascii/mermaid) com ramos de decisão, retry, delegação | Sempre |
| 5 | Dependências | Subseção por dependência: import literal + tabela `Item\|Responsabilidade` | Se houver dependência interna |
| 6 | Constantes de Módulo | Tabela `Constante\|Valor\|Uso` | Se houver constantes |
| 7 | Funções Auxiliares Privadas | Tabela `Função\|Assinatura\|Descrição` | Se houver `_privadas` |
| 8 | Descrição dos Componentes Públicos | 1 subseção por função pública, com assinatura real | Sempre |
| 9 | Regras de Processamento | Casos de decisão (A/B/C/D), tabela `Status\|Detalhes` | Se houver lógica de decisão |
| — | Delegação / seções de domínio | O que for específico do módulo | Conforme o caso |
| — | Recuperação de Falhas Técnicas | Nº de tentativas, gatilho de retry, Clean State | Se houver retry |
| — | Relatório de Auditoria | Formato REAL do arquivo de saída (extensão, colunas) | Se gerar relatório |
| — | API Pública do Módulo | Tabela `Função\|Responsabilidade` — só o que está em `__all__`/é de fato importado | Sempre |
| — | Contratos entre RFCs | 1 subseção por RFC relacionada (evento/exceção/retorno + interpretação) | Se houver módulo relacionado |
| — | Considerações Operacionais | Lista numerada de invariantes | Sempre |
| — | Limitações Conhecidas | Tabela `Limitação\|Impacto` | Sempre |
| Última | Estado Atual da RFC | Bullets do que esta revisão cobre. **Deve ser a última seção — nada depois dela** | Sempre |

Se uma seção não se aplica, escrever "Não aplicável: \<motivo\>" em vez de omitir.

---

## 5. Escopo: núcleo isolado vs. núcleo+UI no mesmo doc

- **Separado** (RFC-001/003): núcleo reutilizado por mais de um chamador, ou UI complexa o bastante para tratamento próprio.
- **Unificado** (RFC-006/007/008/009): UI é wrapper fino e dedicado, sem outro consumidor do núcleo.

Se unificado: usar `**Arquivos:**` (plural) no cabeçalho e declarar a decisão no Resumo.

---

## 6. Formatação

- Tabela de função: sempre 3 colunas com **Assinatura** real (tipos de parâmetro/retorno). Nunca só `Função|Papel`.
- Bloco de import: cópia literal do topo do arquivo, não paráfrase.
- Mensagens de erro/exceções-contrato: string exata entre aspas, copiada do código.
- Nome de arquivo de módulo: exatamente como está no disco, mesmo se inconsistente com o padrão dos irmãos (não "corrigir" na prosa).
- Diagrama: sempre com os ramos de decisão reais, não um fluxo linear se o real se ramifica.

---

## 7. Erros recorrentes a evitar (achados em auditoria real)

| Erro | Causa | Prevenção |
|---|---|---|
| Função/constante/campo documentado que não existe no código | Escrito de memória ou copiado de spec antiga | Conferir cada um no `.py` antes de escrever |
| Formato de relatório errado (ex.: RFC diz CSV, código gera XLSX) | Não verificado após mudança de formato | Abrir o código de escrita do relatório e checar extensão/lib real |
| Lista de "Chamado por"/dependentes incompleta | Copiada de revisão anterior sem nova busca | `grep` real no repo a cada revisão |
| Seção técnica removida do código ainda descrita como existente, ou removida descrita como "melhorada" | Refactor não propagado para a RFC | Ao remover algo do código, escrever explicitamente "foi removido", não parafrasear |
| Seções duplicadas depois de "Estado Atual da RFC" | Edição incremental sem reler o doc inteiro | Reler do início ao fim antes de fechar a revisão |
| Referência quebrada a número de seção (“ver seção 12”) | Renumeração sem busca por refs internas | Buscar `seção \d+` no arquivo após reorganizar |
| Nome de arquivo da RFC com hífen (`RFC-008`) | Inconsistência de criação | Sempre `RFC_0NN_` com underscore |
| Tabela de função sem coluna de assinatura | Preenchimento rápido sem seguir o modelo | Usar sempre `Função\|Assinatura\|Descrição` |

---

## 8. Checklist antes de marcar `Estável`

- [ ] Nome do arquivo: `RFC_0NN_nome_do_modulo.md`
- [ ] Cabeçalho com os 7 campos; "Atualizado em" = data real da última edição
- [ ] Todas as seções da seção 4 presentes, na ordem, ou com nota de não aplicabilidade
- [ ] "Estado Atual da RFC" é a última seção — nada depois
- [ ] Toda tabela de função tem coluna "Assinatura"
- [ ] Toda constante/função/status/mensagem de erro citada foi conferida no `.py` nesta revisão
- [ ] "Chamado por" validado por busca real no repo
- [ ] Formato de relatório/saída conferido no código, não assumido
- [ ] Nenhuma referência a número de seção desatualizada
- [ ] Se núcleo+UI: cabeçalho usa "Arquivos:" e Resumo declara a decisão

---

## 9. Commit

Convenção de `spec.md` §4.3: `<tipo> (<escopo>) : <descrição curta>`.

- RFC sem mudança de código → `docs`.
- Se a revisão expuser algo que exige mudar código → commit separado (`fix`/`chore`/`refactor`) além do `docs` da RFC.

```
docs (aghu) : Realizada correção de estruturação e conteúdo das RFCs 001-009 após auditoria de conformidade com o codigo de cada procedimento
```

---

## 10. Referências

- Modelo a copiar: `docs/rfc/aghu/RFC_001_printerAghu.md`
- Regras de engenharia de domínio AGHU: `docs/guias/Guia_AGHU.md`
- Workflow de commit/teste: `spec.md` §4
