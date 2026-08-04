## Checklist - Backend Genérico de Automação

> Nota: este checklist reúne práticas de engenharia independentes de sistema-alvo, extraídas de `Cheklist_Dev_Automacoes_AGHU.md`. Use-o como base para qualquer novo backend de automação (AGHU ou não). Particularidades de um sistema específico (seletores, autenticação, JSF/PrimeFaces etc.) devem viver no checklist daquele sistema, não aqui.

Resumo prático de estrutura, execução, entrada de dados, resiliência e relatórios para uma nova automação backend, independentemente do sistema-alvo.

### Estrutura do projeto
- [ ] Separar UI (framework de interface) do núcleo de automação (Playwright ou equivalente)
- [ ] Definir posse dos recursos de automação: UI/chamador cria e fecha `Browser`, `BrowserContext`/sessão e `Page` principal; núcleo recebe `context/page` e só cria abas/sessões auxiliares para Clean State ou consultas
- [ ] Se houver tarefa auxiliar delegável, criar especialista separado e deixar o maestro controlar retry/retomada
- [ ] IPs/URLs externas inevitáveis devem ficar em constantes nomeadas e ter proteção contra ambiente errado quando aplicável

### UI e execução
- [ ] Quando houver UI, executar tarefas longas fora da thread principal para manter a interface responsiva
- [ ] Durante a execução, desabilitar o botão de início e restaurar o estado da UI ao finalizar com sucesso ou erro
- [ ] Atualizações de status vindas da thread de automação devem voltar para a thread da UI por callback seguro (`after`, fila ou equivalente)

### Planilhas e entradas
- [ ] Definir `COLUNAS_OBRIGATORIAS_PLANILHA` (ou schema equivalente) no núcleo da automação
- [ ] Validar existência do arquivo, extensão permitida e colunas obrigatórias antes de abrir o navegador
- [ ] Ler Excel com `dtype=str` e `engine="openpyxl"`
- [ ] Para CSV, usar `sep=";"`, `encoding="utf-8-sig"` e fallback para `latin1`
- [ ] Normalizar nomes de colunas com `df.columns.str.strip()`
- [ ] Tratar campos obrigatórios em branco como linha ignorada ou erro descritivo, sem quebrar o lote inteiro
- [ ] Validar regras de negócio da entrada antes de acionar o sistema-alvo sempre que possível

### Resiliência
- [ ] Implementar Clean State: fechar aba/sessão atual, abrir nova, reautenticar e renavegar até a tela/fluxo alvo
- [ ] Retry por item/registro: normalmente 2 tentativas para navegação e 2-3 para processamento
- [ ] Usar `try/finally` para fechar browser e abas auxiliares
- [ ] Abas auxiliares, como consultas externas, devem ser fechadas também nos caminhos de erro
- [ ] Usar `except Exception:` quando for necessário capturar falha técnica geral; evitar `except:` nu
- [ ] Diferenciar erro de negócio previsível de falha técnica/rede/navegador
- [ ] Quando o sistema-alvo não retornar sucesso nem erro conhecido, marcar estado indefinido para conferência manual

### Relatórios
- [ ] Gerar relatório por linha processada com status e detalhes descritivos
- [ ] Incluir auditoria quando o formato comportar: usuário executor e data/hora de geração
- [ ] Se o núcleo gerar CSV, manter separador `;` e `utf-8-sig`
- [ ] Quando houver UI, entregar XLSX final na camada de UI
- [ ] Automações sem CSV intermediário podem gerar XLSX direto, desde que preservem status, detalhes, filtros e colunas legíveis
- [ ] Relatórios devem ser gerados mesmo quando parte das linhas falhar
