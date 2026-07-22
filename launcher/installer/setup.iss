; Instalador único (Inno Setup) dos launchers servicos_ti: Prorrogador + Consultor.
; Os dois executáveis compartilham a mesma instalação (runtime Python,
; Playwright e Chromium embutido), evitando baixar/instalar tudo em dobro.
; Compilar a partir da raiz do build do PyInstaller (launcher\dist\ServicosTI).
; Uso: iscc launcher\installer\setup.iss /DMyAppVersion=1.2.0

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0-dev"
#endif

#define MyAppPublisher "Extrator2"
#define MyDistDir "..\dist\ServicosTI"

[Setup]
AppId={{2B7C9E44-5A1D-4F3B-9E6A-7C1D2F8B9A03}}
AppName=Extrator2 - Serviços TI
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\Extrator2\ServicosTI
DefaultGroupName=Extrator2
DisableProgramGroupPage=yes
OutputDir=..\dist\installers
OutputBaseFilename=ServicosTI-Setup-{#MyAppVersion}
SetupIconFile=..\icons\prorrogador.ico
UninstallDisplayIcon={app}\Prorrogador.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
; Instalação por usuário: não exige privilégios de administrador.
PrivilegesRequired=lowest

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon_prorrogador"; Description: "Criar ícone do Prorrogador STI na área de trabalho"; GroupDescription: "Ícones na área de trabalho:"
Name: "desktopicon_consultor"; Description: "Criar ícone do Consultor STI na área de trabalho"; GroupDescription: "Ícones na área de trabalho:"

[Files]
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "leiame.txt"; DestDir: "{app}"; DestName: "LEIAME.txt"; Flags: isreadme

[Icons]
Name: "{group}\Prorrogador STI"; Filename: "{app}\Prorrogador.exe"; IconFilename: "{app}\Prorrogador.exe"
Name: "{group}\Consultor STI"; Filename: "{app}\Consultor.exe"; IconFilename: "{app}\Consultor.exe"
Name: "{autodesktop}\Prorrogador STI"; Filename: "{app}\Prorrogador.exe"; IconFilename: "{app}\Prorrogador.exe"; Tasks: desktopicon_prorrogador
Name: "{autodesktop}\Consultor STI"; Filename: "{app}\Consultor.exe"; IconFilename: "{app}\Consultor.exe"; Tasks: desktopicon_consultor
Name: "{group}\Leia-me"; Filename: "{app}\LEIAME.txt"
Name: "{group}\Desinstalar Serviços TI"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\Prorrogador.exe"; Description: "Executar Prorrogador STI"; Flags: nowait postinstall skipifsilent unchecked
Filename: "{app}\Consultor.exe"; Description: "Executar Consultor STI"; Flags: nowait postinstall skipifsilent unchecked
