**Sistema:** Serviços TI
**Data:** 2026-07-21
**Arquivo:** sistemas/servicos_ti/consultor_sti.py
**O que mudou:**
- Adicionada classe `UsuarioConsulta` para padronizar e isolar as informações dos usuários capturados via pesquisa manual na interface.
- Criada função `format_multi_results` para sumarizar e concatenar o detalhamento de múltiplas pesquisas numa execução em lote unitária em memória.
- Adicionada função orquestradora `run_multi_automation`, responsável por gerenciar um único contexto do navegador (Playwright) enquanto itera a execução de `search_user_prepared_value` sobre múltiplos CPFs ou Nomes, consolidando todos os retornos.
**Observações:** As funções complementam o uso singular e em lote, fornecendo uma opção multi-unitária sem a necessidade de uma planilha de entrada.
