**Sistema:** Serviços TI
**Data:** 2026-07-21
**Arquivo:** sistemas/servicos_ti/ui_consultor.py
**O que mudou:**
- Adicionada lista dinâmica `linhas_usuarios_individual` substituindo o campo único `entry_search` para suportar múltiplas pesquisas na execução unitária.
- Adicionados controles na interface (`button_adicionar` e botões de exclusão) para gerenciar até 5 linhas de pesquisa simultâneas.
- Modificado o método `iniciar_execucao_individual` para validar e agregar todos os valores preenchidos na interface antes de acionar a thread em background.
- Alterada a assinatura da devolução assíncrona no método `finish_automation` para recepcionar um terceiro argumento `detail`, utilizado para exibir resultados detalhados por pesquisa em tela através do método `mostrar_resultado_detalhado`.
- Atualizado o acoplamento do método `start_automation` para chamar `run_multi_automation` enviando a lista completa `usuarios_validos`.
**Observações:** Alterações incluem correções em toda a suíte de testes de UI do módulo para compatibilização com a nova assinatura de execução multi-usuário em memória.
