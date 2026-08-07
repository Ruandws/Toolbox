## Guia — Build e Release dos Launchers

> Cobre o empacotamento das automações num instalador Windows distribuído via GitHub Releases. Público-alvo: técnico de TI, sem Python instalado, sem garantia de acesso irrestrito à internet.

Há **dois produtos independentes**, cada um com seu spec, instalador, tag e workflow:

| Produto | Automações | Pasta | Tag | Instalador |
|---------|-----------|-------|-----|------------|
| Serviços TI | Prorrogador, Consultor | `launcher/` | `vX.Y.Z` | `ServicosTI-Setup-X.Y.Z.exe` |
| AGHU | Impressora, Concessor, Criar Pessoa, Criar Usuário, Profissionais da Unidade Cirúrgica | `launcher/aghu/` | `aghu-vX.Y.Z` | `AGHU-Setup-X.Y.Z.exe` |

Dentro de cada produto vale a mesma regra: **um único COLLECT** para todas as automações daquele sistema, para que compartilhem um só `_internal` e uma só cópia do Chromium. Os dois produtos são separados porque têm públicos e ciclos de release distintos — o custo é uma segunda cópia das dependências para quem instala ambos.

### Arquitetura — Serviços TI (`launcher/`)

Todos os arquivos de empacotamento ficam centralizados em `launcher/` (a única exceção é o workflow do GitHub Actions, que precisa obrigatoriamente estar em `.github/workflows/`):

```
launcher/
  launchers.spec     # spec único do PyInstaller (os dois executáveis)
  _spec_common.py    # config compartilhada: lista de launchers, version_info
  icons/
    prorrogador.ico       consultor.ico
  installer/
    setup.iss          # instalador único (Inno Setup)
    leiame.txt          # LEIAME entregue ao técnico, cobrindo os dois apps
  build/                                       # gerado pelo PyInstaller (git-ignorado)
  dist/                                        # gerado pelo PyInstaller/Inno Setup (git-ignorado)
```

- **PyInstaller** (onedir) empacota Prorrogador e Consultor num único spec (`launcher/launchers.spec`), que itera sobre a lista `LAUNCHERS` em `launcher/_spec_common.py` (nome, entry script, ícone, descrição) e junta os dois executáveis num só `COLLECT` chamado `ServicosTI`. Isso faz os dois compartilharem o mesmo `_internal` (runtime Python, Playwright, customtkinter, Chromium embutido) — sem isso, cada app carregava sua própria cópia completa das dependências (~160MB cada). Compartilhado, o total cai praticamente pela metade.
- Para adicionar uma nova automação, basta um novo item em `LAUNCHERS` — não é preciso criar outro `.spec`.
- O driver do Playwright é coletado automaticamente pelo hook que o próprio pacote `playwright` registra junto ao PyInstaller (`playwright._impl.__pyinstaller`); não precisa de `datas` manual no spec.
- O **navegador Chromium** não vem no pacote pip — é baixado à parte e embutido manualmente na pasta `ms-playwright/` ao lado dos `.exe`, para funcionar offline em ambientes com proxy/firewall restritivo. Como os dois launchers agora vivem na mesma pasta, essa pasta também é compartilhada — só existe uma cópia do Chromium na instalação final.
- `ui_prorrogador.py` e `ui_consultor.py` chamam `bootstrap_playwright_browsers_path()` de `sistemas/servicos_ti/_launcher_runtime.py` (apenas quando `sys.frozen`) para apontar `PLAYWRIGHT_BROWSERS_PATH` para essa pasta `ms-playwright/`. Lógica única, compartilhada pelos dois — antes existia duplicada em cada `ui_*.py`.
- **`version_info`**: cada executável embute versão/editor/descrição no recurso VERSIONINFO do Windows (visível em Propriedades do arquivo → Detalhes), gerado por `_spec_common.gerar_version_info()` a partir da variável de ambiente `LAUNCHER_VERSION` (o CI define a partir da tag; localmente, sem a variável, fica `0.0.0.0`). **Isso não assina o executável nem remove o aviso do SmartScreen** — apenas resolve a ausência de versão nas propriedades do arquivo. Assinatura de código exigiria certificado pago e não está no escopo atual; o LEIAME já orienta o técnico a clicar em "Mais informações → Executar assim mesmo".
- **Inno Setup** (`launcher/installer/setup.iss`) empacota o build do PyInstaller num único instalador com atalhos, ícones e desinstalador — instalação por usuário (`PrivilegesRequired=lowest`), sem exigir admin. Duas tasks (`desktopicon_prorrogador`, `desktopicon_consultor`) deixam o técnico escolher quais ícones de área de trabalho criar.
- O instalador embute um LEIAME único (`leiame.txt`, cobrindo os dois apps) — copiado para a pasta instalada como `LEIAME.txt`, oferecido para leitura ao final da instalação (`Flags: isreadme`) e com atalho próprio no Menu Iniciar.
- **GitHub Actions** (`.github/workflows/release.yml`) builda tudo, gera um checksum SHA256 do instalador e publica ambos como assets de um GitHub Release quando uma tag `vX.Y.Z` é enviada. O download do Chromium usa `actions/cache` (chave por versão do Playwright) para não rebaixar ~150MB a cada release sem necessidade.
- O `ruff`/`pytest` do workflow rodam escopados (`sistemas/servicos_ti launcher` e `testes/servicos_ti`, não o repositório inteiro). O monorepo tem outras automações (AGHU, wiki etc.) e até pastas alheias a este projeto que às vezes aparecem no diretório de trabalho — rodar sem escopo faz o release falhar por lint/teste de código que este pipeline nem builda (foi o que quebrou o primeiro release, `v0.1.0`).

### Arquitetura — AGHU (`launcher/aghu/`)

Mesma arquitetura, arquivos próprios (nada é compartilhado com `launcher/`, para que os dois produtos possam ser versionados e lançados de forma independente):

```
launcher/aghu/
  launcher_aghu.spec   # spec único do PyInstaller (os cinco executáveis)
  _spec_common.py      # config compartilhada: lista de launchers, version_info
  icons/
    aghu.ico                  impressora_aghu.ico       concessor_aghu.ico
    criar_pessoa_aghu.ico     criar_usuario_aghu.ico
    profissionais_unidade_cirurgica_aghu.ico
  installer/
    setup.iss          # instalador único (Inno Setup)
    leiame.txt         # LEIAME entregue ao técnico, cobrindo os cinco apps
  build/                                     # gerado pelo PyInstaller (git-ignorado)
  dist/                                      # gerado pelo PyInstaller/Inno Setup (git-ignorado)
```

- As cinco automações (`ImpressoraAGHU`, `ConcessorAGHU`, `CriarPessoaAGHU`, `CriarUsuarioAGHU`, `ProfissionaisUnidadeAGHU`) saem num só `COLLECT` chamado `AGHU`. Antes da unificação, a release `aghu-v1.0.0` publicava só a Impressora; um instalador por automação replicaria cinco vezes runtime, Playwright e Chromium (~160MB cada).
- Os `ui_*.py` do AGHU não estão todos no mesmo diretório: quatro ficam em `sistemas/aghu/` e a Impressora em `sistemas/aghu/Habilitar_impressora_em_computador/`. Por isso cada item de `LAUNCHERS` traz `app_dir` (diretório do entry script) e `pathex_extra` (diretórios adicionais de import) — a Impressora usa `pathex_extra` para alcançar `autenticador.py`/`menu.py` em `sistemas/aghu`.
- `sistemas/aghu/_launcher_runtime.py` é o bootstrap único dos cinco `ui_*.py` (antes existia só dentro de `Habilitar_impressora_em_computador/`, para a Impressora).
- **Inno Setup** (`launcher/aghu/installer/setup.iss`): AppId próprio, produto `Extrator2 - AGHU` em `%LocalAppData%\Programs\Extrator2\AGHU`, cinco tasks `desktopicon_*` e uma seção `[Code]` que localiza e roda silenciosamente o desinstalador do produto antigo `Extrator2 - AGHU Impressora` (AppId `{7F2A5C31-…}`, releases `aghu-v1.x`) antes de instalar. O `unins000.exe` do Inno se copia para `%TEMP%` e encerra o processo original antes de terminar, então `ewWaitUntilTerminated` não basta: o código aguarda o executável sumir do disco (até 60s).
- O Menu Iniciar usa o grupo `Extrator2`, **compartilhado com o instalador do Serviços TI**. Nomes de atalho devem ser distintos entre os dois produtos, senão a desinstalação de um apaga atalhos do outro — por isso aqui o LEIAME vira `Leia-me AGHU`.
- **GitHub Actions**: `.github/workflows/release-aghu.yml`, gatilho em tag `aghu-vX.Y.Z`, escopo `ruff check sistemas/aghu launcher/aghu` e `pytest testes/aghu`.

### Buildar localmente (checagem antes de commitar)

```powershell
pip install -r requirements-dev.txt

# Serviços TI
python -m PyInstaller launcher/launchers.spec --distpath launcher/dist --workpath launcher/build --noconfirm

# AGHU
python -m PyInstaller launcher/aghu/launcher_aghu.spec --distpath launcher/aghu/dist --workpath launcher/aghu/build --noconfirm
```

- Serviços TI: os dois executáveis ficam em `launcher\dist\ServicosTI\`, compartilhando `launcher\dist\ServicosTI\_internal\`.
- AGHU: os cinco ficam em `launcher\aghu\dist\AGHU\`, compartilhando `launcher\aghu\dist\AGHU\_internal\`.
- Sem a pasta `ms-playwright` bundlada, o app usa o cache padrão do Playwright (`%LOCALAPPDATA%\ms-playwright`) — suficiente para teste local se o Chromium já estiver instalado (`playwright install chromium`).
- Para testar com uma versão específica no `version_info`: `$env:LAUNCHER_VERSION = "1.2.3"` antes do build.
- `dist/` e `build/` são ignorados pelo git em qualquer profundidade — nunca commitar esses artefatos.

### Gerar um release

1. Confirmar que lint e testes passam no **mesmo escopo que o CI usa**:
   - Serviços TI: `ruff check sistemas/servicos_ti launcher` e `pytest testes/servicos_ti`
   - AGHU: `ruff check sistemas/aghu launcher/aghu` e `pytest testes/aghu`
2. Criar e enviar a tag do produto (`vX.Y.Z` para Serviços TI, `aghu-vX.Y.Z` para AGHU):
   ```bash
   git tag aghu-v2.0.0
   git push origin aghu-v2.0.0
   ```
3. O workflow builda todos os apps do produto num único COLLECT, baixa o Chromium (com cache), embute em `ms-playwright/`, compila o instalador via Inno Setup (pré-instalado nos runners `windows-latest`), gera o checksum SHA256 e publica o `.exe` + `.exe.sha256` como assets do Release da tag.
4. Técnico baixa o instalador direto da página de Releases do repositório — não precisa de Python, git ou pip. Quem quiser conferir integridade compara o hash do arquivo baixado com o `.sha256` publicado junto.

### Ao adicionar uma nova automação com launcher

Substitua `<produto>` por `launcher` (Serviços TI) ou `launcher/aghu` (AGHU).

- [ ] Criar `.ico` em `<produto>/icons/`
- [ ] Adicionar um item em `LAUNCHERS` (`<produto>/_spec_common.py`): `nome`, `entry`, `icone`, `descricao` — e, no AGHU, também `app_dir` e `pathex_extra`
- [ ] Adicionar os atalhos da nova automação em `<produto>/installer/setup.iss` (`[Icons]`, `[Tasks]`, `[Run]`) e uma seção no `leiame.txt`. Conferir que os nomes de atalho não colidem com os do outro produto — o grupo `Extrator2` do Menu Iniciar é compartilhado
- [ ] Se a automação usar Playwright, chamar `bootstrap_playwright_browsers_path()` (de `sistemas/<sistema>/_launcher_runtime.py`) no topo do `ui_*.py`, dentro de `if getattr(sys, "frozen", False):`, antes de qualquer import que carregue `playwright`
- [ ] Rebuildar (o `.spec` do produto já pega o novo item automaticamente) e conferir que o novo executável abre
