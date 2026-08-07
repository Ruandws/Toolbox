; Instalador único (Inno Setup) dos launchers AGHU: Impressora, Concessor,
; Criar Pessoa, Criar Usuário e Profissionais da Unidade Cirúrgica.
; As cinco automações compartilham a mesma instalação (runtime Python,
; Playwright e Chromium embutido), evitando baixar/instalar tudo cinco vezes.
; Compilar a partir da raiz do build do PyInstaller (launcher\aghu\dist\AGHU).
; Uso: iscc launcher\aghu\installer\setup.iss /DMyAppVersion=2.0.0

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0-dev"
#endif

#define MyAppPublisher "Extrator2"
#define MyDistDir "..\dist\AGHU"

[Setup]
AppId={{3D6E1A82-47C5-4B90-A2F1-8E5B0C7D9146}}
AppName=Extrator2 - AGHU
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\Extrator2\AGHU
DefaultGroupName=Extrator2
DisableProgramGroupPage=yes
OutputDir=..\dist\installers
OutputBaseFilename=AGHU-Setup-{#MyAppVersion}
SetupIconFile=..\icons\aghu.ico
UninstallDisplayIcon={app}\ConcessorAGHU.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
; Instalação por usuário: não exige privilégios de administrador.
PrivilegesRequired=lowest

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon_impressora"; Description: "Criar ícone da Impressora AGHU na área de trabalho"; GroupDescription: "Ícones na área de trabalho:"
Name: "desktopicon_concessor"; Description: "Criar ícone da Concessão de Perfis AGHU na área de trabalho"; GroupDescription: "Ícones na área de trabalho:"
Name: "desktopicon_criar_pessoa"; Description: "Criar ícone do Cadastro de Pessoa AGHU na área de trabalho"; GroupDescription: "Ícones na área de trabalho:"
Name: "desktopicon_criar_usuario"; Description: "Criar ícone da Importação de Usuário AGHU na área de trabalho"; GroupDescription: "Ícones na área de trabalho:"
Name: "desktopicon_profissionais"; Description: "Criar ícone dos Profissionais da Unidade Cirúrgica AGHU na área de trabalho"; GroupDescription: "Ícones na área de trabalho:"

[Files]
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "leiame.txt"; DestDir: "{app}"; DestName: "LEIAME.txt"; Flags: isreadme

[Icons]
Name: "{group}\AGHU Impressora"; Filename: "{app}\ImpressoraAGHU.exe"; IconFilename: "{app}\ImpressoraAGHU.exe"
Name: "{group}\AGHU Concessão de Perfis"; Filename: "{app}\ConcessorAGHU.exe"; IconFilename: "{app}\ConcessorAGHU.exe"
Name: "{group}\AGHU Cadastro de Pessoa"; Filename: "{app}\CriarPessoaAGHU.exe"; IconFilename: "{app}\CriarPessoaAGHU.exe"
Name: "{group}\AGHU Importação de Usuário"; Filename: "{app}\CriarUsuarioAGHU.exe"; IconFilename: "{app}\CriarUsuarioAGHU.exe"
Name: "{group}\AGHU Profissionais da Unidade Cirúrgica"; Filename: "{app}\ProfissionaisUnidadeAGHU.exe"; IconFilename: "{app}\ProfissionaisUnidadeAGHU.exe"
Name: "{autodesktop}\AGHU Impressora"; Filename: "{app}\ImpressoraAGHU.exe"; IconFilename: "{app}\ImpressoraAGHU.exe"; Tasks: desktopicon_impressora
Name: "{autodesktop}\AGHU Concessão de Perfis"; Filename: "{app}\ConcessorAGHU.exe"; IconFilename: "{app}\ConcessorAGHU.exe"; Tasks: desktopicon_concessor
Name: "{autodesktop}\AGHU Cadastro de Pessoa"; Filename: "{app}\CriarPessoaAGHU.exe"; IconFilename: "{app}\CriarPessoaAGHU.exe"; Tasks: desktopicon_criar_pessoa
Name: "{autodesktop}\AGHU Importação de Usuário"; Filename: "{app}\CriarUsuarioAGHU.exe"; IconFilename: "{app}\CriarUsuarioAGHU.exe"; Tasks: desktopicon_criar_usuario
Name: "{autodesktop}\AGHU Profissionais da Unidade Cirúrgica"; Filename: "{app}\ProfissionaisUnidadeAGHU.exe"; IconFilename: "{app}\ProfissionaisUnidadeAGHU.exe"; Tasks: desktopicon_profissionais
; Nome com sufixo AGHU: o grupo "Extrator2" do Menu Iniciar é compartilhado com
; o instalador servicos_ti, que também registra um atalho "Leia-me".
Name: "{group}\Leia-me AGHU"; Filename: "{app}\LEIAME.txt"
Name: "{group}\Desinstalar AGHU"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\ImpressoraAGHU.exe"; Description: "Executar AGHU Impressora"; Flags: nowait postinstall skipifsilent unchecked
Filename: "{app}\ConcessorAGHU.exe"; Description: "Executar AGHU Concessão de Perfis"; Flags: nowait postinstall skipifsilent unchecked
Filename: "{app}\CriarPessoaAGHU.exe"; Description: "Executar AGHU Cadastro de Pessoa"; Flags: nowait postinstall skipifsilent unchecked
Filename: "{app}\CriarUsuarioAGHU.exe"; Description: "Executar AGHU Importação de Usuário"; Flags: nowait postinstall skipifsilent unchecked
Filename: "{app}\ProfissionaisUnidadeAGHU.exe"; Description: "Executar AGHU Profissionais da Unidade Cirúrgica"; Flags: nowait postinstall skipifsilent unchecked

[Code]
{ Remove a instalação isolada "Extrator2 - AGHU Impressora" (releases aghu-v1.x),
  substituída por este pacote unificado. Sem isso o técnico ficaria com duas
  instalações e duas cópias do Chromium (~150MB duplicados), e o desinstalador
  antigo, se rodasse depois, apagaria atalhos recriados aqui. }

const
  AppIdImpressoraIsolada = '{7F2A5C31-9B44-4E1A-8C3D-6A0E9B5F2C17}_is1';
  TentativasEspera = 120;
  IntervaloEsperaMs = 500;

function LocalizarDesinstaladorAntigo(var Executavel: String): Boolean;
var
  Chave: String;
  Valor: String;
begin
  Chave := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\' + AppIdImpressoraIsolada;

  if not RegQueryStringValue(HKCU, Chave, 'UninstallString', Valor) then
    if not RegQueryStringValue(HKLM, Chave, 'UninstallString', Valor) then
    begin
      Result := False;
      Exit;
    end;

  Executavel := RemoveQuotes(Trim(Valor));
  Result := (Executavel <> '') and FileExists(Executavel);
end;

{ O unins000.exe do Inno se copia para %TEMP% e encerra o processo original
  antes de terminar de remover os arquivos; esperar só pelo Exec() não basta.
  Por isso aguardamos o executável original sumir do disco. }
procedure AguardarFimDaDesinstalacao(const Executavel: String);
var
  Tentativas: Integer;
begin
  Tentativas := 0;

  while FileExists(Executavel) and (Tentativas < TentativasEspera) do
  begin
    Sleep(IntervaloEsperaMs);
    Tentativas := Tentativas + 1;
  end;
end;

procedure RemoverInstalacaoAntiga();
var
  Executavel: String;
  CodigoSaida: Integer;
begin
  if not LocalizarDesinstaladorAntigo(Executavel) then
    Exit;

  if not Exec(Executavel, '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART', '',
              SW_HIDE, ewWaitUntilTerminated, CodigoSaida) then
  begin
    SuppressibleMsgBox(
      'Não foi possível remover automaticamente a versão anterior ' +
      '"Extrator2 - AGHU Impressora". Desinstale-a manualmente pelo Menu ' +
      'Iniciar depois que esta instalação terminar.',
      mbInformation, MB_OK, IDOK);
    Exit;
  end;

  AguardarFimDaDesinstalacao(Executavel);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    RemoverInstalacaoAntiga();
end;
