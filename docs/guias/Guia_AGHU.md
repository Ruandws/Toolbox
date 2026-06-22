# Guia AGHU/AGHUX — Práticas Essenciais

- **Tipo:** guia transversal, não substitui as RFCs de módulo.
- **Base normativa:** RFC-001 a RFC-005 em `docs/rfc/aghu`.
- **Uso:** referenciar este guia em novas RFCs e documentar exceções na RFC do módulo.

Se houver conflito entre este guia e uma RFC específica, a RFC do módulo prevalece.

---

## 1. Autenticação e URLs

- A autenticação deve ficar centralizada em `autenticador.py` (RFC-005).
- Robôs de procedimento não devem duplicar seletores de usuário, senha, botão **Entrar**, mensagem de credencial inválida ou regra de sessão ativa.
- Use `autenticar_aghu_page` com uma `Page` existente; ela não é dona do browser, context ou page recebidos.
- Valide o retorno com `exigir_login_valido`; somente `sucesso` e `sessao_ativa` são aceitáveis para prosseguir.
- URLs de Produção/Homologação vêm do autenticador (`AGHU_URL`, `AGHU_URL_HOMOLOGACAO`) e devem ser repassadas como `url_aghu` por login, navegação, processamento, retries e Clean State.
- Senha não deve ser normalizada, logada nem incluída em mensagens de retorno.

---

## 2. Navegação e iframes

- A navegação de menu deve ser delegada a `navegar_menu_aghu` em `menu.py` (RFC-004).
- `menu.py` deve saber apenas **como** navegar; caminhos de negócio ficam no chamador, como `CAMINHO_MENU_IMPRESSORA_POR_COMPUTADOR` e `CAMINHO_MENU_CADASTRO_IMPRESSORA`.
- Itens de menu são localizados por texto visível exato (`exact=True`) e visibilidade, para evitar correspondência parcial e cliques em itens ocultos.
- A navegação é idempotente: se o próximo nível já estiver visível, não clica novamente no nível atual.
- `navegar_menu_aghu` retorna `page.frame_locator("iframe").last`; depois disso, o módulo chamador deve operar no iframe retornado.
- A validação da tela final é responsabilidade do chamador, normalmente aguardando um elemento confiável como o botão **Pesquisar**.
- Retry de navegação não fica dentro de `menu.py`; o chamador define a recuperação.

---

## 3. Seletores

Prioridade recomendada:

1. Atributos estáveis, como `input[name='QUERY']`, `input[id*='fila' i]` e `textarea[id*='localizacao' i]`.
2. Role e nome acessível, como `get_by_role("button", name="Pesquisar")`.
3. Componentes JSF/PrimeFaces como fallback documentado, por exemplo `div.ui-selectonemenu-trigger` e `button.ui-autocomplete-dropdown:has(.ui-icon-triangle-1-s)`.
4. Texto visível exato para menu e botões de ação estáveis, como **Pesquisar**, **Novo** e **Gravar**.

Regras práticas:

- Preferir `id*='...' i` quando o AGHUX gerar IDs com prefixos ou sufixos dinâmicos.
- Fallback por posição, como "primeiro" ou "segundo" `div.ui-selectonemenu-trigger`, deve estar documentado na RFC do módulo.
- Autocompletes JSF podem exigir `press_sequentially(..., delay=150)` para disparar eventos corretamente.
- Seleções sensíveis devem validar o item escolhido. Exemplo da RFC-001: o computador selecionado deve conter o IP esperado como valor exato, evitando confundir `10.6.0.22` com `10.6.0.225`.

---

## 4. Recuperação de Estado

- Falha inicial de navegação no Maestro aciona Clean State: nova aba no mesmo `BrowserContext`, acesso a `url_aghu`, autenticação centralizada e nova navegação (RFC-001).
- Falha inicial de navegação no Almoxarifado usa `reload()` e nova tentativa (RFC-002).
- Falhas técnicas por linha no Maestro têm até três tentativas; nas primeiras, recria aba limpa e renavega; na última, registra erro da linha.
- Falhas funcionais devem limpar ou cancelar a tela antes de seguir para a próxima linha.
- Não continue operando em estado de página indefinido.

---

## 5. Ambientes

- A UI escolhe `Produção` ou `Homologação` e repassa a URL resolvida ao Maestro (RFC-003).
- Produção é o padrão atual da UI e deve exibir alerta operacional antes da execução.
- Todo Clean State e retry deve preservar `url_aghu`; isso evita voltar para Produção quando a execução começou em Homologação.
- Na seleção do servidor CUPS, o item deve conter `10.6.0.121` e `CUPS`, e não pode conter `HOMOLOGAÇÃO` (RFC-002).

---

## 6. Contratos entre Módulos

- Toda função pública usada por outro módulo deve constar na seção **API Pública** da RFC correspondente.
- Funções privadas com prefixo `_` não devem ser importadas por outros módulos.
- Mensagens de exceção interpretadas por outro módulo são contrato e não devem mudar sem atualizar RFCs e tratadores.

Mensagens contratuais atuais:

| Mensagem | Origem | Interpretação |
|---|---|---|
| `ValueError("Impressora não existe")` | Maestro | Aciona Almoxarifado |
| `ValueError("Não existe no CUPS")` | Almoxarifado | Marca fila como inexistente |
| `ValueError("Computador não encontrado")` | Maestro | Marca computador como inexistente |

Retornos silenciosos também precisam estar documentados. Exemplo: `cadastrar_nova_impressora` pode retornar sem criar registro quando a impressora já existe no AGHUX.

---

## 7. Checklist para Nova RFC AGHU

- Login delegado ao `autenticador.py`.
- URLs importadas do autenticador e `url_aghu` propagado por todo o fluxo.
- Navegação delegada a `menu.py`, com caminho declarado localmente.
- Tela final validada pelo módulo chamador.
- Seletores principais e fallbacks documentados.
- Retry e recuperação de estado descritos por fluxo.
- Proteções de ambiente documentadas quando houver opções semelhantes.
- Exceções e retornos usados entre módulos registrados como contrato.
- Limitações conhecidas listadas quando dependerem de texto visível, estrutura HTML, iframes ou componentes JSF.

---

## 8. Conformidade Atual

Este guia está alinhado às RFCs atuais:

- RFC-001: Maestro, Clean State, contratos com Almoxarifado, retries por linha e propagação de `url_aghu`.
- RFC-002: Almoxarifado, consulta CUPS, cadastro de impressora, fallback JSF e anti-homologação do servidor CUPS.
- RFC-003: UI, seleção de ambiente, alerta de Produção e repasse de `url_aghu`.
- RFC-004: navegação genérica de menu e retorno do último iframe.
- RFC-005: autenticação centralizada, URLs públicas e `ResultadoLogin`.
