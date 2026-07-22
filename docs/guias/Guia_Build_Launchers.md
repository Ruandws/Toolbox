## Guia — Build e Release dos Launchers (Prorrogador / Consultor)

> Cobre o empacotamento das automações `servicos_ti` (Prorrogador e Consultor) num único instalador Windows distribuído via GitHub Releases. Público-alvo: técnico de TI, sem Python instalado, sem garantia de acesso irrestrito à internet.

### Arquitetura

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

### Buildar localmente (checagem antes de commitar)

```powershell
pip install -r requirements-dev.txt
python -m PyInstaller launcher/launchers.spec --distpath launcher/dist --workpath launcher/build --noconfirm
```

- Os dois executáveis ficam em `launcher\dist\ServicosTI\Prorrogador.exe` e `launcher\dist\ServicosTI\Consultor.exe`, compartilhando `launcher\dist\ServicosTI\_internal\`.
- Sem a pasta `ms-playwright` bundlada, o app usa o cache padrão do Playwright (`%LOCALAPPDATA%\ms-playwright`) — suficiente para teste local se o Chromium já estiver instalado (`playwright install chromium`).
- Para testar com uma versão específica no `version_info`: `$env:LAUNCHER_VERSION = "1.2.3"` antes do build.
- `launcher/dist/` e `launcher/build/` são ignorados pelo git (regras `dist/`/`build/` do `.gitignore` valem em qualquer profundidade) — nunca commitar esses artefatos.

### Gerar um release

1. Confirmar que `ruff check .` e `pytest` passam.
2. Criar e enviar uma tag semântica:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
3. O workflow builda os dois apps num único COLLECT, baixa o Chromium (com cache), embute em `ms-playwright/`, compila o instalador via Inno Setup (pré-instalado nos runners `windows-latest`), gera o checksum SHA256 e publica `ServicosTI-Setup-1.0.0.exe` + `ServicosTI-Setup-1.0.0.exe.sha256` como assets do Release da tag.
4. Técnico baixa o instalador direto da página de Releases do repositório — não precisa de Python, git ou pip. Quem quiser conferir integridade compara o hash do arquivo baixado com o `.sha256` publicado junto.

### Ao adicionar uma nova automação com launcher

- [ ] Criar `.ico` em `launcher/icons/`
- [ ] Adicionar um item em `LAUNCHERS` (`launcher/_spec_common.py`): `nome`, `entry`, `icone`, `descricao`
- [ ] Adicionar os atalhos da nova automação em `launcher/installer/setup.iss` (`[Icons]`, `[Tasks]`, `[Run]`) e uma seção no `leiame.txt`
- [ ] Se a automação usar Playwright, chamar `bootstrap_playwright_browsers_path()` (de `sistemas/servicos_ti/_launcher_runtime.py`) no topo do `ui_*.py`, dentro de `if getattr(sys, "frozen", False):`, antes de qualquer import que carregue `playwright`
- [ ] Rebuildar (`launcher/launchers.spec` já pega o novo item automaticamente) e conferir que o novo executável abre
